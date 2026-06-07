#!/usr/bin/env python3
"""
批量将 Raw/未分析其他材料 的提取稿消化为 Wiki/其他材料/*.md 并归档。

用法:
  python material_ingest_batch.py --dry-run
  python material_ingest_batch.py
"""
from __future__ import annotations

import argparse
import os
import re
from datetime import date
from pathlib import Path

from raw_paths import (
    RAW_PENDING_MATERIALS,
    WIKI_MATERIALS,
    list_pending_material_files,
)

ROOT = Path(__file__).resolve().parents[1]
EXTRACT_DIR = Path(WIKI_MATERIALS) / "_extracts"
LOG_MD = ROOT / "Wiki" / "log.md"
INDEX_MD = ROOT / "Wiki" / "index.md"

SECTION_RE = re.compile(r"^---\s*(?:幻灯片|第)\s*(\d+)\s*(?:页|---)\s*---\s*$", re.M)
META_SOURCE = re.compile(r"^#\s*来源:\s*(.+)$", re.M)
META_FMT = re.compile(r"^>\s*格式:\s*(\S+)", re.M)

CATEGORY_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("投资教学", re.compile(r"F10|模块|PB\.|PEG|PS\.|第一讲|第二讲|第三讲|第四讲|估值法|PE 分行业", re.I)),
    ("外资研报", re.compile(r"高盛|Goldman|摩根|Morgan|us-equity|MS_|TimeScaling", re.I)),
    ("券商研报", re.compile(r"证券_|华泰|东吴|华安|研报", re.I)),
    ("产业深度", re.compile(r"AIDC|AI算力|产业链|Token|OpenClaw|创新药|Rubin|PCB|基础设施", re.I)),
    ("宏观策略", re.compile(r"宏观|碳|global_market|再通胀|战略|策略", re.I)),
]

LINK_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("[[Rubin-VR200产业链梳理]]", re.compile(r"Rubin|VR200|PCB|MLCC|光互连", re.I)),
    ("[[板块轮动记录]]", re.compile(r"产业链|算力|半导体|创新药|机器人|AI", re.I)),
    ("[[宏观分析框架]]", re.compile(r"宏观|美债|利率|再通胀|碳", re.I)),
    ("[[选股框架]]", re.compile(r"估值|PE|PB|PEG|PS|F10|财务", re.I)),
    ("[[技术分析体系]]", re.compile(r"K线|技术|布林", re.I)),
    ("[[仓位管理]]", re.compile(r"仓位|建仓|分仓", re.I)),
]


