#!/usr/bin/env python3
"""
批量 ingest 已审阅视频文稿（抖音/B 站）：双轨写入日更 + 视频专题。

用法:
  python video_ingest_batch.py --dry-run
  python video_ingest_batch.py --limit 10
  python video_ingest_batch.py
"""
from __future__ import annotations

import argparse
import os
import re
from datetime import date, datetime
from pathlib import Path

from archive_raw import archive_file
from raw_paths import RAW_APPROVED_VIDEO, mark_video_ingested
from wiki.video_topic import (
    classify_video_category,
    list_video_ing_pending,
    mark_video_wiki_topic,
    wiki_slug_from_raw_basename,
    _read_fm,
    _FM_SPLIT,
)

ROOT = Path(__file__).resolve().parents[1]
WIKI_DAILY = ROOT / "Wiki" / "每日复盘"
LOG_MD = ROOT / "Wiki" / "log.md"

_DATE_PREFIX = re.compile(r"^(\d{2})-(\d{2})-(\d{2})_")
_SESSION_PAT = re.compile(r"(午评|收评|早盘|午盘|周复盘|周末分享|收评，|午评，)")
_INDEX_LEVELS = re.compile(
    r"(4033|4133|4130|4120|4080|4047|4000|3993|3950|3902|3680|3500|"
    r"五日线|十日线|缺口|地量|缩量|黑周四|中阳线|年线)"
)
_POSITION_PAT = re.compile(r"([五六七八九]成|[半全]仓|加仓|减仓|七成|八成)")
_SECTOR_WORDS = (
    "光刻机", "半导体", "商业航天", "世界杯", "保险", "证券", "创新药",
    "软件", "新能源", "光模块", "存储", "机器人", "锂电", "钨", "靶材",
    "电子特气", "六氟", "液冷", "煤炭", "电力", "消费", "芯片", "AI",
    "华为", "昇腾", "智能体", "物理AI", "有色", "化工", "光伏",
)
_SKIP_DAILY_TITLE = (
    "品牌", "护肤", "双12", "年度回忆", "新年礼物", "过年", "美妆",
)


def _parse_iso_date(name: str, fm: dict) -> str | None:
    pub = (fm.get("pub_time") or "")[:10]
    if re.match(r"\d{4}-\d{2}-\d{2}", pub):
        return pub
    m = _DATE_PREFIX.match(name)
    if not m:
        return None
    yy, mm, dd = m.groups()
    return f"20{yy}-{mm}-{dd}"


def _extract_body(text: str) -> str:
    m = _FM_SPLIT.match(text)
    body = text[m.end() :] if m else text
    lines = body.splitlines()
    out: list[str] = []
    for ln in lines:
        if ln.startswith("# ") or (ln.startswith(">") and len(out) < 3):
            continue
        out.append(ln)
    return "\n".join(out).strip()


def _split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", "", text)
    parts = re.split(r"(?<=[。！？])", text)
    sents: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p) > 120:
            sents.extend(x.strip() for x in re.split(r"(?<=[，；])", p) if x.strip())
        else:
            sents.append(p)
    return sents


def _pick_bullets(sents: list[str], limit: int = 8) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for s in sents:
        if len(s) < 12 or s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= limit:
            break
    return out


def _extract_index_bits(text: str) -> list[str]:
    hits: list[str] = []
    for m in _INDEX_LEVELS.finditer(text):
        hits.append(m.group(0))
    for n in re.findall(r"(?<!\d)(\d{4})(?!\d)", text):
        if n.startswith(("39", "40", "41", "42", "35", "36")):
            hits.append(n)
    return list(dict.fromkeys(hits))[:8]


def _extract_sectors(text: str) -> list[str]:
    return [w for w in _SECTOR_WORDS if w in text][:10]


def _session_label(title: str, filename: str) -> str:
    hay = f"{title}{filename}"
    if "午评" in hay or "午盘" in hay:
        return "午评"
    if "收评" in hay or "晚间" in hay:
        return "收评"
    if "周复盘" in hay or "周末" in hay:
        return "周复盘"
    if "早盘" in hay:
        return "早盘"
    return "视频"


def _skip_daily(title: str) -> bool:
    return any(k in title for k in _SKIP_DAILY_TITLE)


def _summary_one_line(sents: list[str], max_len: int = 80) -> str:
    for s in sents:
        if len(s) >= 20:
            return s[:max_len] + ("…" if len(s) > max_len else "")
    return (sents[0][:max_len] if sents else "（见正文）")


