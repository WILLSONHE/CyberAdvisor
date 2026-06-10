"""1日/3日/7日技术倾向可校准参数（outlook_tracker 读写）。"""
from __future__ import annotations

import json
import os
from typing import Any

from outlook_paths import PARAMS_PATH, migrate_legacy_files

migrate_legacy_files()

DEFAULTS: dict[str, Any] = {
    "version": "2026-06-10-vipdoc-prob",
    "sigma_divisor_1d": 3.0,
    "sigma_divisor_3d": 2.8,
    "sigma_divisor_7d": 2.4,
    "sigma_dev_floor_1d": 0.28,
    "sigma_dev_floor_3d": 0.35,
    "sigma_dev_floor_7d": 0.45,
    "track_level_boost": 1.25,
    "band_days_scale": 5,
    "use_realized_vol_floor": True,
    "realized_vol_lookback": 20,
    "band_vol_scale": 1.0,
    "prob_center_price_weight": 0.55,
    "prob_center_price_weight_mid": 0.65,
    "prob_horizon_reversion_pull": 0.07,
    "prob_mid_weight_per_day": 0.055,
    "prob_track_boost_decay_per_day": 0.04,
    "prob_sigma_halfband_scale": 0.92,
    "prob_uniform_weight": 0.06,
    "calibration_notes": [],
    "stats": {},
}


def load_params() -> dict[str, Any]:
    if not os.path.isfile(PARAMS_PATH):
        return dict(DEFAULTS)
    try:
        raw = json.loads(open(PARAMS_PATH, encoding="utf-8").read())
        out = dict(DEFAULTS)
        out.update({k: v for k, v in raw.items() if k in DEFAULTS or k == "stats"})
        if isinstance(raw.get("stats"), dict):
            out["stats"] = raw["stats"]
        if isinstance(raw.get("calibration_notes"), list):
            out["calibration_notes"] = raw["calibration_notes"]
        out["version"] = raw.get("version", out["version"])
        return out
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULTS)


def save_params(params: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(PARAMS_PATH), exist_ok=True)
    with open(PARAMS_PATH, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)
