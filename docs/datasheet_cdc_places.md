# Datasheet: CDC PLACES (County-Level Health Outcomes)

*Following Gebru et al. (2018) "Datasheets for Datasets"*

## Motivation for Dataset Creation

**Why was the dataset created?**  
CDC PLACES (Population Level Analysis and Community Estimates) provides model-based, small-area estimates of health outcomes and risk behaviors to support public health planning and research. It fills a gap in standardized, geographically comparable health data at county, place, census tract, and ZCTA levels.

**What (other) tasks could the dataset be used for?**  
- Public health surveillance and planning  
- Health disparities research  
- Predictive modeling of health outcomes (e.g., asthma, COPD)  
- Policy and intervention targeting  

**Tasks for which it should NOT be used:**  
- Individual-level diagnosis or clinical decision-making  
- Proving causality (estimates are modeled from BRFSS and other sources)  

**Who funded the creation of the dataset?**  
Centers for Disease Control and Prevention (CDC).

---

## Dataset Composition

**What are the instances?**  
Each instance is a geographic unit (county, place, census tract, or ZCTA) with one row per measure. We use **county-level** data.

**How many instances?**  
~3,100+ U.S. counties. One row per county per measure in long format; pivoted to one row per county with measure columns.

**What data does each instance consist of?**  
- `locationid` (5-digit FIPS for counties)  
- `measureid` (e.g., CASTHMA, COPD, CSMOKING, OBESITY, DIABETES)  
- `data_value` (prevalence %, crude or age-adjusted)  
- `year`, `datasource` (BRFSS), `category`  

**Is there a label/target?**  
Yes—CASTHMA and COPD are our primary targets. CSMOKING, OBESITY, DIABETES used as confounders.

**Subpopulations?**  
Estimates are model-based (MRP) and may vary in reliability by county size and demographic composition.

---

## Data Collection Process

**How was the data collected?**  
Model-based estimates using multilevel regression and poststratification (MRP) applied to Behavioral Risk Factor Surveillance System (BRFSS) and American Community Survey (ACS) data. Not direct surveys at county level.

**Over what time-frame?**  
PLACES releases map to BRFSS years (e.g., release 2020 → 2018 BRFSS, release 2021 → 2019 BRFSS). This project uses **releases 2020 (2018 BRFSS) and 2021 (2019 BRFSS)**; merged on FIPS + YEAR so the joint dataset has one PLACES row per county per year for 2018 and 2019.

**Does the dataset contain all possible instances?**  
All U.S. counties included in PLACES. Some counties may have higher uncertainty.

**Are there known errors?**  
Model-based estimates have confidence intervals. Small counties and rare subgroups may have wider uncertainty.

---

## Data Preprocessing (Project-Specific)

**What preprocessing was done in this project?**  
- Loaded via R CDCPLACES package or CDC SODA CSV  
- Pivoted from long (county × measure) to wide (one row per county, columns = measures)  
- FIPS standardized to 5-digit string  
- Measures used: CASTHMA, COPD, CSMOKING, OBESITY, DIABETES  

---

## Dataset Distribution

**How is the dataset distributed?**  
- CDC PLACES: https://www.cdc.gov/places/  
- CDC Open Data: https://data.cdc.gov/  
- R package: CDCPLACES (CRAN)  

**License / fees?**  
Public domain (U.S. Government). No fees.

---

## Legal & Ethical Considerations

**Does it relate to people?**  
Yes—health outcomes and behaviors. Data are aggregated; no individual-level PII.

**Were people informed/consent?**  
BRFSS respondents consent to survey participation. PLACES aggregates and models these data.

**Could it expose people to harm?**  
Low risk at county level. Stigmatization of high-prevalence areas is a possible concern.

**Sensitive/confidential?**  
Aggregated, de-identified. No PII in PLACES outputs.
