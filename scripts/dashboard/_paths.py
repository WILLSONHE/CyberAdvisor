"""Dashboard 路径常量。"""
from __future__ import annotations

import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS = os.path.join(ROOT, "scripts")
SUG_VAULT = os.path.join(ROOT, "SugVault")
BACKTEST_DIR = os.path.join(ROOT, "Wiki", "数据", "缠论回测")
PREDICT_DIR = os.path.join(ROOT, "Wiki", "数据", "股价预测追踪")
REVIEW_DIR = os.path.join(PREDICT_DIR, "复盘")
LOG_PATH = os.path.join(PREDICT_DIR, "预测登记.json")
PARAMS_PATH = os.path.join(PREDICT_DIR, "参数.json")
CHAN_GLOSSARY_MD = os.path.join(ROOT, "Wiki", "投资方法论", "缠论-术语与读表指南.md")
GRAPH_PROGRESS_DIR = os.path.join(ROOT, "Wiki", "数据", "graph_progress")
GRAPH_RUNS_DIR = os.path.join(ROOT, "Wiki", "数据", "graph_runs")
