# Data directory

Generated and intermediate data for the pesticide–respiratory modeling pipeline. Paths in notebooks assume this directory lives at **repo root** as `data/`; EDA and modeling notebooks use `../data/` when run from their folders.

| File | Producer | Description |
|------|----------|-------------|
| `pesticide_2016_17.tsv`, `pesticide_2018.tsv`, `pesticide_2019.tsv` | `scripts/download_pesticide_data.py` | USGS pesticide data (optional). If ScienceBase times out, run the download script and the build notebook will use these. |
| `joint_county_year_2018_2019.csv` | `EDA/build_joint_dataset.ipynb` | Joint county–year table (2018–2019): pesticide, PLACES, census, cropland. Primary input for EDA and modeling. |
| `train.csv` | `modeling/train_test_split.ipynb` | Training set (60% by default; spatial split by state or county). |
| `validation.csv` | `modeling/train_test_split.ipynb` | Validation set (20%); use for hyperparameter tuning. |
| `test.csv` | `modeling/train_test_split.ipynb` | Hold-out test set (20%); evaluate final model once. |
| `split_mapping.csv` | `modeling/train_test_split.ipynb` | Mapping of FIPS (or state FIPS) to split for reproducibility when variables or filters change. |

Create this directory if it does not exist before running the EDA or modeling notebooks. Do not commit very large files if your team uses Git; consider `.gitignore` for big CSVs or document where to obtain them.
