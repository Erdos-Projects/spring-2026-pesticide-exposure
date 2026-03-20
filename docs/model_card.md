# Model Card: County-Level Pesticide–Respiratory Risk Model

*Following Mitchell et al. (2019) "Model Cards for Model Reporting"*

> **Status:** Active. Final model selected and evaluated.

---

## Model Details

**Model type:** Gradient-boosted decision trees (**XGBoost Regressor**)  
**Final feature set:** `Full_pesticides_raw` — see **Feature inventory** below.  
**Model version:** `final_full_pesticides_xgboost`  
**Date created:** March 2026  
**Developers:** Allison Londeree; CJ Concepcion; Matthew Hamil; Ryan Bausback; Sunyoung Park  
**Point of contact:** Allison Londeree

### Feature inventory (`Full_pesticides_raw`)

Defined in code as: every column whose name matches `pesticide_*_kg`, plus shared baseline covariates `BASE_COLS` from `modeling/_exposure_defs.py` (intersection with columns present after `engineer_signal_isolation_features`).

**1. Pesticide mass features (kg, county–year)** — **445** columns  

One column per active ingredient / rollup in the USGS-style naming convention: `pesticide_<slug>_kg`. The **complete sorted list** (as in `data/train_CASTHMA.csv`) is in:

- [`full_pesticides_raw_pesticide_kg_columns.txt`](full_pesticides_raw_pesticide_kg_columns.txt)

Rollups included in that set (non-exhaustive examples; see file for full list) include class and summary columns such as `pesticide_total_kg`, `pesticide_respiratory_kg`, and chemical-class totals (e.g. `pesticide_organophosphate_kg`, `pesticide_carbamate_kg`, `pesticide_pyrethroid_kg`, …) **plus** all compound-level `pesticide_*_kg` fields.

**2. Baseline covariates (`BASE_COLS`) — 16 columns**

| Group | Column names |
|-------|----------------|
| Demographics | `population`, `median_age`, `median_income`, `pct_white`, `pct_black`, `pct_asian`, `pct_hispanic`, `rural_binary` |
| Health confounders (PLACES) | `CSMOKING`, `OBESITY`, `DIABETES` |
| Cropland structure | `cropland_diversity`, `county_crop_concentration`, `pct_cropland` |
| Time | `YEAR` |

*`rural_binary` is derived in preprocessing as `(nchs_urban_rural >= 5).astype(int)` before modeling.*

**Implementation + artifacts:**  
- Training/model-selection notebook: `modeling/model_selection.ipynb`  
- External validation script: `modeling/validate_model_accuracy.py`  
- Prediction outputs:  
  - `modeling/results/CASTHMA/xgboost_predictions_Full_pesticides_raw.csv`  
  - `modeling/results/COPD/xgboost_predictions_Full_pesticides_raw.csv`  
- External holdout evaluation outputs:  
  - `modeling/results/CASTHMA/validation_eval_Full_pesticides_raw__XGBoost_(tuned)/metrics.csv`  
  - `modeling/results/COPD/validation_eval_Full_pesticides_raw__XGBoost_(tuned)/metrics.csv`

---

## Intended Use

**Primary intended use:**  
Predict county-level prevalence of asthma (CASTHMA) and COPD from pesticide use estimates, cropland composition, and demographic/health confounders. Intended to support resource allocation, policy targeting, and research—not individual diagnosis or legal evidence.

**Intended users:**  
- Public health agencies and policymakers  
- Researchers in environmental epidemiology  
- Insurers and health systems (for population-level planning)

**Out-of-scope uses:**  
- Individual-level diagnosis or clinical decision-making  
- Causal inference (model is associative; ecological fallacy applies)  
- Real-time or near-term forecasting without retraining

---

## Factors

**Relevant factors:**  
- Geographic region (county FIPS)  
- Pesticide use (total kg, by chemical class, respiratory-relevant compounds)  
- Cropland composition (corn, soybean, cotton, wheat, hay, diversity)  
- Demographics (age, income, race/ethnicity)  
- Health behaviors (smoking, obesity, diabetes)

**Evaluation factors:**  
- Performance by region (e.g., Midwest vs. other)  
- Performance by county size (population, cropland area)  
- Fairness across demographic subgroups (race/ethnicity, income)

---

## Metrics

