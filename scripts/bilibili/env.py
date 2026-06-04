"""从 .env / .env.example 加载 B 站配置（项目根目录）。"""
from __future__ import annotations

import os
from dataclasses import dataclass


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _parse_env_file(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            if raw.startswith("#"):
                raw = raw.lstrip("#").strip()
                if not raw or raw.startswith("可选") or raw.startswith("获取"):
                    continue
            if "=" not in raw:
                continue
            key, val = raw.split("=", 1)
            key, val = key.strip(), val.strip()
            if key and val:
                out[key] = val
    return out


def load_config() -> dict[str, str]:
    env_path = os.path.join(ROOT, ".env")
    example_path = os.path.join(ROOT, ".env.example")
    cfg = _parse_env_file(example_path)
    cfg.update(_parse_env_file(env_path))  # .env 优先
    return cfg


@dataclass
class BiliConfig:
    sessdata: str
    bili_jct: str
    dede_user_id: str
    uid: str
    source: str

    @classmethod
    def load(cls) -> "BiliConfig":
        cfg = load_config()
        sess = cfg.get("BILIBILI_SESSDATA", "")
        jct = cfg.get("BILIBILI_BILI_JCT") or cfg.get("bili_jct", "")
        uid_user = cfg.get("BILIBILI_DEDEUSERID") or cfg.get("DedeUserID", "")
        uid = cfg.get("BLOGGER_UID", "")
        source = ".env" if os.path.isfile(os.path.join(ROOT, ".env")) else ".env.example"

        missing = []
        if not sess:
            missing.append("BILIBILI_SESSDATA")
        if not jct:
            missing.append("bili_jct")
        if not uid_user:
            missing.append("DedeUserID")
        if not uid:
            missing.append("BLOGGER_UID")
        if missing:
            raise SystemExit(
                f"缺少配置: {', '.join(missing)}\n"
                f"请在项目根目录创建 .env（可参考 .env.example），勿将真实 Cookie 提交 git。"
            )
        return cls(sessdata=sess, bili_jct=jct, dede_user_id=uid_user, uid=uid, source=source)

    def cookie_header(self) -> str:
        return (
            f"SESSDATA={self.sessdata}; "
            f"bili_jct={self.bili_jct}; "
            f"DedeUserID={self.dede_user_id}"
        )
