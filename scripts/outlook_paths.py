"""股价预测追踪目录与文件路径（Wiki/数据/股价预测追踪）。"""
from __future__ import annotations

import json
import os
import shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

PREDICT_DIR = os.path.join(ROOT, "Wiki", "数据", "股价预测追踪")
LOG_PATH = os.path.join(PREDICT_DIR, "预测登记.json")
PARAMS_PATH = os.path.join(PREDICT_DIR, "参数.json")
QUERIED_PATH = os.path.join(PREDICT_DIR, "询问标的.json")
REVIEW_DIR = os.path.join(PREDICT_DIR, "复盘")
REVIEW_XLSX_PATH = os.path.join(REVIEW_DIR, "数据复盘.xlsx")

REVIEW_XLSX_COLUMNS = (
    "标的代码",
    "标的名称",
    "当前日期",
    "预测日期",
    "预测周期",
    "预测价格",
    "实际价格",
    "差距%",
    "原因",
)

_OLD_LOG = os.path.join(ROOT, "Wiki", "数据", "技术预测追踪.json")
_OLD_PARAMS = os.path.join(ROOT, "Wiki", "数据", "技术预测参数.json")


def ensure_predict_dir() -> None:
    os.makedirs(PREDICT_DIR, exist_ok=True)
    os.makedirs(REVIEW_DIR, exist_ok=True)


def migrate_legacy_files() -> None:
    """首次使用时从旧路径复制数据（不删除旧文件）。"""
    ensure_predict_dir()
    if not os.path.isfile(LOG_PATH) and os.path.isfile(_OLD_LOG):
        shutil.copy2(_OLD_LOG, LOG_PATH)
        try:
            raw = json.loads(open(LOG_PATH, encoding="utf-8").read())
            meta = raw.setdefault("meta", {})
            meta["migrated_from"] = _OLD_LOG
            meta["note"] = "sug / 分析报告 / daily / 持仓 1日·3日·7日预测登记"
            with open(LOG_PATH, "w", encoding="utf-8") as f:
                json.dump(raw, f, ensure_ascii=False, indent=2)
        except (OSError, json.JSONDecodeError):
            pass
    if not os.path.isfile(PARAMS_PATH) and os.path.isfile(_OLD_PARAMS):
        shutil.copy2(_OLD_PARAMS, PARAMS_PATH)
    if not os.path.isfile(QUERIED_PATH):
        # 从已有登记推断询问标的
        symbols: list[dict] = []
        if os.path.isfile(LOG_PATH):
            try:
                data = json.loads(open(LOG_PATH, encoding="utf-8").read())
                seen: set[str] = set()
                for rec in data.get("records") or []:
                    src = rec.get("source") or ""
                    if src not in ("analysis_report", "qry"):
                        continue
                    code = str(rec.get("code", "")).zfill(6)
                    if code in seen:
                        continue
                    seen.add(code)
                    symbols.append(
                        {
                            "code": code,
                            "name": rec.get("name") or code,
                            "first_seen": rec.get("date"),
                            "last_seen": rec.get("date"),
                            "source": src,
                        }
                    )
            except (OSError, json.JSONDecodeError):
                pass
        with open(QUERIED_PATH, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "symbols": symbols,
                    "meta": {"note": "用户询问过的标的（qry / 分析报告 / record --code）"},
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
