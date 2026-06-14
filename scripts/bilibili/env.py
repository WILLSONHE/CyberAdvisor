"""从项目根目录 .env 加载配置（.env.example 仅作 GitHub 模板，运行时不用）。"""
from __future__ import annotations

import dataclasses
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


@dataclass(frozen=True)
class BiliUp:
    mid: str
    name: str


def parse_bilibili_ups(raw: str) -> list[BiliUp]:
    """解析 BILIBILI_UPS=mid:name,mid:name"""
    ups: list[BiliUp] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            mid, name = part.split(":", 1)
        else:
            mid, name = part, ""
        mid = mid.strip()
        if mid:
            ups.append(BiliUp(mid=mid, name=name.strip()))
    return ups


@dataclass
class BiliConfig:
    sessdata: str
    bili_jct: str
    dede_user_id: str
    uid: str
    source: str
    ups: tuple[BiliUp, ...] = ()
    creator: str = ""

    @classmethod
    def load(cls, *, mid: str | None = None) -> "BiliConfig":
        if not os.path.isfile(ENV_PATH):
            raise SystemExit(
                "未找到项目根目录 .env。\n"
                "请复制 .env.example 为 .env 并填写配置（.env.example 仅推 GitHub 用，程序不读取）。"
            )
        cfg = load_config()
        sess = cfg.get("BILIBILI_SESSDATA", "")
        jct = cfg.get("BILIBILI_BILI_JCT") or cfg.get("bili_jct", "")
        uid_user = cfg.get("BILIBILI_DEDEUSERID") or cfg.get("DedeUserID", "")

        ups = parse_bilibili_ups(cfg.get("BILIBILI_UPS", ""))
        if not ups:
            legacy = cfg.get("UP_UID") or cfg.get("BLOGGER_UID", "")
            if legacy:
                ups = [BiliUp(mid=legacy, name=cfg.get("BILIBILI_UP_NAME", ""))]

        missing = []
        if not sess:
            missing.append("BILIBILI_SESSDATA")
        if not jct:
            missing.append("bili_jct")
        if not uid_user:
            missing.append("DedeUserID")
        if not ups:
            missing.append("BILIBILI_UPS 或 UP_UID")
        if missing:
            raise SystemExit(
                f"缺少配置: {', '.join(missing)}\n"
                f"请在 .env 中填写（可参考 .env.example），勿将真实 Cookie 提交 git。"
            )

        if mid:
            up = next((u for u in ups if u.mid == mid), None)
            if not up:
                known = ", ".join(u.mid for u in ups)
                raise SystemExit(f"未在 BILIBILI_UPS 中找到 mid={mid}（已配置: {known}）")
            active_mid, creator = up.mid, up.name
        else:
            active_mid, creator = ups[0].mid, ups[0].name

        return cls(
            sessdata=sess,
            bili_jct=jct,
            dede_user_id=uid_user,
            uid=active_mid,
            source=".env",
            ups=tuple(ups),
            creator=creator,
        )

    def with_up(self, up: BiliUp) -> "BiliConfig":
        return dataclasses.replace(self, uid=up.mid, creator=up.name)

    def iter_targets(self, mid: str | None = None) -> list[BiliUp]:
        if mid:
            matched = [u for u in self.ups if u.mid == mid]
            return matched or [BiliUp(mid=mid, name="")]
        return list(self.ups)

    def cookie_header(self) -> str:
        return (
            f"SESSDATA={self.sessdata}; "
            f"bili_jct={self.bili_jct}; "
            f"DedeUserID={self.dede_user_id}"
        )
