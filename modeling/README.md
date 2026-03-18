# Modeling — Split and Train

This folder contains the train/test split notebook plus the first baseline modeling script. Run from the repo root or from this directory with paths adjusted accordingly.

## Split notebooks

**`train_test_split.ipynb`**

- **Inputs:**  
  - `../data/joint_county_year_2018_2019.csv`  
  - Optionally `../data/split_mapping.csv` when `USE_SAVED_MAPPING = True` (reproducible split when variables or rows change).

- **Outputs:**  
  - `../data/train.csv`, `../data/validation.csv`, `../data/test.csv`  
  - `../data/split_mapping.csv` (FIPS or state → train/validation/test).

- **Behavior:**  
  Drops rows missing CASTHMA/COPD, then assigns geography (states or counties) to 60% train, 20% validation, 20% test via a spatial split. When the mapping file exists and is loaded, the same geography stays in each split across runs. Use validation for tuning; evaluate once on test.

**`train_test_split_stratify.ipynb`**

- **Inputs:**  
  - `../data/joint_county_year_2018_2019.csv`

- **Outputs:**  
  - `../data/train_CASTHMA.csv`, `../data/test_CASTHMA.csv`  
  - `../data/train_COPD.csv`, `../data/test_COPD.csv`

- **Behavior:**  
  Creates a county-grouped 80/20 train/test split separately for CASTHMA and COPD using stratified bins of the target. This is the split used by the baseline regression script below.

## Baseline regression

**`regression_baseline.py`**

- **Inputs:**  
  - `data/train_CASTHMA.csv`, `data/test_CASTHMA.csv`  
  - `data/train_COPD.csv`, `data/test_COPD.csv`

- **Models:**  
  - Ridge regression  
  - Lasso regression

- **Behavior:**  
  Uses grouped cross-validation by county (`FIPS`) inside the training split, with target quantile bins for stratification across folds. The script excludes identifier columns and other health outcome columns by default, imputes missing values, one-hot encodes categoricals, scales numeric features, tunes `alpha`, and evaluates the final models on the hold-out test split.

- **Outputs:**  
  - `modeling/results/<TARGET>/model_summary.csv`  
  - `modeling/results/<TARGET>/model_summary.json`  
  - `modeling/results/<TARGET>/<model>_predictions.csv`  
  - `modeling/results/<TARGET>/<model>_top_coefficients.csv`

- **Run:**  
  - `python3 modeling/regression_baseline.py --target CASTHMA`  
  - `python3 modeling/regression_baseline.py --target COPD`  
  - `python3 modeling/regression_baseline.py --target both`

## Next steps

- Add Elastic Net and tree-based baselines that reuse the same train/test files and grouped CV strategy.
- Compare whether broader covariate sets or log-transformed pesticide features improve test RMSE.
- Export the best model’s county-level predictions to `web/data/risk_estimates.json` when you are ready to surface modeled risk on the map.
