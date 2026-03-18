# Schema: IPM Integration (County–Crop–Year → County–Year)

This document describes the data model for integrating IPM (Integrated Pest Management) with the county–year analysis. The goal is to keep **county–year** as the final unit while respecting how IPM sources are structured: **crop/commodity × geography × document type**, typically state or region, not county.

**Important framing:** County–year IPM measures should be interpreted as  
**"the IPM characteristics of the crop mix grown in this county"**  
—not as "measured county adoption of IPM."

---

## Design principle

- **County–year outcome** (respiratory, pesticide burden) is the target.
- **County–crop–year** is the integration layer: crop composition (acres, value) per county per year.
- **Crop–state–year IPM scores** come from documents (Crop Profiles, PMSPs) and are joined to county crops via crop + state.
- **Collapse** to county–year using defensible weights (acreage, value, or pesticide-risk), so the model does not "learn" crop structure from a handful of crop acreage columns but explicitly uses weighted IPM indices.

---

## Tables

### 1. `county_crop_year_ag`

County–crop–year composition from CDL (and optionally NASS for value).

| Column | Description |
|--------|-------------|
| `FIPS` | 5-digit county FIPS |
| `year` | 2016–2019 (or CDL year) |
| `crop` | Standard crop name (e.g. corn, soybean, cotton, wheat, hay, fruit_veg, rice, sorghum, other_crop) |
| `acres` | Crop acreage in county-year |
| `crop_value` | Optional: value of production (from NASS; NaN if not available) |
| `share_county_crop_acres` | acres / sum(acres) over crops in that county-year |
| `share_county_crop_value` | crop_value / sum(crop_value) in county-year (NaN if no value data) |

**Source:** USDA CDL via CropScape (acreage by category); NASS for value if added later.  
**Note:** CDL is currently fetched for 2019 only in the main joint EDA; county_crop_year_ag is expanded to all years present in the pesticide data (2016–2019), but the **joint dataset** keeps only 2018–2019 (merge with PLACES and county_year_collapsed on FIPS + YEAR).

---

### 2. `crop_geo_doc_ipm`

IPM document-derived scores per crop × geography × document year.

| Column | Description |
|--------|-------------|
| `crop` | Crop/commodity name (align with county_crop_year_ag); inferred from SOURCE title |
| `state_or_region` | State FIPS (2-digit); from `/state` mapping using source REGION name |
| `document_year` | Year parsed from SOURCEDATE (e.g. "August, 01 2000 00:00:00" → 2000) |
| `document_type` | e.g. Crop Profile, PMSP (from API SOURCETYPE) |
| `source_id` | SOURCEID from API; use for joining to `/sourcereport` or document content |
| `url` | Document URL from API for traceability |
| `ipm_breadth_index` | **Raw** composite: nonchemical / threshold / monitoring emphasis (kept; not overwritten by rescale) |
| `chemical_reliance_index` | **Raw** composite: how central pesticide use is (kept) |
| `ipm_breadth_index_rescaled` | 0–1 min-max rescaled across documents (optional for modeling) |
| `chemical_reliance_index_rescaled` | 0–1 min-max rescaled across documents (optional) |
| `monitoring_score`, `nonchemical_score`, … | Subscales (optional) |
| `text_parse_quality`, `geo_match_confidence` | QA for coverage/confidence features |

**How to fully source this table:**

1. **Geography (state_or_region)**  
   The `/source` endpoint returns **REGION** (e.g. "Southern", "Western"), not state FIPS. Use the `/state` endpoint to build a mapping: REGION name → list of state FIPS. Match each source’s REGION to that mapping; if the source uses region names that don’t match exactly (e.g. "Southern"), map by prefix (e.g. "Sout" → Southeast, Southcentral, Southwest) and take the union of state FIPS. Emit one row per (crop, state_fips); drop any row where state would be "00" or missing.

2. **Document year (document_year)**  
   SOURCEDATE is a string like `"August, 01 2000 00:00:00"`. Parse the 4-digit year (e.g. with a regex `\b(19|20)\d{2}\b`) so every document has a numeric year when possible.

3. **Scores (ipm_breadth_index, chemical_reliance_index, subscales)**  
   The API does not return pre-computed scores. Options in `joint_eda.ipynb`: (a) **Metadata-based (default):** heuristic from document_type, year, crop; (b) **PDF keyword-based (optional):** set `USE_PDF_SCORING=True`, install `pdfminer.six`, fetch PDFs and count keywords. (c) **Manually code** a sample into subscales and impute, or use placeholders so county-year collapse is non-NaN.

**Source:** National IPM Database API (`https://ipmdata.ipmcenters.org/rest/...`). Crop Profiles (sourcetypeid=3), PMSPs (sourcetypeid=4).  
**Implementation:** Inline in `EDA/joint_eda.ipynb` Section 3b. Lexicons tightened (ambiguous terms like organic, application, treatment, timing, pollinator, integrated, reduced-risk removed). Raw indices kept; optional 0–1 rescaled columns added. PDF via pdfminer + PyMuPDF fallback; HTML source report when PDF fails. Optional `USE_MOST_RECENT_DOC_ONLY`: fetch only the newest document per (crop, state_fips) to speed run. Document-level rows are aggregated by **recency-weighted mean** per (crop, state_fips, analysis_year), not simple mean, so document_year is not averaged away.  
**Status:** Fetched from API; geography and year from REGION and SOURCEDATE; scores from content (and priors when text is missing).

---

### 3. `county_crop_year_ipm`

Join of county crop composition to crop–geo IPM scores.

