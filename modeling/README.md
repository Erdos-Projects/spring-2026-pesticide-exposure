# Modeling — Split and (future) train

Notebooks here prepare data for training and will host model training. Run from this directory so that paths like `../data/` point to the repo’s `data/` folder.

## Current notebook

**`train_test_split.ipynb`**

- **Inputs:**  
  - `../data/joint_county_year_2018_2019.csv`  
  - Optionally `../data/split_mapping.csv` when `USE_SAVED_MAPPING = True` (reproducible split when variables or rows change).

- **Outputs:**  
  - `../data/train.csv`, `../data/validation.csv`, `../data/test.csv`  
  - `../data/split_mapping.csv` (FIPS or state → train/validation/test).

- **Behavior:**  
  Drops rows missing CASTHMA/COPD, then assigns geography (states or counties) to 60% train, 20% validation, 20% test via a spatial split. When the mapping file exists and is loaded, the same geography stays in each split across runs. Use validation for tuning; evaluate once on test.

## Future

- Model training notebook(s) that read `train.csv` and `validation.csv`, then export county-level risk for **`web/data/risk_estimates.json`** so the map shows real results.
