# Datasheet: Joint County–Year Dataset (Pesticide + PLACES + Cropland + Census)

*Following Gebru et al. (2018) "Datasheets for Datasets" — combined/summary datasheet*

This document describes the **merged** dataset used for modeling. The joint dataset is in **county–year** form: one row per county per year for **2018 and 2019 only** (years with CDC PLACES data). For source-level details, see the individual datasheets: [USGS Pesticide](datasheet_usgs_pesticide.md), [CDC PLACES](datasheet_cdc_places.md), [USDA Cropland](datasheet_usda_cropland.md), [Census ACS](datasheet_census_acs.md).

---

## Motivation for the Joint Dataset

**Why was this dataset created?**  
To support county-level predictive modeling of respiratory outcomes (asthma, COPD) from pesticide use, cropland composition, and demographic/health confounders. The joint dataset is the primary input for model training and evaluation.

**What tasks is it used for?**  
- Regression of CASTHMA and COPD prevalence from pesticide, cropland, and demographic features  
- Exploratory analysis of pesticide–health associations  
- Risk mapping and policy targeting  

**What tasks should it NOT be used for?**  
- Individual-level inference  
- Causal inference (ecological design; associations only)
---

## Dataset Composition

**What are the instances?**  
One row per **county per year** (county–year panel). Each row is identified by 5-digit FIPS (state + county code) and **YEAR** (2018 or 2019 only).

**How many instances?**  
Roughly 3,066 counties × 2 years ≈ 6,132 county–year rows. The pesticide dataset is filtered to 2018–2019; PLACES is merged on **FIPS and YEAR** (one PLACES row per county per year for 2018 and 2019); census and cropland are county-level and left-joined on FIPS.

