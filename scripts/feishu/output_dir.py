"""飞书 Cloud Agent 产出目录（禁止写入项目仓库）。"""
from __future__ import annotations

import os
import tempfile


def resolve_feishu_output_dir() -> str:
    """
    解析 Agent 报告落盘目录：优先飞书/Lark 客户端 Temp，否则系统临时目录。
    可通过 FEISHU_AGENT_OUTPUT_DIR 覆盖。
    """
    explicit = (os.environ.get("FEISHU_AGENT_OUTPUT_DIR") or "").strip()
    if explicit:
        os.makedirs(explicit, exist_ok=True)
        return os.path.abspath(explicit)

    candidates: list[str] = []
    local = os.environ.get("LOCALAPPDATA") or ""
    appdata = os.environ.get("APPDATA") or ""
    tmp = os.environ.get("TEMP") or tempfile.gettempdir()

    for base_name in ("Feishu", "Lark", "LarkShell", "feishu", "lark"):
        for root in (local, appdata):
            if not root:
                continue
            base = os.path.join(root, base_name)
            if not os.path.isdir(base):
                continue
            for sub in ("Temp", "temp", "tmp", "Cache", "cache"):
                candidates.append(os.path.join(base, sub, "CyberAdvisor"))
            candidates.append(os.path.join(base, "CyberAdvisor"))

    candidates.extend(
        [
            os.path.join(tmp, "Feishu", "CyberAdvisor"),
            os.path.join(tmp, "Lark", "CyberAdvisor"),
            os.path.join(tmp, "CyberAdvisor", "feishu-agent"),
        ]
    )

    for path in candidates:
        if not path:
            continue
        parent = os.path.dirname(path)
        try:
            if os.path.isdir(parent) or parent == path:
                os.makedirs(path, exist_ok=True)
                return os.path.abspath(path)
        except OSError:
            continue

    fallback = os.path.join(tempfile.gettempdir(), "CyberAdvisor", "feishu-agent")
    os.makedirs(fallback, exist_ok=True)
    return os.path.abspath(fallback)
