"""One-shot rebuild of model_selection.ipynb: five exposure sets (incl. full pesticide kg), SI section removed."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXP = (ROOT / "_exposure_defs.py").read_text()

CELL5 = (
    "# --- Data splits ---\n"
    "# Five exposure designs (+ Full_pesticides_raw: every pesticide_*_kg) + shared BASE_COLS.\n\n"
    "def choose_feature_columns(train_df: pd.DataFrame, target: str) -> list:\n"
    "    drop = set(DEFAULT_DROP_COLUMNS)\n"
    "    lc = {c: str(c).lower() for c in train_df.columns}\n"
    "    for c, name in lc.items():\n"
    "        if name.startswith(\"ipm_\") or name.startswith(\"chemical_reliance\"):\n"
    "            drop.add(c)\n"
    "    drop.update(\n"
    "        c for c in train_df.columns\n"
    "        if c in {\"mean_text_quality\", \"mean_geo_confidence\", \"weighted_doc_age\", \"total_ag_value\"}\n"
    "    )\n"
    "    return [c for c in train_df.columns if c not in drop]\n\n\n"
    + EXP
    + "\n\ndata = {}\n"
    "for TARGET in TARGETS:\n"
    "    train_df = pd.read_csv(TARGET_PATHS[TARGET][\"train\"])\n"
    "    test_df = pd.read_csv(TARGET_PATHS[TARGET][\"test\"])\n"
    "    feature_columns = choose_feature_columns(train_df, TARGET)\n"
    "    etr = engineer_signal_isolation_features(train_df.copy())\n"
    "    ete = engineer_signal_isolation_features(test_df.copy())\n"
    "    X_by = {}\n"
    "    for k, cols in EXPOSURE_SETS.items():\n"
    "        use = [c for c in cols if c in etr.columns]\n"
    "        X_by[k] = (etr[use].copy(), ete[use].copy())\n"
    "    pest_kg_cols = sorted(c for c in train_df.columns if str(c).startswith(\"pesticide_\") and str(c).endswith(\"_kg\"))\n"
    "    full_raw = [c for c in list(dict.fromkeys(pest_kg_cols + BASE_COLS)) if c in etr.columns and c in ete.columns]\n"
    "    X_by[FULL_PESTICIDES_RAW_KEY] = (etr[full_raw].copy(), ete[full_raw].copy())\n"
    "    data[TARGET] = {\n"
    "        \"train_df\": train_df,\n"
    "        \"test_df\": test_df,\n"
    "        \"train_eng\": etr,\n"
    "        \"test_eng\": ete,\n"
    "        \"X_by_exposure\": X_by,\n"
    "        \"X_train\": train_df[feature_columns].copy(),\n"
    "        \"y_train\": train_df[TARGET].copy(),\n"
    "        \"y_test\": test_df[TARGET].copy(),\n"
    "        \"groups\": train_df[\"FIPS\"].copy(),\n"
    "        \"feature_columns\": feature_columns,\n"
    "    }\n"
    "    print(f\"{TARGET}: train {len(train_df)}, test {len(test_df)}, full pipeline cols {len(feature_columns)} | exposure sets: {list(X_by.keys())}\")\n\n"
    "TARGET = TARGETS[0]\n"
    "PLOT_EXPOSURE_KEY = \"Aggs_engineered\"\n"
    "y_train = data[TARGET][\"y_train\"]\n"
    "y_test = data[TARGET][\"y_test\"]\n"
    "groups = data[TARGET][\"groups\"]\n"
    "X_train, X_test = data[TARGET][\"X_by_exposure\"][PLOT_EXPOSURE_KEY]\n"
    "feature_columns = data[TARGET][\"feature_columns\"]\n"
    "data[TARGET][\"X_train\"].head()\n"
)

CELL6_MD = (
    "---\n## Models 1–7 × exposure sets\n\n"
    "For each target (CASTHMA, COPD) and each exposure set (**Aggs_raw**, **Aggs_engineered**, **Components_raw**, **Components_engineered**, **Full_pesticides_raw**), "
    "we fit: Simple LR (1 feat), multiple Ridge (numeric), Ridge (full preprocess), tuned Ridge/Lasso/ElasticNet, XGBoost. "
    "**Diagnostic plots / SHAP / coef tables** below use **CASTHMA** + **Aggs_engineered** by default (`PLOT_EXPOSURE_KEY`). "
    "**Full_pesticides_raw** is wide (~450+ features with BASE_COLS); expect much longer runtimes (especially XGBoost grid search).\n"
)

CELL7_CODE = r'''def make_strata(y: pd.Series, n_bins: int = 5) -> pd.Series:
    n_unique = y.nunique(dropna=True)
    bins = max(2, min(n_bins, n_unique))
    return pd.qcut(y, q=bins, labels=False, duplicates="drop")


def build_preprocessor(X: pd.DataFrame) -> ColumnTransformer:
    numeric_features = X.select_dtypes(include=["number", "bool"]).columns.tolist()
    categorical_features = [c for c in X.columns if c not in numeric_features]
    numeric_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorical_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, numeric_features),
            ("cat", categorical_pipeline, categorical_features),
        ],
        remainder="drop",
    )


SI_TOP_N = 8
SI_XGB_PARAM_GRID = {
    "model__max_depth": [3, 5, 7],
    "model__learning_rate": [0.05, 0.1],
    "model__n_estimators": [100, 200],
}
SI_MODEL_ORDER = [
    "Simple LR (1 feat)", "Multiple LR (Ridge, numeric)", "Multiple LR (Ridge, full preprocess)",
    "Ridge (tuned)", "Lasso (tuned)", "ElasticNet (tuned)", "XGBoost (tuned)",
]


def top_coefficients_from_linear_search(search, top_n=SI_TOP_N):
    names = search.best_estimator_.named_steps["preprocess"].get_feature_names_out()
    coef = search.best_estimator_.named_steps["model"].coef_
    df = pd.DataFrame({"feature": names, "coefficient": coef, "abs_coef": np.abs(coef)})
    return df.sort_values("abs_coef", ascending=False).head(top_n)


def top_importances_from_xgb_search(search, top_n=SI_TOP_N):
    fnames = search.best_estimator_.named_steps["preprocess"].get_feature_names_out()
    im = search.best_estimator_.named_steps["model"].feature_importances_
    return pd.DataFrame({"feature": fnames, "importance": im}).sort_values("importance", ascending=False).head(top_n)


def run_exposure_models_all(target, exposure_name, X_tr, X_te, y_tr, y_te, folds):
    feature_cols = list(X_tr.columns)
    if exposure_name == "Aggs_raw":
        pool = [c for c in AGGREGATE_KG_PROXIES if c in feature_cols]
    elif exposure_name == "Full_pesticides_raw":
        pool = sorted(c for c in feature_cols if str(c).startswith("pesticide_") and str(c).endswith("_kg"))
    elif exposure_name == "Aggs_engineered":
        pool = [c for c in PEST_AGGREGATE_ORDER if c in feature_cols]
    elif exposure_name == "Components_raw":
        pool = [c for c in COMPONENT_KG_RAW if c in feature_cols]
    else:
        pool = [c for c in PEST_COMPONENTS if c in feature_cols]
    if exposure_name == "Full_pesticides_raw" and pool:
        single_pest = "pesticide_total_kg" if "pesticide_total_kg" in feature_cols else pool[0]
    else:
        single_pest = pool[0] if pool else feature_cols[0]

    imp_single = SimpleImputer(strategy="median")
    x_tr_s = imp_single.fit_transform(X_tr[[single_pest]])
    x_te_s = imp_single.transform(X_te[[single_pest]])
    m_simple = LinearRegression().fit(x_tr_s, y_tr)
    pred_simple = m_simple.predict(x_te_s)
    simple_top = pd.DataFrame({"feature": [single_pest], "coefficient": [float(m_simple.coef_[0])], "abs_coef": [float(np.abs(m_simple.coef_[0]))]})

    numeric_cols = X_tr.select_dtypes(include=["number", "bool"]).columns.tolist()
    pipe_num = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("model", Ridge(alpha=1.0)),
    ])
    pipe_num.fit(X_tr[numeric_cols], y_tr)
    pred_multi_numeric = pipe_num.predict(X_te[numeric_cols])
    ridge_numeric_top = (
        pd.DataFrame({"feature": numeric_cols, "coefficient": pipe_num.named_steps["model"].coef_, "abs_coef": np.abs(pipe_num.named_steps["model"].coef_)})
        .sort_values("abs_coef", ascending=False).head(SI_TOP_N)
    )

    preproc_full = build_preprocessor(X_tr)
    X_tr_f = preproc_full.fit_transform(X_tr)
    X_te_f = preproc_full.transform(X_te)
    m_full = Ridge(alpha=1.0).fit(X_tr_f, y_tr)
    pred_multi_full = m_full.predict(X_te_f)
    ridge_full_top = (
        pd.DataFrame({"feature": preproc_full.get_feature_names_out(), "coefficient": m_full.coef_, "abs_coef": np.abs(m_full.coef_)})
        .sort_values("abs_coef", ascending=False).head(SI_TOP_N)
    )

    preproc = build_preprocessor(X_tr)
    ridge_search = GridSearchCV(
        Pipeline([("preprocess", preproc), ("model", Ridge())]),
        param_grid={"model__alpha": ALPHA_GRID}, cv=folds, scoring="neg_root_mean_squared_error", refit=True, n_jobs=1,
    ).fit(X_tr, y_tr)
    pred_ridge = ridge_search.predict(X_te)

    lasso_search = GridSearchCV(
        Pipeline([("preprocess", preproc), ("model", Lasso(max_iter=20000, random_state=RANDOM_STATE))]),
        param_grid={"model__alpha": ALPHA_GRID}, cv=folds, scoring="neg_root_mean_squared_error", refit=True, n_jobs=1,
    ).fit(X_tr, y_tr)
    pred_lasso = lasso_search.predict(X_te)

    elastic_search = GridSearchCV(
        Pipeline([("preprocess", preproc), ("model", ElasticNet(max_iter=20000, random_state=RANDOM_STATE))]),
        param_grid={"model__alpha": ALPHA_GRID, "model__l1_ratio": [0.25, 0.5, 0.75]},
        cv=folds, scoring="neg_root_mean_squared_error", refit=True, n_jobs=1,
    ).fit(X_tr, y_tr)
    pred_elastic = elastic_search.predict(X_te)

    xgb_search = GridSearchCV(
        Pipeline([("preprocess", preproc), ("model", XGBRegressor(random_state=RANDOM_STATE, n_jobs=-1))]),
        param_grid=SI_XGB_PARAM_GRID, cv=folds, scoring="neg_root_mean_squared_error", refit=True, n_jobs=1,
    ).fit(X_tr, y_tr)
    pred_xgb = xgb_search.predict(X_te)

    preds = {
        "Simple LR (1 feat)": pred_simple,
        "Multiple LR (Ridge, numeric)": pred_multi_numeric,
        "Multiple LR (Ridge, full preprocess)": pred_multi_full,
        "Ridge (tuned)": pred_ridge,
        "Lasso (tuned)": pred_lasso,
        "ElasticNet (tuned)": pred_elastic,
        "XGBoost (tuned)": pred_xgb,
    }
    top_features = {
        "Simple LR (1 feat)": simple_top,
        "Multiple LR (Ridge, numeric)": ridge_numeric_top,
        "Multiple LR (Ridge, full preprocess)": ridge_full_top,
        "Ridge (tuned)": top_coefficients_from_linear_search(ridge_search),
        "Lasso (tuned)": top_coefficients_from_linear_search(lasso_search),
        "ElasticNet (tuned)": top_coefficients_from_linear_search(elastic_search),
        "XGBoost (tuned)": top_importances_from_xgb_search(xgb_search),
    }
    rows = []
    for model_name in SI_MODEL_ORDER:
        pred = preds[model_name]
        row = {
            "target": target, "exposure_set": exposure_name, "model": model_name,
            "rmse": float(np.sqrt(mean_squared_error(y_te, pred))),
            "mae": float(mean_absolute_error(y_te, pred)),
            "r2": float(r2_score(y_te, pred)),
            "best_alpha": np.nan, "best_l1_ratio": np.nan, "best_params": np.nan,
        }
        if model_name == "Ridge (tuned)":
            row["best_alpha"] = ridge_search.best_params_["model__alpha"]
        elif model_name == "Lasso (tuned)":
            row["best_alpha"] = lasso_search.best_params_["model__alpha"]
        elif model_name == "ElasticNet (tuned)":
            row["best_alpha"] = elastic_search.best_params_["model__alpha"]
            row["best_l1_ratio"] = elastic_search.best_params_["model__l1_ratio"]
        elif model_name == "XGBoost (tuned)":
            row["best_params"] = repr(xgb_search.best_params_)
        rows.append(row)

    bundle = {
        "ridge_search": ridge_search, "lasso_search": lasso_search, "elastic_search": elastic_search, "xgb_search": xgb_search,
        "pred_ridge": pred_ridge, "pred_lasso": pred_lasso, "pred_elastic": pred_elastic, "pred_xgb": pred_xgb,
        "preds": preds,
    }
    return pd.DataFrame(rows), top_features, bundle


fitted_store = {}
summaries = []
for target in TARGETS:
    print(f"\n=== {target} ===")
    d = data[target]
    etr, ete = d["train_eng"], d["test_eng"]
    y_tr, y_te = d["y_train"], d["y_test"]
    strata = make_strata(y_tr)
    folds = list(
        StratifiedGroupKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE).split(d["X_train"], strata, d["groups"])
    )
    for ek in EXPOSURE_SET_KEYS:
        X_tr, X_te = d["X_by_exposure"][ek]
        print(f"  {ek}: {X_tr.shape[1]} cols")
        summary_df, _top, bundle = run_exposure_models_all(target, ek, X_tr, X_te, y_tr, y_te, folds)
        fitted_store[(target, ek)] = bundle
        summaries.append(summary_df)

exposure_summary_all = pd.concat(summaries, ignore_index=True)
print("\n=== All targets × exposure sets × models (sorted by RMSE) ===")
display(exposure_summary_all.sort_values(["target", "exposure_set", "rmse"]))

TARGET = TARGETS[0]
PLOT_EXPOSURE_KEY = "Aggs_engineered"
b = fitted_store[(TARGET, PLOT_EXPOSURE_KEY)]
ridge_search, lasso_search, elastic_search, xgb_search = b["ridge_search"], b["lasso_search"], b["elastic_search"], b["xgb_search"]
pred_ridge, pred_lasso, pred_elastic, pred_xgb = b["pred_ridge"], b["pred_lasso"], b["pred_elastic"], b["pred_xgb"]
y_test = data[TARGET]["y_test"]
y_train = data[TARGET]["y_train"]
X_train, X_test = data[TARGET]["X_by_exposure"][PLOT_EXPOSURE_KEY]
print(f"Plots use TARGET={TARGET}, exposure={PLOT_EXPOSURE_KEY}")
'''

FULLPIPE = (
    "# --- Export: bootstrap RMSE CIs + save CSVs (uses `fitted_store` from models cell) ---\n\n"
    "def bootstrap_ci(y_true, y_pred, n_boot=N_BOOT, seed=RANDOM_STATE):\n"
    "    rng = np.random.default_rng(seed)\n"
    "    n = len(y_true)\n"
    "    rmse_boot = []\n"
    "    for _ in range(n_boot):\n"
    "        idx = rng.integers(0, n, size=n)\n"
    "        rmse_boot.append(np.sqrt(mean_squared_error(y_true.iloc[idx], y_pred[idx])))\n"
    "    return np.percentile(rmse_boot, [2.5, 97.5])\n\n"
    "combined_rows = []\n"
    "for target in TARGETS:\n"
    "    y_te = data[target][\"y_test\"]\n"
    "    for ek in EXPOSURE_SET_KEYS:\n"
    "        preds = fitted_store[(target, ek)][\"preds\"]\n"
    "        for name, pred in preds.items():\n"
    "            row = {\"target\": target, \"exposure_set\": ek, \"model\": name,\n"
    "                \"rmse\": float(np.sqrt(mean_squared_error(y_te, pred))),\n"
    "                \"mae\": float(mean_absolute_error(y_te, pred)), \"r2\": float(r2_score(y_te, pred))}\n"
    "            lo, hi = bootstrap_ci(y_te, pred)\n"
    "            row[\"rmse_ci_low\"], row[\"rmse_ci_high\"] = lo, hi\n"
    "            combined_rows.append(row)\n"
    "combined_summary = pd.DataFrame(combined_rows)\n"
    "display(combined_summary.sort_values([\"target\", \"exposure_set\", \"rmse\"]))\n\n"
    "for t in TARGETS:\n"
    "    td = RESULTS_DIR / t\n"
    "    td.mkdir(parents=True, exist_ok=True)\n"
    "    combined_summary[combined_summary[\"target\"] == t].to_csv(td / \"model_summary_exposure_sets.csv\", index=False)\n"
    "    b = fitted_store[(t, \"Aggs_engineered\")]\n"
    "    y_te = data[t][\"y_test\"]\n"
    "    td_df = data[t][\"test_df\"]\n"
    "    for name, key in [(\"ridge\", \"pred_ridge\"), (\"lasso\", \"pred_lasso\"), (\"elasticnet\", \"pred_elastic\"), (\"xgboost\", \"pred_xgb\")]:\n"
    "        pred = b[key]\n"
    "        pd.DataFrame({\"FIPS\": td_df[\"FIPS\"], \"YEAR\": td_df[\"YEAR\"], \"actual\": y_te, \"prediction\": pred}).to_csv(td / f\"{name}_predictions_Aggs_engineered.csv\", index=False)\n"
    "    x_s = b[\"xgb_search\"]\n"
    "    fn = x_s.best_estimator_.named_steps[\"preprocess\"].get_feature_names_out()\n"
    "    im = x_s.best_estimator_.named_steps[\"model\"].feature_importances_\n"
    "    pd.DataFrame({\"feature\": fn, \"importance\": im}).sort_values(\"importance\", ascending=False).head(25).to_csv(td / \"xgboost_top_importances_Aggs_engineered.csv\", index=False)\n"
    "    for nm, srch in [(\"ridge\", b[\"ridge_search\"]), (\"lasso\", b[\"lasso_search\"]), (\"elasticnet\", b[\"elastic_search\"])]:\n"
    "        top_coefficients(srch).to_csv(td / f\"{nm}_top_coefficients_Aggs_engineered.csv\", index=False)\n"
    "    print(f\"Saved {t}\")\n"
)


def main():
    """Refresh data (cell 5), models header (6), models code (7), exposure markdown (4), intro (0). Preserves all other cells."""
    nb_path = ROOT / "model_selection.ipynb"
    nb = json.loads(nb_path.read_text())
    if len(nb["cells"]) < 8:
        raise SystemExit("Notebook needs at least 8 cells")

    nb["cells"][5].update(
        {"source": [CELL5], "outputs": [], "execution_count": None}
    )
    nb["cells"][6] = {"cell_type": "markdown", "metadata": {}, "source": [CELL6_MD]}
    nb["cells"][7].update(
        {"source": [CELL7_CODE], "outputs": [], "execution_count": None}
    )

    intro = "".join(nb["cells"][0]["source"])
    intro = intro.replace(
        "| **Feature variants** | Short table: raw vs engineered pesticide scaling. |\n",
        "| **Exposure sets** | Five designs (+ **Full_pesticides_raw**). |\n",
    )
    for line in (
        "| **Model 1** | Simple LR — reports **raw vs engineered** (one feature). |\n",
        "| **Model 2** | Multiple Ridge numeric — **both variants**. |\n",
        "| **Model 3** | Full preprocess Ridge — **both variants** (downstream uses raw). |\n",
        "| **Models 4–5** | Tuned Ridge/Lasso/EN — **both variants** (coef plots: raw). |\n",
        "| **Model 6** | XGBoost — **both variants** (SHAP: raw). |\n",
    ):
        intro = intro.replace(line, "")
    intro = intro.replace(
        "| **Metrics / plots / SHAP** | Test metrics table: **all models × raw & engineered** (bootstrap RMSE CIs). Plots/SHAP use **raw** tuned fits. |\n",
        "| **Models × exposures** | All seven model families on each exposure set; combined table. Plots/SHAP use **CASTHMA + Aggs_engineered**. |\n",
    )
    intro = intro.replace(
        "| **Full pipeline** | `run_pipeline` per target × **raw/engineered**; combined summary with `feature_variant`. |\n",
        "| **Export** | Bootstrap CIs + CSVs per target; optional save cell. |\n",
    )
    intro = intro.replace(
        "| **SI** | Four pesticide blocks: **Aggs_raw**, **Aggs_engineered**, **Components_raw**, **Components_engineered** (+ `BASE_COLS`); column-overlap table; **SI v2** trains all models on each. |\n",
        "",
    )
    intro = intro.replace(
        "| **Data** | Four **exposure sets** (see below) + engineered county-level intensities. |\n",
        "| **Data** | Five **exposure sets** (see below), including **Full_pesticides_raw** (all `pesticide_*_kg`). |\n",
    )
    intro = intro.replace(
        "| **Models × exposures** | Seven model families × **Aggs_raw**, **Aggs_engineered**, **Components_raw**, **Components_engineered** for CASTHMA & COPD. |\n",
        "| **Models × exposures** | Seven model families × five exposure sets (incl. **Full_pesticides_raw**) for CASTHMA & COPD. |\n",
    )
    nb["cells"][0]["source"] = [intro]

    nb["cells"][4] = {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "## Exposure sets (used throughout)\n\n"
            "Same **demographic / health / land-use / YEAR** block (`BASE_COLS`) for all runs. Pesticide signal varies:\n\n"
            "| Set | Pesticide predictors |\n"
            "|-----|----------------------|\n"
            "| **Aggs_raw** | County kg rollups (respiratory, total, class totals). |\n"
            "| **Aggs_engineered** | Those kg + log1p(per-capita) & log1p(per-cropland-acre) per rollup. |\n"
            "| **Components_raw** | OP, carbamate, pyrethroid kg only. |\n"
            "| **Components_engineered** | Six log-intensity features for those classes. |\n"
            "| **Full_pesticides_raw** | Every **pesticide_*_kg** column (~400+ compounds + class/total rollups) + BASE_COLS; raw kg. |\n",
        ],
    }

    nb_path.write_text(json.dumps(nb, indent=1))
    print("Wrote", nb_path, "cells:", len(nb["cells"]))


if __name__ == "__main__":
    main()
