#!/usr/bin/env python3
"""批量修正文件名/内容中的非交易日日期 → 最近交易日。"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from typing import Iterable

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from trading_calendar import (  # noqa: E402
    ensure_calendar,
    filename_trading_date,
    format_filename_date,
    is_trading_day,
)

SKIP_DIRS = {
    ".git",
    ".obsidian",
    "__pycache__",
    "node_modules",
    "External_Skills",
    "云",
}
SCAN_ROOTS = (
    "SugVault",
    "Raw",
    os.path.join("Wiki", "数据"),
    os.path.join("Wiki", "每日复盘"),
    "graph_progress",
)

DATE_IN_NAME = re.compile(
    r"(?P<long>20\d{2}-\d{2}-\d{2})|(?P<short>(?<!\d)\d{2}-\d{2}-\d{2}(?!\d))"
)
VIPDOC_LINE = re.compile(r"数据日（vipdoc）：\*\*(20\d{2}-\d{2}-\d{2})\*\*")
DATE_LINE = re.compile(r"^- 日期：\*\*(20\d{2}-\d{2}-\d{2})\*\*\s*$", re.M)
ISO_DATE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")


def _parse_any_date(s: str) -> date | None:
    s = s.strip()[:10]
    try:
        if len(s) == 8 and s[4] != "-":
            return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        return date.fromisoformat(s)
    except ValueError:
        return None


def _short_fmt(d: date) -> str:
    return format_filename_date(d, short=True)


def _long_fmt(d: date) -> str:
    return format_filename_date(d)


def _infer_target_date(path: str, name_date: date) -> date:
    try:
        head = open(path, encoding="utf-8", errors="ignore").read(12000)
    except OSError:
        return filename_trading_date(name_date)
    m = VIPDOC_LINE.search(head)
    if m:
        vd = _parse_any_date(m.group(1))
        if vd and is_trading_day(vd):
            return vd
    return filename_trading_date(name_date)


def _replace_dates_in_text(text: str, mapping: dict[str, str]) -> str:
    out = text
    for old, new in sorted(mapping.items(), key=lambda x: -len(x[0])):
        if old == new:
            continue
        out = out.replace(old, new)
    return out


def _rename_file(path: str, new_name: str, *, dry_run: bool) -> str | None:
    d = os.path.dirname(path)
    dest = os.path.join(d, new_name)
    if os.path.normpath(path) == os.path.normpath(dest):
        return None
    if os.path.exists(dest):
        stem, ext = os.path.splitext(new_name)
        i = 2
        while os.path.exists(dest):
            dest = os.path.join(d, f"{stem}_{i}{ext}")
            i += 1
    if dry_run:
        print(f"  [DRY] {os.path.basename(path)} -> {os.path.basename(dest)}")
        return dest
    os.rename(path, dest)
    print(f"  [OK] {os.path.basename(path)} -> {os.path.basename(dest)}")
    return dest


def _fix_filename(path: str, *, dry_run: bool) -> tuple[str | None, dict[str, str]]:
    """返回 (新路径, 日期替换映射 long->long)。"""
    fn = os.path.basename(path)
    m = DATE_IN_NAME.search(fn)
    if not m:
        return None, {}
    old_token = m.group("long") or m.group("short")
    name_date = _parse_any_date(old_token if m.group("long") else f"20{old_token}")
    if not name_date or is_trading_day(name_date):
        return None, {}

    target = _infer_target_date(path, name_date)
    if target == name_date:
        return None, {}

    new_token = _long_fmt(target) if m.group("long") else _short_fmt(target)
    new_fn = fn[: m.start()] + new_token + fn[m.end() :]
    new_path = _rename_file(path, new_fn, dry_run=dry_run)
    mapping = {_long_fmt(name_date): _long_fmt(target)}
    if m.group("short"):
        mapping[_short_fmt(name_date)] = _short_fmt(target)
    return new_path or path, mapping


def _fix_markdown_body(path: str, mapping: dict[str, str], *, dry_run: bool) -> bool:
    if not mapping or not path.endswith(".md"):
        return False
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return False
    new_text = _replace_dates_in_text(text, mapping)
    if new_text == text:
        return False
    if dry_run:
        print(f"  [DRY] patch body {os.path.basename(path)}")
        return True
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_text)
    print(f"  [PATCH] {os.path.basename(path)}")
    return True


def _walk_files(roots: Iterable[str]) -> list[str]:
    out: list[str] = []
    for rel in roots:
        base = os.path.join(ROOT, rel) if not os.path.isabs(rel) else rel
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn.startswith("."):
                    continue
                out.append(os.path.join(dirpath, fn))
    return out


def _fix_json_paths(json_path: str, renames: dict[str, str], *, dry_run: bool) -> None:
    if not os.path.isfile(json_path):
        return
    try:
        text = open(json_path, encoding="utf-8").read()
    except OSError:
        return
    new_text = text
    for old, new in sorted(renames.items(), key=lambda x: -len(x[0])):
        new_text = new_text.replace(old.replace("/", "\\"), new.replace("/", "\\"))
        new_text = new_text.replace(old, new)
    if new_text == text:
        return
    if dry_run:
        print(f"  [DRY] patch {os.path.relpath(json_path, ROOT)}")
        return
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(new_text)
    print(f"  [PATCH] {os.path.relpath(json_path, ROOT)}")


def _fix_prediction_json(mapping: dict[str, str], *, dry_run: bool) -> None:
    log_path = os.path.join(ROOT, "Wiki", "数据", "股价预测追踪", "预测登记.json")
    if not mapping or not os.path.isfile(log_path):
        return
    try:
        data = json.load(open(log_path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    changed = False
    for rec in data.get("records") or []:
        old_d = str(rec.get("date") or "")
        if old_d in mapping:
            rec["date"] = mapping[old_d]
            rid = str(rec.get("id") or "")
            if rid.startswith(old_d):
                rec["id"] = mapping[old_d] + rid[len(old_d) :]
            changed = True
        for hk, h in (rec.get("horizons") or {}).items():
            if not isinstance(h, dict):
                continue
            for key in ("track_from", "due_date", "params_version"):
                val = str(h.get(key) or "")
                if val in mapping:
                    h[key] = mapping[val]
                    changed = True
    if not changed:
        return
    if dry_run:
        print("  [DRY] patch 预测登记.json dates")
        return
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("  [PATCH] 预测登记.json")


def _fix_inline_report_dates(path: str, *, dry_run: bool) -> bool:
    """复盘 md：日期行非交易日 → 对齐 vipdoc 数据日。"""
    if not path.endswith(".md"):
        return False
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return False
    vip = VIPDOC_LINE.search(text)
    if not vip:
        return False
    data_d = _parse_any_date(vip.group(1))
    if not data_d or not is_trading_day(data_d):
        return False

    def _repl(m: re.Match[str]) -> str:
        old = _parse_any_date(m.group(1))
        if not old or is_trading_day(old) or old == data_d:
            return m.group(0)
        return f"- 日期：**{_long_fmt(data_d)}**"

    new_text = DATE_LINE.sub(_repl, text)
    if new_text == text:
        return False
    if dry_run:
        print(f"  [DRY] inline date {os.path.basename(path)}")
        return True
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_text)
    print(f"  [INLINE] {os.path.basename(path)}")
    return True


def run(*, dry_run: bool = False) -> dict[str, int]:
    ensure_calendar(start=date(2023, 1, 1), end=date(2027, 12, 31))
    stats = {"renamed": 0, "patched": 0, "skipped": 0}
    global_mapping: dict[str, str] = {}
    path_renames: dict[str, str] = {}

    roots = list(SCAN_ROOTS) + [
        os.path.join("Wiki", "数据", "graph_progress"),
        os.path.join("Wiki", "数据", "graph_runs"),
        os.path.join("Wiki", "数据", "缠论回测"),
    ]
    files = _walk_files(roots)
    # 根目录 YYYY-MM-DD_*.md
    for fn in os.listdir(ROOT):
        if re.match(r"20\d{2}-\d{2}-\d{2}_.*\.md$", fn):
            files.append(os.path.join(ROOT, fn))

    for path in sorted(set(files)):
        if _fix_inline_report_dates(path, dry_run=dry_run):
            stats["patched"] += 1
        new_path, mapping = _fix_filename(path, dry_run=dry_run)
        if not mapping:
            stats["skipped"] += 1
            continue
        stats["renamed"] += 1
        global_mapping.update(mapping)
        if new_path and new_path != path:
            path_renames[os.path.normpath(path)] = os.path.normpath(new_path)
        target = new_path or path
        if _fix_markdown_body(target, mapping, dry_run=dry_run):
            stats["patched"] += 1

    for old_p, new_p in list(path_renames.items()):
        rel_old = os.path.relpath(old_p, ROOT)
        rel_new = os.path.relpath(new_p, ROOT)
        path_renames[rel_old] = rel_new

    for jp in (
        os.path.join(ROOT, "Wiki", "数据", "bilibili_sync.json"),
        os.path.join(ROOT, "Wiki", "数据", "douyin_sync.json"),
        os.path.join(ROOT, "Wiki", "数据", "技术预测追踪.json"),
    ):
        _fix_json_paths(jp, path_renames, dry_run=dry_run)

    _fix_prediction_json(global_mapping, dry_run=dry_run)

    # Wiki 内链：[[2026-06-13]] → [[2026-06-12]]
    if global_mapping:
        wiki_root = os.path.join(ROOT, "Wiki")
        for dirpath, _, filenames in os.walk(wiki_root):
            if any(s in dirpath for s in SKIP_DIRS):
                continue
            for fn in filenames:
                if not fn.endswith(".md"):
                    continue
                p = os.path.join(dirpath, fn)
                if _fix_markdown_body(p, global_mapping, dry_run=dry_run):
                    stats["patched"] += 1

    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="修正非交易日文件名/内容日期")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    print(f"fix_trading_day_names | dry_run={args.dry_run}")
    stats = run(dry_run=args.dry_run)
    print(f"\n完成: 重命名 {stats['renamed']} | 内容修正 {stats['patched']} | 跳过 {stats['skipped']}")


if __name__ == "__main__":
    main()
