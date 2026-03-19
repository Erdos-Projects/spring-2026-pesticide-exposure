"""IPM National Database bridge: API fetch, document scoring, crop-state aggregation, county-crop join, county-year collapse.

Used by EDA/build_joint_dataset.ipynb Section 3b and EDA/ipm_data_load_troubleshoot.ipynb.
"""
# --- crop_geo_doc_ipm: section-aware scores (inline; National IPM Database API) ---
# Expected runtime: ~5-15 min with PDF/HTML fallback (API + per-doc fetches). Coverage-first mode keeps all docs,
# then lets aggregation / match tiers decide how to back off when exact crop-state matches are sparse.
import re
import requests
import numpy as np
import pandas as pd

IPM_API_BASE = "https://ipmdata.ipmcenters.org/rest/ipmdata_ipmcenters_org_restapi"
ANALYSIS_YEARS_IPM = [2018, 2019]
USE_MOST_RECENT_DOC_ONLY = False
USE_STRUCTURED_TEXT = True
USE_PDF_FALLBACK = True
PDF_TIMEOUT = 20
REQUEST_TIMEOUT = 30

CROP_FAMILY_MAP = {
    "corn": "field_crop", "soybean": "field_crop", "cotton": "field_crop", "wheat": "field_crop",
    "rice": "field_crop", "sorghum": "field_crop", "hay": "forage", "fruit_veg": "specialty_crop",
    "other_crop": "other_crop",
}

TITLE_TO_CROP = {
    "sweet corn": "corn", "maize": "corn", "corn": "corn",
    "soybeans": "soybean", "soybean": "soybean", "soy": "soybean",
    "cotton": "cotton",
    "durum": "wheat", "spring wheat": "wheat", "winter wheat": "wheat", "wheat": "wheat",
    "alfalfa": "hay", "hay": "hay", "forage": "hay",
    "rice": "rice",
    "grain sorghum": "sorghum", "sorghum": "sorghum",
    "strawberry": "fruit_veg", "strawberries": "fruit_veg", "vegetable": "fruit_veg", "vegetables": "fruit_veg",
    "vineyard": "fruit_veg", "vineyards": "fruit_veg", "orchard": "fruit_veg", "orchards": "fruit_veg",
    "potato": "fruit_veg", "potatoes": "fruit_veg", "tomato": "fruit_veg", "tomatoes": "fruit_veg",
    "berry": "fruit_veg", "berries": "fruit_veg", "apple": "fruit_veg", "apples": "fruit_veg",
    "almond": "fruit_veg", "almonds": "fruit_veg", "peach": "fruit_veg", "peaches": "fruit_veg",
    "grape": "fruit_veg", "grapes": "fruit_veg", "citrus": "fruit_veg", "melon": "fruit_veg", "melons": "fruit_veg",
    "lettuce": "fruit_veg", "onion": "fruit_veg", "onions": "fruit_veg", "carrot": "fruit_veg", "carrots": "fruit_veg",
    "broccoli": "fruit_veg", "pepper": "fruit_veg", "peppers": "fruit_veg", "fruit": "fruit_veg", "fruits": "fruit_veg",
    "bean": "other_crop", "beans": "other_crop", "dry bean": "other_crop", "peanut": "other_crop",
    "sunflower": "other_crop", "canola": "other_crop", "barley": "other_crop", "oat": "other_crop",
}
_SORTED_TITLE_CROPS = sorted(TITLE_TO_CROP.items(), key=lambda kv: len(kv[0]), reverse=True)

