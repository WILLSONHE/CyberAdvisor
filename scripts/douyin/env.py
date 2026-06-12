"""抖音抓取配置（.env + 可选 secrets/douyin.cookie）。"""
from __future__ import annotations

import os
from dataclasses import dataclass

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENV_PATH = os.path.join(ROOT, ".env")
COOKIE_PATH = os.path.join(ROOT, "secrets", "douyin.cookie")

DEFAULT_SEC_UID = (
    "MS4wLjABAAAA6DxQ0-ZPlNTXGX2vGEUfNisdS5ZassI0AwR_cPbOYy9kZKWbzq4tNFuT0EtFVarc"
)
DEFAULT_CREATOR = "钱加贝"


def _parse_env_file(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if not os.path.isfile(path):
        return out
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, encoding=encoding) as f:
                for line in f:
                    raw = line.strip()
                    if not raw or raw.startswith("#") or "=" not in raw:
                        continue
                    key, val = raw.split("=", 1)
                    key, val = key.strip(), val.strip()
                    if key and val:
                        out[key] = val
            return out
        except UnicodeDecodeError:
            continue
    return out


def _read_cookie_file() -> str:
    if not os.path.isfile(COOKIE_PATH):
        return ""
    with open(COOKIE_PATH, encoding="utf-8") as f:
        return f.read().strip()


def _build_cookie_from_parts(cfg: dict[str, str]) -> str:
    """从 Application 面板逐项复制的 Cookie 拼成请求头（类似 B 站 SESSDATA + bili_jct）。"""
    parts: list[str] = []
    mapping = [
        ("DOUYIN_TTWID", "ttwid"),
        ("DOUYIN_SESSIONID", "sessionid"),
        ("DOUYIN_S_V_WEB_ID", "s_v_web_id"),
        ("DOUYIN_PASSPORT_CSRF", "passport_csrf_token"),
        ("DOUYIN_ODIN_TT", "odin_tt"),
        ("DOUYIN_UIFID", "UIFID"),
    ]
    for env_key, cookie_name in mapping:
        val = cfg.get(env_key, "").strip()
        if val:
            parts.append(f"{cookie_name}={val}")
    extra = cfg.get("DOUYIN_COOKIE_EXTRA", "").strip()
    if extra:
        parts.append(extra.strip("; "))
    return "; ".join(parts)


@dataclass
class DouyinConfig:
    sec_uid: str
    creator: str
    cookie: str
    source: str

    @classmethod
    def load(cls) -> "DouyinConfig":
        cfg = _parse_env_file(ENV_PATH)
        sec_uid = (
            cfg.get("DOUYIN_SEC_UID")
            or cfg.get("TIKTOK_SEC_UID")
            or os.environ.get("DOUYIN_SEC_UID")
            or DEFAULT_SEC_UID
        )
        creator = cfg.get("DOUYIN_CREATOR") or cfg.get("TIKTOK_CREATOR") or DEFAULT_CREATOR
        cookie = (
            cfg.get("DOUYIN_COOKIE")
            or cfg.get("TIKTOK_COOKIE")
            or os.environ.get("DOUYIN_COOKIE")
            or _build_cookie_from_parts(cfg)
            or ""
        )
        source = ""
        if cfg.get("DOUYIN_COOKIE") or cfg.get("TIKTOK_COOKIE"):
            source = ".env DOUYIN_COOKIE"
        elif cfg.get("DOUYIN_TTWID") or cfg.get("DOUYIN_SESSIONID"):
            source = ".env 分项 Cookie"
        elif cookie:
            source = "env"
        if not cookie:
            cookie = _read_cookie_file()
            if cookie:
                source = "secrets/douyin.cookie"
        if not cookie:
            source = "missing"
        return cls(sec_uid=sec_uid, creator=creator, cookie=cookie, source=source)
