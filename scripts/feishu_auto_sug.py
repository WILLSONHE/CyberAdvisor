#!/usr/bin/env python3
"""daily.bat 完成后自动 Cloud Agent 生成 sug 全员（按时段选早盘/午盘）。"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from bilibili.env import apply_config_to_environ
from feishu.agent_jobs import agent_enabled
from feishu.agent_prompts import build_sug_prompt
from feishu.env import FeishuConfig
from feishu.notify import push_sug_done
from portfolio_utils import SUG_VAULT, load_holder_names, sug_archive_basename

log = logging.getLogger("feishu.auto_sug")


def resolve_auto_session(now: datetime | None = None) -> str | None:
    """
    11:30–13:00 → 早盘；15:00 及以后 → 午盘；其余时段不自动跑。
    """
    now = now or datetime.now()
    minutes = now.hour * 60 + now.minute
    if 11 * 60 + 30 <= minutes <= 13 * 60:
        return "早盘"
    if minutes >= 15 * 60:
        return "午盘"
    return None


def auto_sug_enabled() -> bool:
    apply_config_to_environ()
    flag = (os.environ.get("FEISHU_AUTO_SUG") or "0").strip().lower()
    return flag in ("1", "true", "yes", "on")


def _write_sugvault(holder: str, session: str | None, body: str, *, agent_id: str = "") -> str:
    os.makedirs(SUG_VAULT, exist_ok=True)
    fname = sug_archive_basename(holder, session)
    path = os.path.join(SUG_VAULT, fname)
    meta = f"<!-- auto-sug session={session or ''} agent={agent_id} -->\n\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(meta)
        f.write(body.strip())
        f.write("\n")
    return path


def run_sug_for_holder(holder: str, *, session: str | None) -> dict:
    from ai_sim.agent_client import AgentClientError, run_analysis_prompt

    apply_config_to_environ()
    log.info("生成 sug %s %s …", holder, session or "")
    prompt = build_sug_prompt(holder, session=session)
    resp = run_analysis_prompt(prompt)
    body = (resp.get("result") or "").strip()
    if not body:
        raise AgentClientError(f"{holder} 无 Agent 输出")
    path = _write_sugvault(holder, session, body, agent_id=str(resp.get("agent_id") or ""))
    return {"holder": holder, "path": path, "tokens": resp.get("token_total"), "url": resp.get("url")}


def run_auto_sug(
    *,
    session: str | None = None,
    after_daily: bool = False,
    dry_run: bool = False,
    notify: bool = True,
) -> bool:
    apply_config_to_environ()

    if after_daily and not auto_sug_enabled():
        print("[SKIP] FEISHU_AUTO_SUG 未开启（.env 设 FEISHU_AUTO_SUG=1 启用）")
        return False

    if not agent_enabled():
        print("[SKIP] 未配置 CURSOR_API_KEY，无法自动 sug")
        return False

    if session is None and after_daily:
        session = resolve_auto_session()
        if not session:
            print("[SKIP] 当前不在自动 sug 时段（11:30–13:00 早盘 / 15:00 后午盘）")
            return False

    holders = load_holder_names()
    if not holders:
        print("[SKIP] 无持有人，请先同步 持仓.xlsx")
        return False

    label = f"sug 全员{f' {session}' if session else ''}"
    print(f"=== {label} × {len(holders)} 人 ===")
    if dry_run:
        for h in holders:
            print(f"  [DRY-RUN] {h} → SugVault/{sug_archive_basename(h, session)}")
        return True

    ok, fail = 0, 0
    for h in holders:
        try:
            info = run_sug_for_holder(h, session=session)
            print(f"  [OK] {h} -> {info['path']}")
            ok += 1
        except Exception as e:
            log.exception("sug 失败 %s", h)
            print(f"  [FAIL] {h}: {e}")
            fail += 1

    print(f"完成：成功 {ok}，失败 {fail}")
    if ok and notify:
        cfg = FeishuConfig.load()
        try:
            push_sug_done(cfg, session=session, all_holders=True)
        except Exception as e:
            print(f"[WARN] Webhook 推送失败：{e}")
    return fail == 0


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="自动 Cloud Agent 生成 sug 全员")
    ap.add_argument("--after-daily", action="store_true", help="daily.bat 调用：检查 FEISHU_AUTO_SUG 与时段")
    ap.add_argument("--session", default="", help="强制盘次：早盘|午盘")
    ap.add_argument("--dry-run", action="store_true", help="只打印不调用 Agent")
    ap.add_argument("--no-notify", action="store_true", help="不写 Webhook")
    args = ap.parse_args()
    session = args.session.strip() or None
    if session and session not in ("早盘", "午盘"):
        raise SystemExit("--session 须为 早盘 或 午盘")
    ok = run_auto_sug(
        session=session,
        after_daily=args.after_daily,
        dry_run=args.dry_run,
        notify=not args.no_notify,
    )
    if not ok and not args.dry_run:
        sys.exit(1)


if __name__ == "__main__":
    main()
