# spring-2026-pesticide-exposure
Team project: spring-2026-pesticide-exposure

**Live site (GitHub Pages):** [Pesticide Exposure & Respiratory Health](https://erdos-projects.github.io/spring-2026-pesticide-exposure/index.html) — overview, interactive county map, and model specifics.

# Problem:
Agricultural pesticide use varies widely by crop and region and may contribute to localized increases in preventable healthcare utilization (e.g., asthma, respiratory distress). Public health agencies and Medicaid programs need data-driven tools to target preventative interventions, such as evidence-based prevention planning under constrained budgets.

# Objective:
Build a county/region-level predictive risk model to identify regions in the United States where pesticide exposure is associated with elevated healthcare burden, enabling targeted, high-ROI public health investments.  Real world stakeholders include insurers, policy makers, hospital systems, public health departments.

# Modeling Approach:
Our predictive model will forecast the respiratory illnesses present in each geographic region from pesticide usage, as well as crop data and weather patterns. To make the map, we might categorize each region into bins based on several thresholds such as "high risk", "low risk", etc. which can then be used to create the risk map which could be presented to stakeholders to inform decisionmaking. If our model struggles with MSE regression, then we could potentially categorize the target variables in this way first, and then train a categorical regression such as logistic regression instead. 

Our primary datasets are:
1. CDC PLACES (County-level health indicators): https://www.cdc.gov/places/data/index.html
2. USGS / EPA Pesticide Use Estimates: https://water.usgs.gov
3. USDA Cropland Data Layer (Crop coverage): https://nassgeodata.gmu.edu/CropScape/

Our target years are **2018 and 2019**, the years with CDC PLACES county-level data (releases 2020 and 2021). The joint dataset is in county–year form (one row per county per year); time (YEAR) can be used as a feature or for temporal splits. 

The two respiratory illness that our model targets are COPD and Asthma, as these diseases have the most direct link to pesticide exposure in literature. These illness may have causes other than pesticide exposure but we control for that when building our model.


# Anti-goals: 
This project will NOT seek to definitively prove the link between respiratory illness and the use of pesticides. Such a causality has already been well established in scientific papers such as: 
1. Ye M, Beach J, Martin JW, Senthilselvan A. Occupational pesticide exposures and respiratory health. Int J Environ Res Public Health. 2013 Nov 28;10(12):6442-71. doi: 10.3390/ijerph10126442. PMID: 24287863; PMCID: PMC3881124.

2. Cecilia S. Alcalá, Cynthia Armendáriz-Arnez, Ana M. Mora, Maria G. Rodriguez-Zamora, Asa Bradman, Samuel Fuhrimann, Christian Lindh, María José Rosa,
Association of pesticide exposure with respiratory health outcomes and rhinitis in avocado farmworkers from Michoacán, Mexico,Science of The Total Environment,Volume 945,2024,173855,ISSN 0048-9697,https://doi.org/10.1016/j.scitotenv.2024.173855.

3. Salameh P, Waked M, Baldi I, Brochard P, Saleh BA. Respiratory diseases and pesticide exposure: a case-control study in Lebanon. J Epidemiol Community Health. 2006 Mar;60(3):256-61. doi: 10.1136/jech.2005.039677. PMID: 16476757; PMCID: PMC2465555.

And many others. We will however attempt to validate our predictive model by performing hypothesis testing on the coefficients and determining their statistical significance.


---

## Repo layout

| Path | Purpose |
|------|---------|
| **`data/`** | Generated data: joint CSV, train/test splits. See `data/README.md`. |
| **`EDA/`** | Build and explore the joint dataset. See `EDA/README.md`. |
| **`modeling/`** | Train/validation/test split and (future) model training. See `modeling/README.md`. |
| **`docs/`** | Datasheets (Gebru-style) and model card (Mitchell-style). |
| **`web/`** | Static site + interactive county risk map for GitHub Pages. See `web/README.md`. |

**Notebooks (in order):**
1. **`EDA/build_joint_dataset.ipynb`** — Fetches USGS pesticide, CDC PLACES, Census ACS, NCHS, CDL; builds crop-composition layers in memory; joins and saves **`data/joint_county_year_2018_2019.csv`**. Run from `EDA/` (paths use `../data/`).
2. **`EDA/joint_eda.ipynb`** — Loads the joint CSV; exploratory analysis (missingness, correlations, maps).
3. **`modeling/train_test_split_stratify.ipynb`** — Loads joint CSV; 60/20/20 spatial split (by county), stratify on target; writes **`data/train.csv`**, **`data/test.csv`**. Run from `modeling/` (paths use `../data/`).
4. *(Future)* Model training notebook(s) that read train/validation, then export county risk for **`web/data/risk_estimates.json`**.

**Documentation:**  
- **`docs/`** — One consolidated [`docs/datasheets.md`](docs/datasheets.md) (sources + joint table) and model card. See Gebru et al. (2018) and Mitchell et al. (2019).
- **`web/`** — Deploy to GitHub Pages; replace **`web/data/risk_estimates.json`** with model output to show real results (see `web/README.md`).

---

## Setup (for teammates)

- Activate the ERDOS data-science environment used by this repo notebooks: `erdos_ds_environment`.
- Install project-specific dependencies once (into your active ERDOS environment):  
  `bash scripts/load_extra_dependencies.sh`
- Run notebooks from their directory (e.g. open `EDA/build_joint_dataset.ipynb` and run; it expects `../data/` to exist). Create **`data/`** if missing before the first run.

---

## TO DO / ideas

- Model card and data cards (templates in `docs/`; fill when model is trained).
- Note in write-up: the paucity of public, county-level data on this topic as of 2020.

---

## References (lit / data)

https://pmc.ncbi.nlm.nih.gov/articles/PMC11664077/table/tbl0010/
https://pmc.ncbi.nlm.nih.gov/articles/PMC11664077/
https://www.sciencedirect.com/science/article/pii/S016041202300524X
https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2021GH000544
https://www.epa.gov/pesticides/pesticides-industry-sales-and-usage-2008-2012-market-estimates
