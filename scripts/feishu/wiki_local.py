"""本机 Wiki 目录树与 Markdown → PDF 导出（飞书 Bot）。"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from bilibili.env import ROOT

WIKI_ROOT = os.path.join(ROOT, "Wiki")

SKIP_FILES = frozenset({"feishu_debug.log"})

FOLDER_HINTS: dict[str, str] = {
    "投资方法论": "博主投资框架与方法",
    "市场分析": "大盘/板块/产业链分析",
    "每日复盘": "按日归档复盘",
    "博主": "标的总览、追踪、决策时间线",
    "数据": "脚本输出（市场日报、标的池、粗筛/精筛 CSV）",
    "待审阅视频文稿": "bilibili_fetch 写入，待 txtcfm",
    "标的追踪": "活跃池标的专页",
    "不活跃标的": "已移出活跃池的追踪页",
}

FILE_HINTS: dict[str, str] = {
    "index.md": "Wiki 首页目录",
    "log.md": "ingest 变更日志",
    "schema.md": "Wiki 操作规范（根目录）",
}


def _hint(entry: Path, wiki_root: Path) -> str:
    if entry.is_dir():
        return FOLDER_HINTS.get(entry.name, "")
    rel = entry.relative_to(wiki_root).as_posix()
    return FILE_HINTS.get(entry.name, "") or FILE_HINTS.get(rel, "")


def _visible_entries(dir_path: Path) -> list[Path]:
    out: list[Path] = []
    for entry in sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if entry.name.startswith("."):
            continue
        if entry.is_file() and entry.name in SKIP_FILES:
            continue
        out.append(entry)
    return out


def build_wiki_tree(wiki_root: str = WIKI_ROOT) -> str:
    """生成 Wiki/ 下目录树（含 .md / .csv 等文件）。"""
    root = Path(wiki_root)
    if not root.is_dir():
        return f"（Wiki 目录不存在：{wiki_root}）"

    lines = ["Wiki/"]

    def walk(dir_path: Path, prefix: str) -> None:
        entries = _visible_entries(dir_path)
        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            branch = "└── " if is_last else "├── "
            hint = _hint(entry, root)
            suffix = f"  ← {hint}" if hint else ""
            if entry.is_dir():
                lines.append(f"{prefix}{branch}{entry.name}/{suffix}")
                ext = "    " if is_last else "│   "
                walk(entry, prefix + ext)
            else:
                lines.append(f"{prefix}{branch}{entry.name}{suffix}")

    walk(root, "")
    return "\n".join(lines)


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        m = re.match(r"---\s*\n.*?\n---\s*\n", text, re.DOTALL)
        if m:
            return text[m.end() :]
    return text


def _find_windows_font() -> str | None:
    candidates = (
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\msyhbd.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\msyh.ttf",
    )
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def _plainify_md_line(line: str) -> str:
    line = re.sub(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]", r"\1", line)
    line = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", line)
    line = line.replace("|", " ").strip()
    return line


def _sanitize_pdf_text(text: str) -> str:
    out: list[str] = []
    for ch in text:
        o = ord(ch)
        if o in (0xFE0F, 0x200B):
            continue
        if 0x1F300 <= o <= 0x1FAFF or 0x2600 <= o <= 0x27BF:
            continue
        out.append(ch)
    return "".join(out)


def _pdf_write_line(pdf, line: str, *, line_h: float = 6, font_size: int = 10) -> None:
    pdf.set_x(pdf.l_margin)
    pdf.set_font("zh", size=font_size)
    text = _sanitize_pdf_text(_plainify_md_line(line))
    if not text:
        pdf.ln(4)
        return
    width = pdf.w - pdf.l_margin - pdf.r_margin
    while text:
        chunk = text[:100]
        if len(text) > 100:
            cut = chunk.rfind(" ")
            if cut > 40:
                chunk = text[:cut]
        try:
            pdf.multi_cell(width, line_h, chunk)
        except Exception:
            chunk = chunk.encode("gbk", errors="ignore").decode("gbk", errors="ignore")
            if chunk:
                pdf.multi_cell(width, line_h, chunk)
        text = text[len(chunk) :].lstrip()


def _export_pdf_fpdf(md_path: Path, out_path: Path) -> None:
    from fpdf import FPDF

    font_path = _find_windows_font()
    if not font_path:
        raise RuntimeError("未找到 Windows 中文字体（msyh/simhei/simsun），无法生成 PDF")

    text = _strip_frontmatter(md_path.read_text(encoding="utf-8"))

    pdf = FPDF(format="A4")
    pdf.set_margins(20, 15, 20)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.add_font("zh", "", font_path)

    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            pdf.ln(4)
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            title = line.lstrip("#").strip()
            size = max(11, 16 - level)
            _pdf_write_line(pdf, title, line_h=8, font_size=size)
            continue
        _pdf_write_line(pdf, line)

    pdf.output(str(out_path))


def _export_pdf_pandoc(md_path: Path, out_path: Path) -> bool:
    pandoc = shutil.which("pandoc")
    if not pandoc:
        return False
    cmd = [pandoc, str(md_path), "-o", str(out_path)]
    # wkhtmltopdf / xelatex 若存在则优先
    if shutil.which("wkhtmltopdf"):
        cmd.extend(["--pdf-engine=wkhtmltopdf"])
    elif shutil.which("xelatex"):
        cmd.extend(["--pdf-engine=xelatex", "-V", "CJKmainfont=Microsoft YaHei"])
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        return out_path.is_file() and out_path.stat().st_size > 0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False


def export_md_to_pdf(md_path: str | Path) -> Path:
    """将 Wiki Markdown 导出为 PDF，返回临时 PDF 路径。"""
    src = Path(md_path).resolve()
    wiki = Path(WIKI_ROOT).resolve()
    if not str(src).startswith(str(wiki)):
        raise ValueError("仅允许导出 Wiki 目录下的文件")
    if not src.is_file() or src.suffix.lower() != ".md":
        raise ValueError("仅支持 .md 文件导出 PDF")

    out = Path(tempfile.gettempdir()) / f"ca_wiki_{src.stem}.pdf"
    if _export_pdf_pandoc(src, out):
        return out
    _export_pdf_fpdf(src, out)
    if not out.is_file():
        raise RuntimeError("PDF 生成失败")
    return out


def _norm_query(q: str) -> str:
    q = q.strip().replace("\\", "/")
    if q.lower().startswith("wiki/"):
        q = q[5:]
    return q.removesuffix(".md").strip()


def find_wiki_md(query: str, wiki_root: str = WIKI_ROOT) -> list[Path]:
    """按相对路径 / 文件名 / 无后缀名匹配 Wiki 内 .md 文件。"""
    root = Path(wiki_root)
    if not root.is_dir():
        return []

    q = _norm_query(query)
    if not q:
        return []

    all_md = sorted(root.rglob("*.md"))
    exact: list[Path] = []
    stem_hits: list[Path] = []
    partial: list[Path] = []

    for path in all_md:
        rel = path.relative_to(root).as_posix()
        rel_no_ext = rel[:-3] if rel.endswith(".md") else rel
        name = path.name
        stem = path.stem

        if q == rel or q == rel_no_ext or q == name or q == stem:
            exact.append(path)
            continue
        if stem == q or name == f"{q}.md":
            stem_hits.append(path)
            continue
        if rel_no_ext.endswith(q) or q in rel_no_ext:
            partial.append(path)

    if exact:
        return exact
    if len(stem_hits) == 1:
        return stem_hits
    if stem_hits:
        return stem_hits
    if len(partial) == 1:
        return partial
    return partial
