# Datasheet: US Census American Community Survey (ACS) 5-Year Estimates

*Following Gebru et al. (2018) "Datasheets for Datasets"*

## Motivation for Dataset Creation

**Why was the dataset created?**  
The ACS provides detailed demographic, social, economic, and housing data for geographic areas across the U.S. The 5-year estimates offer the most reliable data for smaller areas (e.g., counties) by pooling five years of surveys.

**What (other) tasks could the dataset be used for?**  
- Demographic and socioeconomic research  
- Policy and planning  
- Confounding adjustment in health/environmental models (age, income, race)  
- Fairness and disparity analysis  

**Tasks for which it should NOT be used:**  
- Real-time or single-year precision (5-year estimates are smoothed)  
- Individual-level inference  

**Who funded the creation of the dataset?**  
U.S. Census Bureau (Department of Commerce).

---

## Dataset Composition

**What are the instances?**  
Each instance is a county (or other geographic unit). We use county-level ACS 5-year estimates.

**How many instances?**  
~3,200 U.S. counties.

**What data does each instance consist of?**  
- `NAME`, `state`, `county`, `FIPS`  
- `B01003_001E`: Total population  
- `B01002_001E`: Median age  
- `B19013_001E`: Median household income  
- `B03002_001E`, `B03002_003E`, `B03002_004E`, `B03002_006E`, `B03002_012E`: Race/ethnicity (total, White, Black, Asian, Hispanic)  
- Derived: `pct_white`, `pct_black`, `pct_asian`, `pct_hispanic`  

**Is there a label/target?**  
No; these are confounders/covariates.

**Subpopulations?**  
Race/ethnicity and other demographics enable disparity and fairness analyses.

---

## Data Collection Process

**How was the data collected?**  
Continuous household survey. ACS samples ~3.5 million addresses per year. Estimates produced using survey weights and statistical methods.

**Over what time-frame?**  
We use 2019 ACS 5-year (2015–2019). Collection is ongoing.

**Does the dataset contain all possible instances?**  
All U.S. counties. Some small counties have higher margins of error.

**Are there known errors?**  
Survey estimates have margins of error (MOE). Census uses -666666666, -222222222 as null/withheld codes for some variables.

---

## Data Preprocessing (Project-Specific)

**What preprocessing was done in this project?**  
- Fetched via Census API: `https://api.census.gov/data/2019/acs/acs5`  
- FIPS = state (2-digit) + county (3-digit), zero-padded  
- Race percentages = 100 × (group count / total pop_race)  
- Null codes replaced with NaN for analysis  

---

## Dataset Distribution

**How is the dataset distributed?**  
- Census API: https://api.census.gov/  
- Census Bureau data portal  

**License / fees?**  
Public domain (U.S. Government). No fees. API key optional for higher rate limits.

---

## Legal & Ethical Considerations

**Does it relate to people?**  
Yes—demographics. Data are aggregated; no individual PII in county-level tables.

**Could it unfairly advantage/disadvantage groups?**  
Demographic variables enable controlling for confounders and assessing fairness. Careful interpretation needed to avoid reinforcing stereotypes.

**Sensitive/confidential?**  
Aggregated; Census disclosure avoidance applied. No PII at county level.
