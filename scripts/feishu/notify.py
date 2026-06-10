"""飞书推送：daily / sug / AI 模拟盘。"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime

from bilibili.env import ROOT
from feishu.client import send_file_to_chat, upload_im_file
from feishu.text_util import extract_one_liner
from feishu.env import FeishuConfig
from feishu.webhook import send_post, send_text
from portfolio_utils import latest_sug_path, load_holder_names

JOURNAL_PATH = os.path.join(ROOT, "Wiki", "数据", "AI模拟交易日志.md")
JOURNAL_NOTIFY_STATE = os.path.join(ROOT, "Wiki", "数据", "ai_sim_journal_notify.json")


def _read_head(path: str, lines: int = 25) -> str:
    if not os.path.isfile(path):
        return "（暂无）"
    with open(path, encoding="utf-8") as f:
        return "".join(f.readline() for _ in range(lines)).strip()


def build_pipeline_summary() -> tuple[str, list[tuple[str, str]]]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = f"CyberAdvisor 每日流水线完成 {now}"

    holders = load_holder_names()
    holder_line = ", ".join(holders) if holders else "（暂无）"

    one_liner = ""
    if holders:
        path = latest_sug_path(holders[0])
        if path:
            with open(path, encoding="utf-8") as f:
                one_liner = extract_one_liner(f.read())
    if not one_liner:
        one_liner = f"（今日尚未生成 sug，请在 Cursor 说 sug {{持有人}}，如 sug {holders[0] if holders else 'Wilson'}）"

    pool_head = _read_head(os.path.join(ROOT, "Wiki", "数据", "标的池日报.md"), 18)
    pool_lines = [ln for ln in pool_head.splitlines() if ln.strip()][:8]
    pool_snip = "\n".join(pool_lines) if pool_lines else "（暂无标的池日报）"

    text = (
        f"{title}\n\n"
        f"【持有人】\n{holder_line}\n\n"
        f"【今日一句话】\n{one_liner}\n\n"
        f"【标的池摘要】\n{pool_snip}\n\n"
        f"完整 sug → SugVault/YYYY-MM-DD_{{持有人}}_sug.md\n"
        f"深度对话 → Cursor + 项目 SKILL.md（sug {{持有人}}）"
    )

    post_lines: list[tuple[str, str]] = [
        ("text", f"完成时间：{now}"),
        ("text", f"持有人：{holder_line}"),
        ("text", f"今日一句话：{one_liner}"),
        ("text", "标的池见 Wiki/数据/标的池日报.md"),
        ("text", "下一步：飞书 `sug 全员 午盘` 读报告，或 `agent sug 全员 午盘` 生成（FEISHU_AUTO_SUG=1 则 daily 已自动）"),
    ]
    return text, post_lines


def build_sug_done_summary(holder: str, session: str | None = None) -> tuple[str, list[tuple[str, str]]]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    session_label = f" {session}" if session else ""
    path = latest_sug_path(holder, session)
    if not path:
        title = f"sug 完成通知 — {holder}{session_label}"
        one_liner = f"（未找到 {holder} 的 sug 报告文件）"
        fname = "—"
    else:
        with open(path, encoding="utf-8") as f:
            body = f.read()
        one_liner = extract_one_liner(body) or "（报告无「今日一句话」摘要）"
        fname = os.path.basename(path)
        title = f"sug 已完成 — {holder}{session_label}"

    text = (
        f"{title}\n"
        f"时间：{now}\n"
        f"文件：{fname}\n\n"
        f"【今日一句话】\n{one_liner}\n\n"
        f"完整报告 → SugVault/{fname}"
    )
    post_lines: list[tuple[str, str]] = [
        ("text", f"持有人：{holder}{session_label}"),
        ("text", f"时间：{now}"),
        ("text", f"今日一句话：{one_liner}"),
        ("text", f"文件：{fname}"),
    ]
    return text, post_lines


def _load_journal_offset() -> int:
    if not os.path.isfile(JOURNAL_NOTIFY_STATE):
        return 0
    try:
        with open(JOURNAL_NOTIFY_STATE, encoding="utf-8") as f:
            data = json.load(f)
        return int(data.get("offset", 0))
    except (OSError, ValueError, json.JSONDecodeError):
        return 0


def _save_journal_offset(offset: int) -> None:
    os.makedirs(os.path.dirname(JOURNAL_NOTIFY_STATE), exist_ok=True)
    with open(JOURNAL_NOTIFY_STATE, "w", encoding="utf-8") as f:
        json.dump({"offset": offset, "updated_at": datetime.now().isoformat(timespec="seconds")}, f, ensure_ascii=False)


def read_journal_delta(*, reset: bool = False) -> str:
    if not os.path.isfile(JOURNAL_PATH):
        return ""
    with open(JOURNAL_PATH, encoding="utf-8") as f:
        content = f.read()
    if reset:
        return content
    offset = _load_journal_offset()
    if offset > len(content):
        offset = 0
    return content[offset:]


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


def push_sug_done(
    cfg: FeishuConfig,
    *,
    holder: str = "",
    session: str | None = None,
    all_holders: bool = False,
    dry_run: bool = False,
) -> bool:
    if not cfg.webhook_enabled:
        print("跳过飞书推送：未配置 FEISHU_WEBHOOK_URL")
        return False
    holders = load_holder_names() if all_holders else [holder]
    if not holders or not holders[0]:
        raise SystemExit("需要 --holder 或 --all-holders")
    sent = False
    for h in holders:
        text, post_lines = build_sug_done_summary(h, session)
        if dry_run:
            print(f"=== [DRY-RUN] sug 推送 {h} ===")
            print(text)
            sent = True
            continue
        send_post(cfg.webhook_url, f"sug 完成 — {h}", post_lines)
        print(f"已推送 sug 完成通知：{h}")
        sent = True
    return sent


def push_ai_sim_journal(
    cfg: FeishuConfig,
    *,
    new_block: str = "",
    dry_run: bool = False,
) -> bool:
    """推送本次 tick 新增日志；并尝试发送完整 md 文件（需 FEISHU_NOTIFY_CHAT_ID + 应用凭证）。"""
    if not os.path.isfile(JOURNAL_PATH):
        print("跳过：无 AI 模拟交易日志")
        return False

    delta = new_block.strip() if new_block else read_journal_delta()
    if not delta.strip():
        print("跳过：无新增日志内容")
        return False

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = f"AI 模拟盘 tick {now}"
    preview = delta.strip()
    if len(preview) > 3500:
        preview = preview[:3500] + "\n…（截断，完整见附件或本地文件）"

    if cfg.webhook_enabled:
        if dry_run:
            print("=== [DRY-RUN] AI 模拟盘日志 ===")
            print(preview)
        else:
            send_post(
                cfg.webhook_url,
                title,
                [("text", f"时间：{now}\n\n{preview}")],
            )
            print("已推送 AI 模拟盘新增日志（Webhook）")
    elif not cfg.notify_chat_enabled:
        print("跳过飞书推送：未配置 FEISHU_WEBHOOK_URL")
        return False

    if cfg.notify_chat_enabled and not dry_run:
        try:
            file_key = upload_im_file(cfg.app_id, cfg.app_secret, JOURNAL_PATH, file_name="AI模拟交易日志.md")
            send_file_to_chat(cfg.app_id, cfg.app_secret, cfg.notify_chat_id, file_key)
            print("已发送 AI模拟交易日志.md（飞书文件）")
        except Exception as e:
            print(f"飞书文件发送失败（Webhook 已发新增内容）：{e}")
    elif not cfg.notify_chat_enabled and cfg.webhook_enabled:
        # Webhook 无法发文件；若日志较短再补一条
        if not dry_run and os.path.getsize(JOURNAL_PATH) < 6000:
            try:
                with open(JOURNAL_PATH, encoding="utf-8") as f:
                    full = f.read()
                send_text(cfg.webhook_url, f"【完整日志】\n{full[:7500]}")
            except Exception:
                pass

    if not dry_run:
        with open(JOURNAL_PATH, encoding="utf-8") as f:
            _save_journal_offset(len(f.read()))
    return True


def push_test(cfg: FeishuConfig) -> None:
    if not cfg.webhook_enabled:
        raise SystemExit("未配置 FEISHU_WEBHOOK_URL")
    send_text(cfg.webhook_url, "CyberAdvisor 飞书 Webhook 测试成功 ✅")


def main() -> None:
    ap = argparse.ArgumentParser(description="飞书 Webhook 推送")
    ap.add_argument("--pipeline-done", action="store_true", help="daily 流水线完成后推送摘要")
    ap.add_argument("--sug-done", action="store_true", help="sug 生成完成后推送通知")
    ap.add_argument("--holder", default="", help="sug 持有人")
    ap.add_argument("--session", default="", help="早盘|午盘")
    ap.add_argument("--all-holders", action="store_true", help="sug 全员完成后推送")
    ap.add_argument("--ai-sim-journal", action="store_true", help="推送 AI 模拟盘新增日志（测试用）")
    ap.add_argument("--test", action="store_true", help="发送测试消息")
    ap.add_argument("--dry-run", action="store_true", help="只打印不发送")
    args = ap.parse_args()
    cfg = FeishuConfig.load()
    session = args.session.strip() or None

    if args.test:
        if args.dry_run:
            print("[DRY-RUN] 将发送测试消息")
            return
        push_test(cfg)
        return

    if args.pipeline_done:
        push_pipeline_done(cfg, dry_run=args.dry_run)
        return

    if args.sug_done:
        push_sug_done(
            cfg,
            holder=args.holder,
            session=session,
            all_holders=args.all_holders,
            dry_run=args.dry_run,
        )
        return

    if args.ai_sim_journal:
        push_ai_sim_journal(cfg, dry_run=args.dry_run)
        return

    ap.print_help()


if __name__ == "__main__":
    main()
