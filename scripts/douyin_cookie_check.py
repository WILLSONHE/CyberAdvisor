#!/usr/bin/env python3
"""检查抖音 Cookie 是否可用（列表 API 探测）。"""
from __future__ import annotations

import sys

from douyin.client import DouyinClient
from douyin.env import DouyinConfig


def main() -> int:
    cfg = DouyinConfig.load()
    print(f"博主: {cfg.creator}")
    print(f"sec_uid: {cfg.sec_uid[:24]}…")
    print(f"来源: {cfg.source}")

    if cfg.source == "missing":
        print("\n[FAIL] 未配置 Cookie。")
        print("请在 .env 填写 DOUYIN_COOKIE 或 DOUYIN_TTWID 等（见 .env.example）。")
        return 1

    ck = cfg.cookie
    for key in ("ttwid", "sessionid", "s_v_web_id"):
        has = f"{key}=" in ck or f"{key}=" in ck.lower()
        print(f"  {key}: {'有' if has else '无 ← 列表 API 常需要'}")

    try:
        client = DouyinClient(sec_uid=cfg.sec_uid, cookie=cfg.cookie)
        n = 0
        first_title = ""
        for v in client.iter_videos(page_size=5):
            n += 1
            if not first_title:
                first_title = v.get("title") or ""
            if n >= 3:
                break
        client.close()
    except RuntimeError as e:
        print(f"\n[FAIL] {e}")
        return 1
    except Exception as e:
        err = str(e)
        if "SSL" in err or "Connection" in err or "EOF" in err:
            print(f"\n[FAIL] 网络/SSL 连接失败（Cookie 本身可能没问题）: {e}")
            print("请检查：代理/VPN/防火墙；关闭后重试 douyin_cookie_check.py")
        else:
            print(f"\n[FAIL] API 探测失败: {e}")
            print("建议：登录 douyin.com 后，从 Application 复制 ttwid + sessionid 到 .env")
        return 1

    if n == 0:
        print("\n[WARN] API 返回 0 条。Cookie 可能过期或未登录。")
        return 1

    print(f"\n[OK] 可拉取作品列表（样本 {n} 条，首条: {first_title[:40]}）")
    if "sessionid=" not in ck and "sessionid=" not in ck.lower():
        print("[提示] 未检测到 sessionid，未登录时通常只能拿到近 ~20 条。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
