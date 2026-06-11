#!/usr/bin/env python3
"""
飞书 Bot 本机服务入口。

用法（在 scripts/ 目录）:
  python feishu_bot.py

需配置 .env 中 FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_VERIFICATION_TOKEN，
并在飞书开放平台 → 事件订阅 → Request URL 指向本机公网地址：
  http://<你的域名或IP>:8765/feishu/event

本机关机后 Bot 不可用；推送仍可用 Webhook（若 daily 在别的机器跑）。

内容类指令（sug/持仓/标的池/trk/chk/qry/sim 等）只发 .md 附件，见 feishu/delivery.py。
帮助 / ping / agent 提交确认仍为短文本。
"""
from feishu.server import main

if __name__ == "__main__":
    main()
