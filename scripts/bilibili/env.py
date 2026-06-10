"""从项目根目录 .env 加载配置（.env.example 仅作 GitHub 模板，运行时不用）。"""
from __future__ import annotations

import os
from dataclasses import dataclass


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENV_PATH = os.path.join(ROOT, ".env")


def _parse_env_file(path: str) -> dict[str, str]:
    out: dict[str, str] = {}
    if not os.path.isfile(path):
        return out
    last_err: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, encoding=encoding) as f:
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
        except UnicodeDecodeError as e:
            last_err = e
            out = {}
    if last_err:
        raise SystemExit(f"无法读取 {path}（编码错误），请保存为 UTF-8：{last_err}") from last_err
    return out


def load_config() -> dict[str, str]:
    return _parse_env_file(ENV_PATH)


def apply_config_to_environ() -> dict[str, str]:
    """将 .env 写入 os.environ（不覆盖已有变量）。"""
    cfg = load_config()
    for key, val in cfg.items():
        if key and key not in os.environ:
            os.environ[key] = val
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
        if not os.path.isfile(ENV_PATH):
            raise SystemExit(
                "未找到项目根目录 .env。\n"
                "请复制 .env.example 为 .env 并填写配置（.env.example 仅推 GitHub 用，程序不读取）。"
            )
        cfg = load_config()
        sess = cfg.get("BILIBILI_SESSDATA", "")
        jct = cfg.get("BILIBILI_BILI_JCT") or cfg.get("bili_jct", "")
        uid_user = cfg.get("BILIBILI_DEDEUSERID") or cfg.get("DedeUserID", "")
        uid = cfg.get("UP_UID") or cfg.get("BLOGGER_UID", "")

        missing = []
        if not sess:
            missing.append("BILIBILI_SESSDATA")
        if not jct:
            missing.append("bili_jct")
        if not uid_user:
            missing.append("DedeUserID")
        if not uid:
            missing.append("UP_UID")
        if missing:
            raise SystemExit(
                f"缺少配置: {', '.join(missing)}\n"
                f"请在 .env 中填写（可参考 .env.example），勿将真实 Cookie 提交 git。"
            )
        return cls(sessdata=sess, bili_jct=jct, dede_user_id=uid_user, uid=uid, source=".env")

    def cookie_header(self) -> str:
        return (
            f"SESSDATA={self.sessdata}; "
            f"bili_jct={self.bili_jct}; "
            f"DedeUserID={self.dede_user_id}"
        )
