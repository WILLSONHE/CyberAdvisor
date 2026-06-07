"""B 站内容同步：视频字幕 → Raw/未审阅视频文稿/（专栏/动态改用手动放入 Raw/未分析归档）。"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any

from .client import BiliClient
from .env import BiliConfig, ROOT
from .naming import pending_video_filename, raw_filename, title_to_timestamp
from .rw_format import format_transcript
from .transcript import pick_subtitle

RAW_DIR = os.path.join(ROOT, "Raw")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from raw_paths import RAW_PENDING_VIDEO  # noqa: E402

PENDING_DIR = RAW_PENDING_VIDEO
STATE_PATH = os.path.join(ROOT, "Wiki", "数据", "bilibili_sync.json")

META_BVID = re.compile(r"^bvid:\s*(\S+)", re.M)
META_DYNAMIC = re.compile(r"^dynamic_id:\s*(\S+)", re.M)
META_ARTICLE = re.compile(r"^cvid:\s*(\d+)", re.M)
META_OPUS = re.compile(r"^opus_id:\s*(\S+)", re.M)

_STUB_ARTICLE = re.compile(r"App|客户端|升级|观看")


def _is_stub_article_content(text: str, words: int) -> bool:
    if words > 100 and len(text.strip()) < 80:
        return True
    return bool(_STUB_ARTICLE.search(text))


def _ensure_dirs() -> None:
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(PENDING_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)


def _load_state() -> dict:
    if os.path.isfile(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"videos": {}, "dynamics": {}, "articles": {}, "opus": {}}


def _save_state(state: dict) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _scan_existing_ids() -> tuple[set[str], set[str], set[str], set[str]]:
    bvids, dynamics, articles, opus_ids = set(), set(), set(), set()
    for folder in (RAW_DIR, PENDING_DIR):
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            if not name.endswith(".md"):
                continue
            path = os.path.join(folder, name)
            try:
                head = open(path, encoding="utf-8").read(800)
            except OSError:
                continue
            m = META_BVID.search(head)
            if m:
                bvids.add(m.group(1))
            m = META_DYNAMIC.search(head)
            if m:
                dynamics.add(m.group(1))
            m = META_ARTICLE.search(head)
            if m:
                articles.add(str(m.group(1)))
            m = META_OPUS.search(head)
            if m:
                opus_ids.add(m.group(1))
    return bvids, dynamics, articles, opus_ids


def _frontmatter(meta: dict[str, Any]) -> str:
    lines = ["---"]
    for k, v in meta.items():
        lines.append(f"{k}: {v}")
    lines.append("---\n")
    return "\n".join(lines)


def _unique_path(directory: str, filename: str) -> str:
    path = os.path.join(directory, filename)
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(filename)
    i = 2
    while True:
        alt = os.path.join(directory, f"{stem}_{i}{ext}")
        if not os.path.exists(alt):
            return alt
        i += 1


def _safe_print(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("gbk", errors="replace").decode("gbk"))


def _raw_already_has(title: str, pub_ts: int | None) -> bool:
    """避免与已有 Raw 重复（按日期+标题核心匹配）。"""
    fname = raw_filename(title, pub_ts)
    if os.path.exists(os.path.join(RAW_DIR, fname)):
        return True
    core = title.strip()[:40]
    if not core:
        return False
    for name in os.listdir(RAW_DIR):
        if not name.endswith(".md"):
            continue
        if core in name:
            return True
    return False


def _write(path: str, content: str, dry_run: bool) -> None:
    if dry_run:
        print(f"  [DRY] would write {path}")
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _parse_since(since: str | None) -> int | None:
    if not since:
        return None
    since = since.strip()
    for fmt in ("%Y-%m-%d", "%y-%m-%d"):
        try:
            return int(datetime.strptime(since, fmt).timestamp())
        except ValueError:
            continue
    raise SystemExit(f"无效 --since 日期: {since}，用 YYYY-MM-DD")


def _rich_nodes_to_text(nodes: list) -> str:
    chunks: list[str] = []
    for node in nodes or []:
        ntype = node.get("type") or ""
        if ntype == "TEXT_NODE_TYPE_WORD":
            txt = (node.get("word") or {}).get("words") or ""
        elif ntype == "TEXT_NODE_TYPE_LINK":
            link = node.get("link") or {}
            txt = link.get("show_text") or link.get("title") or ""
        elif ntype == "TEXT_NODE_TYPE_RICH":
            txt = _rich_nodes_to_text((node.get("rich") or {}).get("nodes"))
        else:
            txt = node.get("text") or (node.get("word") or {}).get("words") or ""
        if txt:
            chunks.append(txt)
    return "".join(chunks)


def _opus_paragraph_to_text(para: dict) -> str:
    if not para:
        return ""
    if para.get("para_type") == 2:
        return ""
    text_block = para.get("text") or {}
    if text_block.get("nodes"):
        return _rich_nodes_to_text(text_block["nodes"])
    items = (para.get("list") or {}).get("items") or []
    if items:
        lines: list[str] = []
        for item in items:
            line = _rich_nodes_to_text(item.get("nodes"))
            if line.strip():
                lines.append(f"- {line}")
        return "\n".join(lines)
    return ""


def _extract_opus_detail_text(item: dict) -> tuple[str, str, str, int]:
    """从 opus/detail 的 item 提取 (cvid, title, body, pub_ts)。"""
    basic = item.get("basic") or {}
    cvid = str(basic.get("comment_id_str") or basic.get("rid_str") or "")
    title = ""
    pub_ts = 0
    chunks: list[str] = []
    modules = item.get("modules") or []
    if isinstance(modules, dict):
        modules = [modules]
    for mod in modules:
        mtype = mod.get("module_type") or ""
        if mtype == "MODULE_TYPE_TITLE":
            title = (mod.get("module_title") or {}).get("text") or title
        elif mtype == "MODULE_TYPE_AUTHOR":
            author = mod.get("module_author") or {}
            pub_ts = int(author.get("pub_ts") or author.get("pub_time") or 0)
        elif mtype == "MODULE_TYPE_CONTENT":
            for para in (mod.get("module_content") or {}).get("paragraphs") or []:
                text = _opus_paragraph_to_text(para)
                if text.strip():
                    chunks.append(text)
    if not title:
        title = (basic.get("title") or "").split(" - ")[0].strip()
    body = "\n\n".join(chunks).strip()
    return cvid, title, body, pub_ts


def _fetch_article_body(client: BiliClient, cvid: int, detail: dict | None = None) -> tuple[str, str, int]:
    """拉取专栏正文；充电文走 opus/detail。"""
    detail = detail or client.article_detail(cvid)
    html = detail.get("content") or detail.get("origin_content") or ""
    body = _html_to_text(html)
    words = int(detail.get("words") or 0)
    if _is_stub_article_content(body, words):
        dyn_id = str(detail.get("dyn_id_str") or "")
        if dyn_id:
            try:
                opus_data = client.opus_detail(dyn_id)
                _, _, body, pub_ts = _extract_opus_detail_text(opus_data.get("item") or {})
                title = detail.get("title") or ""
                if body.strip():
                    return body, title, pub_ts or int(detail.get("publish_time") or 0)
            except Exception:
                pass
        try:
            upower = client.article_detail(cvid, from_source="web_upower")
            html = upower.get("content") or upower.get("origin_content") or ""
            alt = _html_to_text(html)
            if alt.strip() and not _is_stub_article_content(alt, words):
                body = alt
        except Exception:
            pass
    title = detail.get("title") or f"专栏{cvid}"
    pub_ts = int(detail.get("publish_time") or 0)
    return body, title, pub_ts


def _opus_to_text(opus: dict) -> str:
    if not opus:
        return ""
    chunks: list[str] = []
    title = opus.get("title") or ""
    if title:
        chunks.append(title)
    summary = _rich_nodes_to_text((opus.get("summary") or {}).get("rich_text_nodes"))
    if summary:
        chunks.append(summary)
    for block in opus.get("paragraphs") or []:
        para = _rich_nodes_to_text(block.get("text_nodes"))
        if para:
            chunks.append(para)
    return "\n\n".join(chunks).strip()


def _dynamic_major_type(item: dict) -> str:
    md = (item.get("modules") or {}).get("module_dynamic") or {}
    return (md.get("major") or {}).get("type") or ""


def _dynamic_pub_time(item: dict) -> int:
    basic = item.get("basic") or {}
    for key in ("pub_time", "pub_ts"):
        if basic.get(key):
            return int(basic[key])
    md = (item.get("modules") or {}).get("module_dynamic") or {}
    for key in ("pub_time", "pub_ts"):
        if md.get(key):
            return int(md[key])
    arc = (md.get("major") or {}).get("archive") or {}
    for key in ("pubtime", "ctime", "pub_time"):
        if arc.get(key):
            return int(arc[key])
    return 0


def _extract_dynamic_text(item: dict, client: BiliClient, *, _depth: int = 0) -> tuple[str, str, int]:
    """返回 (dynamic_id, plain_text, pub_ts)。"""
    basic = item.get("basic") or {}
    dyn_id = str(basic.get("comment_id_str") or basic.get("comment_id") or basic.get("rid_str") or "")
    modules = item.get("modules") or {}
    md = modules.get("module_dynamic") or {}
    major = md.get("major") or {}
    pub_ts = _dynamic_pub_time(item)

    if major.get("type") == "MAJOR_TYPE_ARCHIVE":
        return dyn_id, "", pub_ts

    opus = major.get("opus") or {}
    text = _opus_to_text(opus)
    if text:
        return dyn_id, text, pub_ts

    desc = (md.get("desc") or {}).get("text") or ""
    if desc.strip():
        return dyn_id, desc.strip(), pub_ts

    if dyn_id and _depth == 0:
        try:
            detail = client.dynamic_detail(dyn_id)
            inner = detail.get("item") or {}
            return _extract_dynamic_text(inner, client, _depth=1)
        except Exception:
            pass

    return dyn_id, "", pub_ts


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", html)
    html = re.sub(r"(?i)<br\s*/?>", "\n", html)
    html = re.sub(r"(?i)</p>", "\n\n", html)
    html = re.sub(r"<[^>]+>", "", html)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html.strip()


def sync_all(
    *,
    since: str | None = "2026-05-14",
    dry_run: bool = False,
    videos: bool = True,
    dynamics: bool = False,
    articles: bool = False,
) -> dict[str, int]:
    _ensure_dirs()
    cfg = BiliConfig.load()
    print(f"配置来源: {cfg.source} | UID={cfg.uid}")
    if dynamics or articles:
        print(
            "[提示] 专栏/动态/充电文已改为手动：请复制 md 到 Raw/未分析归档/，"
            "ing 后自动移入 Raw/已分析归档/"
        )

    since_ts = _parse_since(since)
    state = _load_state()
    state.setdefault("opus", {})
    known_bvids, known_dyn, known_art, known_opus = _scan_existing_ids()
    stats = {
        "videos": 0, "dynamics": 0, "articles": 0, "opus": 0,
        "skipped": 0, "no_subtitle": 0, "dyn_skipped_video": 0,
    }

    client = BiliClient(cfg)
    try:
        if videos:
            print("\n[视频] 拉取投稿列表 + 字幕 → Raw/未审阅视频文稿/")
            for v in client.iter_videos():
                bvid = v.get("bvid") or ""
                if not bvid or bvid in known_bvids or bvid in state["videos"]:
                    stats["skipped"] += 1
                    continue
                pub_ts = int(v.get("created") or 0)
                if since_ts and pub_ts and pub_ts < since_ts:
                    continue
                title = v.get("title") or bvid
                try:
                    view = client.video_view(bvid)
                    cid = view.get("cid")
                    subs = client.video_subtitles(bvid, cid) if cid else []
                except Exception as e:
                    print(f"  [WARN] {bvid} 详情/字幕失败: {e}")
                    stats["skipped"] += 1
                    continue

                lan, body = pick_subtitle(subs, title)
                if not body or len(body.strip()) < 30:
                    print(f"  [SKIP] {bvid} 无有效字幕正文: {title}")
                    stats["no_subtitle"] += 1
                    continue

                body = format_transcript(body, force_punctuate=True)

                fname = pending_video_filename(title, bvid, pub_ts)
                path = _unique_path(PENDING_DIR, fname)
                pub_date = datetime.fromtimestamp(pub_ts).strftime("%Y-%m-%d") if pub_ts else ""
                content = _frontmatter({
                    "bvid": bvid,
                    "title": title,
                    "source": "bilibili",
                    "type": "video_transcript",
                    "subtitle_lang": lan,
                    "pub_time": pub_date,
                    "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "review_status": "pending",
                })
                content += f"# {title}\n\n> B站视频字幕稿（待审阅）| {bvid}\n\n{body}\n"
                _write(path, content, dry_run)
                tag = "[DRY]" if dry_run else "[NEW]"
                _safe_print(f"  {tag} {os.path.basename(path)}")
                state["videos"][bvid] = {"path": path, "fetched_at": datetime.now().isoformat()}
                known_bvids.add(bvid)
                stats["videos"] += 1
                time.sleep(0.5)

        if dynamics:
            stats["skipped"] += 1
            print("\n[动态] 已停用自动抓取（请手动放入 Raw/未分析归档/）")

        if articles:
            stats["skipped"] += 1
            print("\n[专栏] 已停用自动抓取（请手动放入 Raw/未分析归档/）")

    finally:
        client.close()
        if not dry_run:
            _save_state(state)

    return stats
