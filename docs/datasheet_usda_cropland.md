# Datasheet: USDA Cropland Data Layer (CDL)

*Following Gebru et al. (2018) "Datasheets for Datasets"*

## Motivation for Dataset Creation

**Why was the dataset created?**  
The USDA National Agricultural Statistics Service (NASS) Cropland Data Layer provides raster, crop-specific land cover data to support agricultural policy, commodity forecasting, and environmental research. County-level statistics (acreage by crop category) are derived via the CropScape web service.

**What (other) tasks could the dataset be used for?**  
- Agricultural land use and crop acreage estimation  
- Environmental and water quality modeling  
- Predictive modeling of pesticide use (crop mix drives pesticide profiles)  
- Conservation and land management  

**Tasks for which it should NOT be used:**  
- Field-level precision (30 m resolution; some misclassification)  
- Legal or property boundary determination  

**Who funded the creation of the dataset?**  
USDA NASS, with support from other federal and state partners.

---

## Dataset Composition

**What are the instances?**  
Each instance is a county–year combination with acreage by land-cover/crop category. Categories include Corn, Soybeans, Cotton, Wheat, Hay, Forest, Developed, etc.

**How many instances?**  
~3,100 U.S. counties. One CDL stat request per county per year. We use 2019 for this project.

**What data does each instance consist of?**  
- County FIPS  
- Category/Class name (e.g., "Corn", "Soybeans", "Developed Land")  
- Acres (or similar area column)  
- Derived in project: `cropland_acres`, `pct_cropland`, `corn_acres`, `soybean_acres`, `cotton_acres`, `wheat_acres`, `hay_acres`, `fruit_veg_acres`, `cropland_diversity`  

**Is there a label/target?**  
No; this is an input/feature dataset.

---

## Data Collection Process

**How was the data collected?**  
Satellite imagery (Landsat, etc.) classified using machine learning and ground truth. County statistics derived by summing pixel acreages within county boundaries.

**Over what time-frame?**  
Annual; CDL available 2008–present. We use 2019.

**Does the dataset contain all possible instances?**  
All CONUS counties. Some counties (e.g., urban, water) may have minimal cropland.

**Are there known errors?**  
Classification errors occur; small or heterogeneous fields may be misclassified. Water, forest, and developed land generally more reliable than fine-grained crop distinctions.

---

## Data Preprocessing (Project-Specific)

**What preprocessing was done in this project?**  
- Fetched via CropScape GetCDLStat API (parallel requests)  
- Categories grouped: corn, soybean, cotton, wheat, hay, fruit/vegetable, rice, sorghum  
- Non-crop (developed, water, forest, wetland, etc.) excluded from cropland total  
- `pct_cropland` = 100 × cropland_acres / total_area  
- `cropland_diversity` = number of distinct crop categories  

---

## Dataset Distribution

**How is the dataset distributed?**  
- CropScape: https://nassgeodata.gmu.edu/CropScape/  
- GetCDLStat API: https://nassgeodata.gmu.edu/axis2/services/CDLService/GetCDLStat  

**License / fees?**  
Public domain (U.S. Government). No fees. API may have rate limits.

---

## Legal & Ethical Considerations

**Does it relate to people?**  
Indirectly—land use, not individuals. No PII.

**Sensitive/confidential?**  
No. Public, aggregated land cover data.