**What data does each instance consist of?**  
- **YEAR**: 2018 or 2019 only  
- **Pesticide** (from USGS, varies by year): `pesticide_total_kg`, `pesticide_respiratory_kg`, chemical class totals, 435+ compound-level columns  
- **Demographics** (from Census ACS, county-level, repeated by year): `NAME`, `population`, `median_age`, `median_income`, `pct_white`, `pct_black`, `pct_asian`, `pct_hispanic`; **rural/urban** (from [CDC NCHS](https://www.cdc.gov/nchs/data-analysis-tools/urban-rural.html)): `nchs_urban_rural` (1–6: Large central metro, Large fringe, Medium metro, Small metro, Micropolitan, Noncore)  
- **Cropland** (from USDA CDL, county-level, repeated by year): `cropland_acres`, `total_area_acres`, `pct_cropland`, crop acres, `cropland_diversity`  
- **County–year collapsed crop/IPM** (from county_crop_year_ag → county_year_collapsed): **Raw/rescaled indices:** `ipm_breadth_acre`, `chemical_reliance_acre` (acre-weighted raw); `ipm_breadth_acre_rescaled`, `chemical_reliance_acre_rescaled` (0–1); `ipm_breadth_value`, `chemical_reliance_value` (value-weighted; NaN if no NASS). **Coverage/confidence:** `ipm_doc_coverage_share` (share of county crop acres with a matching IPM doc), `mean_text_quality`, `mean_geo_confidence`, `weighted_doc_age`. **Composition:** `county_crop_concentration`, `specialty_crop_share`, `total_ag_value`. See [Schema: IPM integration](schema_ipm_integration.md).  
- **Health outcomes** (from CDC PLACES, merged on FIPS + YEAR): `CASTHMA`, `COPD`, `CSMOKING`, `OBESITY`, `DIABETES` (prevalence %; one row per county per year for 2018 and 2019)

**Targets:**  
`CASTHMA` and `COPD` are the primary prediction targets. `CSMOKING`, `OBESITY`, `DIABETES` are confounders.

---

## Variable definitions and calculations

All variables in the joint county–year dataset, with their calculation (formula) and a brief definition. *k* = crop index; *c* = county (FIPS); *t* = year; *s* = state (from FIPS).

| Variable | Calculation / formula | Definition |
|----------|----------------------|------------|
| **Identifiers** | | |
| `FIPS` | 2-digit state + 3-digit county, zero-padded | County identifier (e.g. 01001). |
| `YEAR` | 2018 or 2019 | Analysis year (PLACES coverage). |
| **Pesticide** | | |
| `pesticide_total_kg` | ∑ compounds `EPEST_MEAN_KG`; `EPEST_MEAN_KG` = (EPEST_LOW_KG + EPEST_HIGH_KG) / 2 | Total estimated pesticide mass (kg) applied in county-year. |
| `pesticide_respiratory_kg` | Sum of respiratory-relevant compound kg (e.g. OP, carbamate, pyrethroid) | Pesticide mass from compounds relevant to respiratory risk. |
| `pesticide_*_kg` (by class) | Sum of `EPEST_MEAN_KG` over compounds in that class | Mass by chemical class (anilide, carbamate, chlorophenoxy, organophosphate, pyrethroid, etc.). |
| **Demographics** | | |
| `population` | From Census ACS (B01003) | Total population, county. |
| `median_age` | From Census ACS | Median age, county. |
| `median_income` | From Census ACS | Median household income, county. |
| `pct_white`, `pct_black`, `pct_asian`, `pct_hispanic` | 100 × (group count / total population) | Share of population by race/ethnicity (%). |
| `nchs_urban_rural` | CDC NCHS 6-level code (1–6) | Urban–rural classification: 1 = Large central metro … 6 = Noncore. |
| **Cropland** | | |
| `cropland_acres` | Sum of CDL crop-category acres in county | Total cropland acreage from CDL. |
| `total_area_acres` | From CDL or Census | Total land area, county. |
| `pct_cropland` | 100 × cropland_acres / total_area_acres | Share of county land in cropland (%). |
| `cropland_diversity` | Diversity index over crop acre shares (e.g. Shannon or count) | How spread or concentrated crop acreage is. |
| **County–year collapsed (crop/IPM)** | | |
| `ipm_breadth_acre` | ∑_k (acres_ckt / ∑_k acres_ckt) × IPMBreadth_raw,kst | Acreage-weighted IPM breadth (raw): emphasis on nonchemical/threshold/monitoring in the county’s crop mix. |
| `chemical_reliance_acre` | ∑_k (acres_ckt / ∑_k acres_ckt) × ChemReliance_raw,kst | Acreage-weighted chemical reliance (raw): how central pesticides are in the crop mix’s IPM docs. |
| `ipm_breadth_acre_rescaled` | Same as above but using 0–1 rescaled index per doc | Acreage-weighted IPM breadth on 0–1 scale (for modeling). |
| `chemical_reliance_acre_rescaled` | Same as above but using 0–1 rescaled index per doc | Acreage-weighted chemical reliance on 0–1 scale (for modeling). |
| `ipm_breadth_value` | ∑_k (value_ckt / ∑_k value_ckt) × IPMBreadth,kst | Value-weighted IPM breadth (NaN if no NASS value). |
| `chemical_reliance_value` | ∑_k (value_ckt / ∑_k value_ckt) × ChemReliance,kst | Value-weighted chemical reliance (NaN if no NASS value). |
| `ipm_doc_coverage_share` | ∑_k (acres_ckt / ∑_k acres_ckt) over crops *k* with a matching IPM doc | Share of county crop acres that have a matching crop–state IPM document. |
| `mean_text_quality` | Acre-weighted mean of text_parse_quality (0–1) over IPM-matched crops only | Average quality of extracted text (PDF/HTML) for docs covering the county’s crop mix. |
| `mean_geo_confidence` | Acre-weighted mean of geo_match_confidence over IPM-matched crops only | Average confidence that document geography matches the county’s state. |
| `weighted_doc_age` | Acre-weighted mean of (analysis_year − document_year) over IPM-matched crops | How old the IPM documents are for the county’s crop mix (years before analysis year). |
| `county_crop_concentration` | ∑_k (share_acres_k)² (Herfindahl) | Concentration of crop acreage (higher = more dominated by few crops). |
| `specialty_crop_share` | acres_fruit_veg / ∑_k acres_ckt | Share of county crop acres in fruit/vegetable (and similar) crops. |
| `total_ag_value` | ∑_k crop_value_ckt | Total crop production value in county-year (NaN if no NASS). |
| **Health (PLACES)** | | |
| `CASTHMA` | Modeled prevalence from BRFSS (PLACES) | Current adult asthma prevalence (%). |
| `COPD` | Modeled prevalence from BRFSS (PLACES) | COPD prevalence (%). |
| `CSMOKING`, `OBESITY`, `DIABETES` | Modeled prevalence from BRFSS (PLACES) | Current smoking, obesity, and diabetes prevalence (%). |

*IPM scores at crop–state–year* (IPMBreadth_raw,kst, ChemReliance_raw,kst) are recency-weighted means over documents: weight = 1 / (1 + |document_year − analysis_year|), then normalized so weights sum to 1 per (crop, state, year).

---

## Merge Process

**Join key:**  
5-digit FIPS (zero-padded: 2-digit state + 3-digit county). All sources standardized to this format before merging.

**Merge order:**  
1. **Base:** USGS Pesticide (county–year, filtered to 2018–2019; one row per FIPS per year)  
2. **Left join** Census ACS on FIPS (county-level; same row repeated for each year)  
3. **Left join** USDA Cropland on FIPS  
4. **Left join** CDC PLACES on **FIPS and YEAR** (one PLACES row per county per year for 2018 and 2019)  
5. **Left join** county_year_collapsed on FIPS and YEAR (crop-weighted IPM indices and composition; see schema_ipm_integration.md)  

**Rationale:** Pesticide is the primary exposure and varies by year; we retain all county–year pesticide rows. Census and cropland are county-level and repeated for each year; PLACES and county_year_collapsed are merged on FIPS + YEAR so health and IPM indices vary by year. Counties missing from other sources receive NaN for those features.

**Handling of duplicates:**  
None expected; FIPS + YEAR is unique per county-year. Pesticide is filtered to 2018–2019 (one row per county per year); no aggregation across years before merge.

---

## Temporal Alignment

| Source   | Time period        | Notes                                                                 |
|----------|--------------------|-----------------------------------------------------------------------|
| Pesticide| 2018–2019          | Varies by year.                                                       |
| Cropland | 2019               | Single CDL year; composition repeated for 2018 and 2019 in joint.     |
| Census ACS | 2019 (5-year)   | 2015–2019 pooled; county-level, repeated by year.                     |
| PLACES   | 2018–2019          | Releases 2020 (2018 BRFSS) and 2021 (2019 BRFSS); merged on FIPS + YEAR. |
| county_year_collapsed | 2018–2019 | One row per county-year; IPM indices joined by analysis year; crop composition from CDL. |

**Temporal alignment:** Analysis is restricted to **2018 and 2019**. PLACES releases 2020 and 2021 provide 2018 and 2019 BRFSS data; merged on FIPS + YEAR so each county–year has the correct PLACES row.

**Which variables are truly time-varying?** Pesticide and PLACES vary by year (merge on FIPS + YEAR). County_year_collapsed varies by year (one row per county-year; IPM recency-weighted by analysis year). Census and single-year CDL are merged on FIPS and repeated across 2018–2019.

---

## Coverage and Missingness

- **Pesticide:** All 3,066 rows have pesticide data (base dataset).  
- **Census:** Most counties covered; some may have nulls (e.g., suppressed or withheld codes).  
- **Cropland:** Fetched per county via CropScape API; some counties may have missing cropland stats.  
- **PLACES:** All U.S. counties in PLACES; coverage should be complete.  

For modeling, rows with missing targets (CASTHMA, COPD) are typically dropped. Rows with missing confounders may be imputed or dropped depending on model choice.

---

## Data Preprocessing (Project-Specific)

- **FIPS:** Standardized to 5-character string, zero-padded.  
- **Pesticide:** `EPEST_MEAN_KG` = mean of low/high bounds; aggregated by chemical class (Shekhar et al. 2024) and respiratory-relevant compounds (OP, Carbamate, Pyrethroid).  
- **Census:** Race percentages = 100 × (group count / total); null codes (-666666666, -222222222) replaced with NaN for analysis.  
- **Cropland:** Non-crop categories (developed, water, forest, etc.) excluded from cropland total; `pct_cropland` = 100 × cropland_acres / total_area_acres.  
- **PLACES:** Pivoted from long to wide; measures CASTHMA, COPD, CSMOKING, OBESITY, DIABETES.  

---

## Distribution

**File:** `data/joint_county_year_2018_2019.csv`  
**Format:** CSV  
**Generated by:** `EDA/build_joint_dataset.ipynb` (data gathering, join, and save). Exploratory analysis is in `EDA/joint_eda.ipynb` (loads this CSV).  

---

## Legal & Ethical Considerations

Same as individual sources: public, aggregated data; no PII. See individual datasheets for details. The joint dataset inherits limitations of each source (modeled estimates, ecological design).
