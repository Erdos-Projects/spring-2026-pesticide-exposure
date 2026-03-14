# Datasheet: USGS Pesticide Use Estimates

*Following Gebru et al. (2018) "Datasheets for Datasets"*

## Motivation for Dataset Creation

**Why was the dataset created?**  
The USGS Pesticide National Synthesis Project provides county-level estimates of agricultural pesticide use to support water-quality modeling, ecological risk assessment, and public health research. The data fill a gap in publicly available, spatially explicit pesticide use estimates for the United States.

**What (other) tasks could the dataset be used for?**  
- Water quality and watershed modeling  
- Ecological risk assessment  
- Public health / environmental epidemiology (e.g., pesticide–respiratory outcome associations)  
- Policy and regulatory analysis  

**Tasks for which it should NOT be used:**  
- Individual-level exposure assessment (data are county-level aggregates)  
- Proving causality (estimates are modeled, not measured; ecological fallacy applies)  

**Who funded the creation of the dataset?**  
U.S. Geological Survey (USGS), National Water-Quality Assessment Program.

---

## Dataset Composition

**What are the instances?**  
Each instance is a county–year–compound combination. Counties are identified by 5-digit FIPS (state + county).

**How many instances?**  
~3,066 counties with pesticide data; hundreds of compounds per county per year. Years 2016–2019 used in this project.

**What data does each instance consist of?**  
- `STATE_FIPS_CODE`, `COUNTY_FIPS_CODE` (or derived `FIPS`)  
- `YEAR`  
- `COMPOUND` (e.g., atrazine, glyphosate, chlorpyrifos)  
- `EPEST_LOW_KG`, `EPEST_HIGH_KG` (estimated kg applied; we use mean)  
- Derived: `chemical_class` (Organophosphate, Carbamate, Pyrethroid, Triazine, etc. per Shekhar et al. 2024)

**Is there a label/target?**  
No; this is an input/feature dataset. Targets (asthma, COPD) come from CDC PLACES.

**Are there recommended data splits?**  
In the joint pipeline, pesticide is filtered to 2018–2019 and kept at county–year level (one row per county per year). Temporal or spatial holdouts can be used for evaluation.

---

## Data Collection Process

**How was the data collected?**  
Model-based estimates derived from USDA surveys of pesticide use by crop, combined with USDA Cropland Data Layer and other spatial data. Not direct measurements.

**Over what time-frame?**  
Annual estimates; we use 2016–2019.

**Does the dataset contain all possible instances?**  
Covers CONUS counties with significant agricultural activity. Some counties may have no or minimal pesticide use reported.

**Are there known errors, sources of noise?**  
Estimates have uncertainty (low/high bounds). Model assumptions and input data quality affect accuracy. Undercounting of some compounds or uses is possible.

---

## Data Preprocessing (Project-Specific)

**What preprocessing was done in this project?**  
- FIPS standardized to 5-digit string  
- `EPEST_MEAN_KG` = mean of low/high bounds  
- Chemical class assignment via substring matching on compound names (Shekhar et al. 2024)  
- Aggregation: total kg, by chemical class, respiratory-relevant (OP, Carbamate, Pyrethroid), and by individual compound  

---

## Dataset Distribution

**How is the dataset distributed?**  
ScienceBase (USGS): https://www.sciencebase.gov/catalog/  
Direct URLs used in project: ScienceBase file downloads for 2016–2017, 2018, 2019.

**License / fees?**  
Public domain (U.S. Government). No fees.

---

## Legal & Ethical Considerations

**Does it relate to people?**  
Indirectly—county-level aggregates, not individual data. No PII.

**Could it expose people to harm?**  
Low risk at county level. Stigmatization of agricultural regions is a possible concern; framing should emphasize targeting resources, not blame.

**Sensitive/confidential?**  
No. Public, aggregated data.
