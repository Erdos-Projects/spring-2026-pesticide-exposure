from __future__ import annotations

# Standalone exposure-set definitions + feature engineering helpers.
# This file used to be embedded into a notebook cell; add imports so it can
# be safely imported from scripts (e.g. validate_model_accuracy.py).

import numpy as np
import pandas as pd

# Embedded into model_selection data cell — four exposure designs + engineer

def engineer_signal_isolation_features(df: pd.DataFrame) -> pd.DataFrame:
    """Per-capita / per-cropland-acre loads, log1p intensities, rural_binary."""

    def safe_divide(num, denom):
        denom_arr = denom.to_numpy() if hasattr(denom, "to_numpy") else denom
        num_arr = num.to_numpy() if hasattr(num, "to_numpy") else num
        out = np.where(denom_arr == 0, np.nan, num_arr / denom_arr)
        return pd.Series(out, index=getattr(num, "index", None)) if hasattr(num, "index") else out

    df = df.copy()
    df["resp_per_capita"] = safe_divide(df["pesticide_respiratory_kg"], df["population"])
    df["resp_per_cropland_acre"] = safe_divide(df["pesticide_respiratory_kg"], df["cropland_acres"])

    for kg_col in AGGREGATE_KG_PROXIES:
        if kg_col not in df.columns or kg_col == "pesticide_respiratory_kg":
            continue
        slug = kg_col.replace("pesticide_", "").replace("_kg", "")
        pc, pa = f"{slug}_per_capita", f"{slug}_per_cropland_acre"
        df[pc] = safe_divide(df[kg_col], df["population"])
        df[pa] = safe_divide(df[kg_col], df["cropland_acres"])
        df[f"log_{pc}"] = np.log1p(df[pc])
        df[f"log_{pa}"] = np.log1p(df[pa])

    df["op_per_capita"] = safe_divide(df["pesticide_organophosphate_kg"], df["population"])
    df["op_per_cropland_acre"] = safe_divide(df["pesticide_organophosphate_kg"], df["cropland_acres"])
    df["carbamate_per_capita"] = safe_divide(df["pesticide_carbamate_kg"], df["population"])
    df["carbamate_per_cropland_acre"] = safe_divide(df["pesticide_carbamate_kg"], df["cropland_acres"])
    df["pyrethroid_per_capita"] = safe_divide(df["pesticide_pyrethroid_kg"], df["population"])
    df["pyrethroid_per_cropland_acre"] = safe_divide(df["pesticide_pyrethroid_kg"], df["cropland_acres"])

    for col in [
        "resp_per_capita", "resp_per_cropland_acre", "op_per_capita", "op_per_cropland_acre",
        "carbamate_per_capita", "carbamate_per_cropland_acre",
        "pyrethroid_per_capita", "pyrethroid_per_cropland_acre",
    ]:
        df[f"log_{col}"] = np.log1p(df[col])

    df["rural_binary"] = (df["nchs_urban_rural"] >= 5).astype(int)
    return df


AGGREGATE_KG_PROXIES = [
    "pesticide_respiratory_kg", "pesticide_total_kg", "pesticide_chlorophenoxy_kg",
    "pesticide_triazine_kg", "pesticide_anilide_kg", "pesticide_organochlorine_kg", "pesticide_other_kg",
]


def _aggregate_log_intensity_feature_names():
    names = ["log_resp_per_capita", "log_resp_per_cropland_acre"]
    for kg_col in AGGREGATE_KG_PROXIES:
        if kg_col == "pesticide_respiratory_kg":
            continue
        slug = kg_col.replace("pesticide_", "").replace("_kg", "")
        names.extend([f"log_{slug}_per_capita", f"log_{slug}_per_cropland_acre"])
    return names


AGGREGATE_LOG_INTENSITY = _aggregate_log_intensity_feature_names()
PEST_AGGREGATE_ORDER = list(dict.fromkeys(AGGREGATE_KG_PROXIES + AGGREGATE_LOG_INTENSITY))
PEST_COMPONENTS = [
    "log_op_per_capita", "log_op_per_cropland_acre",
    "log_carbamate_per_capita", "log_carbamate_per_cropland_acre",
    "log_pyrethroid_per_capita", "log_pyrethroid_per_cropland_acre",
]
COMPONENT_KG_RAW = [
    "pesticide_organophosphate_kg", "pesticide_carbamate_kg", "pesticide_pyrethroid_kg",
]

DEMO_COLS = [
    "population", "median_age", "median_income", "pct_white", "pct_black",
    "pct_asian", "pct_hispanic", "rural_binary",
]
HEALTH_CONFOUNDER_COLS = ["CSMOKING", "OBESITY", "DIABETES"]
CROPLAND_COLS = ["cropland_diversity", "county_crop_concentration", "pct_cropland"]
OTHER_COLS = ["YEAR"]
BASE_COLS = DEMO_COLS + HEALTH_CONFOUNDER_COLS + CROPLAND_COLS + OTHER_COLS

EXPOSURE_SETS = {
    "Aggs_raw": list(dict.fromkeys(AGGREGATE_KG_PROXIES + BASE_COLS)),
    "Aggs_engineered": list(dict.fromkeys(AGGREGATE_KG_PROXIES + AGGREGATE_LOG_INTENSITY + BASE_COLS)),
    "Components_raw": list(dict.fromkeys(COMPONENT_KG_RAW + BASE_COLS)),
    "Components_engineered": list(dict.fromkeys(PEST_COMPONENTS + BASE_COLS)),
}
# Full_pesticides_raw is built per-split in the data cell (all pesticide_*_kg + BASE_COLS).
FULL_PESTICIDES_RAW_KEY = "Full_pesticides_raw"
EXPOSURE_SET_KEYS = list(EXPOSURE_SETS.keys()) + [FULL_PESTICIDES_RAW_KEY]
