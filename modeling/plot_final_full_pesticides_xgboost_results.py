#!/usr/bin/env python3
"""
Plot final Full pesticides raw XGBoost results.

Creates a 2x2 grid:
  - Rows: CASTHMA, COPD
  - Cols: cross-validation (OOF) vs final validation holdout

Source files:
  - CV: modeling/results/{target}/xgboost_predictions_Full_pesticides_raw.csv
  - Final validation: modeling/results/{target}/validation_eval_Full_pesticides_raw__XGBoost_(tuned)/predictions_validation_holdout.csv
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

try:
    import matplotlib.pyplot as plt
except ModuleNotFoundError:  # pragma: no cover
    plt = None


REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = REPO_ROOT / "modeling" / "results"


def load_predictions_csv(path: Path) -> tuple[list[float], list[float]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing expected file: {path}")
    y_true: list[float] = []
    y_pred: list[float] = []
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        required = {"actual", "prediction"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path} missing columns: {sorted(missing)} (found {reader.fieldnames})")
        for row in reader:
            try:
                yt = float(row["actual"])
                yp = float(row["prediction"])
            except (TypeError, ValueError):
                continue
            if math.isnan(yt) or math.isnan(yp):
                continue
            y_true.append(yt)
            y_pred.append(yp)
    return y_true, y_pred


def regression_metrics(y_true: list[float], y_pred: list[float]) -> dict[str, float]:
    if not y_true:
        return {"r2": float("nan"), "rmse": float("nan"), "mae": float("nan")}
    n = len(y_true)
    errors = [yt - yp for yt, yp in zip(y_true, y_pred)]
    abs_errors = [abs(e) for e in errors]

    mae = sum(abs_errors) / n
    rmse = math.sqrt(sum(e * e for e in errors) / n)

    mean_y = sum(y_true) / n
    ss_res = sum((yt - yp) ** 2 for yt, yp in zip(y_true, y_pred))
    ss_tot = sum((yt - mean_y) ** 2 for yt in y_true)
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else float("nan")

    return {"r2": float(r2), "rmse": float(rmse), "mae": float(mae)}


def plot_pred_vs_actual(ax, y_true: list[float], y_pred: list[float], title: str) -> None:
    m = regression_metrics(y_true, y_pred)

    ax.scatter(y_true, y_pred, s=18, alpha=0.5)
    lims = [min(min(y_true), min(y_pred)), max(max(y_true), max(y_pred))]
    ax.plot(lims, lims, "k--", lw=2, label="45° reference")
    ax.set_xlabel("Actual")
    ax.set_ylabel("Predicted")
    ax.set_title(
        f"{title}\nR2={m['r2']:.3f} | RMSE={m['rmse']:.3f} | MAE={m['mae']:.3f}",
        fontsize=10,
    )
    ax.set_aspect("equal", adjustable="box")
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.25)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULTS_ROOT / "final_full_pesticides_xgboost_cv_vs_external_holdout.png",
        help="Where to save the plot.",
    )
    parser.add_argument("--dpi", type=int, default=180, help="Figure DPI.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    targets = ["CASTHMA", "COPD"]
    cv_paths = {
        "CASTHMA": RESULTS_ROOT / "CASTHMA" / "xgboost_predictions_Full_pesticides_raw.csv",
        "COPD": RESULTS_ROOT / "COPD" / "xgboost_predictions_Full_pesticides_raw.csv",
    }
    holdout_paths = {
        "CASTHMA": RESULTS_ROOT
        / "CASTHMA"
        / "validation_eval_Full_pesticides_raw__XGBoost_(tuned)"
        / "predictions_validation_holdout.csv",
        "COPD": RESULTS_ROOT
        / "COPD"
        / "validation_eval_Full_pesticides_raw__XGBoost_(tuned)"
        / "predictions_validation_holdout.csv",
    }

    if plt is None:
        raise SystemExit(
            "matplotlib is required to generate the plot. "
            "Install it in the environment you use for modeling notebooks."
        )

    fig, axes = plt.subplots(2, 2, figsize=(13, 10))

    for row, target in enumerate(targets):
        y_true_cv, y_pred_cv = load_predictions_csv(cv_paths[target])
        plot_pred_vs_actual(axes[row, 0], y_true_cv, y_pred_cv, f"{target} - Cross validation (OOF)")

        y_true_h, y_pred_h = load_predictions_csv(holdout_paths[target])
        plot_pred_vs_actual(axes[row, 1], y_true_h, y_pred_h, f"{target} - Final validation (holdout)")

    plt.suptitle("Final Full pesticides raw: XGBoost tuned", fontsize=16)
    plt.tight_layout(rect=[0, 0.02, 1, 0.97])

    fig.savefig(args.output, dpi=args.dpi)
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()

