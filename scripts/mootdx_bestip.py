#!/usr/bin/env python3
"""每日 mootdx 行情服务器测速（bestip），供 60/30/5/1min 与财务接口 fallback。"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
STAMP = ROOT / "Wiki" / "数据" / "mootdx_bestip.date"
LOG = ROOT / "Wiki" / "数据" / "mootdx_bestip.log"


def _already_today() -> bool:
    if not STAMP.is_file():
        return False
    return STAMP.read_text(encoding="utf-8").strip() == date.today().isoformat()


def _write_stamp() -> None:
    STAMP.parent.mkdir(parents=True, exist_ok=True)
    STAMP.write_text(date.today().isoformat(), encoding="utf-8")


def _append_log(line: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_bestip(*, force: bool = False) -> int:
    if not force and _already_today():
        msg = f"mootdx bestip 今日已执行，跳过（删 {STAMP.name} 或 --force 重跑）"
        print(msg)
        return 0

    print(f"mootdx bestip | {date.today()} | 测速并写入 ~/.mootdx/config.json …")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "mootdx", "bestip"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        _append_log(f"{date.today()} TIMEOUT bestip >120s")
        print("[WARN] mootdx bestip 超时（>120s），沿用现有 BESTIP 配置")
        return 0
    except FileNotFoundError:
        print("[WARN] 未安装 mootdx：pip install mootdx")
        return 0

    out = (proc.stdout or "") + (proc.stderr or "")
    if out.strip():
        tail = "\n".join(out.strip().splitlines()[-8:])
        print(tail)

    if proc.returncode == 0:
        _write_stamp()
        _append_log(f"{date.today()} OK rc=0")
        print("mootdx bestip 完成")
        return 0

    _append_log(f"{date.today()} FAIL rc={proc.returncode}")
    print(f"[WARN] mootdx bestip 退出码 {proc.returncode}，沿用现有 BESTIP（流水线继续）")
    return 0  # 不阻断 daily.bat


def main() -> int:
    ap = argparse.ArgumentParser(description="每日 mootdx bestip（daily.bat 第 1 步）")
    ap.add_argument("--force", action="store_true", help="忽略今日已执行标记")
    args = ap.parse_args()
    return run_bestip(force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
