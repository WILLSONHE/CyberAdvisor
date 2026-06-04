#!/usr/bin/env python3
"""飞书 Bot 配置诊断。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from feishu.client import get_tenant_access_token
from feishu.env import FeishuConfig


def main() -> None:
    cfg = FeishuConfig.load()
    print("=== CyberAdvisor 飞书诊断 ===\n")

    print(f"APP_ID: {'已配置' if cfg.app_id else '缺失'}")
    print(f"APP_SECRET: {'已配置' if cfg.app_secret else '缺失'}")
    print(f"VERIFICATION_TOKEN: {'已配置' if cfg.verification_token else '缺失'}")
    print(f"WEBHOOK_URL: {'已配置' if cfg.webhook_enabled else '未配置（推送可选）'}")
    print(f"BOT_PORT: {cfg.bot_port}\n")

    if not cfg.bot_enabled:
        print("[FAIL] Bot 配置不完整")
        return

    try:
        token = get_tenant_access_token(cfg.app_id, cfg.app_secret)
        print(f"[OK] tenant_access_token 获取成功（长度 {len(token)}）")
    except Exception as e:
        print(f"[FAIL] tenant_access_token 失败: {e}")
        return

    print("\n--- 若 ping 无反应，请逐项检查 ---")
    print("1. feishu_bot.bat 窗口是否仍在运行？")
    print("2. ngrok 是否仍在运行？域名是否与飞书 Request URL 一致？")
    print("3. 飞书 → 事件订阅 → Request URL 保存是否成功（无红色报错）？")
    print("4. 是否已订阅 im.message.receive_v1 ？")
    print("5. 权限是否包含 im:message、im:message:send_as_bot 并已启用？")
    print("6. 应用是否已发布，或你已加入「测试企业和人员」？")
    print("7. 私聊：搜机器人名单聊发 ping")
    print("8. 群聊：先把「应用机器人」拉进群，再 @机器人 ping（不是群 Webhook 机器人）")
    print("9. 群聊权限：im:message.group_at_msg:readonly（@ 机器人消息）")
    print("10. 私聊权限：im:message.p2p_msg:readonly")
    print("11. 改权限后必须「创建版本并发布」")
    print("\n发 ping 时，feishu_bot 窗口应出现「收到 POST」「事件: im.message.receive_v1」")
    print("若无任何 POST 日志 → 飞书事件没到本机（URL/ngrok/订阅问题）")


if __name__ == "__main__":
    main()
