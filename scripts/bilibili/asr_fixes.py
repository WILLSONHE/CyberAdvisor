"""视频字幕 ASR 常见误识别校正（财经/半导体/博主口癖）。"""
from __future__ import annotations

import re

# 顺序敏感：长串优先
ASR_REPLACEMENTS: list[tuple[str, str]] = [
    ("MICC", "MLCC"),
    ("MISCC", "MLCC"),
    ("MACC", "MLCC"),
    ("MIACC", "MLCC"),
    ("Mcc", "MLCC"),
    ("mlcc", "MLCC"),
    ("robrobin", "Rubin"),
    ("RUBIN", "Rubin"),
    ("ruby", "Rubin"),
    ("VR200", "VR200"),
    ("GB300", "GB300"),
    ("GB200", "GB200"),
    ("大魔", "大摩"),
    ("摩根斯坦利", "摩根士丹利"),
    ("润剑", "润建"),
    ("润剑股份", "润建股份"),
    ("长兴", "长鑫"),
    ("长形", "长鑫"),
    ("长新", "长鑫"),
    ("长鑫存储", "长鑫存储"),
    ("工业妇联", "工业富联"),
    ("燕东微", "燕东微"),
    ("春田", "村田"),
    ("云种", "昀冢"),
    ("云种科技", "昀冢科技"),
    ("力合心逆", "力芯微"),
    ("力核心", "力芯微"),
    ("结美", "洁美"),
    ("杰美", "洁美"),
    ("新源V", "芯源微"),
    ("新源微", "芯源微"),
    ("科马", "珂玛"),
    ("河马科技", "珂玛科技"),
    ("铺床紧密", "富创精密"),
    ("茂来", "茂莱"),
    ("冒蓝", "茂莱"),
    ("macroied", "MicroLED"),
    ("moied", "MicroLED"),
    ("Macied", "MicroLED"),
    ("echoled", "MicroLED"),
    ("普源金电", "普源精电"),
    ("联谊仪器", "联芸科技"),
    ("于太微", "裕太微"),
    ("新环科技", "芯环科技"),
    ("六福", "六氟"),
    ("脑灯", "老登"),
    ("老登股", "老登股"),
    ("斗神", "豆神"),
    ("碧浪", "B浪"),
    ("C浪", "C浪"),
    ("A浪", "A浪"),
    ("钟才文", "钟才文"),
    ("韬定律", "韬定律"),
    ("Token", "Token"),
    ("CPO", "CPO"),
    ("HVDC", "HVDC"),
    ("ABF", "ABF"),
    ("HDI", "HDI"),
    ("英伟达", "英伟达"),
    ("英特尔", "英特尔"),
    ("沃什", "沃什"),
    ("麻辣粉", "MLF"),
    ("中证1000", "中证1000"),
    ("幺蛾子", "幺蛾子"),
    ("霍尔木兹", "霍尔木兹"),
]

# 明显非财经字幕（错配检测）
MISMATCH_MARKERS = re.compile(
    r"Faker|英雄联盟|Gen\.G|T1|兰博|369|脱口秀|哥斯拉|三体|"
    r"Offer|校招|总包|惠普|音响|靶场|M249|巴雷特|"
    r"诺贝尔|引力波|量子计算|永恩|"
    r"监狱|露丝|凯蒂|贾士官|"
    r"小米|试驾|南京大学|五菱|星驰|"
    r"麦当劳|帕尼尼|板烧鸡腿|腌料|"
    r"兴趣爱好|尤克里里|架子鼓"
)


def apply_asr_fixes(text: str) -> tuple[str, list[str]]:
    """返回 (修正后文本, 变更记录)。"""
    changes: list[str] = []
    out = text
    for old, new in ASR_REPLACEMENTS:
        if old in out and old != new:
            count = out.count(old)
            out = out.replace(old, new)
            changes.append(f"{old}→{new}×{count}")
    return out, changes


def looks_like_mismatch(body: str, title: str = "") -> bool:
    if not body or len(body.strip()) < 30:
        return True
    if re.fullmatch(r"(音乐[♪\s]*)+", body.strip()):
        return True
    if MISMATCH_MARKERS.search(body):
        # 标题含投资关键词但正文像段子
        invest_kw = re.search(r"复盘|产业链|大盘|华为|K线|房地产|充电|抄底|牛市", title)
        if invest_kw:
            return True
    return False
