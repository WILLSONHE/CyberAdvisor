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
        return

    if not cfg.app_id or not cfg.app_secret:
        raise SystemExit("需要 FEISHU_APP_ID 与 FEISHU_APP_SECRET")

    if args.dry_run:
        print("[DRY-RUN] 将从飞书下载持仓并覆盖:")
        print(f"  {XLSX_PATH}")
        if pcfg.url:
            print(f"  来源 URL: {pcfg.url}")
        elif pcfg.token:
            print(f"  来源 token: {pcfg.token} type={pcfg.doc_type}")
        else:
            print(f"  来源名称: {pcfg.name}")
        return

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
    print(f"已下载持仓.xlsx ← 飞书 {dtype}/{token[:12]}...")


if __name__ == "__main__":
    main()
