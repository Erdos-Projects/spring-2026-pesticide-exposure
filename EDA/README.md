# EDA — Build and explore the joint dataset

Notebooks here build and explore the **county–year** joint dataset used for modeling. Run from this directory so that paths like `../data/` resolve to the repo’s `data/` folder.

## Main pipeline

1. **`build_joint_dataset.ipynb`**  
   Fetches and joins:
   - USGS pesticide use (county–year)
   - CDC PLACES (asthma, COPD, etc.)
   - Census ACS demographics
   - NCHS urban–rural codes
   - USDA CDL / CropScape cropland
   - Optional experimental crop-practice indices (in `ipm-testing`)

   **Output:** `../data/joint_county_year_2018_2019.csv`

2. **`joint_eda.ipynb`**  
   Loads the joint CSV and runs exploratory analysis (missingness, correlations, visualizations). No outputs; exploratory only.

## Source-specific EDA

- **`census-demographics/census_eda.ipynb`** — Census API
- **`cdc-places/`** — CDC PLACES (e.g. `places_eda.ipynb`)
- **`croplands/croplands_eda.ipynb`** — CDL/CropScape
- **`usgs/pesticide_prelimEDA.ipynb`** — USGS pesticide

These support the main pipeline and ad-hoc exploration; the single source of truth for modeling is the joint CSV produced by `build_joint_dataset.ipynb`.
