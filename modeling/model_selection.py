#!/usr/bin/env python3
"""
Train ridge and lasso baselines on the stratified county split outputs.

Example:
    python3 modeling/regression_baseline.py --target CASTHMA
    python3 modeling/regression_baseline.py --target COPD
    python3 modeling/regression_baseline.py --target both
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Lasso, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
RESULTS_DIR = REPO_ROOT / "modeling" / "results"

TARGET_PATHS = {
    "CASTHMA": {
        "train": DATA_DIR / "train_CASTHMA.csv",
        "test": DATA_DIR / "test_CASTHMA.csv",
    },
    "COPD": {
        "train": DATA_DIR / "train_COPD.csv",
        "test": DATA_DIR / "test_COPD.csv",
    },
}

DEFAULT_DROP_COLUMNS = {
    "index",
    "FIPS",
    "NAME",
    "state_fips",
    "CASTHMA",
    "COPD",
    "CSMOKING",
    "OBESITY",
    "DIABETES",
    "cat3_CASTHMA",
    "cat3_COPD",
}

ALPHA_GRID = np.logspace(-3, 3, 13)
RANDOM_STATE = 42


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        choices=["CASTHMA", "COPD", "both"],
        default="both",
        help="Target to model. Default trains both targets.",
    )
    parser.add_argument(
        "--cv-splits",
        type=int,
        default=5,
        help="Number of grouped CV folds inside the training data.",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=RESULTS_DIR,
        help="Directory for metrics, predictions, and coefficient outputs.",
    )
    return parser.parse_args()


def make_strata(y: pd.Series, n_bins: int = 5) -> pd.Series:
    n_unique = y.nunique(dropna=True)
    bins = max(2, min(n_bins, n_unique))
    return pd.qcut(y, q=bins, labels=False, duplicates="drop")


def choose_feature_columns(train_df: pd.DataFrame, target: str) -> list[str]:
    # Always drop both CASTHMA and COPD (and other non-features) so we never use
    # one outcome to predict the other or use the target as a feature.
    drop_columns = set(DEFAULT_DROP_COLUMNS)
    return [col for col in train_df.columns if col not in drop_columns]


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


def build_models(preprocessor: ColumnTransformer, cv_splits: list[tuple[np.ndarray, np.ndarray]]) -> dict[str, GridSearchCV]:
    ridge_pipeline = Pipeline(
        steps=[
            ("preprocess", preprocessor),
            ("model", Ridge()),
        ]
    )
    lasso_pipeline = Pipeline(
        steps=[
            ("preprocess", preprocessor),
            ("model", Lasso(max_iter=20000, random_state=RANDOM_STATE)),
        ]
    )

    return {
        "ridge": GridSearchCV(
            estimator=ridge_pipeline,
            param_grid={"model__alpha": ALPHA_GRID},
            cv=cv_splits,
            scoring="neg_root_mean_squared_error",
            n_jobs=None,
            refit=True,
        ),
        "lasso": GridSearchCV(
            estimator=lasso_pipeline,
            param_grid={"model__alpha": ALPHA_GRID},
            cv=cv_splits,
            scoring="neg_root_mean_squared_error",
            n_jobs=None,
            refit=True,
        ),
    }


def evaluate_model(model: GridSearchCV, X_test: pd.DataFrame, y_test: pd.Series) -> tuple[dict, np.ndarray]:
    predictions = model.predict(X_test)
    metrics = {
        "rmse": float(np.sqrt(mean_squared_error(y_test, predictions))),
        "mae": float(mean_absolute_error(y_test, predictions)),
        "r2": float(r2_score(y_test, predictions)),
    }
    return metrics, predictions


def extract_coefficients(model: GridSearchCV, top_n: int = 25) -> pd.DataFrame:
    feature_names = model.best_estimator_.named_steps["preprocess"].get_feature_names_out()
    coefficients = model.best_estimator_.named_steps["model"].coef_
    coef_df = pd.DataFrame(
        {
            "feature": feature_names,
            "coefficient": coefficients,
            "abs_coefficient": np.abs(coefficients),
        }
    ).sort_values("abs_coefficient", ascending=False)
    return coef_df.head(top_n)


def run_target(target: str, cv_splits: int, results_dir: Path) -> None:
    train_df = pd.read_csv(TARGET_PATHS[target]["train"])
    test_df = pd.read_csv(TARGET_PATHS[target]["test"])

    feature_columns = choose_feature_columns(train_df, target)
    X_train = train_df[feature_columns].copy()
    X_test = test_df[feature_columns].copy()
    y_train = train_df[target].copy()
    y_test = test_df[target].copy()
    groups = train_df["FIPS"].copy()
    strata = make_strata(y_train)
    cv_splitter = StratifiedGroupKFold(
        n_splits=cv_splits,
        shuffle=True,
        random_state=RANDOM_STATE,
    )
    fold_indices = list(cv_splitter.split(X_train, strata, groups))

    preprocessor = build_preprocessor(X_train)
    model_searches = build_models(preprocessor, fold_indices)

    target_dir = results_dir / target
    target_dir.mkdir(parents=True, exist_ok=True)

    summary_rows = []

    for model_name, search in model_searches.items():
        search.fit(X_train, y_train)
        metrics, predictions = evaluate_model(search, X_test, y_test)

        prediction_df = test_df[["FIPS", "YEAR", target]].copy()
        prediction_df = prediction_df.rename(columns={target: "actual"})
        prediction_df["prediction"] = predictions
        prediction_df["residual"] = prediction_df["actual"] - prediction_df["prediction"]
        prediction_df.to_csv(target_dir / f"{model_name}_predictions.csv", index=False)

        coef_df = extract_coefficients(search)
        coef_df.to_csv(target_dir / f"{model_name}_top_coefficients.csv", index=False)

        summary_rows.append(
            {
                "target": target,
                "model": model_name,
                "best_alpha": float(search.best_params_["model__alpha"]),
                "cv_rmse": float(-search.best_score_),
                **metrics,
                "n_train_rows": int(len(train_df)),
                "n_test_rows": int(len(test_df)),
                "n_features_raw": int(len(feature_columns)),
            }
        )

    summary_df = pd.DataFrame(summary_rows).sort_values("rmse")
    summary_df.to_csv(target_dir / "model_summary.csv", index=False)
    with (target_dir / "model_summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary_rows, f, indent=2)


def main() -> None:
    args = parse_args()
    targets = ["CASTHMA", "COPD"] if args.target == "both" else [args.target]

    for target in targets:
        run_target(target=target, cv_splits=args.cv_splits, results_dir=args.results_dir)


if __name__ == "__main__":
    main()
