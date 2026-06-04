"""飞书推送：daily 流水线完成通知、测试消息。"""
from __future__ import annotations

import argparse
import glob
import os
import re
from datetime import datetime

from bilibili.env import ROOT
from feishu.commands import _extract_one_liner, _latest_sug_path
from feishu.env import FeishuConfig
from feishu.webhook import send_post, send_text


def _read_head(path: str, lines: int = 25) -> str:
    if not os.path.isfile(path):
        return "（暂无）"
    with open(path, encoding="utf-8") as f:
        return "".join(f.readline() for _ in range(lines)).strip()


def build_pipeline_summary() -> tuple[str, list[tuple[str, str]]]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = f"CyberAdvisor 每日流水线完成 {now}"

    sug_path = _latest_sug_path()
    one_liner = ""
    if sug_path:
        with open(sug_path, encoding="utf-8") as f:
            one_liner = _extract_one_liner(f.read())
    if not one_liner:
        one_liner = "（今日尚未生成 sug，请在 Cursor 说 sug）"

    pool_head = _read_head(os.path.join(ROOT, "Wiki", "数据", "博主标的池日报.md"), 18)
    pool_lines = [ln for ln in pool_head.splitlines() if ln.strip()][:8]
    pool_snip = "\n".join(pool_lines) if pool_lines else "（暂无标的池日报）"

    portfolio = _read_head(os.path.join(ROOT, "portfolio.md"), 12)

    text = (
        f"{title}\n\n"
        f"【今日一句话】\n{one_liner}\n\n"
        f"【持仓】\n{portfolio}\n\n"
        f"【标的池摘要】\n{pool_snip}\n\n"
        f"完整 sug → SugVault/\n"
        f"深度对话 → Cursor + finance-wiki skill"
    )

    post_lines: list[tuple[str, str]] = [
        ("text", f"完成时间：{now}"),
        ("text", f"今日一句话：{one_liner}"),
        ("text", "持仓见 portfolio.md；标的池见 Wiki/数据/博主标的池日报.md"),
        ("text", "下一步：Cursor 说 sug 生成完整交易策略"),
    ]
    return text, post_lines


def push_pipeline_done(cfg: FeishuConfig, *, dry_run: bool = False) -> bool:
    if not cfg.webhook_enabled:
        print("跳过飞书推送：未配置 FEISHU_WEBHOOK_URL")
        return False
    text, post_lines = build_pipeline_summary()
    if dry_run:
        print("=== [DRY-RUN] 飞书推送内容 ===")
        print(text)
        return True
    send_post(cfg.webhook_url, "CyberAdvisor 每日流水线", post_lines)
    print("已推送到飞书群（Webhook）")
    return True


def push_test(cfg: FeishuConfig) -> None:
    if not cfg.webhook_enabled:
        raise SystemExit("未配置 FEISHU_WEBHOOK_URL")
    send_text(cfg.webhook_url, "CyberAdvisor 飞书 Webhook 测试成功 ✅")


def main() -> None:
    ap = argparse.ArgumentParser(description="飞书 Webhook 推送")
    ap.add_argument("--pipeline-done", action="store_true", help="daily 流水线完成后推送摘要")
    ap.add_argument("--test", action="store_true", help="发送测试消息")
    ap.add_argument("--dry-run", action="store_true", help="只打印不发送")
    args = ap.parse_args()
    cfg = FeishuConfig.load()

    if args.test:
        if args.dry_run:
            print("[DRY-RUN] 将发送测试消息")
            return
        push_test(cfg)
        return

    if args.pipeline_done:
        push_pipeline_done(cfg, dry_run=args.dry_run)
        return

    ap.print_help()


if __name__ == "__main__":
    main()
