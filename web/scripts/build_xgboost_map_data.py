#!/usr/bin/env python3
"""
Build web/data/xgboost_map_data.json from modeling XGBoost prediction CSVs.

Prefers **full coverage** predictions (train + validation + test) from
``predictions_all_counties.csv`` produced by::

    python modeling/validate_model_accuracy.py --target CASTHMA --exposure-set Full_pesticides_raw \\
        --model-family \"XGBoost (tuned)\" --validation-set external_holdout --export-all-counties
    (repeat for COPD)

Falls back to ``xgboost_predictions_Full_pesticides_raw.csv``, then ``xgboost_predictions.csv``
(test-only) if the full export is missing.

Run from repo root: python web/scripts/build_xgboost_map_data.py
Requires: stdlib only.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET_DIR = {"casthma": "CASTHMA", "copd": "COPD"}
OUTPUT = REPO_ROOT / "web/data/xgboost_map_data.json"
OUTPUT_VALIDATION_ALIAS = REPO_ROOT / "web/data/validation_map_data.json"
DISPLAY_YEAR = 2019
META_KEY = "_meta"


def _prediction_csv_candidates(target_folder: str) -> list[Path]:
    """Ordered preference: all counties (full model universe) → full-pesticides test → default test."""
    base = REPO_ROOT / "modeling/results" / target_folder
    return [
        base
        / "validation_eval_Full_pesticides_raw__XGBoost_(tuned)"
        / "predictions_all_counties.csv",
        base / "xgboost_predictions_Full_pesticides_raw.csv",
        base / "xgboost_predictions.csv",
    ]


def _pick_csv(target_folder: str) -> Path:
    for p in _prediction_csv_candidates(target_folder):
        if p.is_file():
            return p
    raise FileNotFoundError(
        f"No prediction CSV found under modeling/results/{target_folder}/. "
        "Run validate_model_accuracy with --export-all-counties or model_selection export."
    )


def _float_or_nan(s: str) -> float:
    if s is None or (isinstance(s, str) and not s.strip()):
        return float("nan")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def load_year(path: Path, year: int) -> dict[str, dict]:
    """FIPS (5-digit) -> {actual, prediction}."""
    by_fips: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            if int(row["YEAR"]) != year:
                continue
            fips = str(row["FIPS"]).strip().zfill(5)
            by_fips[fips] = {
                "actual": _float_or_nan(row.get("actual", "")),
                "prediction": _float_or_nan(row.get("prediction", "")),
            }
    return by_fips


def min_max_norm(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [0.5 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def main() -> None:
    merged: dict[str, dict] = {}
    norms_by_outcome: dict[str, dict[str, float]] = {}
    sources: dict[str, str] = {}

    for key, folder in TARGET_DIR.items():
        csv_path = _pick_csv(folder)
        sources[key] = str(csv_path.relative_to(REPO_ROOT))
        rows = load_year(csv_path, DISPLAY_YEAR)
        fips_list = [f for f, v in rows.items() if math.isfinite(v["prediction"])]
        if not fips_list:
            raise SystemExit(f"No finite predictions for year {DISPLAY_YEAR} in {csv_path}")
        preds = [rows[f]["prediction"] for f in fips_list]
        norms_by_outcome[key] = dict(zip(fips_list, min_max_norm(preds)))
        print(f"{key}: {len(fips_list)} counties from {csv_path.relative_to(REPO_ROOT)}")

        for fips in fips_list:
            if fips not in merged:
                merged[fips] = {"year": DISPLAY_YEAR}
            act = rows[fips]["actual"]
            merged[fips][key] = {
                "actual": act if math.isfinite(act) else None,
                "prediction": rows[fips]["prediction"],
                "risk_index": norms_by_outcome[key][fips],
            }

    payload: dict = {
        META_KEY: {
            "year": DISPLAY_YEAR,
            "prediction_sources": sources,
            "legend_note": (
                "Final tuned XGBoost (Full_pesticides_raw), 2019 layer — same external-holdout "
                "pipeline as the model card when built from predictions_all_counties.csv "
                "(see build script for fallbacks)."
            ),
            "pipeline_detail": (
                "County predictions from validate_model_accuracy.py (external_holdout); "
                "prefers predictions_all_counties.csv under validation_eval_*__XGBoost_(tuned)/ "
                "per target, else xgboost_predictions_Full_pesticides_raw.csv, else "
                "xgboost_predictions.csv."
            ),
        }
    }
    payload.update(merged)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=0)
    OUTPUT.write_text(text, encoding="utf-8")
    OUTPUT_VALIDATION_ALIAS.write_text(text, encoding="utf-8")
    print(f"Wrote {len(merged)} counties + metadata to {OUTPUT} (year {DISPLAY_YEAR})")
    print(f"Mirrored to {OUTPUT_VALIDATION_ALIAS} (keeps ?source=validation in sync)")


if __name__ == "__main__":
    main()
