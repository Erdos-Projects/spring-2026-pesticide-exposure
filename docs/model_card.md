# Model Card: County-Level Pesticide–Respiratory Risk Model

*Following Mitchell et al. (2019) "Model Cards for Model Reporting"*

> **Status:** Template / placeholder. No model has been trained yet. This card will be updated when modeling is complete.

---

## Model Details

**Model type:** *TBD* (e.g., linear regression, random forest, gradient boosting)  
**Model version:** *TBD*  
**Date created:** *TBD*  
**Developers:** *TBD*  
**Point of contact:** *TBD*

---

## Intended Use

**Primary intended use:**  
Predict county-level prevalence of asthma (CASTHMA) and COPD from pesticide use estimates, cropland composition, and demographic/health confounders. Intended to support resource allocation, policy targeting, and research—not individual diagnosis or legal evidence.

**Intended users:**  
- Public health agencies and policymakers  
- Researchers in environmental epidemiology  
- Insurers and health systems (for population-level planning)

**Out-of-scope uses:**  
- Individual-level diagnosis or clinical decision-making  
- Causal inference (model is associative; ecological fallacy applies)  
- Real-time or near-term forecasting without retraining

---

## Factors

**Relevant factors:**  
- Geographic region (county FIPS)  
- Pesticide use (total kg, by chemical class, respiratory-relevant compounds)  
- Cropland composition (corn, soybean, cotton, wheat, hay, diversity)  
- Demographics (age, income, race/ethnicity)  
- Health behaviors (smoking, obesity, diabetes)

**Evaluation factors:**  
- Performance by region (e.g., Midwest vs. other)  
- Performance by county size (population, cropland area)  
- Fairness across demographic subgroups (race/ethnicity, income)

---

## Metrics

**Model performance metrics:**  
- *TBD* (e.g., MSE, MAE, R² for regression; RMSE for county-level predictions)  
- *TBD* (e.g., correlation with held-out PLACES estimates)

**Decision thresholds:**  
- *TBD* (if model is used for binary classification or risk tiers)

**Variation across groups:**  
- *TBD* (performance by region, county size, demographic composition)

---

## Evaluation Data

**Training data:**  
- USGS Pesticide Use Estimates (2018–2019, county–year)  
- CDC PLACES (2018 and 2019 BRFSS; CASTHMA, COPD, CSMOKING, OBESITY, DIABETES; merged on FIPS + YEAR)  
- USDA Cropland Data Layer (2019)  
- US Census ACS 5-year (2019)

**Evaluation data:**  
- *TBD* (e.g., temporal holdout by year, or spatial holdout by region)  
- See datasheets in `docs/` for dataset details.

---

## Training Data

**Data preprocessing:**  
- Joint county–year dataset: `data/joint_county_year_2018_2019.csv` (one row per county per year for 2018 and 2019)  
- FIPS standardized; pesticide filtered to 2018–2019, aggregated by chemical class and respiratory-relevant compounds  
- Census and cropland merged by FIPS; PLACES and county_year_collapsed merged by FIPS + YEAR  

**Known limitations:**  
- Ecological design: county-level associations do not imply individual-level causation  
- Pesticide estimates are modeled, not measured  
- PLACES outcomes are model-based (MRP)  
- Temporal alignment: 2018 and 2019 (PLACES releases 2020 and 2021); census and cropland are county-level and repeated by year

---

## Quantitative Analyses

*To be filled when model is trained.*

| Metric        | Overall | By region | By county size |
|---------------|---------|-----------|----------------|
| MSE / RMSE    | *TBD*   | *TBD*     | *TBD*          |
| R²            | *TBD*   | *TBD*     | *TBD*          |
| Correlation   | *TBD*   | *TBD*     | *TBD*          |

---

## Ethical Considerations

**Risks:**  
- Stigmatization of agricultural counties or demographic groups  
- Misuse for blame rather than resource allocation  
- Overinterpretation of associations as causation  

**Mitigations:**  
- Clear documentation of limitations (ecological design, modeled data)  
- Emphasis on population-level planning, not individual inference  
- Fairness evaluation across demographic subgroups when model is trained  

**Recommendations:**  
- Use model outputs to target resources and interventions, not to penalize regions or groups  
- Pair with qualitative and domain expertise for policy decisions  

---

## Caveats and Recommendations

- **Ecological fallacy:** County-level associations do not apply to individuals.  
- **Data quality:** Pesticide and PLACES data are estimates with uncertainty.  
- **Temporal alignment:** Data aligned to 2018 and 2019 (PLACES releases 2020 and 2021; pesticide county–year; census and cropland county-level). Consider retraining when newer data become available.  
- **Recommendation:** Treat this as a research and planning tool; validate findings with domain experts and additional data sources.