def _build_topic_page(
    *,
    iso_date: str,
    title: str,
    category: str,
    creator: str,
    aweme_or_bvid: str,
    source_raw: str,
    body: str,
    slug: str,
) -> str:
    sents = _split_sentences(body)
    idx = _extract_index_bits(body)
    sectors = _extract_sectors(body)
    pos = list(dict.fromkeys(_POSITION_PAT.findall(body)))[:4]
    core = _pick_bullets(sents, 6)
    sector_sents = [s for s in sents if any(w in s for w in _SECTOR_WORDS)][:6]
    discipline = [s for s in sents if any(k in s for k in ("仓位", "纪律", "加仓", "减仓", "买", "卖", "T"))][:4]

    id_key = "bvid" if aweme_or_bvid.startswith("BV") else "aweme_id"
    fm = (
        f"---\n"
        f"date: {iso_date}\n"
        f"type: 视频专题\n"
        f"category: {category}\n"
        f"creator: {creator}\n"
        f"{id_key}: {aweme_or_bvid}\n"
        f"tags: [{', '.join(sectors[:6])}]\n"
        f"source_raw: {source_raw}\n"
        f"ingested_at: {date.today().isoformat()}\n"
        f"---\n"
    )
    lines = [
        fm,
        f"\n# {title}\n",
        f"\n> {creator} · {iso_date} · {_summary_one_line(sents)}\n",
        "\n## 核心观点\n",
    ]
    for b in core:
        lines.append(f"- {b}")
    lines.append("\n## 指数/盘面\n")
    if idx:
        lines.append("| 关键词 | " + " · ".join(idx) + " |")
        lines.append("|--------|------|")
    for b in _pick_bullets([s for s in sents if _INDEX_LEVELS.search(s) or "指数" in s], 5):
        lines.append(f"- {b}")
    lines.append("\n## 板块与标的\n")
    if sectors:
        lines.append("- **提及方向**：" + "、".join(sectors))
    for b in sector_sents:
        lines.append(f"- {b}")
    if pos:
        lines.append("\n## 操作纪律\n")
        lines.append("- **仓位/节奏**：" + "、".join(pos))
        for b in discipline:
            lines.append(f"- {b}")
    lines.append("\n## 链接\n")
    lines.append(f"- [[{iso_date}]]")
    lines.append("- [[指数纪律框架]]")
    lines.append("- [[板块轮动记录]]")
    return "\n".join(lines) + "\n"


def _append_daily_section(
    iso_date: str,
    session: str,
    title: str,
    creator: str,
    source_raw: str,
    slug: str,
    body: str,
    *,
    dry_run: bool,
) -> bool:
    if _skip_daily(title):
        return False
    path = WIKI_DAILY / f"{iso_date}.md"
    sents = _split_sentences(body)
    idx = _extract_index_bits(body)
    sectors = _extract_sectors(body)
    marker = f"§ {creator}抖音·{session}"
    if path.is_file() and marker in path.read_text(encoding="utf-8"):
        return False

    section = [
        f"\n---\n\n## {marker}\n",
        f"\n*来源：`{source_raw}` · 专题 [[{slug}]]*\n",
        "\n### 要点\n",
    ]
    for b in _pick_bullets(sents, 5):
        section.append(f"- {b}")
    if idx:
        section.append(f"\n- **指数关键词**：{' · '.join(idx)}")
    if sectors:
        section.append(f"- **板块**：{'、'.join(sectors[:8])}")

    if path.is_file():
        text = path.read_text(encoding="utf-8")
        insert_at = text.find("\n## 七、链接")
        if insert_at < 0:
            insert_at = text.find("\n## 链接")
        if insert_at < 0:
            new_text = text.rstrip() + "".join(section)
        else:
            new_text = text[:insert_at] + "".join(section) + text[insert_at:]
    else:
        new_text = (
            f"---\ndate: {iso_date}\ntype: 视频日更\ntags: [{', '.join(sectors[:5])}]\n---\n\n"
            f"# {iso_date} · {creator}视频摘要\n\n"
            f"> 由 `video_ingest_batch.py` 自 ASR 稿结构化提取\n"
            + "".join(section)
            + "\n## 链接\n\n- [[指数纪律框架]]\n"
        )
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new_text, encoding="utf-8")
    return True


