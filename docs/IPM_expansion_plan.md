# IPM Data Pipeline Expansion Plan

This document is the deliverable from the LLM instruction block for expanding IPM coverage in the pesticide–respiratory research repo. It summarizes the current pipeline, coverage gaps, candidate sources, expansion strategies, feature schema, and implementation order.

---

## 1. Current pipeline summary

**Location:** [EDA/build_joint_dataset.ipynb](../EDA/build_joint_dataset.ipynb) (IPM section: crop_geo_doc_ipm, aggregate to crop_state, join to county_crop_year, collapse to county_year). See also [docs/schema_ipm_integration.md](schema_ipm_integration.md).

### Sources currently used

- **National IPM Database** (REST API: `https://ipmdata.ipmcenters.org/rest/ipmdata_ipmcenters_org_restapi`).
  - **Document types:** Only **Crop Profiles** (`sourcetypeid=3`) and **Pest Management Strategic Plans (PMSPs)** (`sourcetypeid=4`). The database also contains **Elements**, **Priority** documents, **Pest-centric Management Strategic Plans**, and **Timelines** (other sourcetypeids), which are not currently queried.
- **Content:** Document metadata (title, SOURCEDATE, REGION, URL) from the API; document text from **PDF fetch** (when URL available) via pdfminer.six + PyMuPDF fallback, or **HTML report** (`source_report.cfm?sourceid=...`) when PDF fails.
- **Scoring:** Lexicon-based counts (monitoring, nonchemical, chemical, decision_support, dependency, resistance_management) on full text and regex-detected sections → `ipm_breadth_index`, `chemical_reliance_index`; blended with metadata priors when text is missing.

### Geographic unit

- **Document level:** API returns **REGION** (e.g. Southern, North Central, Western, Northeastern) or multi-state lists. The pipeline maps REGION → list of **state FIPS** via `/state` endpoint (regionid/region name → state_fips). One row per **(crop, state_fips)** per document; "ALL" used when no state list.
- **Aggregation:** Recency-weighted mean per **(crop, state_fips, analysis_year)**.
- **County:** Counties get IPM by **join on crop + state_fips** (county’s state) from `county_crop_year_ag`; no county-level IPM source.

### Time unit

- **Document:** `document_year` parsed from SOURCEDATE (e.g. "August, 01 2000 00:00:00" → 2000).
- **Analysis:** `ANALYSIS_YEARS_IPM = [2018, 2019]`; crop_state IPM is recency-weighted by document_year for each analysis year.
- **County-year:** Final table is county–year (FIPS + YEAR); IPM indices are acreage- (and optionally value-) weighted over county crops.

### Current bottlenecks for coverage

1. **Only two source types:** Crop Profiles and PMSPs; Elements, Priorities, Pest-centric PMSPs, and Timelines are unused.
2. **Crop from title only:** Crop inferred from SOURCE title via keyword match (`_crop_from_title`); no structured crop/commodity field from API, so mismatches and "other_crop" for non-mapped titles.
3. **Geography is region→state:** Documents are region- or multi-state; state_fips is derived. No county or sub-state geography; sparse state–crop combinations fall back to crop_family or national ("ALL").
4. **Document age:** Many documents are pre-2015; recency weighting helps but guidance may be stale for 2018–2019.
5. **No practice/adoption data:** Pipeline measures **guidance** (what documents recommend), not what growers do; no survey or adoption data.
6. **Missing when no document:** Counties/crops with no matching (crop, state) document get metadata-only priors or NA in collapse; `ipm_doc_coverage_share` and match tiers expose this.

---

## 2. Coverage gaps

- **Crop–state–year cells** with no Crop Profile or PMSP (e.g. minor crops, states with few uploaded docs).
- **Interpretation:** All current IPM features are **guidance** (document-derived), not reported **practices** or **adoption**.
- **County:** No direct county-level IPM measure; county = weighted crop-mix of crop–state guidance.
- **Time:** 2018–2019 alignment relies on recency-weighted document years; no explicit 2018/2019 survey or report dates for most docs.

---

## 3. Candidate data sources

### Guidance sources (documents describing recommended pest management)

