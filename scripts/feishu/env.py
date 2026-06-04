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
        )

    @property
    def webhook_enabled(self) -> bool:
        return bool(self.webhook_url)

    @property
    def bot_enabled(self) -> bool:
        return bool(self.app_id and self.app_secret and self.verification_token)
