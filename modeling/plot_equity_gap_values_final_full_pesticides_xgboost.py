#!/usr/bin/env python3
"""
Equity gap plot for final validation (external_holdout) predictions.

Generates a compact SVG (tight canvas height, centered title) showing MAE "gap"
(group MAE - overall MAE) for
key groups for:
  - Asthma: CASTHMA
  - COPD: COPD

Group definitions (based on columns available in `data/joint_county_year_2018_2019.csv`):
  - Poverty proxy: `median_income` tertiles (Low / Mid / High)
  - Urban-rural proxy: `nchs_urban_rural` NCHS codes
      * Urban (metro): codes 1-4
      * Rural (non-metro): codes 5-6
  - Majority-BIPOC: pct_white < 0.5  vs pct_white >= 0.5

This script avoids numpy/pandas/matplotlib so it can run in minimal Python
environments; it renders SVG directly.

**Website:** Model specifics embeds this chart as **inline SVG** in
``web/model-specifics.html`` (external ``<img src="*.svg">`` is unreliable on
some browsers / GitHub Pages). After regenerating, replace the inline
``<svg class="equity-gap-chart" …>…</svg>`` block with the new SVG body (omit
the XML declaration), or copy from ``web/assets/model/equity_gap_values_final_full_pesticides_xgboost.svg``.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = REPO_ROOT / "data" / "joint_county_year_2018_2019.csv"

RESULTS_ROOT = REPO_ROOT / "modeling" / "results"

PRED_PATHS = {
    "CASTHMA": RESULTS_ROOT
    / "CASTHMA"
    / "validation_eval_Full_pesticides_raw__XGBoost_(tuned)"
    / "predictions_validation_holdout.csv",
    "COPD": RESULTS_ROOT
    / "COPD"
    / "validation_eval_Full_pesticides_raw__XGBoost_(tuned)"
    / "predictions_validation_holdout.csv",
}

OUT_SVG = RESULTS_ROOT / "equity_gap_values_final_full_pesticides_xgboost.svg"
OUT_SVG_SQUARE = RESULTS_ROOT / "equity_gap_values_final_full_pesticides_xgboost_square.svg"


def _read_header_and_indices(path: Path, needed: set[str]) -> tuple[list[str], dict[str, int]]:
    with path.open("r", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
    indices = {}
    for i, name in enumerate(header):
        if name in needed:
            indices[name] = i
    missing = needed - set(indices.keys())
    if missing:
        raise ValueError(f"{path} missing needed columns: {sorted(missing)}")
    return header, indices


def load_group_lookup(joint_csv: Path) -> dict[tuple[int, int], dict[str, float]]:
    needed = {"FIPS", "YEAR", "median_income", "nchs_urban_rural", "pct_white"}
    _, idx = _read_header_and_indices(joint_csv, needed)

    out: dict[tuple[int, int], dict[str, float]] = {}
    with joint_csv.open("r", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        # Map indices for required fields
        for row in reader:
            if not row:
                continue
            try:
                fips = int(row[idx["FIPS"]])
                year = int(row[idx["YEAR"]])
            except (ValueError, TypeError):
                continue

            def parse_float(col: str) -> float | None:
                v = row[idx[col]].strip() if idx[col] < len(row) else ""
                if v == "":
                    return None
                try:
                    return float(v)
                except ValueError:
                    return None

            median_income = parse_float("median_income")
            nchs_urban_rural = parse_float("nchs_urban_rural")
            pct_white = parse_float("pct_white")

            if nchs_urban_rural is None or median_income is None or pct_white is None:
                continue

            out[(fips, year)] = {
                "median_income": float(median_income),
                "nchs_urban_rural": float(nchs_urban_rural),
                "pct_white": float(pct_white),
            }
    return out


def load_holdout_predictions(pred_csv: Path) -> list[dict[str, float]]:
    needed = {"FIPS", "YEAR", "actual", "prediction"}
    _, idx = _read_header_and_indices(pred_csv, needed)

    rows: list[dict[str, float]] = []
    with pred_csv.open("r", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if not row:
                continue
            try:
                fips = int(row[idx["FIPS"]])
                year = int(row[idx["YEAR"]])
                actual = float(row[idx["actual"]])
                pred = float(row[idx["prediction"]])
            except (ValueError, TypeError):
                continue
            if math.isnan(actual) or math.isnan(pred):
                continue
            abs_err = abs(actual - pred)
            rows.append({"fips": float(fips), "year": float(year), "abs_err": float(abs_err)})
    return rows


def quantile(sorted_vals: list[float], q: float) -> float:
    """Linear interpolation quantile with q in [0,1]."""
    if not sorted_vals:
        return float("nan")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    q = min(1.0, max(0.0, q))
    pos = q * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    frac = pos - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def compute_group_gaps(
    *,
    target: str,
    predictions: list[dict[str, float]],
    group_lookup: dict[tuple[int, int], dict[str, float]],
) -> tuple[list[dict[str, object]], float]:
    # Attach group labels + compute overall MAE across rows with complete group info.
    joined: list[dict[str, object]] = []
    abs_errs: list[float] = []
    incomes: list[float] = []
    for r in predictions:
        fips_i = int(r["fips"])
        year_i = int(r["year"])
        g = group_lookup.get((fips_i, year_i))
        if g is None:
            continue
        abs_err = float(r["abs_err"])
        joined.append(
            {
                "abs_err": abs_err,
                "median_income": float(g["median_income"]),
                "nchs_urban_rural": float(g["nchs_urban_rural"]),
                "pct_white": float(g["pct_white"]),
            }
        )
        abs_errs.append(abs_err)
        incomes.append(float(g["median_income"]))

    if not joined:
        raise RuntimeError(f"No joined rows for {target}; check input CSV columns/keys.")

    overall_mae = sum(abs_errs) / len(abs_errs)

    # Poverty proxy bins: tertiles
    s_incomes = sorted(incomes)
    q1 = quantile(s_incomes, 1 / 3)
    q2 = quantile(s_incomes, 2 / 3)

    def poverty_bin(income: float) -> str:
        if income <= q1:
            return "Low income"
        if income <= q2:
            return "Mid income"
        return "High income"

    def urban_rural_bin(code: float) -> str:
        # NCHS Urban-Rural Classification Scheme for Counties:
        # codes 1-4 are metro categories; 5-6 are non-metro.
        try:
            c_int = int(code)
        except ValueError:
            return "Unknown"
        if c_int <= 4:
            return "Urban (metro)"
        return "Rural (non-metro)"

    def majority_bipoc(pct_white: float) -> str:
        # `pct_white` is stored as a percent (0-100) in the joint county dataset.
        return "Majority-BIPOC" if pct_white < 50.0 else "Majority-white"

    group_order = [
        "Low income",
        "Mid income",
        "High income",
        "Urban (metro)",
        "Rural (non-metro)",
        "Majority-BIPOC",
        "Majority-white",
    ]
    group_map = {
        "Low income": [],
        "Mid income": [],
        "High income": [],
        "Urban (metro)": [],
        "Rural (non-metro)": [],
        "Majority-BIPOC": [],
        "Majority-white": [],
    }

    # Aggregate absolute error for each group label.
    # Note: each row contributes to multiple proxy groupings, so the groups here
    # are evaluated independently (not a single intersection).
    for j in joined:
        mae = float(j["abs_err"])
        group_map[poverty_bin(float(j["median_income"]))].append(mae)
        group_map[urban_rural_bin(float(j["nchs_urban_rural"]))].append(mae)
        group_map[majority_bipoc(float(j["pct_white"]))].append(mae)

    group_stats: list[dict[str, object]] = []
    for g in group_order:
        vals = group_map[g]
        if not vals:
            group_stats.append({"group": g, "n": 0, "mae": float("nan"), "gap": float("nan")})
            continue
        mae_g = sum(vals) / len(vals)
        gap = mae_g - overall_mae
        group_stats.append({"group": g, "n": len(vals), "mae": mae_g, "gap": gap})

    return group_stats, overall_mae


def render_svg(
    *,
    out_svg: Path,
    panels: list[tuple[str, list[dict[str, object]]]],
    canvas_width: int,
    canvas_height: int | None = None,
) -> None:
    """Write SVG. If ``canvas_height`` is None, height is computed from content (no extra bottom margin)."""
    width = canvas_width
    margin = 40

    # Compute global scale per-panel for readability.
    panel_w = (width - 3 * margin) // 2
    n_stats = len(panels[0][1])
    bar_h = 46
    top_y = 110

    def fmt_gap(x: float) -> str:
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return "n/a"
        return f"{x:+.3f}"

    body_parts: list[str] = []
    # Use entity so inline SVG in HTML is valid (raw "<" would start a bogus tag).
    proxies_note = "Proxies: income tertiles; metro vs non-metro; Majority-BIPOC (pct_white&lt;50%)."

    # Baseline y start and bar layout
    left_x = margin
    right_x = margin + panel_w + margin

    # Footnote sits just below the bar block; card must extend past text descenders (11px muted).
    footnote_y = top_y + 55 + n_stats * bar_h + 18
    card_top = top_y - 25
    min_card_for_bars = bar_h * n_stats + 120
    min_card_for_footnote = int(footnote_y - card_top + 28)
    card_height = max(min_card_for_bars, min_card_for_footnote)

    for pi, (title, stats) in enumerate(panels):
        x0 = left_x if pi == 0 else right_x
        y0 = top_y

        body_parts.append(
            f'<rect x="{x0 - 10}" y="{card_top}" width="{panel_w + 20}" height="{card_height}" rx="14" fill="#ffffff" stroke="#e5e7eb"/>'
        )
        body_parts.append(f'<text x="{x0}" y="{y0}" class="eqg-panelTitle">{title}</text>')
        body_parts.append(
            f'<text x="{x0}" y="{y0 + 20}" class="eqg-muted">Positive gap = worse error for that group</text>'
        )

        # Determine max abs gap in this panel
        gaps: list[float] = []
        for s in stats:
            gap = s.get("gap")  # type: ignore[attr-defined]
            if isinstance(gap, float) and not math.isnan(gap):
                gaps.append(float(gap))
        max_abs = max([abs(g) for g in gaps] + [0.001])

        # Bar axis
        baseline_x = x0 + panel_w * 0.52
        bar_max_w = panel_w * 0.40

        for i, s in enumerate(stats):
            y = y0 + 55 + i * bar_h
            group = str(s["group"])
            n = int(s["n"])
            gap = s["gap"]
            mae = s["mae"]
            gap_f = float(gap) if isinstance(gap, float) and not math.isnan(gap) else float("nan")

            # Axis baseline
            if i == 0:
                body_parts.append(
                    f'<line x1="{baseline_x}" y1="{y0 + 40}" x2="{baseline_x}" y2="{y0 + 40 + bar_h*len(stats)}" stroke="#9ca3af" stroke-dasharray="4 4"/>'
                )

            # Bar geometry
            if not math.isnan(gap_f):
                bar_w = (abs(gap_f) / max_abs) * bar_max_w
                if gap_f >= 0:
                    x_bar = baseline_x
                    fill = "#f59e0b"
                else:
                    x_bar = baseline_x - bar_w
                    fill = "#10b981"

                body_parts.append(
                    f'<rect x="{x_bar}" y="{y - 14}" width="{bar_w}" height="28" rx="8" fill="{fill}" opacity="0.9"/>'
                )

            # Labels
            body_parts.append(f'<text x="{x0 + 10}" y="{y + 4}" class="eqg-label">{group}</text>')
            body_parts.append(
                f'<text x="{x0 + panel_w - 10}" y="{y + 4}" class="eqg-num" text-anchor="end">gap={fmt_gap(gap_f)} (n={n})</text>'
            )

        body_parts.append(
            f'<text x="{x0}" y="{footnote_y}" class="eqg-muted">{proxies_note}</text>'
        )

    # Tight canvas: end just below the cards (footnote is inside the card); small outer margin only.
    panel_card_bottom = card_top + card_height
    content_bottom = panel_card_bottom + 14
    height = int(content_bottom + 12) if canvas_height is None else int(canvas_height)

    # Class names are prefixed so inline SVG on the site does not pick up global page CSS.
    style_block = """
  <style>
    .eqg-title { font: 700 18px Arial, Helvetica, sans-serif; fill: #111827; }
    .eqg-subtitle { font: 400 12px Arial, Helvetica, sans-serif; fill: #374151; }
    .eqg-panelTitle { font: 700 14px Arial, Helvetica, sans-serif; fill: #111827; }
    .eqg-label { font: 400 12px Arial, Helvetica, sans-serif; fill: #111827; }
    .eqg-muted { font: 400 11px Arial, Helvetica, sans-serif; fill: #6b7280; }
    .eqg-num { font: 700 12px Arial, Helvetica, sans-serif; fill: #111827; }
  </style>
    """.strip()
    cx = width // 2
    title_lines = [
        f'<text x="{cx}" y="30" class="eqg-title" text-anchor="middle">Equity gap (Final validation holdout): MAE gaps by key groups</text>',
        f'<text x="{cx}" y="52" class="eqg-subtitle" text-anchor="middle">Gap = group MAE - overall MAE (within each condition). Poverty proxy uses median income tertiles.</text>',
    ]
    full_svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" class="equity-gap-chart" width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n'
        # Opaque backdrop so title/subtitle (dark text) stay visible on dark-themed sites (e.g. model-specifics).
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>\n'
        f"{style_block}\n"
        + "\n".join(title_lines)
        + "\n"
        + "\n".join(body_parts)
        + "\n</svg>"
    )

    out_svg.parent.mkdir(parents=True, exist_ok=True)
    out_svg.write_text(full_svg, encoding="utf-8")


def main() -> None:
    group_lookup = load_group_lookup(DATA_PATH)
    panels: list[tuple[str, list[dict[str, object]]]] = []

    for target in ["CASTHMA", "COPD"]:
        pred_path = PRED_PATHS[target]
        if not pred_path.exists():
            raise FileNotFoundError(f"Missing predictions file: {pred_path}")
        predictions = load_holdout_predictions(pred_path)
        group_stats, overall_mae = compute_group_gaps(
            target=target,
            predictions=predictions,
            group_lookup=group_lookup,
        )
        # Embed overall MAE by prepending a pseudo-label stat (not rendered as a bar).
        panels.append((f"{target} (overall MAE={overall_mae:.3f})", group_stats))

    # Wide layout with tight height (no large blank band under the panels).
    render_svg(out_svg=OUT_SVG, panels=panels, canvas_width=1040, canvas_height=None)
    # Legacy filename: same graphic (square canvas was only for old PNG thumbnails).
    render_svg(out_svg=OUT_SVG_SQUARE, panels=panels, canvas_width=1040, canvas_height=None)
    print(f"Saved: {OUT_SVG}")
    print(f"Saved: {OUT_SVG_SQUARE}")


if __name__ == "__main__":
    main()