def _append_video_index(slug: str, iso_date: str, vid_id: str, summary: str, category: str) -> None:
    index_path = ROOT / "Wiki" / "视频专题" / "视频专题索引.md"
    if not index_path.is_file():
        return
    text = index_path.read_text(encoding="utf-8")
    link = f"[[{slug}]]"
    if link in text:
        return
    short = iso_date[5:].replace("-", "-")
    row = f"| {link} | {short} | {vid_id or '—'} | {summary[:40]} |"
    header = f"## {category}（"
    pos = text.find(header)
    if pos < 0:
        return
    table_end = text.find("\n\n>", pos)
    if table_end < 0:
        table_end = text.find("\n---", pos)
    if table_end < 0:
        return
    text = text[:table_end] + "\n" + row + text[table_end:]
    text = re.sub(
        r"最后更新：\d{4}-\d{2}-\d{2}",
        f"最后更新：{date.today().isoformat()}",
        text,
        count=1,
    )
    index_path.write_text(text, encoding="utf-8")


def _append_log(n: int, *, dry_run: bool) -> None:
    if dry_run or n <= 0:
        return
    today = date.today().isoformat()
    block = (
        f"## [{today}] ingest × {n} | 钱加贝抖音视频批量入库\n\n"
        f"- 操作类型：ingest（`scripts/video_ingest_batch.py` 双轨）\n"
        f"- **视频**：{n} 篇 → `Wiki/每日复盘/` + `Wiki/视频专题/复盘/`\n"
        f"- Raw：`review_status: ingested` + `wiki_topic_path` 回写\n\n"
    )
    text = LOG_MD.read_text(encoding="utf-8")
    marker = "\n---\n\n"
    if marker in text:
        head, rest = text.split(marker, 1)
        LOG_MD.write_text(head + marker + block + rest, encoding="utf-8")
    else:
        LOG_MD.write_text(text.rstrip() + "\n\n" + block, encoding="utf-8")


def ingest_one(item: dict, *, dry_run: bool) -> dict:
    path = item["path"]
    name = os.path.basename(path)
    fm, full = _read_fm(path)
    iso = _parse_iso_date(name, fm)
    if not iso:
        return {"path": path, "status": "skip", "reason": "no_date"}

    title = fm.get("title") or name
    creator = fm.get("creator") or ("B站" if fm.get("bvid") else "钱加贝")
    vid = fm.get("bvid") or fm.get("aweme_id") or ""
    body = _extract_body(full)
    if len(body) < 20:
        return {"path": path, "status": "skip", "reason": "empty_body"}

    category = classify_video_category(title=title, filename=name, body=body)
    slug = wiki_slug_from_raw_basename(name, title=title)
    wiki_rel = f"Wiki/视频专题/{category}/{slug}.md"
    wiki_path = ROOT / wiki_rel.replace("/", os.sep)
    source_raw = item["relpath"]
    session = _session_label(title, name)
    sents = _split_sentences(body)

    if not dry_run:
        wiki_path.parent.mkdir(parents=True, exist_ok=True)
        if not wiki_path.is_file():
            wiki_path.write_text(
                _build_topic_page(
                    iso_date=iso,
                    title=title,
                    category=category,
                    creator=creator,
                    aweme_or_bvid=vid,
                    source_raw=source_raw,
                    body=body,
                    slug=slug,
                ),
                encoding="utf-8",
            )
        daily_ok = False
        if "daily_wiki" in item.get("tasks", []):
            daily_ok = _append_daily_section(
                iso, session, title, creator, source_raw, slug, body, dry_run=False
            )
        mark_video_wiki_topic(path, wiki_rel)
        mark_video_ingested(path)
        _append_video_index(slug, iso, vid, _summary_one_line(sents), category)
    else:
        daily_ok = "daily_wiki" in item.get("tasks", [])

    return {
        "path": path,
        "status": "ok",
        "wiki": wiki_rel,
        "date": iso,
        "daily": daily_ok,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="批量 ingest 已审阅视频文稿")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    pending = list_video_ing_pending()
    if args.limit:
        pending = pending[: args.limit]

    ok = skip = 0
    for item in pending:
        r = ingest_one(item, dry_run=args.dry_run)
        tag = "[DRY] " if args.dry_run else ""
        if r["status"] == "ok":
            ok += 1
            print(f"{tag}OK  {os.path.basename(r['path'])} → {r['wiki']}")
        else:
            skip += 1
            print(f"{tag}SKIP {os.path.basename(r['path'])} ({r.get('reason')})")

    _append_log(ok, dry_run=args.dry_run)
    print(f"\n完成: {len(pending)} 队列 | {ok} 入库 | {skip} 跳过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
