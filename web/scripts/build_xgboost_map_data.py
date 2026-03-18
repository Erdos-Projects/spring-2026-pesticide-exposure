#!/usr/bin/env python3
"""
Build web/data/xgboost_map_data.json from modeling XGBoost prediction CSVs.
Run from repo root: python web/scripts/build_xgboost_map_data.py
Requires: stdlib only.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTCOME_FILES = {
    "casthma": REPO_ROOT / "modeling/results/CASTHMA/xgboost_predictions.csv",
    "copd": REPO_ROOT / "modeling/results/COPD/xgboost_predictions.csv",
}
OUTPUT = REPO_ROOT / "web/data/xgboost_map_data.json"
DISPLAY_YEAR = 2019


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
                "actual": float(row["actual"]),
                "prediction": float(row["prediction"]),
            }
    return by_fips


def min_max_norm(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [0.5 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def main() -> None:
    merged: dict[str, dict] = {}
    for key, csv_path in OUTCOME_FILES.items():
        if not csv_path.is_file():
            raise SystemExit(f"Missing file: {csv_path}")
        rows = load_year(csv_path, DISPLAY_YEAR)
        fips_list = list(rows.keys())
        preds = [rows[f]["prediction"] for f in fips_list]
        norms = dict(zip(fips_list, min_max_norm(preds)))
        for fips in fips_list:
            if fips not in merged:
                merged[fips] = {"year": DISPLAY_YEAR}
            merged[fips][key] = {
                "actual": rows[fips]["actual"],
                "prediction": rows[fips]["prediction"],
                "risk_index": norms[fips],
            }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=0)
    print(f"Wrote {len(merged)} counties to {OUTPUT} (year {DISPLAY_YEAR})")


if __name__ == "__main__":
    main()