# Lexicons (ambiguous terms like organic, application, treatment, timing, pollinator, integrated, reduced-risk removed to reduce noise)
LEXICONS = {
    "monitoring": [r"scout(?:ing)?", r"monitor(?:ing)?", r"trap(?:ping|s)?", r"sampl(?:e|ing)", r"thresholds?", r"economic threshold", r"degree[- ]day", r"forecast(?:ing)?", r"surveillance", r"detection", r"sweep(?:ing)?", r"action threshold", r"monitoring (?:and )?scouting"],
    "nonchemical": [r"cultural control", r"biological control", r"mechanical control", r"physical control", r"crop rotation", r"sanitation", r"resistant variet(?:y|ies)", r"pruning", r"tillage", r"mulch(?:ing)?", r"habitat management", r"natural enemies", r"pheromone disruption", r"nonchemical", r"non-chemical", r"biologicals?", r"beneficial (?:insects?|organisms?)", r"cultural practices", r"cover crop", r"intercropping"],
    "chemical": [r"pesticides?", r"insecticides?", r"herbicides?", r"fungicides?", r"chemical control", r"spray(?:ing| schedule)?", r"active ingredient", r"pre-?emergence", r"post-?emergence", r"chemigation", r"foliar", r"soil applied", r"registered (?:pesticide|chemical)", r"chemical management", r"conventional (?:pesticide|chemical)"],
    "decision_support": [r"thresholds?", r"action threshold", r"economic threshold", r"targeted", r"integrated pest", r"integrated management", r"beneficials?", r"application timing", r"ipm (?:practices?|approach)", r"decision[- ]?making", r"when to (?:spray|treat|apply)", r"scouting (?:for|to)"],
    "dependency": [r"limited alternatives?", r"few effective options?", r"critical use", r"loss of registration", r"resistance concern", r"lack of nonchemical options", r"dependency", r"reliance", r"primary (?:control|tool)", r"conventional (?:control|management)"],
    "resistance_management": [r"resistance management", r"mode of action", r"rotat(?:e|ion) of chemistr(?:y|ies)", r"anti-resistance", r"insecticide resistance", r"herbicide resistance", r"moa", r"tank[- ]?mix", r"rotate (?:modes|chemistry)"],
}

SECTION_PATTERNS = {
    "production_practices": [r"production practices", r"production information", r"production facts", r"growing practices"],
    "monitoring": [r"monitoring", r"scouting", r"sampling", r"threshold", r"pest identification", r"detection"],
    "cultural_controls": [r"cultural control", r"cultural practices", r"cultural management", r"nonchemical"],
    "biological_controls": [r"biological control", r"natural enemies", r"biologicals", r"biocontrol"],
    "physical_controls": [r"physical control", r"mechanical control", r"physical and mechanical"],
    "chemical_controls": [r"chemical control", r"pesticides", r"herbicides", r"insecticides", r"fungicides", r"chemical management", r"pest management (?:strategies|practices)", r"weed management", r"insect management", r"disease management"],
    "research_priorities": [r"research priorities", r"regulatory priorities", r"education priorities", r"priorities", r"transition priorities", r"worker (?:activities|protection)", r"pollinator"],
}

def _compile(patterns):
    return [re.compile(p, re.I) for p in patterns]

COMPILED_LEXICONS = {k: _compile(v) for k, v in LEXICONS.items()}
COMPILED_SECTION_PATTERNS = {k: _compile(v) for k, v in SECTION_PATTERNS.items()}

