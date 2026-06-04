"""视频讲稿格式化：补标点 + 分段。"""
from __future__ import annotations

import re

# 目标：约每 16–22 字一个标点（偏密，便于阅读）
_TARGET_PUNCT_DENSITY = 0.055
_MIN_PUNCT_DENSITY = 0.048

# 口语句末 → 句号
_ORAL_SENTENCE_END = re.compile(
    r"(好吧|对不对|是不是|对吧|没有问题|没问题|谢谢大家|"
    r"今天就到这里|今天视频就到这里|今天也就到这里|"
    r"基本上就是这样|基本上就是这个样子|就这个样子|"
    r"不用太过于担心|不用太担心|不用过多担心|"
    r"我是这么看的|我是这么想的|这是我的一个想法|"
    r"我是这么觉得的|大概如此|大致如此|"
    r"问题也不大|没有什么问题|没啥问题|"
    r"不用担心|不用看|不用慌|"
    r"就完事了|就可以了|就行了|就够了|"
    r"蛮好的|挺好的|还可以|还行)"
    r"(?![。！？；，、])"
)

# 新句开头 → 前加句号（排除「首先/其次/最后/第三」等序数，避免打断列举）
_NEW_SENTENCE = (
    "所以", "但是", "因此", "不过", "然后", "另外", "包括说", "那么", "而且",
    "同时", "总之", "综上", "与此同时", "另一方面",
    "整体来讲", "目前来讲", "从现在来看", "接下来",
    "哈喽大家好", "哈喽大家",
)

# 从句连接 → 前加逗号
_CLAUSE_COMMA = (
    "但是", "所以", "因此", "不过", "然后", "而且", "如果", "因为", "虽然",
    "尽管", "同时", "另外", "包括", "比如", "例如", "也就是说", "换句话说",
    "尤其是", "那么", "就", "也", "还", "又", "却", "并", "以及", "或者",
    "即使", "无论", "只要", "只有", "除非", "由于", "为了", "至于",
    "对于", "关于", "根据", "按照", "通过", "经过", "随着", "随着",
)

# 话题/列举 → 前加逗号
_TOPIC_COMMA = (
    "第一", "第二", "第三", "第四", "第五",
    "一方面", "另一方面", "一个是", "另一个是",
    "第一个", "第二个", "第三个",
)

# 段落主题切换
_PARA_MARKERS = [
    r"哈喽大家好",
    r"哈喽大家",
    r"那么(?:今天|我们|整体|接下来|从|先)",
    r"所以(?:今天|整体|你们|我们|从|我)",
    r"第一(?:个)?(?:逻辑|点|步|类|层|部分|)",
    r"第二(?:个)?(?:逻辑|点|步|类|层|部分|)",
    r"第三(?:个)?(?:逻辑|点|步|类|层|部分|)",
    r"第四(?:个)?(?:逻辑|点|步|类|层|部分|)",
    r"最后(?:来说|总结一下|一个点|部分|)",
    r"## ",
]

_BREAK_CHARS = "的了了吗吧啊呢嘛么呀嘛哈"

_NOT_BEFORE_PUNCT = re.compile(r'[。！？；，、：""''（(\[【]$')  # noqa: W605


def punctuation_density(text: str) -> float:
    if not text:
        return 0.0
    punct = len(re.findall(r"[。！？；，、：]", text))
    return punct / len(text)


def _normalize_raw(text: str) -> str:
    t = re.sub(r"\s+", "", text)
    t = re.sub(r"音乐[♪\s]*", "", t)
    return t.strip()


def _apply_before_words(
    text: str,
    words: tuple[str, ...],
    punct: str,
    min_len: int,
    max_len: int = 120,
) -> str:
    for word in words:
        text = re.sub(
            rf"([^。！？；，、]{{{min_len},{max_len}}})(?<![，、{punct}])(?={re.escape(word)})",
            rf"\1{punct}",
            text,
        )
    return text


def _rhythm_punctuation(text: str, gap: int = 28) -> str:
    """在长无标点片段中，于口语停顿字后插入逗号。"""
    out: list[str] = []
    buf = ""
    since = 0
    for ch in text:
        buf += ch
        if ch in "。！？；，、":
            out.append(buf)
            buf = ""
            since = 0
            continue
        since += 1
        if since < gap:
            continue
        # 回溯找停顿字
        cut = -1
        for j in range(len(buf) - 1, max(0, len(buf) - 14), -1):
            if buf[j] in _BREAK_CHARS:
                cut = j + 1
                break
        if cut > 0:
            out.append(buf[:cut] + "，")
            buf = buf[cut:]
            since = len(buf)
        elif since >= gap + 12:
            out.append(buf + "，")
            buf = ""
            since = 0
    if buf:
        out.append(buf)
    return "".join(out)


def _sentence_period_pass(text: str, min_len: int = 10) -> str:
    """在新句词前加句号（较短阈值）。"""
    for word in _NEW_SENTENCE:
        pattern = rf"(?<![。！？；，、])(?<=\S)(?={re.escape(word)})"
        parts: list[str] = []
        last = 0
        for m in re.finditer(pattern, text):
            pos = m.start()
            segment = text[last:pos]
            if len(segment) >= min_len and not _NOT_BEFORE_PUNCT.search(segment):
                parts.append(segment + "。")
            else:
                parts.append(segment)
            last = pos
        if parts:
            parts.append(text[last:])
            text = "".join(parts)
    return text