| Source | Link | Scope | Format | Unit of analysis | Years | Fit | Limitations |
|--------|------|--------|--------|-------------------|-------|-----|--------------|
| National IPM Database – Crop Profile, PMSP | https://ipmdata.ipmcenters.org/ (API: /source?sourcetypeid=3,4) | National, regional, state, crop-specific | API (metadata) + PDF/HTML (text) | Document → crop × region/state | Various (1990s–2020s) | **In use** | Region→state; crop from title; no county. |
| National IPM Database – Elements | Same API; sourcetypeid for "Element" (e.g. 5 or per docs) | Regional/state, crop-specific | PDF/HTML | Document → crop × state | 2015–2023 common | **Good** | Need to discover sourcetypeid; often shorter; same geo/crop mapping issues. |
| National IPM Database – Priority | e.g. source_list.cfm?sourcetypeid=11 | Regional/state, crop or “No Crop” | PDF/HTML | Document → region/state | 2018–2022 | **Moderate** | Priorities, not full guidance; “No Crop” entries. |
| National IPM Database – Pest-centric PMSP | Via source_list / API | Crop/commodity × state/region | PDF/HTML | Document → crop × state | Recent (e.g. 2025–2026) | **Good** | Same pipeline; adds pest-centric plans. |
| Regional IPM Centers (crop–pest data) | https://www.ipmcenters.org/crop-pest-data/ ; Southern IPM: https://southernipm.org/ipm-data/ | Regional, state, crop | Web/links; National IPM Database is the shared backend | Same as National IPM Database | Same | **Redundant** for docs; portals point to same DB. | Not an additional dataset; use for discovery/validation. |

### Practice / adoption sources (what growers report doing)

| Source | Link | Scope | Format | Unit of analysis | Years | Fit | Limitations |
|--------|------|--------|--------|-------------------|-------|-----|--------------|
| USDA ARMS (pest management practices) | https://www.ers.usda.gov/data-products/arms-farm-financial-and-crop-production-practices/ | National, crop × state (rotating crops) | Structured (survey microdata / tailored reports) | Farm survey → crop × state; some state-level estimates | 1996–2010 (e.g. corn 2001, 2005, 2010; pest mgt in Phase II) | **High value, date mismatch** | **Practice/adoption** not guidance. No 2018–2019 pest mgt wave; ERS tailored reports by crop, state, year. Best for “IPM practice” proxy (scouting, thresholds, etc.) if using nearest year or state-level. |
| NASS Chemical Use Survey | https://www.nass.usda.gov/Surveys/Guide_to_NASS_Surveys/Chemical_Use/ | National, state-level for target crops | Structured (state × crop × chemical) | State × crop × year | 2018 (e.g. corn, soybeans, peanuts), 2019 (e.g. wheat, field crops) | **Good for 2018–2019** | **Chemical use**, not IPM breadth; can proxy intensity/complexity. State-level, not county. |
| California Pesticide Use Reporting (PUR) | California DPR (annual reports by commodity, chemical) | State (CA), commodity/crop | Structured | State × commodity × year (county available in some products) | Annual | **Niche** | CA only; pesticide use, not IPM guidance. |

### Capacity / infrastructure sources (grants, extension, institutional IPM support)

| Source | Link | Scope | Format | Unit of analysis | Years | Fit | Limitations |
|--------|------|--------|--------|-------------------|-------|-----|--------------|
| NIFA CPPM / IPM grants | https://www.nifa.usda.gov/grants/programs/crop-protection-pest-management-program ; https://www.nifa.usda.gov/grants/programs/integrated-pest-management-program-ipm | National → state/region/institution | Semi-structured (grant awards) | Project × state/institution × year | Award years (e.g. 2021–2026) | **Moderate** | **Capacity** (funding, extension presence), not guidance or practice. Would need scraping/API of NIFA reporting (e.g. CRIS) to get state/institution; could support `ipm_capacity_*` at state level. |
| Regional IPM Centers (funding/priorities) | https://www.ipmcenters.org/ | Regional | Web/organizational | Region | Ongoing | **Low** for new data | Structural; same doc set as National IPM Database. |
| Land-grant extension (IPM programs) | State extension websites | State, sometimes crop | Web, PDF, semi-structured | State × program | Varies | **Possible but labor-intensive** | Would require scraping or manual coding; state-level capacity/availability. |

