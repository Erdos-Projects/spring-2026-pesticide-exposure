#!/usr/bin/env python3
"""
Export XGBoost model predictions to web/data/risk_estimates.json for the map.

Reads predictions from modeling/results/<TARGET>/xgboost_predictions.csv,
merges with test data for county names, aggregates by county, and writes
the format expected by web/map.js.

Usage:
    python scripts/export_risk_estimates.py
"""

import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "modeling" / "results"
DATA_DIR = REPO_ROOT / "data"
WEB_DATA_DIR = REPO_ROOT / "web" / "data"


def main() -> None:
    # Load XGBoost predictions for both targets
    casthma_pred = pd.read_csv(RESULTS_DIR / "CASTHMA" / "xgboost_predictions.csv")
    copd_pred = pd.read_csv(RESULTS_DIR / "COPD" / "xgboost_predictions.csv")

    # Load test data for county names (NAME column)
    test_casthma = pd.read_csv(DATA_DIR / "test_CASTHMA.csv")[["FIPS", "YEAR", "NAME", "CASTHMA", "COPD"]]
    test_copd = pd.read_csv(DATA_DIR / "test_COPD.csv")[["FIPS", "YEAR", "NAME", "CASTHMA", "COPD"]]

    # Merge predictions with test data for names and actuals
    casthma = casthma_pred.merge(
        test_casthma[["FIPS", "YEAR", "NAME"]].drop_duplicates(),
        on=["FIPS", "YEAR"],
        how="left",
    )
    copd = copd_pred.merge(
        test_copd[["FIPS", "YEAR", "NAME"]].drop_duplicates(),
        on=["FIPS", "YEAR"],
        how="left",
    )

    # Aggregate by county: mean across years
    casthma_agg = (
        casthma.groupby("FIPS")
        .agg(
            prediction=("prediction", "mean"),
            actual=("actual", "mean"),
            county_name=("NAME", "first"),
        )
        .reset_index()
    )
    casthma_agg = casthma_agg.rename(columns={"prediction": "CASTHMA_pred", "actual": "CASTHMA_actual"})

    copd_agg = (
        copd.groupby("FIPS")
        .agg(
            prediction=("prediction", "mean"),
            actual=("actual", "mean"),
            county_name=("NAME", "first"),
        )
        .reset_index()
    )
    copd_agg = copd_agg.rename(columns={"prediction": "COPD_pred", "actual": "COPD_actual"})

    # Outer join to include all counties from either target
    combined = casthma_agg.merge(copd_agg, on="FIPS", how="outer", suffixes=("", "_y"))
    if "county_name_y" in combined.columns:
        combined["county_name"] = combined["county_name"].fillna(combined["county_name_y"])
    combined = combined[[c for c in combined.columns if not c.endswith("_y")]]

    # risk_index: normalize combined predicted risk to 0-1
    # Use average of CASTHMA and COPD predicted % when both exist; else use the one we have
    pred_cols = ["CASTHMA_pred", "COPD_pred"]
    combined["pred_avg"] = combined[pred_cols].mean(axis=1, skipna=True)
    pmin = combined["pred_avg"].min()
    pmax = combined["pred_avg"].max()
    if pmax > pmin:
        combined["risk_index"] = (combined["pred_avg"] - pmin) / (pmax - pmin)
    else:
        combined["risk_index"] = 0.5

    # Build output dict: FIPS (5-digit string) -> { risk_index, CASTHMA_prev, COPD_prev, county_name }
    combined["FIPS"] = combined["FIPS"].astype(int).astype(str).str.zfill(5)
    risk_by_fips = {}
    for _, row in combined.iterrows():
        fips = row["FIPS"]
        entry = {
            "risk_index": round(float(row["risk_index"]), 4),
            "county_name": str(row["county_name"]) if pd.notna(row["county_name"]) else "",
        }
        if pd.notna(row.get("CASTHMA_pred")):
            entry["CASTHMA_prev"] = round(float(row["CASTHMA_pred"]), 1)
        if pd.notna(row.get("COPD_pred")):
            entry["COPD_prev"] = round(float(row["COPD_pred"]), 1)
        risk_by_fips[fips] = entry

    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = WEB_DATA_DIR / "risk_estimates.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(risk_by_fips, f, indent=2)

    print(f"Exported {len(risk_by_fips)} counties to {out_path}")


if __name__ == "__main__":
    main()
