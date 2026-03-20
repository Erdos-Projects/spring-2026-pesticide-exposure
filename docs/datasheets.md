# Datasheet: Joint U.S. County–Year Dataset (2018–2019)

**Pesticide exposure, land use, demographics, crop-practice related indices, and respiratory health at county resolution**

*This datasheet follows the question template in Gebru et al., [“Datasheets for Datasets”](https://arxiv.org/abs/1803.09010) (FAT/ML 2018). A copy of the paper is in the course materials at `Ethics in AI/Pesticide Project/datasheets for datasets.pdf`.*

The **dataset documented here** is the merged table used for modeling: one row per U.S. county per calendar year for **2018 and 2019**, stored as `data/joint_county_year_2018_2019.csv` after running `EDA/build_joint_dataset.ipynb`. Upstream sources (USGS, CDC PLACES, Census ACS, USDA CDL, CDC NCHS urban–rural, National experimental crop-practice Database–derived features) are described where they affect composition, collection, and ethics.

---

## Motivation for Dataset Creation

**Why was the dataset created? (e.g., were there specific tasks in mind, or a specific gap that needed to be filled?)**  
To support **county-level modeling** of associations between **agricultural pesticide use**, **cropland composition**, **demographic and behavioral confounders**, **crop-practice related (text-derived) indices weighted by local crop mix**, and **respiratory-related health outcomes** (asthma and COPD prevalence). The gap addressed is the lack of a single, documented, reproducible join of public federal datasets at **county×year** resolution aligned to PLACES release years.

**What (other) tasks could the dataset be used for? Are there obvious tasks for which it should not be used?**  
*Could be used for:* exploratory mapping; regression or ML with geographic or temporal holdouts; sensitivity analyses on feature sets; teaching data documentation and ecological/epidemiologic limits.  
*Should **not** be used for:* individual-level exposure or diagnosis; causal inference without a dedicated design; fine-scale (field or sub-county) land-use decisions; ranking counties for “blame” or resource denial without context; any use that ignores uncertainty in modeled/survey-based inputs.

**Has the dataset been used for any tasks already? If so, where are the results so others can compare (e.g., links to published papers)?**  
Used internally in this repository for EDA (`EDA/joint_eda.ipynb`), train/validation/test construction (`modeling/train_test_split.ipynb`, `modeling/train_test_split_stratify.ipynb`), and model selection/evaluation notebooks under `modeling/`. Published benchmark links are **to be added** when available.

**Who funded the creation of the dataset? If there is an associated grant, provide the grant number.**  
The **joint file** is assembled by this project (Ohio State / course context—confirm locally). **Upstream sources** are federal/public: USGS, CDC, U.S. Census Bureau, USDA NASS (CDL), CDC NCHS; experimental crop-practice document pipeline uses the National experimental crop-practice Database (experimental crop-practice Centers). Grant numbers for this merge, if any, should be recorded by the project PI.

**Any other comments?**  
The scientific object is **associations at aggregate level**, not proof of harm from pesticides for any person or place.

---

## Dataset Composition

**What are the instances? Are there multiple types of instances?**  
Each instance is one **U.S. county × year** (2018 or 2019), identified by **5-digit county FIPS** and **YEAR**. There is a single instance type (panel row).

**Are relationships between instances made explicit in the data?**  
**Geography:** Counties nest within states (FIPS prefix). The dataset does not ship an edges table; analysts can construct state or spatial neighbors externally. **Time:** Same county appears twice (2018, 2019) when both years are present.

**How many instances of each type are there?**  
On the order of **~3,066 counties × 2 years ≈ ~6,132** county–year rows at full pesticide coverage; exact row count depends on filtering and merges. Rows missing key outcomes may be dropped for modeling (see modeling README).

**What data does each instance consist of? “Raw” data vs features/attributes?**  
Attributes include:

| Group | Examples | Provenance (summary) |
|-------|----------|----------------------|
| Identifiers | `FIPS`, `YEAR` | Project standard |
| Pesticide | Totals by mass (kg), by chemical class, by compound (many columns), respiratory-relevant subset | USGS county-level estimates |
| Demographics | Population, median age, income, race/ethnicity shares | ACS 5-year, county |
| Urban–rural | `nchs_urban_rural` (6-level) | CDC NCHS |
| Cropland | Cropland acres, % cropland, major crop acres, diversity | USDA CDL (2019 in pipeline; repeated across years in joint) |
| Crop structure (experimental scores archived) | Acre- and value-weighted experimental crop-practice breadth & chemical reliance, coverage/quality/age of docs, crop concentration, specialty share, ag value | Archived experimental scoring notes + CDL (+ NASS value when present); see [`../EDA/ipm-testing/schema_ipm_integration.md`](../EDA/ipm-testing/schema_ipm_integration.md) |
| Health | `CASTHMA`, `COPD`, `CSMOKING`, `OBESITY`, `DIABETES` (prevalence %) | CDC PLACES, merged on FIPS **and** YEAR |

Detailed formulas for archived experimental weighted fields are in [`../EDA/ipm-testing/schema_ipm_integration.md`](../EDA/ipm-testing/schema_ipm_integration.md). Compound-level pesticide column names match USGS compound strings after preprocessing in the build notebook.

**Is there a label/target associated with instances?**  
**Primary modeling targets:** `CASTHMA` (current asthma), `COPD`. **Confounders / covariates:** `CSMOKING`, `OBESITY`, `DIABETES`, demographics, urban–rural, cropland, pesticide totals/classes.

**If the instances are related to people, are subpopulations identified and what is their distribution?**  
County-level **race/ethnicity shares** and **smoking/obesity/diabetes** come from modeled or survey-based sources; they describe **populations**, not individuals. PLACES includes uncertainty by area size; small counties may be less stable.

**Is everything included or does the data rely on external resources?**  
The CSV is **self-contained** for columns written by the notebook. **Provenance** depends on continued availability of **ScienceBase** (USGS), **CDC**, **Census API**, **CropScape**, **experimental crop-practice API** for reproduction. Archived copies of raw pulls (e.g. `pesticide_*.tsv`) may live under `data/` per [`data/README.md`](../data/README.md).

**Are there licenses, fees or rights associated with any of the data?**  
U.S. government sources used here are generally **public domain** or open; **no fees** for typical API/download use. experimental crop-practice Database terms should be verified at time of use.

**Are there recommended data splits or evaluation measures?**  
**Recommended:** **Spatial** train/validation/test (e.g., by county or state) to reduce leakage across adjacent areas—implemented in `modeling/train_test_split.ipynb` (~60/20/20) with optional `split_mapping.csv` for reproducibility. **Measures:** task-dependent (e.g., RMSE, MAE, R² for regression; appropriate calibration checks for prevalence modeling). See [`modeling/README.md`](../modeling/README.md).

**What experiments were initially run on this dataset?**  
Model selection and evaluation notebooks under `modeling/`; document metrics and figures there when finalizing.

**Any other comments?**  
**Time alignment:** Pesticide and PLACES vary by year; ACS (2019 5-year) and 2019 CDL are **constant** across 2018/2019 for a given county in the joint table. Interpret temporal models accordingly.

---

## Data Collection Process

**How was the data collected? (hardware, manual curation, API, validation)**  
The joint dataset does not use a single sensor; it **integrates**:

| Source | Collection / estimation method |
|--------|--------------------------------|
| **USGS pesticide** | Model-based county estimates from USDA survey and spatial inputs; not direct measurement. [ScienceBase](https://www.sciencebase.gov/catalog/); file URLs in `EDA/build_joint_dataset.ipynb`. |
| **CDC PLACES** | Multilevel regression and poststratification on **BRFSS** (+ auxiliary data); county estimates. [PLACES](https://www.cdc.gov/places/), [data.cdc.gov](https://data.cdc.gov/). |
| **Census ACS** | Ongoing household survey; **5-year** county estimates. [ACS](https://www.census.gov/programs-surveys/acs), [API](https://api.census.gov/data/2019/acs/acs5). |
| **USDA CDL** | Satellite classification → county acreage via **CropScape** / GetCDLStat. [CropScape](https://nassgeodata.gmu.edu/CropScape/). |
| **CDC NCHS** | County urban–rural scheme from Census-linked definitions. [NCHS documentation](https://www.cdc.gov/nchs/data-analysis-tools/urban-rural.html). |
| **Experimental crop-practice features (archived)** | Documents from an archived experimental source; scores from metadata/PDF text heuristics per [`../EDA/ipm-testing/schema_ipm_integration.md`](../EDA/ipm-testing/schema_ipm_integration.md). |

**Who was involved in the data collection process? How were they compensated?**  
Federal agencies and contractors produce upstream data. **This merge** is performed by the project authors in Jupyter notebooks; no crowdworkers for the joint CSV itself.

**Over what time-frame was the data collected? Does it match creation?**  
**Analysis window:** 2018–2019 county–years. **ACS:** 2015–2019 pooled. **CDL:** 2019 layer in current pipeline. **PLACES:** releases aligned to 2018 and 2019 BRFSS years. **Pesticide:** annual estimates matched to 2018 and 2019.

**How was the data associated with each instance acquired? Direct, reported, or inferred?**  
Largely **inferred or modeled** at county level (pesticide, PLACES); **survey-estimated** (ACS); **remote-sensing-derived** (CDL). See source documentation for validation practices.

**Does the dataset contain all possible instances?**  
**U.S. counties** in scope of each source; some areas may lack cropland or have suppressed ACS cells. Not a random sample of global geographies.

**If the dataset is a sample, what is the population? Sampling strategy?**  
Population is **U.S. counties with available merges**. Pesticide data targets agriculturally relevant counties; inclusion is **deterministic** from source coverage, not a random sample of counties.

**Is there information missing from the dataset and why?**  
Yes: API failures, **suppressed** Census values (disclosure avoidance), counties without CDL stats, missing experimental crop-practice doc match for some crops → NaNs. Optional NASS value columns may be missing where value not fetched.

**Are there known errors, noise, or redundancies?**  
USGS low/high bounds imply uncertainty; PLACES has CIs; CDL misclassification; ecological bias; duplicate conceptual information across correlated pesticide/crop variables.

**Any other comments?**  
Ecological fallacy: county associations **do not** imply individual risk.

---

## Data Preprocessing

**What preprocessing/cleaning was done?**  
Including but not limited to: FIPS zero-padding and string format; pesticide `EPEST_MEAN_KG` from low/high; aggregation by chemical class (e.g., Shekhar et al.–style groupings); ACS null sentinels → NaN; CDL category grouping; PLACES long→wide; left joins in documented order; experimental crop-practice recency weighting and county–year collapse per schema doc.

**Was the “raw” data saved in addition to the preprocessed data?**  
Yes where practical: e.g. `pesticide_2016_17.tsv`, `pesticide_2018.tsv`, `pesticide_2019.tsv` under `data/` when downloaded locally; see [`data/README.md`](../data/README.md).

**Is the preprocessing software available?**  
Yes: **`EDA/build_joint_dataset.ipynb`**, related EDA notebooks, and `scripts/download_pesticide_data.py` in this repository.

**Does this procedure achieve the motivation stated above?**  
It produces a **single documented county×year table** for supervised modeling and EDA; limitations are explicit in **Legal & Ethical** and **Composition**.

**Any other comments?**  
Re-run the build notebook after upstream API changes to refresh rows.

---

## Dataset Distribution

**How is the dataset distributed?**  
Primary distribution: **this Git repository** (path `data/joint_county_year_2018_2019.csv` when committed or released). Upstream sources remain on agency sites/APIs. A **DOI** may be added if the project deposits a snapshot (e.g., Zenodo).

**When will the dataset be released / first distributed?**  
Tied to repository releases; document version date in commit or release notes.

**What license is it distributed under? Are there copyrights on the data?**  
Repository license applies to **code and documentation**. **Underlying U.S. federal data** are generally not copyrighted; **verify** experimental crop-practice Database and any third-party assets separately.

**Are there fees or access/export restrictions?**  
None inherent to the joint CSV; API rate limits may apply when reproducing from sources.

**Any other comments?**  
Do not commit extremely large files if policy forbids; use `.gitignore` and document obtain steps.

---

## Dataset Maintenance

**Who is supporting/hosting/maintaining the dataset?**  
Project maintainers (course/research team—**name contact in README or repo settings**).

**How does one contact the owner/curator?**  
Use repository **Issues** or email listed in the root **`README.md`** / course instructions.

**Will the dataset be updated? How often and by whom?**  
Updates when upstream years are added or preprocessing changes; document in **CHANGELOG** or release notes if adopted.

**How will updates/revisions be documented?**  
Git history; optional `split_mapping.csv` versioning for modeling splits.

**If the dataset becomes obsolete how will this be communicated?**  
README / datasheet note pointing users to newer years or methods.

**Is there a repository to link papers/systems that use this dataset?**  
**To be populated** (e.g., bibliography section in README or wiki).

**If others want to extend/augment/build on this dataset, is there a mechanism?**  
Fork/pull request on GitHub; extensions (new years, features) should update **this datasheet** and schema docs.

**Any other comments?**  
Reproducibility: pin notebook run dates and record upstream API versions when publishing.

---

## Legal & Ethical Considerations

**If the dataset relates to people, were they informed about the data collection?**  
**BRFSS** participants consent to survey use; **PLACES** aggregates protect individuals. No individual records in this joint file.

**If it relates to ethically protected subjects, have obligations been met?**  
Aggregated public health and Census statistics; **not** identifiable human subjects data from this project’s merge. Institutional review for **secondary analysis** of public aggregates is context-dependent—consult local IRB if linking to restricted data later.

**Ethical review applications?**  
Project-specific; add if IRB approved.

**Were people told what the dataset would be used for? Did they consent?**  
N/A at individual level for the joint CSV. **Misuse concern:** stigmatizing high–asthma or high–pesticide counties—mitigate by framing **uncertainty**, **structural factors**, and **avoiding punitive use**.

**Could this dataset expose people to harm or legal action?**  
**Low direct risk** (no PII). **Indirect:** misleading maps or rankings could harm communities; **mitigate** with uncertainty, caveats, and peer review.

**Does it unfairly advantage or disadvantage a social group?**  
**Race/ethnicity and income** are included as **confounders**; models can encode historical inequity. **Mitigate:** report performance and residuals by subgroup where valid; avoid deterministic allocation of resources from a single black-box score without oversight.

**Privacy guarantees?**  
County aggregates only; Census disclosure avoidance applies to inputs.

**GDPR / other standards?**  
Dataset is **U.S. county-level**; **GDPR** is not the primary frame. If combined with EU or identifiable data, reassess.

**Sensitive or confidential information?**  
No PII in the distributed joint table as designed.

**Inappropriate or offensive content?**  
None by design; experimental text processing ingests **technical agriculture documents**—source text may contain routine pesticide terminology.

**Any other comments?**  
Pair this document with **[`model_card.md`](model_card.md)** for deployed models. Course reference: Gebru et al., *Datasheets for Datasets* (`datasheets for datasets.pdf` in **Ethics in AI / Pesticide Project**).

---

## Quick reference: official documentation links

| Topic | URL |
|-------|-----|
| Gebru et al. (2018) | <https://arxiv.org/abs/1803.09010> |
| CDC PLACES | <https://www.cdc.gov/places/> |
| Census ACS API (2019 5yr) | <https://api.census.gov/data/2019/acs/acs5> |
| USGS ScienceBase | <https://www.sciencebase.gov/catalog/> |
| USDA CropScape | <https://nassgeodata.gmu.edu/CropScape/> |
| CDC NCHS urban–rural | <https://www.cdc.gov/nchs/data-analysis-tools/urban-rural.html> |
| Repo data files | [`data/README.md`](../data/README.md) |
| archived schema notes | [`../EDA/ipm-testing/schema_ipm_integration.md`](../EDA/ipm-testing/schema_ipm_integration.md) |