**Validity note:** Guidance (current pipeline) ≠ adoption. Adding ARMS or NASS chemical use would introduce **practice/use**; interpret and label clearly (e.g. `ipm_guidance_*` vs `ipm_practice_*`) and do not mix scales without justification.

---

## 4. Best expansion strategies

### Strategy A: Minimal change (extend current notebook)

- **Add National IPM Database source types:** Query **Elements** and **Pest-centric Management Strategic Plans** (discover sourcetypeids from API or source_list.cfm), and optionally **Priority** (e.g. 11). Reuse existing PDF/HTML fetch and lexicon scoring; emit same schema (crop, state_fips, document_year, ipm_breadth_index, chemical_reliance_index, etc.) with a `document_type` column.
- **Improve crop mapping:** Prefer structured crop/commodity from API if available (e.g. from `/source` or related endpoints); otherwise extend `TITLE_TO_CROP` and crop-family fallbacks for Element/Priority titles.
- **Result:** More documents per (crop, state), better coverage and recency mix; same county-year integration (join on crop + state_fips, then collapse). No new data owner or unit of analysis.

### Strategy B: Medium effort (one external structured dataset)

- **Add NASS Chemical Use (state × crop × year):** Use 2018 and 2019 NASS chemical use surveys (state-level for target crops). Derive state–crop–year features (e.g. % acres treated with herbicides/insecticides/fungicides, or intensity indices). Join to county via **state_fips** (county’s state); optionally weight by county crop composition from `county_crop_year_ag`.
- **Output:** New columns in county-year table, e.g. `nass_herbicide_pct_acres_state`, `nass_insecticide_pct_acres_state` (or similar), with clear naming that they are **state-level** and **chemical use**, not IPM guidance. Complements existing `ipm_breadth_acre` / `chemical_reliance_acre`.
- **Caveat:** State-level only; no within-state variation.

### Strategy C: High coverage (multiple source types)

- **Guidance:** Strategy A (more document types from National IPM Database) + improved section/HTML parsing and crop/state mapping.
- **Practice:** ARMS pest management (Phase II) for nearest available years (e.g. 2010) as state–crop **practice** proxy; or NASS chemical use (Strategy B) for 2018–2019 **use** proxy. Document that ARMS is adoption-oriented and may be lagged.
- **Capacity:** NIFA CPPM/IPM grant data (CRIS or public awards) aggregated to **state × year** (e.g. dollars or project count) → `ipm_capacity_*` at state, merged to county by state_fips.
- **Result:** Three families of features (guidance, practice/use, capacity); county-year table gains multiple IPM-related columns with explicit interpretation. Requires handling different units (document vs survey vs grant) and missingness.

---

## 5. Recommended feature schema

Organize new and existing IPM-related columns into families. Keep existing names where they are already in use; add new ones with clear prefixes.

### `ipm_guidance_*` (document-derived; “IPM character of the crop mix”)

- **Existing (keep):** `ipm_breadth_acre`, `chemical_reliance_acre`, `ipm_breadth_acre_rescaled`, `chemical_reliance_acre_rescaled`; `ipm_breadth_value`, `chemical_reliance_value`; `ipm_doc_coverage_share`, `mean_text_quality`, `mean_geo_confidence`, `weighted_doc_age`, `ipm_primary_match_tier`.
- **Optional new:** `ipm_guidance_doc_count` (number of documents contributing to crop–state–year), `ipm_guidance_element_share` (share of guidance from Elements vs CP/PMSP) if multiple source types are merged.

### `ipm_practice_*` (survey/use; “reported or estimated practice/use”)

- **From NASS (state-level):** e.g. `ipm_practice_nass_herbicide_pct_acres`, `ipm_practice_nass_insecticide_pct_acres` (or by crop if joined as state–crop–year then weighted). Name with `_state` suffix if purely state-level.
- **From ARMS (if added):** e.g. `ipm_practice_arms_scouting_pct` (or similar), with year and state in metadata; label as adoption/practice.

### `ipm_capacity_*` (institutional support; state or region)

- **From NIFA/CRIS (if added):** e.g. `ipm_capacity_nifa_projects_state`, `ipm_capacity_nifa_funding_state` (state × year → merged to county by state_fips).