| Column | Description |
|--------|-------------|
| `FIPS` | County FIPS |
| `year` | Year |
| `crop` | Crop |
| `crop_family` | Broader crop family used for fallback matching (e.g. `field_crop`, `forage`, `specialty_crop`) |
| `acres`, `crop_value`, `share_county_crop_acres`, `share_county_crop_value` | From county_crop_year_ag |
| `ipm_breadth_index`, `chemical_reliance_index`, `*_rescaled`, `mean_text_quality`, `mean_geo_confidence`, `weighted_doc_age`, `n_docs` | From crop_state_ipm (recency-weighted by analysis year) |
| `ipm_match_tier` | Provenance of the match: `exact_crop_state`, `crop_family_state`, `exact_crop_national`, or `crop_family_national` |
| `ipm_source_crop`, `ipm_source_crop_family`, `ipm_source_state_fips` | Traceability fields describing which IPM slice supplied the score |

Primary join key: **crop + state_fips + year**. Crop–state IPM is one row per (crop, state_fips, year) with recency-weighted scores and coverage/quality/age.

**Recommended fallback ladder for coverage:**  
1. Exact crop + state + year  
2. Crop family + state + year  
3. Exact crop + national + year  
4. Crop family + national + year  

This preserves the preferred county crop semantics while reducing unnecessary missingness when exact state-level document coverage is sparse.

---

### 4. `county_year_collapsed`

County–year roll-up from county_crop_year_ipm (or county_crop_year_ag when IPM is missing).

| Column | Description |
|--------|-------------|
| `FIPS` | County FIPS |
| `year` | Year |
| **Acreage-weighted (primary)** | |
| `ipm_breadth_acre` | ∑_k (share_acres_k) × IPMBreadth_raw (raw indices) |
| `chemical_reliance_acre` | ∑_k (share_acres_k) × ChemReliance_raw |
| `ipm_breadth_acre_rescaled`, `chemical_reliance_acre_rescaled` | Same with 0–1 rescaled indices (optional for modeling) |
| **Value-weighted (sensitivity)** | |
| `ipm_breadth_value`, `chemical_reliance_value` | Value-weighted (NaN if no NASS) |
| **Coverage / confidence** | |
| `ipm_doc_coverage_share` | Share of county crop acres with a matching IPM document |
| `mean_text_quality` | Acre-weighted mean of text_parse_quality (0–1) over IPM-matched crops |
| `mean_geo_confidence` | Acre-weighted mean of geo_match_confidence over IPM-matched crops |
| `weighted_doc_age` | Acre-weighted mean of (analysis_year − document_year) over IPM-matched crops |
| **Composition** | |
| `county_crop_concentration` | e.g. Herfindahl of acre shares |
| `specialty_crop_share` | Share of acres in fruit_veg, etc. |
| `total_ag_value` | Sum of crop_value in county-year (if available) |
| `ipm_primary_match_tier` | Acreage-dominant provenance tier among matched county crops |

**Weighting formulas:**

- **Acreage-weighted:**  
  \( \text{IPM}_{ct}^{\text{acre}} = \sum_k \frac{\text{acres}_{ckt}}{\sum_k \text{acres}_{ckt}} \cdot \text{IPMScore}_{kst} \)  
  Answers: *What is the IPM environment of the land actually under production in this county?* Best default for environmental exposure.

- **Value-weighted:**  
  \( \text{IPM}_{ct}^{\text{value}} = \sum_k \frac{\text{value}_{ckt}}{\sum_k \text{value}_{ckt}} \cdot \text{IPMScore}_{kst} \)  
  Answers: *What is the IPM environment of the economically important crop mix?* Use for economic-demand sensitivity.

- **Pesticide-risk-weighted:**  
  \( \text{IPM}_{ct}^{\text{risk}} = \sum_k \frac{\text{burden}_{ckt}}{\sum_k \text{burden}_{ckt}} \cdot \text{IPMScore}_{kst} \)  
  Answers: *What is the IPM environment of the crops most responsible for pesticide burden?* Most policy-relevant when respiratory burden is central. Requires county–crop–year burden (e.g. from USGS by crop or proxy); may be approximated or skipped until available.

---

## Use in the joint county–year dataset

- **Primary crop representation for IPM:** Use the collapsed indices from `county_year_collapsed` (acreage-weighted IPM breadth and chemical reliance as main; value-weighted as sensitivity; risk-weighted as exploratory).
- **Exposure denominators:** Keep or add: total kg, kg per cropland acre, respiratory-relevant kg per crop acre, and crop-weighted IPM scores as above.
- **Temporal clarity:** Census and single-year CDL are merged on FIPS and repeated across 2018–2019; PLACES and county_year_collapsed are merged on FIPS + YEAR. See [`datasheets.md`](datasheets.md) for time-varying vs static variables.

---

## File locations (conventional)

**Note:** In the current pipeline, `county_crop_year_ag`, `crop_geo_doc_ipm`, and `county_year_collapsed` are built **in memory** in `EDA/build_joint_dataset.ipynb` and are not written to `data/` by default. The joint output is `data/joint_county_year_2018_2019.csv`, which already includes the collapsed IPM indices. The paths below are the logical schema; to persist intermediate tables, add export steps in the notebook.

| Table | File / producer |
|------|------------------|
| county_crop_year_ag | Built in EDA (`build_joint_dataset.ipynb`); in-memory unless exported |
| crop_geo_doc_ipm | Built in EDA from IPM API; in-memory unless exported |
| county_crop_year_ipm | Built in notebook; optional intermediate save |
| county_year_collapsed | Built in EDA; merged into joint county–year table; in-memory unless exported |
