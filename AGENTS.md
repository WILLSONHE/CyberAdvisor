# AGENTS.md

## Cursor Cloud specific instructions

This repo (CyberAdvisor) is a **Python 3.12 CLI toolkit** (no web server / no build step). It pairs
a Markdown Wiki under `Wiki/` with stock-screening, market-report, and AI-simulation scripts under
`scripts/`. There is no compiled application — you "run" it by invoking individual scripts.

### Environment
- The startup update script installs `requirements.txt` into the **user site** with the system Python 3.12
  (`pip3 install --user --break-system-packages -r requirements.txt`). Run scripts with plain `python3`.
  (User-site install is used because the base VM has no `python3-venv`; this keeps startup robust.)
- `requirements-douyin.txt` (funasr/torch/faster-whisper) is **optional** — only needed for 抖音/视频 ASR
  transcription. It is heavy and not installed by default; install on demand if working on `scripts/douyin/`.
  Those flows also need `ffmpeg`.

### How to run scripts (important gotcha)
- Most scripts in `scripts/` use **flat imports** (e.g. `from wiki import ...`, `from sim_portfolio import ...`)
  and resolve paths relative to the repo root via `..`. **Run them from inside the `scripts/` directory**,
  e.g. `cd scripts && python3 daily_report.py`. Running from the repo root will fail on imports.

### Network / data source
- The market-data scripts use `mootdx` + Tencent/Eastmoney HTTP endpoints to pull **A-share** data. These
  Chinese servers ARE reachable from the Cloud VM (verified), so `daily_report.py`, `coarse_screen.py`,
  `fine_screen.py` work and fetch live data. `mootdx` auto-writes `~/.mootdx/config.json` and picks a server
  on first run (first call is slow while it speed-tests servers).
- Live-data scripts **overwrite tracked output files** under `Wiki/数据/` (e.g. `市场状态日报.md`,
  `市场摘要.json`, screening CSVs). These are regenerated runtime artifacts — do **not** commit them unless
  the change is intentional; `git checkout -- Wiki/` to discard.

### Local-only commands (no network, good smoke tests)
- `cd scripts && python3 wiki_cli.py qry 存储` — keyword search over the Wiki
- `python3 wiki_cli.py trk 寒武纪` — per-stock trace; `python3 wiki_cli.py chk` — Wiki health check

### Optional integrations (need secrets in `.env`)
- 飞书 (Feishu) bot/webhook, Bilibili & 抖音 fetch, and Cursor Cloud Agent all require credentials in a
  root `.env` (see `.env.example`). None are required for screening, reports, or Wiki queries.

### Tests / lint
- There is no test suite, lint config, or build pipeline committed in this repo. Validate changes by running
  the relevant script(s) directly (see above).
- Windows `.bat` files (`daily.bat`, `feishu_bot.bat`, `ai_sim_tick.bat`) are the author's local orchestration
  on Windows; on Linux invoke the underlying `scripts/*.py` directly instead.