### Metadata / provenance

- Keep `ipm_match_tier`, `ipm_source_crop`, `ipm_source_crop_family`, `ipm_source_state_fips` for guidance; add analogous fields for practice/capacity if multiple sources (e.g. `ipm_practice_source`, `ipm_capacity_source`).

---

## 6. Improvements to current National IPM Database workflow

- **Use more source types:** Add Elements, Pest-centric PMSPs, and optionally Priorities (discover sourcetypeids; filter out “No Crop” or non-ag where appropriate). Same scoring and aggregation; more rows in `crop_geo_doc_ipm`.
- **Use structured metadata:** If the API exposes crop/commodity IDs or labels, use them instead of or in addition to title-based `_crop_from_title`; reduce “other_crop” and improve crop–state coverage.
- **Parse HTML report pages:** Already implemented as fallback when PDF fails; consider parsing structure (e.g. section headings) from HTML for more consistent section scoring.
- **Improve crop/state mapping:** Extend `TITLE_TO_CROP` and crop-family map for Elements/Priorities; refine region-name → state_fips (e.g. handle “Southern” vs “Southeastern”); document `geo_match_confidence` and use it in weighting or sensitivity analysis.
- **Recency and weighting:** Already recency-weighted; optionally cap `weighted_doc_age` or down-weight documents older than X years for 2018–2019 analysis.
- **Optional: USE_MOST_RECENT_DOC_ONLY:** Already available; reduces runtime; document when used so coverage vs speed trade-off is clear.

---

## 7. Implementation plan

**First:** Extend the current notebook to pull **Elements** and **Pest-centric Management Strategic Plans** — **DONE (implemented).** The notebook now fetches Crop Profile (3), PMSP (4), Timeline (5), Pest-centric PMSP (10), Priority (11) by `sourcetypeid`, and Element by fetching all sources and filtering on `SOURCETYPE == "Element"`. Config: `IPM_SOURCE_TYPE_IDS`, `IPM_INCLUDE_ELEMENT_FROM_ALL`. Documents are deduped by sourceid before scoring. The existing `document_type` column (from API `SOURCETYPE`) already identifies each row’s source type.

**Second:** Add **one** structured external source—prefer **NASS Chemical Use** for 2018/2019 at state × crop level. Build a small loader (script or notebook section), derive state–crop–year features (e.g. % acres treated), join to county via state_fips (and optionally county crop mix). Add columns to the joint county-year table with an `ipm_practice_*` or explicit `nass_*` naming; document as state-level chemical use, not guidance. **Deliverable:** Reproducible NASS integration; new columns in joint CSV and datasheet.

**Third:** If aiming for high coverage, add **NIFA CPPM/IPM** grant or project data at state × year (e.g. from CRIS or public awards), aggregate to state–year, merge to county by state_fips, add `ipm_capacity_*` columns. Document as capacity/infrastructure. Optionally add **ARMS** pest management for nearest year (e.g. 2010) as state–crop practice proxy with a clear “lagged adoption” note. **Deliverable:** Feature schema with guidance + practice + capacity; implementation order and limitations documented.

**Defer:** Heavy scraping of extension sites; county-level IPM adoption data (none identified); integrating more than one practice source until the first (e.g. NASS) is validated and interpreted. Defer mixing guidance and practice in a single index without explicit methodology.

---

## References (links)

- National IPM Database: https://ipmdata.ipmcenters.org/ ; source list: https://ipmdata.ipmcenters.org/source_list.cfm
- USDA ARMS (ERS): https://www.ers.usda.gov/data-products/arms-farm-financial-and-crop-production-practices/
- NASS Chemical Use: https://www.nass.usda.gov/Surveys/Guide_to_NASS_Surveys/Chemical_Use/
- NIFA CPPM: https://www.nifa.usda.gov/grants/programs/crop-protection-pest-management-program
- NIFA IPM Program: https://www.nifa.usda.gov/grants/programs/integrated-pest-management-program-ipm
- Regional IPM Centers: https://www.ipmcenters.org/crop-pest-data/
- Schema (current): [docs/schema_ipm_integration.md](schema_ipm_integration.md) ; pipeline: [EDA/build_joint_dataset.ipynb](../EDA/build_joint_dataset.ipynb)
