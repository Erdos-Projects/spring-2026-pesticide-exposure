#!/usr/bin/env python3
"""
Evaluate a selected regression model on the "validation" side using the same
pipeline components as the training/model-selection code.

By default, "validation set" means: the out-of-fold predictions produced by
the same `StratifiedGroupKFold` scheme used for hyperparameter tuning.

Outputs:
  - metrics CSV (RMSE/MAE/R2 + bootstrap RMSE CI)
  - predictions CSV (actual/prediction/residual with meta columns)
  - diagnostic plots (from `modeling/model_evaluation.py`)
  - top-error rows (from `modeling/model_evaluation.py`)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet, Lasso, LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Make `from modeling...` work when running this file directly.
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from modeling._exposure_defs import (  # noqa: E402
    AGGREGATE_KG_PROXIES,
    BASE_COLS,
    COMPONENT_KG_RAW,
    EXPOSURE_SETS,
    FULL_PESTICIDES_RAW_KEY,
    PEST_AGGREGATE_ORDER,
    PEST_COMPONENTS,
    engineer_signal_isolation_features,
)
from modeling.model_evaluation import evaluate as run_regression_evaluation  # noqa: E402


ALPHA_GRID = np.logspace(-3, 3, 13)
RANDOM_STATE = 42
DEFAULT_CV_SPLITS = 5
DEFAULT_N_BOOT = 100

SI_XGB_PARAM_GRID = {
    "model__max_depth": [3, 5, 7],
    "model__learning_rate": [0.05, 0.1],
    "model__n_estimators": [100, 200],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--target", choices=["CASTHMA", "COPD"], required=True)
    parser.add_argument(
        "--exposure-set",
        required=True,
        choices=list(EXPOSURE_SETS.keys()) + [FULL_PESTICIDES_RAW_KEY],
    )
    parser.add_argument(
        "--model-family",
        required=True,
        help=(
            "One of: Simple LR (1 feat), Multiple LR (Ridge, numeric), Multiple LR (Ridge, full preprocess), "
            "Ridge (tuned), Lasso (tuned), ElasticNet (tuned), XGBoost (tuned)."
        ),
    )

    parser.add_argument(
        "--validation-set",
        default="cv_oof",
        choices=["cv_oof", "external_holdout"],
        help="cv_oof = out-of-fold CV validation predictions; external_holdout uses data/validation.csv.",
    )
    parser.add_argument(
        "--export-all-counties",
        action="store_true",
        help=(
            "external_holdout only: after fitting on the train split, also write "
            "predictions_all_counties.csv for all available rows (train+validation+test). "
            "This does not refit on validation; it is prediction-only."
        ),
    )
    parser.add_argument("--cv-splits", type=int, default=DEFAULT_CV_SPLITS)
    parser.add_argument("--bootstrap-n", type=int, default=DEFAULT_N_BOOT)
    parser.add_argument("--random-state", type=int, default=RANDOM_STATE)

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "modeling" / "results",
        help="Where to write metrics/plots/predictions.",
    )

    return parser.parse_args()


def make_strata(y: pd.Series, n_bins: int = 5) -> pd.Series:
    # Matches the approach in model-selection code: quantile bins.
    n_unique = y.nunique(dropna=True)
    bins = max(2, min(n_bins, n_unique))
    return pd.qcut(y, q=bins, labels=False, duplicates="drop")


def build_preprocessor(X: pd.DataFrame) -> ColumnTransformer:
    numeric_features = X.select_dtypes(include=["number", "bool"]).columns.tolist()
    categorical_features = [col for col in X.columns if col not in numeric_features]

    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, numeric_features),
            ("cat", categorical_pipeline, categorical_features),
        ],
        remainder="drop",
    )


def exposure_columns(
    train_eng: pd.DataFrame,
    val_eng: pd.DataFrame | None,
    exposure_set: str,
) -> list[str]:
    if exposure_set == FULL_PESTICIDES_RAW_KEY:
        pest_kg_cols = sorted(
            c for c in train_eng.columns if str(c).startswith("pesticide_") and str(c).endswith("_kg")
        )
        # Keep order: pesticide_kg cols first, then BASE_COLS (de-duped).
        use = list(dict.fromkeys(pest_kg_cols + list(BASE_COLS)))
        if val_eng is None:
            return [c for c in use if c in train_eng.columns]
        common = [c for c in use if (c in train_eng.columns and c in val_eng.columns)]
        return common

    cols = EXPOSURE_SETS[exposure_set]
    if val_eng is None:
        return [c for c in cols if c in train_eng.columns]
    return [c for c in cols if (c in train_eng.columns and c in val_eng.columns)]


def bootstrap_rmse_ci(y_true: np.ndarray, y_pred: np.ndarray, *, n_boot: int, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    y_true = np.asarray(y_true).ravel().astype(float)
    y_pred = np.asarray(y_pred).ravel().astype(float)
    n = len(y_true)
    if n == 0:
        return (np.nan, np.nan)

    rmse_boot = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        rmse_boot[i] = float(np.sqrt(mean_squared_error(y_true[idx], y_pred[idx])))
    lo, hi = np.percentile(rmse_boot, [2.5, 97.5])
    return float(lo), float(hi)


def normalize_model_family(s: str) -> str:
    return " ".join(s.strip().split()).lower()


def model_family_key(display_name: str) -> str:
    # Map a user input to our internal canonical names.
    k = normalize_model_family(display_name)
    mapping = {
        normalize_model_family("Simple LR (1 feat)"): "Simple LR (1 feat)",
        normalize_model_family("Multiple LR (Ridge, numeric)"): "Multiple LR (Ridge, numeric)",
        normalize_model_family("Multiple LR (Ridge, full preprocess)"): "Multiple LR (Ridge, full preprocess)",
        normalize_model_family("Ridge (tuned)"): "Ridge (tuned)",
        normalize_model_family("Lasso (tuned)"): "Lasso (tuned)",
        normalize_model_family("ElasticNet (tuned)"): "ElasticNet (tuned)",
        normalize_model_family("XGBoost (tuned)"): "XGBoost (tuned)",
    }
    if k in mapping:
        return mapping[k]
    raise ValueError(
        f"Unrecognized --model-family {display_name!r}. "
        "Try one of: Simple LR (1 feat), Multiple LR (Ridge, numeric), Multiple LR (Ridge, full preprocess), "
        "Ridge (tuned), Lasso (tuned), ElasticNet (tuned), XGBoost (tuned)."
    )


def choose_single_feature_for_simple_lr(X_exposure: pd.DataFrame, exposure_set: str) -> str:
    feature_cols = list(X_exposure.columns)
    if exposure_set == "Aggs_raw":
        pool = [c for c in AGGREGATE_KG_PROXIES if c in feature_cols]
    elif exposure_set == FULL_PESTICIDES_RAW_KEY:
        pool = sorted(c for c in feature_cols if str(c).startswith("pesticide_") and str(c).endswith("_kg"))
    elif exposure_set == "Aggs_engineered":
        pool = [c for c in PEST_AGGREGATE_ORDER if c in feature_cols]
    elif exposure_set == "Components_raw":
        pool = [c for c in COMPONENT_KG_RAW if c in feature_cols]
    else:
        pool = [c for c in PEST_COMPONENTS if c in feature_cols]

    if exposure_set == FULL_PESTICIDES_RAW_KEY and pool:
        return "pesticide_total_kg" if "pesticide_total_kg" in feature_cols else pool[0]
    if pool:
        return pool[0]
    return feature_cols[0]


def build_and_fit_search(
    model_family: str,
    *,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    folds: list[tuple[np.ndarray, np.ndarray]],
    cv_splits: int,
    random_state: int,
    n_jobs: int | None = None,
) -> tuple[Any, dict[str, Any]]:
    """
    Returns (fitted_estimator_or_search, metadata dict).

    For tuned models: returns GridSearchCV object.
    For fixed models: returns a fitted Pipeline (and metadata has best_params=None).
    """

    if model_family == "Ridge (tuned)":
        preproc = build_preprocessor(X_train)
        ridge_pipe = Pipeline([("preprocess", preproc), ("model", Ridge())])
        search = GridSearchCV(
            estimator=ridge_pipe,
            param_grid={"model__alpha": ALPHA_GRID},
            cv=folds,
            scoring="neg_root_mean_squared_error",
            refit=True,
            n_jobs=n_jobs,
        )
        search.fit(X_train, y_train)
        return search, {"best_params": search.best_params_, "best_alpha": search.best_params_["model__alpha"]}

    if model_family == "Lasso (tuned)":
        preproc = build_preprocessor(X_train)
        lasso_pipe = Pipeline(
            [("preprocess", preproc), ("model", Lasso(max_iter=20000, random_state=random_state))]
        )
        search = GridSearchCV(
            estimator=lasso_pipe,
            param_grid={"model__alpha": ALPHA_GRID},
            cv=folds,
            scoring="neg_root_mean_squared_error",
            refit=True,
            n_jobs=n_jobs,
        )
        search.fit(X_train, y_train)
        return search, {"best_params": search.best_params_, "best_alpha": search.best_params_["model__alpha"]}

    if model_family == "ElasticNet (tuned)":
        preproc = build_preprocessor(X_train)
        en_pipe = Pipeline(
            [("preprocess", preproc), ("model", ElasticNet(max_iter=20000, random_state=random_state))]
        )
        search = GridSearchCV(
            estimator=en_pipe,
            param_grid={"model__alpha": ALPHA_GRID, "model__l1_ratio": [0.25, 0.5, 0.75]},
            cv=folds,
            scoring="neg_root_mean_squared_error",
            refit=True,
            n_jobs=n_jobs,
        )
        search.fit(X_train, y_train)
        return search, {"best_params": search.best_params_, "best_alpha": search.best_params_["model__alpha"]}

    if model_family == "XGBoost (tuned)":
        from xgboost import XGBRegressor  # local import so non-XGBoost users can still use other model families

        preproc = build_preprocessor(X_train)
        xgb_pipe = Pipeline(
            [
                ("preprocess", preproc),
                ("model", XGBRegressor(random_state=random_state, n_jobs=-1)),
            ]
        )
        search = GridSearchCV(
            estimator=xgb_pipe,
            param_grid=SI_XGB_PARAM_GRID,
            cv=folds,
            scoring="neg_root_mean_squared_error",
            refit=True,
            n_jobs=n_jobs,
        )
        search.fit(X_train, y_train)
        return search, {"best_params": search.best_params_, "best_params_str": repr(search.best_params_)}

    # Fixed models (not used for hyperparameter search in the original training summary).
    if model_family == "Multiple LR (Ridge, numeric)":
        numeric_cols = X_train.select_dtypes(include=["number", "bool"]).columns.tolist()
        pipe = Pipeline(
            [
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
                ("model", Ridge(alpha=1.0)),
            ]
        )
        pipe.fit(X_train[numeric_cols], y_train)
        return pipe, {"best_params": None}

    if model_family == "Multiple LR (Ridge, full preprocess)":
        preproc = build_preprocessor(X_train)
        pipe = Pipeline([("preprocess", preproc), ("model", Ridge(alpha=1.0))])
        pipe.fit(X_train, y_train)
        return pipe, {"best_params": None}

    if model_family == "Simple LR (1 feat)":
        single_feature = choose_single_feature_for_simple_lr(X_train, exposure_set="__unused__")
        # NOTE: this branch should be handled by the caller because `single_feature`
        # depends on the chosen exposure-set. See `predict_simple_lr_cv_oof`.
        raise ValueError(
            "Simple LR is handled specially during prediction; build_and_fit_search should not be called for it."
        )

    raise ValueError(f"Unhandled model family: {model_family}")


def predict_with_fixed_model(
    model_family: str,
    *,
    X_train_exposure: pd.DataFrame,
    y_train: pd.Series,
    X_val_exposure: pd.DataFrame,
    exposure_set: str,
    fitted_estimator: Any,
) -> np.ndarray:
    if model_family == "Multiple LR (Ridge, numeric)":
        numeric_cols = X_train_exposure.select_dtypes(include=["number", "bool"]).columns.tolist()
        return fitted_estimator.predict(X_val_exposure[numeric_cols])

    if model_family == "Multiple LR (Ridge, full preprocess)":
        return fitted_estimator.predict(X_val_exposure)

    if model_family == "Simple LR (1 feat)":
        single_feature = choose_single_feature_for_simple_lr(X_train_exposure, exposure_set=exposure_set)
        imp = SimpleImputer(strategy="median")
        x_tr_s = imp.fit_transform(X_train_exposure[[single_feature]])
        x_va_s = imp.transform(X_val_exposure[[single_feature]])
        m_simple = LinearRegression().fit(x_tr_s, y_train)
        return m_simple.predict(x_va_s)

    # tuned models come in as fitted pipelines via GridSearchCV.best_estimator_
    if model_family in {"Ridge (tuned)", "Lasso (tuned)", "ElasticNet (tuned)", "XGBoost (tuned)"}:
        return fitted_estimator.predict(X_val_exposure)

    raise ValueError(f"Unhandled model family: {model_family}")


def compute_oof_predictions_for_best_estimator(
    model_family: str,
    *,
    best_estimator: Any,
    X_exposure: pd.DataFrame,
    y: pd.Series,
    folds: list[tuple[np.ndarray, np.ndarray]],
    exposure_set: str,
) -> np.ndarray:
    from sklearn.base import clone

    oof_pred = np.full(len(y), np.nan, dtype=float)

    for train_idx, val_idx in folds:
        X_tr = X_exposure.iloc[train_idx]
        y_tr = y.iloc[train_idx]
        X_va = X_exposure.iloc[val_idx]

        if model_family == "Simple LR (1 feat)":
            preds = predict_with_fixed_model(
                model_family,
                X_train_exposure=X_tr,
                y_train=y_tr,
                X_val_exposure=X_va,
                exposure_set=exposure_set,
                fitted_estimator=None,
            )
        elif model_family == "Multiple LR (Ridge, numeric)":
            # Re-fit the fixed pipeline per fold (so imputer/scaler are fold-specific).
            numeric_cols = X_tr.select_dtypes(include=["number", "bool"]).columns.tolist()
            pipe = Pipeline(
                [
                    ("imputer", SimpleImputer(strategy="median")),
                    ("scaler", StandardScaler()),
                    ("model", Ridge(alpha=1.0)),
                ]
            )
            pipe.fit(X_tr[numeric_cols], y_tr)
            preds = pipe.predict(X_va[numeric_cols])
        elif model_family == "Multiple LR (Ridge, full preprocess)":
            preproc = build_preprocessor(X_tr)
            pipe = Pipeline([("preprocess", preproc), ("model", Ridge(alpha=1.0))])
            pipe.fit(X_tr, y_tr)
            preds = pipe.predict(X_va)
        else:
            # Tuned pipelines: clone best_estimator so preprocess is fold-specific.
            est_fold = clone(best_estimator)
            est_fold.fit(X_tr, y_tr)
            preds = est_fold.predict(X_va)

        oof_pred[val_idx] = preds

    return oof_pred


def load_split_mapping() -> dict[int, str]:
    mapping = pd.read_csv(REPO_ROOT / "data" / "split_mapping.csv")
    # geo_id sometimes has leading zeros; convert to int for robust comparisons.
    mapping["geo_id_int"] = mapping["geo_id"].astype(str).str.replace(r"^0+", "", regex=True)
    mapping["geo_id_int"] = mapping["geo_id_int"].replace("", "0").astype(int)
    return dict(zip(mapping["geo_id_int"], mapping["split"]))


def filter_by_split(df: pd.DataFrame, *, fips_col: str, split_map: dict[int, str], split_value: str) -> pd.DataFrame:
    fips = df[fips_col].astype(int)
    mask = fips.map(lambda x: split_map.get(int(x), None)) == split_value
    return df.loc[mask].copy()


def save_figures(figures: list[tuple[Any, str]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for fig, title in figures:
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in title)
        fig.savefig(out_dir / f"{safe}.png", dpi=150, bbox_inches="tight")
        # Close to avoid memory leaks on repeated runs.
        try:
            import matplotlib.pyplot as plt

            plt.close(fig)
        except Exception:
            pass


def main() -> None:
    args = parse_args()
    model_family = model_family_key(args.model_family)
    exposure_set = args.exposure_set
    target = args.target

    train_path = REPO_ROOT / "data" / f"train_{target}.csv"
    validation_path = REPO_ROOT / "data" / "validation.csv"

    out_dir = args.output_dir / target / f"validation_eval_{exposure_set}__{model_family}".replace(" ", "_")
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------
    # Load & engineer features
    # ---------------------------
    train_df_full = pd.read_csv(train_path)
    train_df_full = train_df_full.loc[train_df_full[target].notna()].copy()
    y_train_full = train_df_full[target].astype(float)

    split_mode: Literal["cv_oof", "external_holdout"] = args.validation_set

    if split_mode == "cv_oof":
        train_df = train_df_full
        X_source_df = train_df_full
        y_source = train_df_full[target].astype(float)
        X_meta = train_df[["FIPS", "YEAR", "NAME", "state_fips"]].copy()

        train_eng = engineer_signal_isolation_features(train_df)
        val_eng = None
        X_cols = exposure_columns(train_eng, val_eng=None, exposure_set=exposure_set)
        X_exposure = train_eng[X_cols].copy()

        # CV folds for tuning match the training/model-selection setup.
        groups = train_df["FIPS"].astype(int).values
        strata = make_strata(y_source)
        cv_splitter = StratifiedGroupKFold(
            n_splits=args.cv_splits, shuffle=True, random_state=args.random_state
        )
        X_dummy = np.zeros((len(train_df), 1))
        folds = list(cv_splitter.split(X_dummy, strata, groups))

        # Grid-search only for tuned models; fixed models use direct fold-specific fits.
        if model_family in {"Ridge (tuned)", "Lasso (tuned)", "ElasticNet (tuned)", "XGBoost (tuned)"}:
            search, meta = build_and_fit_search(
                model_family,
                X_train=X_exposure,
                y_train=y_source,
                folds=folds,
                cv_splits=args.cv_splits,
                random_state=args.random_state,
                n_jobs=1,
            )
            best_estimator = search.best_estimator_
        else:
            # For non-tuned models, we still need something to compute OOF predictions.
            meta = {"best_params": None}
            best_estimator = None

        if model_family == "Simple LR (1 feat)":
            oof_pred = compute_oof_predictions_for_best_estimator(
                model_family,
                best_estimator=None,
                X_exposure=X_exposure,
                y=y_source,
                folds=folds,
                exposure_set=exposure_set,
            )
        else:
            # Tuned models: use best_estimator fitted with best params.
            oof_pred = compute_oof_predictions_for_best_estimator(
                model_family,
                best_estimator=best_estimator,
                X_exposure=X_exposure,
                y=y_source,
                folds=folds,
                exposure_set=exposure_set,
            )

        # ---------------------------
        # Metrics + bootstrap CIs
        # ---------------------------
        y_true_arr = y_source.to_numpy(dtype=float)
        pred_arr = np.asarray(oof_pred, dtype=float)

        rmse = float(np.sqrt(mean_squared_error(y_true_arr, pred_arr)))
        mae = float(mean_absolute_error(y_true_arr, pred_arr))
        r2 = float(r2_score(y_true_arr, pred_arr))
        rmse_ci_low, rmse_ci_high = bootstrap_rmse_ci(
            y_true_arr, pred_arr, n_boot=args.bootstrap_n, seed=args.random_state
        )

        metrics_df = pd.DataFrame(
            [
                {
                    "target": target,
                    "exposure_set": exposure_set,
                    "model": model_family,
                    "validation_mode": split_mode,
                    "rmse": rmse,
                    "mae": mae,
                    "r2": r2,
                    "rmse_ci_low": rmse_ci_low,
                    "rmse_ci_high": rmse_ci_high,
                    "n_rows": int(len(y_true_arr)),
                    **{k: v for k, v in meta.items() if k != "best_params"},
                }
            ]
        )
        metrics_df.to_csv(out_dir / "metrics.csv", index=False)

        pred_df = train_df.copy()
        pred_df = pred_df[["FIPS", "YEAR", "NAME", "state_fips", target]].copy()
        pred_df = pred_df.rename(columns={target: "actual"})
        pred_df["prediction"] = pred_arr
        pred_df["residual"] = pred_df["actual"] - pred_df["prediction"]
        pred_df.to_csv(out_dir / "predictions_oof_validation.csv", index=False)

        # ---------------------------
        # Diagnostic plots (standard)
        # ---------------------------
        eval_out = run_regression_evaluation(
            y_true_arr,
            pred_arr,
            task="regression",
            X_test=X_meta.reset_index(drop=True),
            time_column="YEAR",
            top_n_errors=20,
        )
        save_figures(eval_out["figures"], out_dir / "figures")
        pd.DataFrame(eval_out["top_errors"]).to_csv(out_dir / "top_errors.csv", index=False)
        (out_dir / "interpretation.txt").write_text(
            eval_out.get("interpretation", "") + "\n\n" + eval_out.get("next_steps", ""),
            encoding="utf-8",
        )

        print(f"Wrote validation CV-OoF evaluation to: {out_dir}")
        return

    # ---------------------------
    # External holdout validation
    # ---------------------------
    if split_mode == "external_holdout":
        split_map = load_split_mapping()

        # Train: only the counties labeled `train` in split_mapping.
        train_df = filter_by_split(train_df_full, fips_col="FIPS", split_map=split_map, split_value="train")
        y_train = train_df[target].astype(float)
        groups = train_df["FIPS"].astype(int).values

        val_df_full = pd.read_csv(validation_path)
        val_df_full = val_df_full.loc[val_df_full[target].notna()].copy()
        val_df = filter_by_split(val_df_full, fips_col="FIPS", split_map=split_map, split_value="validation")
        y_val = val_df[target].astype(float)
        X_meta = val_df[["FIPS", "YEAR", "NAME", "state_fips"]].copy()

        train_eng = engineer_signal_isolation_features(train_df)
        val_eng = engineer_signal_isolation_features(val_df)
        X_cols = exposure_columns(train_eng, val_eng, exposure_set=exposure_set)
        X_train_exposure = train_eng[X_cols].copy()
        X_val_exposure = val_eng[X_cols].copy()

        strata = make_strata(y_train)
        cv_splitter = StratifiedGroupKFold(
            n_splits=args.cv_splits, shuffle=True, random_state=args.random_state
        )
        X_dummy = np.zeros((len(train_df), 1))
        folds = list(cv_splitter.split(X_dummy, strata, groups))

        if model_family in {"Ridge (tuned)", "Lasso (tuned)", "ElasticNet (tuned)", "XGBoost (tuned)"}:
            search, meta = build_and_fit_search(
                model_family,
                X_train=X_train_exposure,
                y_train=y_train,
                folds=folds,
                cv_splits=args.cv_splits,
                random_state=args.random_state,
                n_jobs=1,
            )
            best_estimator = search.best_estimator_
            pred_arr = best_estimator.predict(X_val_exposure)
        else:
            # Fixed models: fit on full training split then predict.
            if model_family == "Multiple LR (Ridge, numeric)":
                numeric_cols = X_train_exposure.select_dtypes(include=["number", "bool"]).columns.tolist()
                pipe = Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                        ("model", Ridge(alpha=1.0)),
                    ]
                )
                pipe.fit(X_train_exposure[numeric_cols], y_train)
                pred_arr = pipe.predict(X_val_exposure[numeric_cols])
                meta = {"best_params": None}
            elif model_family == "Multiple LR (Ridge, full preprocess)":
                preproc = build_preprocessor(X_train_exposure)
                pipe = Pipeline([("preprocess", preproc), ("model", Ridge(alpha=1.0))])
                pipe.fit(X_train_exposure, y_train)
                pred_arr = pipe.predict(X_val_exposure)
                meta = {"best_params": None}
            elif model_family == "Simple LR (1 feat)":
                single_feature = choose_single_feature_for_simple_lr(X_train_exposure, exposure_set=exposure_set)
                imp = SimpleImputer(strategy="median")
                x_tr_s = imp.fit_transform(X_train_exposure[[single_feature]])
                x_va_s = imp.transform(X_val_exposure[[single_feature]])
                m_simple = LinearRegression().fit(x_tr_s, y_train)
                pred_arr = m_simple.predict(x_va_s)
                meta = {"best_params": None}
            else:
                raise ValueError(f"Unhandled fixed model: {model_family}")

        y_true_arr = y_val.to_numpy(dtype=float)
        pred_arr = np.asarray(pred_arr, dtype=float)

        rmse = float(np.sqrt(mean_squared_error(y_true_arr, pred_arr)))
        mae = float(mean_absolute_error(y_true_arr, pred_arr))
        r2 = float(r2_score(y_true_arr, pred_arr))
        rmse_ci_low, rmse_ci_high = bootstrap_rmse_ci(
            y_true_arr, pred_arr, n_boot=args.bootstrap_n, seed=args.random_state
        )

        metrics_df = pd.DataFrame(
            [
                {
                    "target": target,
                    "exposure_set": exposure_set,
                    "model": model_family,
                    "validation_mode": split_mode,
                    "rmse": rmse,
                    "mae": mae,
                    "r2": r2,
                    "rmse_ci_low": rmse_ci_low,
                    "rmse_ci_high": rmse_ci_high,
                    "n_rows": int(len(y_true_arr)),
                    **{k: v for k, v in meta.items() if k != "best_params"},
                }
            ]
        )
        metrics_df.to_csv(out_dir / "metrics.csv", index=False)

        pred_df = val_df.copy()
        pred_df = pred_df[["FIPS", "YEAR", "NAME", "state_fips", target]].copy()
        pred_df = pred_df.rename(columns={target: "actual"})
        pred_df["prediction"] = pred_arr
        pred_df["residual"] = pred_df["actual"] - pred_df["prediction"]
        pred_df.to_csv(out_dir / "predictions_validation_holdout.csv", index=False)

        if args.export_all_counties:
            # Build predictions for all available rows (train+validation+test).
            # We use split_mapping to avoid relying on file-specific quirks.
            df_all = pd.concat(
                [
                    pd.read_csv(REPO_ROOT / "data" / "train.csv"),
                    pd.read_csv(REPO_ROOT / "data" / "validation.csv"),
                    pd.read_csv(REPO_ROOT / "data" / "test.csv"),
                ],
                ignore_index=True,
            )
            df_all = df_all.loc[df_all[target].notna()].copy()
            df_all_eng = engineer_signal_isolation_features(df_all)
            X_cols_all = exposure_columns(train_eng, df_all_eng, exposure_set=exposure_set)
            X_all = df_all_eng[X_cols_all].copy()
            pred_all = (
                best_estimator.predict(X_all)
                if model_family in {"Ridge (tuned)", "Lasso (tuned)", "ElasticNet (tuned)", "XGBoost (tuned)"}
                else None
            )
            if pred_all is None:
                raise RuntimeError("export_all_counties currently supports tuned model families only.")

            pred_all_df = df_all[["FIPS", "YEAR", "NAME", "state_fips", target]].copy()
            pred_all_df = pred_all_df.rename(columns={target: "actual"})
            pred_all_df["prediction"] = np.asarray(pred_all, dtype=float)
            pred_all_df["residual"] = pred_all_df["actual"] - pred_all_df["prediction"]
            pred_all_df.to_csv(out_dir / "predictions_all_counties.csv", index=False)

        eval_out = run_regression_evaluation(
            y_true_arr,
            pred_arr,
            task="regression",
            X_test=X_meta.reset_index(drop=True),
            time_column="YEAR",
            top_n_errors=20,
        )
        save_figures(eval_out["figures"], out_dir / "figures")
        pd.DataFrame(eval_out["top_errors"]).to_csv(out_dir / "top_errors.csv", index=False)
        (out_dir / "interpretation.txt").write_text(
            eval_out.get("interpretation", "") + "\n\n" + eval_out.get("next_steps", ""),
            encoding="utf-8",
        )

        print(f"Wrote external holdout validation evaluation to: {out_dir}")
        return

    raise RuntimeError(f"Unhandled validation-set mode: {split_mode}")


if __name__ == "__main__":
    main()

