# spring-2026-pesticide-exposure
Team project: spring-2026-pesticide-exposure

# Problem:
Agricultural pesticide use varies widely by crop and region and may contribute to localized increases in preventable healthcare utilization (e.g., asthma, respiratory distress). Public health agencies and Medicaid programs need data-driven tools to target preventative interventions, such as Integrated Pest Management (IPM), under constrained budgets.

# Objective:
Build a county/region-level predictive risk model to identify regions in the United States where pesticide exposure is associated with elevated healthcare burden, enabling targeted, high-ROI public health and IPM investments.  Real world stakeholders include insurers, policy makers, hospital systems, public health departments.

# Modeling Approach:
Our predictive model will forecast the respiratory illnesses present in each geographic region from pesticide usage, as well as crop data and weather patterns. Our metric will therefore be Mean Squared Error (MSE), since we are predicting the raw case numbers. To make the map, we might categorize each region into bins based on several thresholds such as "high risk", "low risk", etc. which can then be used to create the risk map which could be presented to stakeholders to inform decisionmaking. If our model struggles with MSE regression, then we could potentially categorize the target variables in this way first, and then train a categorical regression such as logistic regression instead. 

Our primary datasets are:
1. CDC PLACES (County-level health indicators): https://www.cdc.gov/places/data/index.html
2. USGS / EPA Pesticide Use Estimates: https://water.usgs.gov
3. USDA Cropland Data Layer (Crop coverage): https://nassgeodata.gmu.edu/CropScape/

Our target years are 2016-2019, as these are the time periods of dataset overlap. We will treat this three year period as a single time instance, and time won't be a feature in our predictions. 

The (two?) respiratory illness that our model targets are COPD and Asthma, as these diseases have the most direct link to pesticide exposure in literature. These illness may have causes other than pesticide exposure but we'll try to control for that when building our model.


# Anti-goals: 
This project will NOT seek to definitively prove the link between respiratory illness and the use of pesticides. Such a causality has already been well established in scientific papers such as: 
1. Ye M, Beach J, Martin JW, Senthilselvan A. Occupational pesticide exposures and respiratory health. Int J Environ Res Public Health. 2013 Nov 28;10(12):6442-71. doi: 10.3390/ijerph10126442. PMID: 24287863; PMCID: PMC3881124.

2. Cecilia S. Alcalá, Cynthia Armendáriz-Arnez, Ana M. Mora, Maria G. Rodriguez-Zamora, Asa Bradman, Samuel Fuhrimann, Christian Lindh, María José Rosa,
Association of pesticide exposure with respiratory health outcomes and rhinitis in avocado farmworkers from Michoacán, Mexico,Science of The Total Environment,Volume 945,2024,173855,ISSN 0048-9697,https://doi.org/10.1016/j.scitotenv.2024.173855.

3. Salameh P, Waked M, Baldi I, Brochard P, Saleh BA. Respiratory diseases and pesticide exposure: a case-control study in Lebanon. J Epidemiol Community Health. 2006 Mar;60(3):256-61. doi: 10.1136/jech.2005.039677. PMID: 16476757; PMCID: PMC2465555.

And many others. We will however attempt to validate our predictive model by performing hypothesis testing on the coefficients and determining their statistical significance.