def _ipm_get(path, params=None):
    r = requests.get(f"{IPM_API_BASE}{path}", params=params or {}, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()

def _ipm_response_to_rows(obj):
    if isinstance(obj, dict) and "COLUMNS" in obj and "DATA" in obj:
        cols = [str(c).strip() for c in obj["COLUMNS"]]
        return [dict(zip(cols, row)) for row in obj["DATA"]]
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        return [obj]
    return []

def _get(d, *keys):
    for k in keys:
        v = d.get(k) or d.get(k.upper() if hasattr(k, "upper") else k) or d.get(k.lower() if hasattr(k, "lower") else k)
        if v is not None:
            return v
    return None

def _parse_doc_year(sourcedate):
    if pd.isna(sourcedate):
        return np.nan
    s = str(sourcedate).strip()
    m = re.search(r"(19|20)\d{2}", s)
    return int(m.group(0)) if m else np.nan

def _crop_family(crop):
    return CROP_FAMILY_MAP.get(str(crop), "other_crop")

def _crop_from_title(title):
    text = re.sub(r"[^a-z0-9]+", " ", str(title or "").lower()).strip()
    for keyword, crop in _SORTED_TITLE_CROPS:
        if re.search(rf"\b{re.escape(keyword)}\b", text):
            return crop
    return "other_crop"

def _bounded(x, lo=0.0, hi=1.0):
    return min(hi, max(lo, x))

def _normalize_rate(count, denom):
    return count / denom if denom > 0 else 0.0

def _metadata_priors(doc_type, doc_year, crop):
    monitoring = nonchemical = chemical = decision_support = dependency = resistance_management = 0.0
    doc_type_str = str(doc_type or "").lower()
    if "pmsp" in doc_type_str:
        decision_support += 0.05
        dependency += 0.05
    if pd.notna(doc_year):
        if doc_year >= 2010:
            monitoring += 0.03
            nonchemical += 0.03
            resistance_management += 0.03
        elif doc_year < 2000:
            chemical += 0.04
            dependency += 0.04
    if crop == "fruit_veg":
        monitoring += 0.03
        nonchemical += 0.03
    return {"monitoring_prior": _bounded(monitoring), "nonchemical_prior": _bounded(nonchemical), "chemical_prior": _bounded(chemical), "decision_support_prior": _bounded(decision_support), "dependency_prior": _bounded(dependency), "resistance_management_prior": _bounded(resistance_management)}

def _fetch_structured_report_text(source_id):
    return None

def _fetch_pdf_text(url):
    if not url:
        return None
    try:
        from io import BytesIO
        r = requests.get(str(url), timeout=PDF_TIMEOUT)
        r.raise_for_status()
        raw = r.content
        if len(raw) < 500:
            return None
        text = None
        try:
            from pdfminer.high_level import extract_text as pdf_extract_text
            text = pdf_extract_text(BytesIO(raw))
        except Exception:
            text = None
        if not text or len(text.strip()) < 150:
            try:
                import fitz
                doc = fitz.open(stream=raw, filetype="pdf")
                parts = [doc.load_page(i).get_text() for i in range(len(doc))]
                doc.close()
                text = "\n".join(parts) if parts else ""
            except Exception:
                pass
        if not text or len(text.strip()) < 150:
            return None
        return text.strip()
    except Exception:
        return None

def _split_sections_from_text(text):
    if not text:
        return {}
    lines = [ln.strip() for ln in str(text).splitlines() if ln.strip()]
    joined = "\n".join(lines)
    lower = joined.lower()
    sections = {}
    heading_candidates = ["production practices", "monitoring", "scouting", "sampling", "threshold", "cultural control", "cultural practices", "biological control", "natural enemies", "physical control", "mechanical control", "chemical control", "pesticides", "research priorities", "regulatory priorities", "education priorities", "pest management", "weed management", "insect management", "disease management", "management strategies", "worker protection", "pollinator"]
    for sec_name, pats in COMPILED_SECTION_PATTERNS.items():
        match_positions = []
        for pat in pats:
            for m in pat.finditer(lower):
                match_positions.append((m.start(), m.group(0)))
        if match_positions:
            start = min(pos for pos, _ in match_positions)
            next_positions = []
            for candidate in heading_candidates:
                for m in re.finditer(re.escape(candidate), lower):
                    if m.start() > start + 20:
                        next_positions.append(m.start())
            end = min(next_positions) if next_positions else len(joined)
            sections[sec_name] = joined[start:end]
    return sections

def _count_lexicon_hits(text, compiled_patterns):
    if not text:
        return 0
    return sum(len(p.findall(text)) for p in compiled_patterns)

def _section_presence_score(sections):
    core = ["monitoring", "cultural_controls", "biological_controls", "physical_controls", "chemical_controls"]
    present = sum(1 for s in core if s in sections and len((sections.get(s) or "").strip()) > 50)
    return present / len(core)

def _score_document_text(full_text, sections, doc_type):
    full_text = full_text or ""
    sections = sections or {}
    token_denom = max(200, len(re.findall(r"\w+", full_text)))
    sec_cov = _section_presence_score(sections)
    mon_ct = _count_lexicon_hits(full_text, COMPILED_LEXICONS["monitoring"])
    non_ct = _count_lexicon_hits(full_text, COMPILED_LEXICONS["nonchemical"])
    chem_ct = _count_lexicon_hits(full_text, COMPILED_LEXICONS["chemical"])
    dec_ct = _count_lexicon_hits(full_text, COMPILED_LEXICONS["decision_support"])
    dep_ct = _count_lexicon_hits(full_text, COMPILED_LEXICONS["dependency"])
    res_ct = _count_lexicon_hits(full_text, COMPILED_LEXICONS["resistance_management"])
    mon_sec = _count_lexicon_hits(sections.get("monitoring", ""), COMPILED_LEXICONS["monitoring"])
    non_sec = _count_lexicon_hits(sections.get("cultural_controls", ""), COMPILED_LEXICONS["nonchemical"]) + _count_lexicon_hits(sections.get("biological_controls", ""), COMPILED_LEXICONS["nonchemical"]) + _count_lexicon_hits(sections.get("physical_controls", ""), COMPILED_LEXICONS["nonchemical"])
    chem_sec = _count_lexicon_hits(sections.get("chemical_controls", ""), COMPILED_LEXICONS["chemical"])
    pri_sec = _count_lexicon_hits(sections.get("research_priorities", ""), COMPILED_LEXICONS["dependency"])
    mon_rate = _normalize_rate(mon_ct + 2 * mon_sec, token_denom / 1000)
    non_rate = _normalize_rate(non_ct + 2 * non_sec, token_denom / 1000)
    chem_rate = _normalize_rate(chem_ct + 2 * chem_sec, token_denom / 1000)
    dec_rate = _normalize_rate(dec_ct, token_denom / 1000)
    dep_rate = _normalize_rate(dep_ct + 2 * pri_sec, token_denom / 1000)
    res_rate = _normalize_rate(res_ct, token_denom / 1000)
    monitoring_score = _bounded(mon_rate / 4.0)
    nonchemical_score = _bounded(non_rate / 5.0)
    chemical_score = _bounded(chem_rate / 6.0)
    decision_support_score = _bounded(dec_rate / 3.0)
    dependency_score = _bounded(dep_rate / 2.5)
    resistance_management_score = _bounded(res_rate / 2.0)
    ipm_breadth_index = _bounded(0.30 * monitoring_score + 0.35 * nonchemical_score + 0.20 * decision_support_score + 0.15 * resistance_management_score + 0.10 * sec_cov)
    chemical_reliance_index = _bounded(0.60 * chemical_score + 0.25 * dependency_score + 0.15 * max(0.0, chemical_score - nonchemical_score))
    if "pmsp" in str(doc_type or "").lower():
        chemical_reliance_index = _bounded(chemical_reliance_index * 0.95)
    return {"monitoring_score": monitoring_score, "nonchemical_score": nonchemical_score, "chemical_score": chemical_score, "decision_support_score": decision_support_score, "dependency_score": dependency_score, "resistance_management_score": resistance_management_score, "section_coverage_score": sec_cov, "ipm_breadth_index": ipm_breadth_index, "chemical_reliance_index": chemical_reliance_index}

def _combine_text_scores_with_priors(text_scores, priors, text_quality):
    if text_scores is None:
        return {"monitoring_score": priors["monitoring_prior"], "nonchemical_score": priors["nonchemical_prior"], "chemical_score": priors["chemical_prior"], "decision_support_score": priors["decision_support_prior"], "dependency_score": priors["dependency_prior"], "resistance_management_score": priors["resistance_management_prior"], "section_coverage_score": 0.0, "ipm_breadth_index": _bounded(0.30 * priors["monitoring_prior"] + 0.35 * priors["nonchemical_prior"] + 0.20 * priors["decision_support_prior"] + 0.15 * priors["resistance_management_prior"]), "chemical_reliance_index": _bounded(0.60 * priors["chemical_prior"] + 0.25 * priors["dependency_prior"] + 0.15 * max(0.0, priors["chemical_prior"] - priors["nonchemical_prior"]))}
    text_wt = 0.85 if text_quality == "high" else 0.70 if text_quality == "medium" else 0.50
    prior_wt = 1.0 - text_wt
    out = {}
    for score_name, prior_name in [("monitoring_score", "monitoring_prior"), ("nonchemical_score", "nonchemical_prior"), ("chemical_score", "chemical_prior"), ("decision_support_score", "decision_support_prior"), ("dependency_score", "dependency_prior"), ("resistance_management_score", "resistance_management_prior")]:
        out[score_name] = _bounded(text_wt * text_scores[score_name] + prior_wt * priors[prior_name])
    out["section_coverage_score"] = text_scores["section_coverage_score"]
    out["ipm_breadth_index"] = _bounded(0.30 * out["monitoring_score"] + 0.35 * out["nonchemical_score"] + 0.20 * out["decision_support_score"] + 0.15 * out["resistance_management_score"] + 0.10 * out["section_coverage_score"])
    out["chemical_reliance_index"] = _bounded(0.60 * out["chemical_score"] + 0.25 * out["dependency_score"] + 0.15 * max(0.0, out["chemical_score"] - out["nonchemical_score"]))
    return out

def _build_region_state_lookup():
    states_json = _ipm_get("/state")
    state_rows = _ipm_response_to_rows(states_json)
    states = pd.DataFrame(state_rows)
    states.columns = [str(c).strip() for c in states.columns]
    fips_col = next((c for c in states.columns if str(c).lower() in ("fipscode", "fips_code", "statefips", "state_fips", "fips")), None)
    region_col = next((c for c in states.columns if str(c).lower() in ("regionid", "region_id", "cipmregionid")), None)
    region_name_col = next((c for c in states.columns if str(c).lower() == "region"), None)
    if fips_col is None or region_col is None:
        raise KeyError("State table missing FIPS or region. Columns: %s" % list(states.columns))
    states = states[states[fips_col].notna()].copy()
    states["state_fips"] = states[fips_col].astype(str).str.replace(r"\D", "", regex=True).str.zfill(2)
    states = states[(states["state_fips"].str.len() >= 2) & (states["state_fips"] != "00")].copy()
    states["_regionid"] = states[region_col]
    regionid_to_states = states.groupby("_regionid")["state_fips"].apply(lambda x: sorted(set(x))).to_dict()
    regionname_to_states = states.groupby(region_name_col)["state_fips"].apply(lambda x: sorted(set(x))).to_dict() if region_name_col else {}
    return regionid_to_states, regionname_to_states

def _state_fips_for_region(region_name, regionname_to_states):
    if not region_name:
        return [], "low"
    rn = str(region_name).strip()
    if rn in regionname_to_states:
        return list(regionname_to_states[rn]), "medium"
    prefix = rn.lower()[:4]
    matched = sorted({f for k, vals in regionname_to_states.items() if prefix in str(k).lower() for f in vals})
    return matched, "low"

def build_crop_geo_doc_ipm(use_structured_text=USE_STRUCTURED_TEXT, use_pdf_fallback=USE_PDF_FALLBACK):
    regionid_to_states, regionname_to_states = _build_region_state_lookup()
    sources_cp = _ipm_response_to_rows(_ipm_get("/source", {"sourcetypeid": 3}))
    sources_pmsp = _ipm_response_to_rows(_ipm_get("/source", {"sourcetypeid": 4}))
    raw_sources = sources_cp + sources_pmsp
    rows = []
    for s in raw_sources:
        title = _get(s, "source")
        source_id = _get(s, "sourceid")
        url = _get(s, "url")
        doc_type = _get(s, "sourcetype") or ""
        doc_year = _parse_doc_year(_get(s, "sourcedate"))
        crop = _crop_from_title(title)
        crop_family = _crop_family(crop)
        region_id = _get(s, "cipmregionid", "regionid")
        region_name = _get(s, "region")
        state_fips_list = []
        geo_match_confidence = "low"
        source_geo_type = "unknown"
        if region_id is not None and region_id in regionid_to_states:
            state_fips_list = list(regionid_to_states[region_id])
            geo_match_confidence = "high"
            source_geo_type = "region"
        else:
            state_fips_list, geo_match_confidence = _state_fips_for_region(region_name, regionname_to_states)
            source_geo_type = "region"
        state_fips_list = [sf for sf in state_fips_list if sf != "00"]
        if not state_fips_list:
            state_fips_list = ["ALL"]
            source_geo_type = "national_fallback"
        full_text = None
        sections = None
        text_source = "none"
        text_parse_quality = "none"
        if use_structured_text and source_id is not None:
            structured = _fetch_structured_report_text(source_id)
            if structured and structured.get("full_text"):
                full_text = structured.get("full_text")
                sections = structured.get("sections") or _split_sections_from_text(full_text)
                text_source = "html_structured"
                text_parse_quality = "high" if sections else "medium"
        if full_text is None and use_pdf_fallback and url:
            pdf_text = _fetch_pdf_text(url)
            if pdf_text:
                full_text = pdf_text
                sections = _split_sections_from_text(pdf_text)
                text_source = "pdf"
                text_parse_quality = "medium" if sections else "low"
        if full_text is None and source_id is not None:
            try:
                r = requests.get("https://ipmdata.ipmcenters.org/source_report.cfm?sourceid=" + str(source_id) + "&view=yes", timeout=PDF_TIMEOUT)
                if r.ok and len(r.text) > 500:
                    html_text = re.sub(r"<script[^>]*>.*?</script>", " ", r.text, flags=re.DOTALL | re.I)
                    html_text = re.sub(r"<[^>]+>", " ", html_text)
                    html_text = re.sub(r"\s+", " ", html_text).strip()
                    if len(html_text) >= 200:
                        full_text = html_text
                        sections = _split_sections_from_text(full_text)
                        text_source = "html_report"
                        text_parse_quality = "medium" if sections else "low"
            except Exception:
                pass
        priors = _metadata_priors(doc_type=doc_type, doc_year=doc_year, crop=crop)
        text_scores = _score_document_text(full_text, sections, doc_type) if full_text else None
        scores = _combine_text_scores_with_priors(text_scores, priors, text_parse_quality)
        for sf in state_fips_list:
            rows.append({
                "crop": crop,
                "crop_family": crop_family,
                "state_fips": sf,
                "document_year": doc_year,
                "document_type": doc_type,
                "source_id": source_id,
                "source_title": title,
                "url": url,
                "source_geo_type": source_geo_type,
                "geo_match_confidence": geo_match_confidence,
                "text_source": text_source,
                "text_parse_quality": text_parse_quality,
                "monitoring_score": scores["monitoring_score"],
                "nonchemical_score": scores["nonchemical_score"],
                "chemical_score": scores["chemical_score"],
                "decision_support_score": scores["decision_support_score"],
                "dependency_score": scores["dependency_score"],
                "resistance_management_score": scores["resistance_management_score"],
                "section_coverage_score": scores["section_coverage_score"],
                "ipm_breadth_index": scores["ipm_breadth_index"],
                "chemical_reliance_index": scores["chemical_reliance_index"],
            })
    out = pd.DataFrame(rows)
    if len(out) == 0:
        return pd.DataFrame(columns=["crop", "crop_family", "state_fips", "document_year", "document_type", "source_id", "source_title", "url", "source_geo_type", "geo_match_confidence", "text_source", "text_parse_quality", "monitoring_score", "nonchemical_score", "chemical_score", "decision_support_score", "dependency_score", "resistance_management_score", "section_coverage_score", "ipm_breadth_index", "chemical_reliance_index"])
    out["crop_family"] = out["crop_family"].astype(str)
    out["state_fips"] = out["state_fips"].astype(str).str.zfill(2).where(out["state_fips"] != "ALL", "ALL")
    for col, rescaled_col in [("ipm_breadth_index", "ipm_breadth_index_rescaled"), ("chemical_reliance_index", "chemical_reliance_index_rescaled")]:
        if col in out.columns and out[col].notna().any():
            lo, hi = out[col].min(), out[col].max()
            if hi > lo:
                out[rescaled_col] = (out[col] - lo) / (hi - lo)
            else:
                out[rescaled_col] = 0.5 if pd.notna(lo) else np.nan
    return out

def _quality_to_numeric(q):
    return {"none": 0.0, "low": 0.25, "medium": 0.5, "high": 1.0}.get(str(q).lower(), 0.0)

def _confidence_to_numeric(c):
    return {"low": 1/3, "medium": 2/3, "high": 1.0}.get(str(c).lower(), 0.0)

def aggregate_crop_geo_doc_ipm_to_crop_state(crop_geo_doc_ipm, analysis_years=None):
    """Aggregate by (crop, state_fips) and analysis year using recency-weighted means."""
    if crop_geo_doc_ipm is None or len(crop_geo_doc_ipm) == 0:
        return pd.DataFrame()
    analysis_years = analysis_years or ANALYSIS_YEARS_IPM
    df = crop_geo_doc_ipm.copy()
    df["_text_quality_num"] = df["text_parse_quality"].map(_quality_to_numeric) if "text_parse_quality" in df.columns else 0.0
    df["_geo_conf_num"] = df["geo_match_confidence"].map(_confidence_to_numeric) if "geo_match_confidence" in df.columns else 0.0
    df["document_year"] = pd.to_numeric(df["document_year"], errors="coerce")
    out_list = []
    for (crop, state_fips), g in df.groupby(["crop", "state_fips"]):
        crop_family = g["crop_family"].dropna().iloc[0] if "crop_family" in g.columns and g["crop_family"].notna().any() else _crop_family(crop)
        for ay in analysis_years:
            recency = 1.0 / (1.0 + np.abs(g["document_year"] - ay).fillna(99))
            w = recency / recency.sum() if recency.sum() > 0 else recency * 0
            row = {"crop": crop, "crop_family": crop_family, "state_fips": state_fips, "year": ay, "n_docs": len(g)}
            for col in ["ipm_breadth_index", "chemical_reliance_index", "ipm_breadth_index_rescaled", "chemical_reliance_index_rescaled"]:
                if col in g.columns:
                    row[col] = (w * g[col]).sum()
            row["mean_text_quality"] = (w * g["_text_quality_num"]).sum()
            row["mean_geo_confidence"] = (w * g["_geo_conf_num"]).sum()
            row["weighted_doc_age"] = (w * (ay - g["document_year"])).sum()
            out_list.append(row)
    out = pd.DataFrame(out_list)
    if len(out) > 0:
        out["state_fips"] = out["state_fips"].astype(str).str.replace(r"\D", "", regex=True).str.zfill(2).where(out["state_fips"] != "ALL", "ALL")
        out["crop"] = out["crop"].astype(str)
        out["crop_family"] = out["crop_family"].astype(str)
        out["year"] = out["year"].astype(int)
    return out

def aggregate_ipm_match_table(df, group_cols, tier_name):
    if df is None or len(df) == 0:
        return pd.DataFrame()
    value_cols = ["ipm_breadth_index", "chemical_reliance_index", "ipm_breadth_index_rescaled", "chemical_reliance_index_rescaled", "mean_text_quality", "mean_geo_confidence", "weighted_doc_age"]
    rows = []
    for key, g in df.groupby(group_cols):
        if not isinstance(key, tuple):
            key = (key,)
        row = dict(zip(group_cols, key))
        weights = pd.to_numeric(g.get("n_docs", 1), errors="coerce").fillna(1).clip(lower=1)
        for col in value_cols:
            if col in g.columns:
                valid = g[col].notna()
                if valid.any():
                    row[col] = np.average(g.loc[valid, col], weights=weights.loc[valid])
                else:
                    row[col] = np.nan
        row["n_docs"] = int(weights.sum())
        row["ipm_match_tier"] = tier_name
        row["ipm_source_crop"] = g["crop"].dropna().iloc[0] if "crop" in g.columns and g["crop"].notna().any() else np.nan
        row["ipm_source_crop_family"] = g["crop_family"].dropna().iloc[0] if "crop_family" in g.columns and g["crop_family"].notna().any() else np.nan
        row["ipm_source_state_fips"] = g["state_fips"].dropna().iloc[0] if "state_fips" in g.columns and g["state_fips"].notna().any() else np.nan
        rows.append(row)
    return pd.DataFrame(rows)

def build_ipm_match_tables(crop_state_ipm):
    if crop_state_ipm is None or len(crop_state_ipm) == 0:
        return {}
    exact_state = crop_state_ipm.copy()
    exact_state["ipm_match_tier"] = "exact_crop_state"
    exact_state["ipm_source_crop"] = exact_state["crop"]
    exact_state["ipm_source_crop_family"] = exact_state["crop_family"]
    exact_state["ipm_source_state_fips"] = exact_state["state_fips"]

    state_only = exact_state[exact_state["state_fips"] != "ALL"].copy()
    national_seed = exact_state.copy()
    national_seed["state_fips"] = "ALL"

    return {
        "exact_crop_state": exact_state,
        "crop_family_state": aggregate_ipm_match_table(state_only, ["crop_family", "state_fips", "year"], "crop_family_state"),
        "exact_crop_national": aggregate_ipm_match_table(national_seed, ["crop", "year"], "exact_crop_national"),
        "crop_family_national": aggregate_ipm_match_table(national_seed, ["crop_family", "year"], "crop_family_national"),
    }

def match_county_crop_year_ipm(ccy, crop_state_ipm):
    fill_cols = [
        "ipm_breadth_index", "chemical_reliance_index", "ipm_breadth_index_rescaled", "chemical_reliance_index_rescaled",
        "mean_text_quality", "mean_geo_confidence", "weighted_doc_age", "n_docs",
        "ipm_match_tier", "ipm_source_crop", "ipm_source_crop_family", "ipm_source_state_fips",
    ]
    base = ccy.copy()
    if len(base) == 0:
        return base
    if "crop_family" not in base.columns:
        base["crop_family"] = base["crop"].map(_crop_family)
    for col in fill_cols:
        base[col] = np.nan
    if crop_state_ipm is None or len(crop_state_ipm) == 0:
        return base
    tables = build_ipm_match_tables(crop_state_ipm)
    match_specs = [
        ("exact_crop_state", ["crop", "state_fips", "year"], ["crop", "state_fips", "year"]),
        ("crop_family_state", ["crop_family", "state_fips", "year"], ["crop_family", "state_fips", "year"]),
        ("exact_crop_national", ["crop", "year"], ["crop", "year"]),
        ("crop_family_national", ["crop_family", "year"], ["crop_family", "year"]),
    ]
    for tier_name, left_on, right_on in match_specs:
        table = tables.get(tier_name)
        if table is None or len(table) == 0:
            continue
        tmp = base[left_on].merge(table, left_on=left_on, right_on=right_on, how="left", suffixes=("", "_match"))
        mask = base["ipm_breadth_index"].isna() & tmp["ipm_breadth_index"].notna()
        if not mask.any():
            continue
        for col in fill_cols:
            if col in tmp.columns:
                base.loc[mask, col] = tmp.loc[mask, col].values
    return base