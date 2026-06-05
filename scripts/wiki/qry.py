"""qry {问题} — Wiki 关键词检索（轻量；深度问答仍走 Cursor AI）。"""
from __future__ import annotations

import re
from pathlib import Path

from wiki.common import WIKI, iter_wiki_md, read_text


def _query_terms(query: str) -> list[str]:
    q = query.strip()
    terms = [q]
    # 去掉常见问句词后拆分
    cleaned = re.sub(r"[？?吗呢吧的了吗什么怎么如何为什么]", " ", q)
    parts = [p for p in cleaned.split() if len(p) >= 2]
    for p in parts:
        if p not in terms:
            terms.append(p)
    return terms


def _score_line(line: str, terms: list[str]) -> int:
    score = 0
    for t in terms:
        if t in line:
            score += 2 if len(t) >= 4 else 1
    return score


def search_wiki(query: str, *, max_files: int = 6, max_lines_per_file: int = 3) -> str:
    terms = _query_terms(query)
    if not terms or not terms[0]:
        return "（空问题）"

    hits: list[tuple[int, Path, list[str]]] = []
    wiki_root = Path(WIKI)

    for p in iter_wiki_md():
        if p.name == "log.md":
            continue
        try:
            lines = read_text(p).splitlines()
        except OSError:
            continue
        snippets: list[str] = []
        score = 0
        for line in lines:
            if line.strip().startswith("---"):
                continue
            s = _score_line(line, terms)
            if s <= 0:
                continue
            score += s
            if len(snippets) < max_lines_per_file and len(line.strip()) > 6:
                snippets.append(line.strip()[:160])
        if score > 0:
            hits.append((score, p, snippets))

    hits.sort(key=lambda x: x[0], reverse=True)
    top = hits[:max_files]

    out = [f"# qry：{query.strip()}", "", "> 轻量 Wiki 检索；综合解读请在 Cursor 说 qry（AI skill）。", ""]
    if not top:
        out.append(f"（未在 Wiki 中匹配到「{query.strip()}」，可换关键词或走 Cursor 深度 qry）")
        return "\n".join(out)

    out.append(f"## 命中 {len(hits)} 页，展示前 {len(top)} 页")
    out.append("")
    for score, p, snippets in top:
        rel = p.relative_to(wiki_root)
        out.append(f"### Wiki/{rel}（相关度 {score}）")
        for sn in snippets:
            out.append(f"- {sn}")
        out.append("")

    return "\n".join(out).strip()
