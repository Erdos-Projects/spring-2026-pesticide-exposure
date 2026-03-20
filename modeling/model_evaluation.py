"""
Model evaluation pipeline: regression and classification.

Uses holdout/validation/test predictions only. Produces metrics, diagnostic
plots, subgroup analysis, top-error inspection, and a short interpretation.

Inputs (all optional except y_true, y_pred):
  - y_true, y_pred
  - y_pred_proba (classification)
  - X_test (for subgroups, time, top-error features)
  - subgroup_columns (list of names in X_test or dict name -> series)
  - time_column (name in X_test or series)
  - sample_weights
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# -----------------------------------------------------------------------------
# Task detection
# -----------------------------------------------------------------------------

def detect_task(y_true: pd.Series | np.ndarray) -> str:
    """Infer task: regression, binary, or multiclass from y_true."""
    y = np.asarray(y_true).ravel()
    if not np.issubdtype(y.dtype, np.number) and not pd.api.types.is_numeric_dtype(pd.Series(y)):
        try:
            y = pd.Series(y).astype("category").cat.codes.values
        except Exception:
            return "unknown"
    n_unique = len(np.unique(y[~np.isnan(y)]))
    if n_unique <= 2:
        return "binary"
    if n_unique <= 20 and np.all(np.equal(np.mod(y, 1), 0)):
        return "multiclass"
    return "regression"


# -----------------------------------------------------------------------------
# Regression evaluation
# -----------------------------------------------------------------------------

def _safe_mape(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float | None, str | None]:
    """Compute MAPE only when sensible (no zeros/near-zero). Returns (value, warning)."""
    y_true = np.asarray(y_true).ravel().astype(float)
    y_pred = np.asarray(y_pred).ravel().astype(float)
    near_zero = np.abs(y_true) < 1e-6
    if np.any(near_zero):
        return None, "MAPE skipped: target has zeros or near-zero values."
    err = np.abs(y_true - y_pred) / np.abs(y_true)
    return float(np.nanmean(err)) * 100, None


def regression_metrics(
    y_true: np.ndarray | pd.Series,
    y_pred: np.ndarray | pd.Series,
    sample_weight: np.ndarray | pd.Series | None = None,
) -> pd.DataFrame:
    """Compute MAE, RMSE, R²; optionally median AE and MAPE."""
    y_true = np.asarray(y_true).ravel().astype(float)
    y_pred = np.asarray(y_pred).ravel().astype(float)
    if sample_weight is not None:
        sw = np.asarray(sample_weight).ravel()
    else:
        sw = np.ones_like(y_true)
    mask = ~(np.isnan(y_true) | np.isnan(y_pred))
    y_true, y_pred, sw = y_true[mask], y_pred[mask], sw[mask]
    n = np.sum(sw)
    if n == 0:
        return pd.DataFrame([{"metric": "error", "value": np.nan}])

    mae = np.average(np.abs(y_true - y_pred), weights=sw)
    rmse = np.sqrt(np.average((y_true - y_pred) ** 2, weights=sw))
    ss_res = np.average(sw * (y_true - y_pred) ** 2)
    ss_tot = np.average(sw * (y_true - np.average(y_true, weights=sw)) ** 2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else np.nan
    med_ae = np.median(np.abs(y_true - y_pred))

    rows = [
        {"metric": "MAE", "value": mae},
        {"metric": "RMSE", "value": rmse},
        {"metric": "R²", "value": r2},
        {"metric": "Median AE", "value": med_ae},
    ]
    mape_val, mape_warn = _safe_mape(y_true, y_pred)
    if mape_warn:
        warnings.warn(mape_warn, UserWarning)
    elif mape_val is not None:
        rows.append({"metric": "MAPE (%)", "value": mape_val})
    return pd.DataFrame(rows)


def _plot_pred_vs_actual(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    ax: plt.Axes | None = None,
    alpha: float = 0.5,
    hexbin: bool = False,
) -> plt.Axes:
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(6, 6))
    if hexbin and len(y_true) > 500:
        ax.hexbin(y_true, y_pred, gridsize=30, mincnt=1, cmap="Blues")
    else:
        ax.scatter(y_true, y_pred, alpha=alpha, s=20)
    lims = [min(y_true.min(), y_pred.min()), max(y_true.max(), y_pred.max())]
    ax.plot(lims, lims, "k--", lw=2, label="45° reference")
    ax.set_xlabel("Actual")
    ax.set_ylabel("Predicted")
    ax.set_title("Predicted vs actual")
    ax.set_aspect("equal")
    ax.legend(loc="upper left")
    return ax


def _plot_residuals_vs_predicted(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    ax: plt.Axes | None = None,
    alpha: float = 0.5,
) -> plt.Axes:
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(6, 4))
    resid = y_true - y_pred
    ax.scatter(y_pred, resid, alpha=alpha, s=20)
    ax.axhline(0, color="k", ls="--", lw=1)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("Residual (actual − predicted)")
    ax.set_title("Residuals vs predicted")
    return ax


def _plot_residual_distribution(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    ax: plt.Axes | None = None,
) -> plt.Axes:
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(5, 4))
    resid = y_true - y_pred
    ax.hist(resid, bins=min(50, max(10, len(resid) // 20)), density=True, alpha=0.7, edgecolor="k", label="Residuals")
    ax.axvline(0, color="k", ls="--", lw=2)
    ax.set_xlabel("Residual")
    ax.set_ylabel("Density")
    ax.set_title("Residual distribution")
    ax.legend()
    return ax


def _plot_error_by_subgroup(
    subgroup_stats: pd.DataFrame,
    subgroup_name: str,
    ax: plt.Axes | None = None,
    metric: str = "MAE",
) -> plt.Axes:
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(8, max(4, len(subgroup_stats) * 0.3)))
    df = subgroup_stats.sort_values(metric, ascending=True)
    y_pos = np.arange(len(df))
    ax.barh(y_pos, df[metric], align="center")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(df.index.astype(str), fontsize=9)
    ax.set_xlabel(metric)
    ax.set_title(f"Error by subgroup: {subgroup_name}")
    return ax


def _plot_actual_vs_pred_over_time(
    time_values: np.ndarray | pd.Series,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    ax: plt.Axes | None = None,
    time_label: str = "Time",
) -> plt.Axes:
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(10, 4))
    ax.plot(time_values, y_true, "o-", label="Actual", alpha=0.7, ms=3)
    ax.plot(time_values, y_pred, "s-", label="Predicted", alpha=0.7, ms=3)
    ax.set_xlabel(time_label)
    ax.set_ylabel("Value")
    ax.set_title("Actual vs predicted over time")
    ax.legend()
    ax.grid(True, alpha=0.3)
    return ax


def regression_subgroup_stats(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    groups: np.ndarray | pd.Series,
    sample_weight: np.ndarray | None = None,
) -> pd.DataFrame:
    """
    Per-group summary for regression.

    Residual is defined as (actual - predicted):
      - positive residual => underprediction
      - negative residual => overprediction
    """
    y_true = np.asarray(y_true).ravel()
    y_pred = np.asarray(y_pred).ravel()
    # Coerce to a pandas string/object series so mixed labels and missing values
    # do not crash np.unique() on heterogeneous arrays.
    groups = pd.Series(groups).astype("string").fillna("missing").astype(str).to_numpy().ravel()
    if sample_weight is None:
        sample_weight = np.ones_like(y_true)
    else:
        sample_weight = np.asarray(sample_weight).ravel()
    mask = ~(np.isnan(y_true) | np.isnan(y_pred))
    rows = []
    for g in pd.unique(groups):
        m = mask & (groups == g)
        if m.sum() < 5:
            rows.append(
                {
                    "group": g,
                    "n": int(m.sum()),
                    "mean_actual": np.nan,
                    "mean_predicted": np.nan,
                    "MAE": np.nan,
                    "RMSE": np.nan,
                    "mean_residual": np.nan,
                    "underprediction_rate": np.nan,
                    "note": "low_support",
                }
            )
            continue
        yt, yp, sw = y_true[m], y_pred[m], sample_weight[m]
        resid = yt - yp
        mae = np.average(np.abs(yt - yp), weights=sw)
        rmse = np.sqrt(np.average((yt - yp) ** 2, weights=sw))
        mean_res = np.average(resid, weights=sw)
        under_rate = np.average((resid > 0).astype(float), weights=sw)
        rows.append(
            {
                "group": g,
                "n": int(m.sum()),
                "mean_actual": np.average(yt, weights=sw),
                "mean_predicted": np.average(yp, weights=sw),
                "MAE": mae,
                "RMSE": rmse,
                "mean_residual": mean_res,
                "underprediction_rate": under_rate,
                "note": "",
            }
        )
    df = pd.DataFrame(rows).set_index("group")
    return df


def regression_top_errors(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    X_test: pd.DataFrame | None = None,
    top_n: int = 20,
) -> pd.DataFrame:
    """Rows with largest absolute residuals; optionally join key features."""
    y_true = np.asarray(y_true).ravel()
    y_pred = np.asarray(y_pred).ravel()
    resid = np.abs(y_true - y_pred)
    idx = np.argsort(resid)[::-1][:top_n]
    out = pd.DataFrame({
        "actual": y_true[idx],
        "predicted": y_pred[idx],
        "residual": (y_true - y_pred)[idx],
        "abs_residual": resid[idx],
    })
    if X_test is not None and len(X_test) == len(y_true):
        # Attach a few key columns if present (avoid huge tables)
        key_cols = [c for c in ["FIPS", "YEAR", "NAME", "state_fips"] if c in X_test.columns][:4]
        if key_cols:
            out = out.reset_index(drop=True)
            for c in key_cols:
                out[c] = X_test.iloc[idx][c].values
    return out


def run_regression_evaluation(
    y_true: np.ndarray | pd.Series,
    y_pred: np.ndarray | pd.Series,
    *,
    X_test: pd.DataFrame | None = None,
    subgroup_columns: list[str] | dict[str, np.ndarray] | None = None,
    time_column: str | pd.Series | None = None,
    sample_weight: np.ndarray | pd.Series | None = None,
    top_n_errors: int = 20,
    min_subgroup_support: int = 5,
    figsize_pred: tuple[int, int] = (6, 6),
    figsize_residual: tuple[int, int] = (6, 4),
    figsize_subgroup: tuple[int, int] = (8, 5),
    figsize_time: tuple[int, int] = (10, 4),
) -> dict[str, Any]:
    """
    Full regression evaluation: metrics, plots, subgroup table, top errors, interpretation.

    Returns dict with:
      - task_detected
      - metrics (DataFrame)
      - figures (list of (fig, title) for saving)
      - subgroup_tables (dict column_name -> DataFrame)
      - top_errors (DataFrame)
      - interpretation (str)
      - next_steps (str)
    """
    y_true = np.asarray(y_true).ravel()
    y_pred = np.asarray(y_pred).ravel()
    n = len(y_true)
    mask = ~(np.isnan(y_true) | np.isnan(y_pred))
    y_true, y_pred = y_true[mask], y_pred[mask]
    if len(y_true) < 10:
        warnings.warn("Very few valid points after dropping NaN; metrics may be unstable.", UserWarning)

    out = {
        "task_detected": "regression",
        "metrics": None,
        "figures": [],
        "subgroup_tables": {},
        "top_errors": None,
        "interpretation": "",
        "next_steps": "",
    }

    # 1) Metrics
    sw = None
    if sample_weight is not None:
        sw = np.asarray(sample_weight).ravel()[mask]
    out["metrics"] = regression_metrics(y_true, y_pred, sample_weight=sw)

    # 2) Core plots
    fig1, axes = plt.subplots(1, 3, figsize=(14, 5))
    _plot_pred_vs_actual(y_true, y_pred, ax=axes[0], alpha=0.5, hexbin=(n > 500))
    _plot_residuals_vs_predicted(y_true, y_pred, ax=axes[1], alpha=0.5)
    _plot_residual_distribution(y_true, y_pred, ax=axes[2])
    plt.tight_layout()
    out["figures"].append((fig1, "regression_core_diagnostics"))

    # 3) Subgroup analysis
    if subgroup_columns is not None:
        if isinstance(subgroup_columns, dict):
            for name, groups in subgroup_columns.items():
                groups = np.asarray(groups).ravel()
                if len(groups) != n:
                    continue
                groups = groups[mask]
                stats = regression_subgroup_stats(y_true, y_pred, groups, sample_weight=sw)
                low = stats.get("n", pd.Series(dtype=int)) < min_subgroup_support
                if low.any():
                    stats = stats.copy()
                    stats.loc[low, "note"] = "low_support"
                out["subgroup_tables"][name] = stats
                fig_s, ax_s = plt.subplots(1, 1, figsize=figsize_subgroup)
                _plot_error_by_subgroup(stats, name, ax=ax_s, metric="MAE")
                plt.tight_layout()
                out["figures"].append((fig_s, f"error_by_subgroup_{name}"))
        elif X_test is not None:
            for col in subgroup_columns:
                if col not in X_test.columns:
                    continue
                groups_full = X_test[col].values
                if len(groups_full) != len(mask):
                    continue
                groups = groups_full[mask]
                stats = regression_subgroup_stats(y_true, y_pred, groups, sample_weight=sw)
                if "n" in stats.columns:
                    low = stats["n"] < min_subgroup_support
                    stats = stats.copy()
                    stats.loc[low, "note"] = "low_support"
                out["subgroup_tables"][col] = stats
                fig_s, ax_s = plt.subplots(1, 1, figsize=figsize_subgroup)
                _plot_error_by_subgroup(stats, col, ax=ax_s, metric="MAE")
                plt.tight_layout()
                out["figures"].append((fig_s, f"error_by_subgroup_{col}"))

    # 4) Time-based
    if time_column is not None:
        if isinstance(time_column, (pd.Series, np.ndarray)):
            time_vals = np.asarray(time_column).ravel()[mask]
        elif X_test is not None and time_column in X_test.columns:
            time_vals = X_test[time_column].values[mask]
        else:
            time_vals = None
        if time_vals is not None and len(time_vals) == len(y_true):
            fig_t, ax_t = plt.subplots(1, 1, figsize=figsize_time)
            _plot_actual_vs_pred_over_time(time_vals, y_true, y_pred, ax=ax_t, time_label=time_column if isinstance(time_column, str) else "Time")
            plt.tight_layout()
            out["figures"].append((fig_t, "actual_vs_pred_over_time"))

    # 5) Top errors
    if X_test is not None and len(X_test) == len(mask):
        X_align = X_test.iloc[mask].reset_index(drop=True)
    else:
        X_align = None
    out["top_errors"] = regression_top_errors(y_true, y_pred, X_test=X_align, top_n=top_n_errors)

    # 6) Interpretation
    mae = out["metrics"].set_index("metric").loc["MAE", "value"]
    rmse = out["metrics"].set_index("metric").loc["RMSE", "value"]
    r2 = out["metrics"].set_index("metric").loc["R²", "value"]
    mean_res = np.mean(y_true - y_pred)
    resid = y_true - y_pred
    try:
        hetero = np.corrcoef(y_pred, resid**2)[0, 1] if len(y_pred) > 2 else 0.0
    except Exception:
        hetero = 0.0

    interp = []
    interp.append("1. Overall: " + (
        f"R² = {r2:.3f}; RMSE = {rmse:.3f}, MAE = {mae:.3f}. "
        + ("Model explains a substantial share of variance." if r2 > 0.5 else "Model has limited explanatory power.")
    ))
    interp.append("2. Bias: " + (
        f"Mean residual = {mean_res:.3f}. "
        + ("Residuals are roughly centered." if np.abs(mean_res) < 0.1 * rmse else "Substantial systematic bias (under/over prediction).")
    ))
    interp.append("3. Residuals: " + (
        "Residuals vs predicted suggests heteroskedasticity (variance changes with level)." if abs(hetero) > 0.2 else "Residual spread does not strongly depend on predicted value."
    ))
    interp.append("4. Subgroups: " + (
        "Subgroup MAE varies; check tables for groups with high error or low support." if out["subgroup_tables"] else "No subgroup columns provided."
    ))
    interp.append("5. Trust: " + (
        "Use metrics, residual plots, and subgroup results to judge whether the model is stable and fair enough for deployment."
    ))
    out["interpretation"] = "\n".join(interp)

    out["next_steps"] = (
        "• Investigate top-error rows for outliers or data issues.\n"
        "• If heteroskedasticity is present, consider transforms or robust metrics.\n"
        "• If subgroups differ sharply, consider stratified models or fairness constraints.\n"
        "• Re-evaluate on a fresh holdout if possible."
    )
    return out


# -----------------------------------------------------------------------------
# Classification stubs (required by spec; implement when needed)
# -----------------------------------------------------------------------------

def run_classification_evaluation(
    y_true: np.ndarray | pd.Series,
    y_pred: np.ndarray | pd.Series,
    *,
    y_pred_proba: np.ndarray | None = None,
    X_test: pd.DataFrame | None = None,
    subgroup_columns: list[str] | None = None,
    time_column: str | None = None,
    sample_weight: np.ndarray | None = None,
) -> dict[str, Any]:
    """Placeholder: classification evaluation not implemented in this module."""
    return {
        "task_detected": "binary_or_multiclass",
        "metrics": pd.DataFrame([{"metric": "note", "value": "Classification evaluation not implemented; use a classification-specific pipeline."}]),
        "figures": [],
        "subgroup_tables": {},
        "top_errors": None,
        "interpretation": "N/A",
        "next_steps": "Implement binary/multiclass metrics and plots (confusion matrix, PR curve, calibration, etc.).",
    }


# -----------------------------------------------------------------------------
# Main entry
# -----------------------------------------------------------------------------

def evaluate(
    y_true: np.ndarray | pd.Series,
    y_pred: np.ndarray | pd.Series,
    *,
    task: str | None = None,
    y_pred_proba: np.ndarray | None = None,
    X_test: pd.DataFrame | None = None,
    subgroup_columns: list[str] | dict | None = None,
    time_column: str | pd.Series | None = None,
    sample_weight: np.ndarray | pd.Series | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Run the appropriate evaluation workflow.

    task: "regression" | "binary" | "multiclass" | None (auto-detect from y_true).
    """
    if task is None:
        task = detect_task(y_true)
    if task == "regression":
        return run_regression_evaluation(
            y_true, y_pred,
            X_test=X_test,
            subgroup_columns=subgroup_columns,
            time_column=time_column,
            sample_weight=sample_weight,
            **kwargs,
        )
    return run_classification_evaluation(
        y_true, y_pred,
        y_pred_proba=y_pred_proba,
        X_test=X_test,
        subgroup_columns=subgroup_columns,
        time_column=time_column,
        sample_weight=sample_weight,
    )
