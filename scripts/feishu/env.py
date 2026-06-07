"""从项目根 .env 加载飞书配置。"""
from __future__ import annotations

import os
from dataclasses import dataclass

from bilibili.env import ROOT, load_config


@dataclass
class FeishuConfig:
    webhook_url: str
    app_id: str
    app_secret: str
    verification_token: str
    encrypt_key: str
    bot_port: int
    notify_chat_id: str

    @classmethod
    def load(cls) -> "FeishuConfig":
        cfg = load_config()
        port_raw = cfg.get("FEISHU_BOT_PORT", "8765")
        try:
            port = int(port_raw)
        except ValueError:
            port = 8765
        return cls(
            webhook_url=cfg.get("FEISHU_WEBHOOK_URL", "").strip(),
            app_id=cfg.get("FEISHU_APP_ID", "").strip(),
            app_secret=cfg.get("FEISHU_APP_SECRET", "").strip(),
            verification_token=cfg.get("FEISHU_VERIFICATION_TOKEN", "").strip(),
            encrypt_key=cfg.get("FEISHU_ENCRYPT_KEY", "").strip(),
            bot_port=port,
            notify_chat_id=cfg.get("FEISHU_NOTIFY_CHAT_ID", "").strip(),
        )

    @property
    def webhook_enabled(self) -> bool:
        return bool(self.webhook_url)

    @property
    def bot_enabled(self) -> bool:
        return bool(self.app_id and self.app_secret and self.verification_token)

    @property
    def notify_chat_enabled(self) -> bool:
        return bool(self.notify_chat_id and self.app_id and self.app_secret)


def _is_portfolio_placeholder(val: str) -> bool:
    s = val.strip().lower()
    if not s:
        return False
    markers = (
        "xxx.feishu.cn",
        "shtxxxx",
        "fldxxxx",
        "xxxxxxxx",
        "your-org/",
        "your-name/",
    )
    return any(m in s for m in markers)


def _clean_portfolio_value(val: str) -> str:
    val = val.strip()
    if not val or _is_portfolio_placeholder(val):
        return ""
    return val


@dataclass
class PortfolioCloudConfig:
    url: str
    token: str
    doc_type: str
    name: str
    folder_token: str

    @property
    def enabled(self) -> bool:
        return bool(self.url or (self.token and self.doc_type) or self.name)


def load_portfolio_cloud_config() -> PortfolioCloudConfig:
    cfg = load_config()
    url = _clean_portfolio_value(cfg.get("FEISHU_PORTFOLIO_URL", ""))
    token = _clean_portfolio_value(cfg.get("FEISHU_PORTFOLIO_TOKEN", ""))
    doc_type = cfg.get("FEISHU_PORTFOLIO_TYPE", "").strip()
    name = cfg.get("FEISHU_PORTFOLIO_NAME", "").strip()
    folder = _clean_portfolio_value(cfg.get("FEISHU_PORTFOLIO_FOLDER_TOKEN", ""))
    if not token:
        doc_type = ""
    return PortfolioCloudConfig(
        url=url,
        token=token,
        doc_type=doc_type,
        name=name,
        folder_token=folder,
    )