def _safe_filename(stem: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", stem).strip()
    return name[:120] or "untitled"


def _parse_extract(text: str) -> tuple[str, str, list[tuple[str, str]]]:
    src = META_SOURCE.search(text)
    fmt = META_FMT.search(text)
    source_name = src.group(1).strip() if src else "unknown"
    material_type = fmt.group(1).strip() if fmt else "unknown"
    body = text
    if META_FMT.search(text):
        body = text.split("\n\n", 3)[-1] if text.count("\n\n") >= 3 else text
    parts = SECTION_RE.split(body)
    sections: list[tuple[str, str]] = []
    if len(parts) > 1:
        it = iter(parts)
        _ = next(it, "")
        for num, content in zip(it, it):
            sections.append((str(num).strip(), content.strip()))
    else:
        sections.append(("全文", body.strip()))
    return source_name, material_type, sections


def _first_summary(sections: list[tuple[str, str]], min_len: int = 80) -> str:
    for _, content in sections:
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        buf: list[str] = []
        for ln in lines:
            if ln.startswith("---"):
                continue
            if re.match(r"^模块|^MODULE|^特别声明", ln, re.I):
                continue
            buf.append(ln)
            if len("".join(buf)) >= min_len:
                break
        s = " ".join(buf)[:400].strip()
        if len(s) >= 40:
            return s
    flat = " ".join(c for _, c in sections)
    return flat[:400].strip() or "（未能自动生成摘要，见正文）"


def _key_points(sections: list[tuple[str, str]], limit: int = 12) -> list[str]:
    points: list[str] = []
    seen: set[str] = set()
    for _, content in sections:
        for ln in content.splitlines():
            ln = ln.strip()
            if not ln or len(ln) < 6:
                continue
            if ln.startswith("---"):
                continue
            is_point = (
                re.match(r"^[\d一二三四五六七八九十]+[、./)]", ln)
                or ln.startswith(("•", "-", "★", "⚠", "✓", "→"))
                or re.match(r"^0?\d\s*/\s*", ln)
                or (len(ln) < 100 and "：" in ln and ln.index("：") < 20)
            )
            if is_point and ln not in seen:
                seen.add(ln)
                points.append(ln.lstrip("•- "))
                if len(points) >= limit:
                    return points
    return points


def _guess_category(source: str, text: str) -> str:
    blob = source + "\n" + text[:3000]
    for label, pat in CATEGORY_RULES:
        if pat.search(blob):
            return label
    return "其他材料"


def _guess_links(text: str) -> list[str]:
    links: list[str] = []
    for link, pat in LINK_RULES:
        if pat.search(text) and link not in links:
            links.append(link)
    return links[:5]


def _section_title(num: str, content: str) -> str:
    first = next((ln.strip() for ln in content.splitlines() if ln.strip()), f"第 {num} 节")
    if len(first) > 80:
        first = first[:77] + "…"
    return first


def build_wiki_md(source_file: str, extract_text: str) -> tuple[str, str]:
    source_name, material_type, sections = _parse_extract(extract_text)
    if not sections or all(len(c.strip()) < 20 for _, c in sections):
        title = Path(source_file).stem
        body = (
            f"# {title}\n\n"
            f"> ⚠️ 未能从 `{source_name}` 提取有效文本（可能为扫描件/图片 PDF）。\n"
            f"> 原文件保留在归档目录，需 OCR 或手动补充。\n"
        )
        return _safe_filename(title) + ".md", body

    category = _guess_category(source_name, extract_text)
    summary = _first_summary(sections)
    points = _key_points(sections)
    links = _guess_links(extract_text)
    today = date.today().isoformat()
    title = Path(source_file).stem
    if re.match(r"^[A-Za-z0-9_.()-]+$", title):
        display_title = title.replace("_", " ")
    else:
        display_title = title

    fm = (
        "---\n"
        f"date: {today}\n"
        f"type: 其他材料\n"
        f"category: {category}\n"
        f"material_type: {material_type}\n"
        f"source_file: {source_name}\n"
        f"ingested_at: {today}\n"
        f"tags: [{category}]\n"
        "---\n\n"
    )
    link_line = " | ".join(links) if links else "（见 [[板块轮动记录]] / [[宏观分析框架]]）"
    lines = [
        fm,
        f"# {display_title}\n",
        f"> **分类**：{category} | **来源**：`{source_name}` | **格式**：{material_type}",
        f"> **摘要**：{summary}\n",
        "---\n",
        "## 核心要点\n",
    ]
    if points:
        for p in points:
            lines.append(f"- {p}")
    else:
        lines.append("- （见下方分节正文）")
    lines.extend(["", "## 关联 Wiki", "", link_line, "", "---", ""])

    if len(sections) == 1 and sections[0][0] == "全文":
        lines.extend(["## 正文\n", sections[0][1], ""])
    else:
        lines.append("## 分节正文\n")
        for num, content in sections:
            if not content.strip():
                continue
            st = _section_title(num, content)
            lines.append(f"### {st}\n")
            lines.append(content)
            lines.append("")

    wiki_name = _safe_filename(title) + ".md"
    return wiki_name, "\n".join(lines)


def _append_log(count: int, names: list[str], *, dry_run: bool = False) -> None:
    today = date.today().isoformat()
    entry = (
        f"\n## [{today}] ingest × {count} | 其他材料批量入库\n\n"
        f"- 操作类型：其他材料 ingest（material_ingest_batch.py）\n"
        f"- 输入：`Raw/未分析其他材料/` {count} 份（pdf/pptx/docx）\n"
        f"- 输出：`Wiki/其他材料/` 新建 {count} 页\n"
        f"- 归档：→ `Raw/已分析其他材料/`\n"
        f"- 页面：{', '.join('[[其他材料/' + Path(n).stem + ']]' if False else '`' + n + '`' for n in names[:8])}"
        + (f" 等共 {count} 篇" if count > 8 else "")
        + "\n"
    )
    if dry_run:
        print(entry)
        return
    with open(LOG_MD, encoding="utf-8") as f:
        head = f.read()
    with open(LOG_MD, "w", encoding="utf-8") as f:
        parts = head.split("\n---\n", 1)
        if len(parts) == 2:
            f.write(parts[0] + "\n---\n" + entry + parts[1])
        else:
            f.write(head + entry)


def _patch_index(count: int, *, dry_run: bool = False) -> None:
    marker = "## 其他材料"
    block = (
        "\n## 其他材料\n\n"
        f"> 最后更新：{date.today().isoformat()} | 共 **{count}** 篇（研报/教程/产业深度）\n\n"
        "| 入口 | 说明 |\n|------|------|\n"
        "| [[其他材料/_index]] | 按分类索引（本批批量入库） |\n\n"
    )
    if not INDEX_MD.is_file():
        return
    text = INDEX_MD.read_text(encoding="utf-8")
    if marker in text:
        # update count line only
        text = re.sub(
            r"> 最后更新：[\d-]+ \| 共 \*\*\d+\*\* 篇",
            f"> 最后更新：{date.today().isoformat()} | 共 **{count}** 篇",
            text,
            count=1,
        )
    else:
        # insert before 关键经验 or at end of main sections
        insert_at = text.find("\n## 数据与脚本")
        if insert_at < 0:
            insert_at = text.find("*本索引由 LLM")
        if insert_at < 0:
            text = text.rstrip() + block
        else:
            text = text[:insert_at] + block + text[insert_at:]
    if dry_run:
        print("Would patch index.md")
        return
    INDEX_MD.write_text(text, encoding="utf-8")


def _write_index_page(wiki_files: list[tuple[str, str, str]], *, dry_run: bool = False) -> None:
    """wiki_files: (filename, category, summary)"""
    by_cat: dict[str, list[tuple[str, str]]] = {}
    for fname, cat, summ in wiki_files:
        by_cat.setdefault(cat, []).append((fname, summ))
    lines = [
        "---",
        f"date: {date.today().isoformat()}",
        "type: 索引",
        "---",
        "",
        "# 其他材料索引",
        "",
        f"> 共 {len(wiki_files)} 篇 | 由 `material_ingest_batch.py` 维护",
        "",
    ]
    for cat in sorted(by_cat.keys()):
        lines.append(f"## {cat}\n")
        lines.append("| 文档 | 摘要 |")
        lines.append("|------|------|")
        for fname, summ in sorted(by_cat[cat], key=lambda x: x[0].lower()):
            stem = Path(fname).stem
            s = summ[:80] + ("…" if len(summ) > 80 else "")
            lines.append(f"| [[{stem}]] | {s} |")
        lines.append("")
    path = Path(WIKI_MATERIALS) / "_index.md"
    if dry_run:
        print(f"Would write {path}")
        return
    path.write_text("\n".join(lines), encoding="utf-8")


def run(*, dry_run: bool = False) -> int:
    os.makedirs(WIKI_MATERIALS, exist_ok=True)
    sources = list_pending_material_files()
    if not sources:
        print("无待 ingest 的其他材料")
        return 0

    written: list[tuple[str, str, str]] = []
    for src in sources:
        stem = Path(src).stem
        extract_path = EXTRACT_DIR / f"{stem}.extract.md"
        if not extract_path.is_file():
            print(f"[SKIP] 无提取稿: {stem}")
            continue
        extract_text = extract_path.read_text(encoding="utf-8")
        wiki_name, wiki_body = build_wiki_md(src, extract_text)
        dest = Path(WIKI_MATERIALS) / wiki_name
        if dest.exists() and not dry_run:
            wiki_name = _safe_filename(stem + "_ingested") + ".md"
            dest = Path(WIKI_MATERIALS) / wiki_name
        category = _guess_category(Path(src).name, extract_text)
        summary = _first_summary(_parse_extract(extract_text)[2])
        if dry_run:
            print(f"[DRY] {Path(src).name} -> {wiki_name} ({len(wiki_body)} chars)")
        else:
            dest.write_text(wiki_body, encoding="utf-8")
            print(f"[OK] {wiki_name}")
        written.append((wiki_name, category, summary))

    if not dry_run and written:
        from archive_material import archive_all

        n = archive_all()
        print(f"\n归档 {n} 个原文件 -> Raw/已分析其他材料/")
        _write_index_page(written)
        _append_log(len(written), [w[0] for w in written])
        _patch_index(len(written))
    elif dry_run:
        _write_index_page(written, dry_run=True)
        _append_log(len(written), [w[0] for w in written], dry_run=True)

    print(f"\n完成: {len(written)}/{len(sources)} 篇")
    return len(written)


def main() -> None:
    ap = argparse.ArgumentParser(description="批量 ingest 其他材料")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    raise SystemExit(0 if run(dry_run=args.dry_run) else 1)


if __name__ == "__main__":
    main()