**Model performance metrics (final model):**  
- **RMSE**, **MAE**, **R²** on county-level prevalence (regression).  
- **Cross-validation (OOF):** out-of-fold predictions on the training split using the same `StratifiedGroupKFold` setup as hyperparameter tuning (see `modeling/model_selection.ipynb` and `model_summary_exposure_sets.csv`).  
- **External holdout:** metrics on the held-out validation split (`data/validation.csv` + `split_mapping.csv`), exported under `validation_eval_Full_pesticides_raw__XGBoost_(tuned)/`.

**Decision thresholds:** **Not applicable.** The shipped model predicts continuous prevalence (%), not classes. Any future risk tiers or map binning should document cutoffs separately.

**Variation across groups:**  
- Equity/stability summaries are generated for final XGBoost outputs, including subgroup gap views in `modeling/results/`.

---

## Evaluation Data

**Training data:**  
- USGS Pesticide Use Estimates (2018–2019, county–year)  
- CDC PLACES (2018 and 2019 BRFSS; CASTHMA, COPD, CSMOKING, OBESITY, DIABETES; merged on FIPS + YEAR)  
- USDA Cropland Data Layer (2019)  
- US Census ACS 5-year (2019)

**Evaluation data:**  
- Cross-validation (OOF) model comparisons across exposure sets from:  
  - `modeling/results/CASTHMA/model_summary_exposure_sets.csv`  
  - `modeling/results/COPD/model_summary_exposure_sets.csv`  
- External holdout validation from:  
  - `modeling/results/CASTHMA/validation_eval_Full_pesticides_raw__XGBoost_(tuned)/`  
  - `modeling/results/COPD/validation_eval_Full_pesticides_raw__XGBoost_(tuned)/`  
- See [`datasheets.md`](datasheets.md) for dataset summary and source links.

---

## Training Data

**Data preprocessing:**  
- Joint county–year dataset: `data/joint_county_year_2018_2019.csv` (one row per county per year for 2018 and 2019)  
- FIPS standardized; pesticide filtered to 2018–2019, aggregated by chemical class and respiratory-relevant compounds  
- Census and cropland merged by FIPS; PLACES and county_year_collapsed merged by FIPS + YEAR  

**Known limitations:**  
- Ecological design: county-level associations do not imply individual-level causation  
- Pesticide estimates are modeled, not measured  
- PLACES outcomes are model-based (MRP)  
- Temporal alignment: 2018 and 2019 (PLACES releases 2020 and 2021); census and cropland are county-level and repeated by year

---

## Quantitative Analyses

### Final selected model: XGBoost + `Full_pesticides_raw`

**Cross-validation / OOF (from `model_summary_exposure_sets.csv`):**

| Target | RMSE | MAE | R² |
|--------|------|-----|----|
| CASTHMA | 0.3453 | 0.2614 | 0.8791 |
| COPD | 0.7240 | 0.5479 | 0.9015 |

**External holdout validation (from `validation_eval_Full_pesticides_raw__XGBoost_(tuned)/metrics.csv`):**

| Target | RMSE | MAE | R² | RMSE 95% CI | N |
|--------|------|-----|----|-------------|---|
| CASTHMA | 0.3888 | 0.2872 | 0.8354 | [0.3658, 0.4097] | 1219 |
| COPD | 0.7650 | 0.5744 | 0.8854 | [0.7284, 0.8030] | 1219 |

**Best hyperparameters on external holdout run:**
- CASTHMA: `{'model__learning_rate': 0.1, 'model__max_depth': 5, 'model__n_estimators': 200}`
- COPD: `{'model__learning_rate': 0.05, 'model__max_depth': 5, 'model__n_estimators': 200}`

---

## Ethical Considerations

**Risks:**  
- Stigmatization of agricultural counties or demographic groups  
- Misuse for blame rather than resource allocation  
- Overinterpretation of associations as causation  

**Mitigations:**  
- Clear documentation of limitations (ecological design, modeled data)  
- Emphasis on population-level planning, not individual inference  
- Fairness evaluation across demographic subgroups when model is trained  

**Recommendations:**  
- Use model outputs to target resources and interventions, not to penalize regions or groups  
- Pair with qualitative and domain expertise for policy decisions  

---

## Caveats and Recommendations

- **Ecological fallacy:** County-level associations do not apply to individuals.  
- **Data quality:** Pesticide and PLACES data are estimates with uncertainty.  
- **Temporal alignment:** Data aligned to 2018 and 2019 (PLACES releases 2020 and 2021; pesticide county–year; census and cropland county-level). Consider retraining when newer data become available.  
- **Recommendation:** Treat this as a research and planning tool; validate findings with domain experts and additional data sources.
