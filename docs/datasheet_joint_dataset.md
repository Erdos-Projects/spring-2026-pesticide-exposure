# Datasheet: Joint County–Year Dataset (Pesticide + PLACES + Cropland + Census)

*Following Gebru et al. (2018) "Datasheets for Datasets" — combined/summary datasheet*

This document describes the **merged** dataset used for modeling. The joint dataset is in **county–year** form: one row per county per year (2016–2019). For source-level details, see the individual datasheets: [USGS Pesticide](datasheet_usgs_pesticide.md), [CDC PLACES](datasheet_cdc_places.md), [USDA Cropland](datasheet_usda_cropland.md), [Census ACS](datasheet_census_acs.md).

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
One row per **county per year** (county–year panel). Each row is identified by 5-digit FIPS (state + county code) and **YEAR** (2016–2019).

**How many instances?**  
Roughly 3,066 counties × 4 years ≈ 12,264 county–year rows (fewer if some county-years are missing). The pesticide dataset is the base (one row per FIPS per year); census, cropland, and PLACES are county-level and left-joined on FIPS, so their values repeat across years for each county.

**What data does each instance consist of?**  
- **YEAR**: 2016, 2017, 2018, or 2019  
- **Pesticide** (from USGS, varies by year): `pesticide_total_kg`, `pesticide_respiratory_kg`, chemical class totals, 435+ compound-level columns  
- **Demographics** (from Census ACS, county-level, repeated by year): `NAME`, `population`, `median_age`, `median_income`, `pct_white`, `pct_black`, `pct_asian`, `pct_hispanic`  
- **Cropland** (from USDA CDL, county-level, repeated by year): `cropland_acres`, `total_area_acres`, `pct_cropland`, crop acres, `cropland_diversity`  
- **Health outcomes** (from CDC PLACES, county-level, repeated by year): `CASTHMA`, `COPD`, `CSMOKING`, `OBESITY`, `DIABETES` (prevalence %)

**Targets:**  
`CASTHMA` and `COPD` are the primary prediction targets. `CSMOKING`, `OBESITY`, `DIABETES` are confounders.

---

## Merge Process

**Join key:**  
5-digit FIPS (zero-padded: 2-digit state + 3-digit county). All sources standardized to this format before merging.

**Merge order:**  
1. **Base:** USGS Pesticide (county–year: one row per FIPS per year, 2016–2019)  
2. **Left join** Census ACS on FIPS (county-level; same row repeated for each year)  
3. **Left join** USDA Cropland on FIPS  
4. **Left join** CDC PLACES on FIPS  

**Rationale:** Pesticide is the primary exposure and varies by year; we retain all county–year pesticide rows. Census, cropland, and PLACES are county-level and are repeated for each year of each county. Counties missing from other sources receive NaN for those features.

**Handling of duplicates:**  
None expected; FIPS is unique per county. Pesticide data aggregated across years (mean) before merge.

---

## Temporal Alignment

| Source   | Time period        | Notes                                      |
|----------|--------------------|--------------------------------------------|
| Pesticide| 2016–2019           | Mean across years; treated as single snapshot |
| Cropland | 2019                | Single year                                |
| Census ACS | 2019 (5-year)    | 2015–2019 pooled                          |
| PLACES   | 2019 BRFSS          | Release 2021; model-based; aligned with census/cropland |

**Temporal alignment:** PLACES release 2021 uses 2019 BRFSS data, aligning with ACS 2019, cropland 2019, and overlapping with pesticide 2016–2019.

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

**File:** `data/joint_county_year_2016_2019.csv`  
**Format:** CSV  
**Generated by:** `EDA/joint_eda.ipynb`  

---

## Legal & Ethical Considerations

Same as individual sources: public, aggregated data; no PII. See individual datasheets for details. The joint dataset inherits limitations of each source (modeled estimates, ecological design).