def insert_punctuation(text: str, *, force: bool = False) -> str:
    """为连续中文插入逗号、句号（多轮直到达到目标密度）。"""
    if not text:
        return ""
    if not force and punctuation_density(text) >= _TARGET_PUNCT_DENSITY:
        return text

    t = text

    # 1. 口语句末
    t = _ORAL_SENTENCE_END.sub(r"\1。", t)

    # 2. 列举/话题词前逗号
    t = _apply_before_words(t, _TOPIC_COMMA, "，", min_len=4)

    # 3. 连接词前逗号（较短前段）
    t = _apply_before_words(t, _CLAUSE_COMMA, "，", min_len=4)

    # 4. 新句前句号
    t = _sentence_period_pass(t, min_len=8)

    # 5. 问句
    t = re.sub(r"([^。！？]{4,50}吗)(?=[，。！？；]|$)", r"\1？", t)
    t = re.sub(r"([^。！？]{4,40}呢)(?=[，。！？；]|$)", r"\1？", t)

    # 6. 节奏补逗号
    for gap in (22, 16, 12):
        if punctuation_density(t) < _MIN_PUNCT_DENSITY:
            t = _rhythm_punctuation(t, gap=gap)

    # 7. 仍不足：在「的/了/吗/吧」后补逗号
    if punctuation_density(t) < _MIN_PUNCT_DENSITY:
        t = re.sub(
            r"([^。！？；，、]{6,22}[的了吗吧])(?![。！？；，、])",
            r"\1，",
            t,
        )

    # 8. 仍不足：短段末尾加句号
    if punctuation_density(t) < _MIN_PUNCT_DENSITY:
        t = re.sub(
            r"([^。！？；，、]{35,80})(?=所以|但是|那么|然后|如果|因为|我们|你们|今天)",
            r"\1。",
            t,
        )

    t = re.sub(r"[，、]{2,}", "，", t)
    t = re.sub(r"。{2,}", "。", t)
    t = re.sub(r"，。", "。", t)
    t = re.sub(r"。，", "，", t)
    return t


def split_paragraphs(text: str, max_para_chars: int = 380) -> str:
    """按语义标记与句号分段。"""
    if not text:
        return ""
    t = text
    for m in _PARA_MARKERS:
        t = re.sub(f"({m})", r"\n\n\1", t)

    paras: list[str] = []
    for block in re.split(r"\n\n+", t):
        block = block.strip()
        if not block:
            continue
        if len(block) <= max_para_chars:
            paras.append(block)
            continue
        parts = re.split(r"(?<=[。！？；])", block)
        buf = ""
        for p in parts:
            if not p:
                continue
            if len(buf) + len(p) > max_para_chars and buf:
                paras.append(buf.strip())
                buf = p
            else:
                buf += p
        if buf.strip():
            paras.append(buf.strip())
    return "\n\n".join(paras)


def cleanup_punctuation_artifacts(text: str) -> str:
    """移除明显误插标点，保留高密度。"""
    # 连接词后误加句号（保留逗号）
    for w in ("那么", "但是", "所以", "包括说", "不过", "因此", "如果", "因为"):
        text = text.replace(f"{w}。", w)
    text = re.sub(r"([但而且让说看听把真])(。)(?=\S)", r"\1", text)
    text = re.sub(r"我。(?=目前|觉得|认为|们)", "我", text)
    text = text.replace("没。那么", "没那么，那么")
    text = text.replace("你，如果", "你如果")
    text = re.sub(r"什么？(?=事)", "什么", text)
    text = text.replace("这，就是", "这就是")
    text = text.replace("也，就是", "也就是")
    text = re.sub(r"是5月的\s*\n+\s*最后", "是5月的最后", text)
    text = re.sub(r"月的\s*\n+\s*最后(?!一个)", "月的最后", text)
    text = re.sub(r"搞得。(?=大家|我们|你们|人)", "搞得，", text)
    text = re.sub(r"给。(?=你们|我们)", "给", text)
    text = re.sub(r"只需要。(?=我|你|他)", "只需要", text)
    text = re.sub(r"那么。(?=今天|我们|他|她|它|A|这)", "那么", text)
    # 数字+点 误断
    text = re.sub(r"(\d)，(点|万亿|万|%)", r"\1\2", text)
    text = re.sub(r"，{2,}", "，", text)
    text = re.sub(r"。{2,}", "。", text)
    text = re.sub(r"，。", "。", text)
    text = re.sub(r"。，", "，", text)
    return text


def re_punctuate(text: str) -> str:
    """去掉已有标点，重新补标点并分段。"""
    plain = re.sub(r"[。！？；，、：""''…]", "", _normalize_raw(text))
    return format_transcript(plain, force_punctuate=True)


def format_transcript(raw: str, *, force_punctuate: bool = False) -> str:
    t = _normalize_raw(raw)
    if not t:
        return ""
    t = insert_punctuation(t, force=force_punctuate)
    t = split_paragraphs(t)
    return cleanup_punctuation_artifacts(t).strip()


def needs_punctuation(text: str) -> bool:
    plain = _normalize_raw(re.sub(r"\n+", "", text))
    if len(plain) < 80:
        return False
    return punctuation_density(plain) < _TARGET_PUNCT_DENSITY
