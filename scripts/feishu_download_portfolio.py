#!/usr/bin/env python3
"""
从飞书云文档下载「持仓」表格，覆盖根目录 持仓.xlsx。

配置（.env 三选一，推荐 URL）：
  FEISHU_PORTFOLIO_URL=https://xxx.feishu.cn/sheets/shtxxxx   # 电子表格/多维表格链接
  FEISHU_PORTFOLIO_TOKEN=shtxxxx + FEISHU_PORTFOLIO_TYPE=sheet
  FEISHU_PORTFOLIO_NAME=持仓                                   # 按名称在云盘搜索

可选：
  FEISHU_PORTFOLIO_FOLDER_TOKEN=fldxxxx  # 搜索范围，默认根目录

用法:
  python feishu_download_portfolio.py
  python feishu_download_portfolio.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bilibili.env import ROOT
from feishu.drive import download_portfolio_xlsx
from feishu.env import FeishuConfig, load_portfolio_cloud_config

XLSX_PATH = os.path.join(ROOT, "持仓.xlsx")


def main() -> None:
    ap = argparse.ArgumentParser(description="从飞书云文档下载持仓.xlsx")
    ap.add_argument("--dry-run", action="store_true", help="只检查配置，不下载")
    args = ap.parse_args()

    cfg = FeishuConfig.load()
    pcfg = load_portfolio_cloud_config()

    if not pcfg.enabled:
        print("跳过飞书持仓下载：未配置 FEISHU_PORTFOLIO_URL / TOKEN / NAME")
        print("  （若 .env 里仍是 .env.example 的 xxx.feishu.cn / shtxxxx 占位符，请改为真实链接）")
        return

    if not cfg.app_id or not cfg.app_secret:
        raise SystemExit("需要 FEISHU_APP_ID 与 FEISHU_APP_SECRET")

    if args.dry_run:
        print("[DRY-RUN] 将从飞书下载持仓并覆盖:")
        print(f"  {XLSX_PATH}")
        if pcfg.url:
            print(f"  来源 URL: {pcfg.url}")
        elif pcfg.token:
            print(f"  来源 token: {pcfg.token[:8]}… type={pcfg.doc_type}")
        elif pcfg.name:
            print(f"  来源名称: {pcfg.name}（云盘搜索）")
        return

    try:
        token, dtype = download_portfolio_xlsx(
        cfg.app_id,
        cfg.app_secret,
        XLSX_PATH,
        cloud_url=pcfg.url,
        doc_token=pcfg.token,
        doc_type=pcfg.doc_type,
        file_name=pcfg.name,
        folder_token=pcfg.folder_token,
        )
    except RuntimeError as e:
        if "file token invalid" in str(e) or "1069914" in str(e):
            raise SystemExit(
                "飞书持仓 token 无效。\n"
                "请检查 .env 中 FEISHU_PORTFOLIO_URL 是否为浏览器打开表格时的真实链接\n"
                "（形如 https://xxx.feishu.cn/sheets/shtXXXXXXXX，勿用 .env.example 占位符）。\n"
                "或配置 FEISHU_PORTFOLIO_NAME=持仓 让程序在云盘按名称搜索。"
            ) from e
        raise
    print(f"已下载持仓.xlsx ← 飞书 {dtype}/{token[:12]}...")
    from xlsx_utils import format_portfolio_xlsx

    format_portfolio_xlsx(XLSX_PATH)


if __name__ == "__main__":
    main()
