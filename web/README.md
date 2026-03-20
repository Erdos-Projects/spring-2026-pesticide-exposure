# Project website — Pesticide Exposure & Respiratory Health

Static site: **project overview** and **interactive county-level risk map**. Hosted for free on **GitHub Pages**.

## Contents

- **index.html** — About the project, objectives, data sources, link to map
- **model-specifics.html** — Model summary, links to datasheet & model card on GitHub, fit & equity plots (`assets/model/*.png`)
- **map.html** + **map.js** — US county choropleth; colors by `risk_index`, popup with county details
- **data/xgboost_map_data.json** — Built from XGBoost prediction CSVs (see below)
- **scripts/build_xgboost_map_data.py** — Regenerates map data (prefers **full-county** exports)

## XGBoost map data (default)

From the repo root:

```bash
python web/scripts/build_xgboost_map_data.py
```

The script prefers **`predictions_all_counties.csv`** under  
`modeling/results/<TARGET>/validation_eval_Full_pesticides_raw__XGBoost_(tuned)/`  
so the choropleth covers **all counties in the joint modeling frame** (~3k+ for year **2019**), not only the test split.

If that file is missing, it falls back to `xgboost_predictions_Full_pesticides_raw.csv`, then `xgboost_predictions.csv`.

To generate the full-county CSVs (after you have train/validation/test splits):

```bash
python modeling/validate_model_accuracy.py --target CASTHMA --exposure-set Full_pesticides_raw \
  --model-family "XGBoost (tuned)" --validation-set external_holdout --export-all-counties
python modeling/validate_model_accuracy.py --target COPD --exposure-set Full_pesticides_raw \
  --model-family "XGBoost (tuned)" --validation-set external_holdout --export-all-counties
```

Then re-run `build_xgboost_map_data.py`. Counties in the Plotly US GeoJSON that lack joint/USGS features stay uncolored (no model row).

## Legacy risk data format (optional)

You can instead use a single `data/risk_estimates.json` if you wire a custom `map.js`; shape:

```json
{
  "01001": {
    "risk_index": 0.42,
    "CASTHMA_prev": 9.2,
    "COPD_prev": 6.1,
    "county_name": "Autauga County, AL"
  },
  "01009": { ... }
}
```

- **Keys**: 5-digit FIPS (state + county, zero-padded), e.g. `"01001"`, `"48201"`.
- **risk_index**: Used for map color (0–1 or your scale; script clamps to color gradient).
- **CASTHMA_prev**, **COPD_prev**: Optional; shown in popup.
- **county_name**: Optional; can use for popup if you prefer your label over GeoJSON name.

Example export from Python (after you have a predictions DataFrame with FIPS and metrics):

```python
import json
# df has columns: FIPS, risk_index, CASTHMA_prev, COPD_prev, county_name
df['FIPS'] = df['FIPS'].astype(str).str.zfill(5)
risk = df.set_index('FIPS')[['risk_index', 'CASTHMA_prev', 'COPD_prev', 'county_name']].to_dict('index')
with open('web/data/risk_estimates.json', 'w') as f:
    json.dump(risk, f, indent=2)
```

Then commit and push; the map will use the new file on the next deploy.

## Local preview

The map uses `fetch()` — opening HTML as `file://` will not load data. You **must** run a local server and **keep it running** while you use the site.

**Recommended (serves the `web/` folder as the site root):**

```bash
cd /path/to/spring-2026-pesticide-exposure
python3 web/serve.py
```

Then open **http://127.0.0.1:8765/map.html** (not `localhost` if that misbehaves on your machine).

- **ERR_EMPTY_RESPONSE** → nothing is listening: start `python3 web/serve.py` first, leave the terminal open, then refresh the browser.
- **Port in use:** `PORT=9000 python3 web/serve.py` and use **http://127.0.0.1:9000/map.html**

Alternative from repo root (site lives under `/web/`):

```bash
python3 -m http.server 8000
```

Open **http://127.0.0.1:8000/web/map.html**.

## Deploy to GitHub Pages (free)

1. **Repo Settings → Pages**
   - Source: **GitHub Actions** (workflow deploys the `web/` folder to `gh-pages`).

2. Push the workflow file (once): `.github/workflows/deploy-pages.yml` is in the repo. On push to `main`, it builds and deploys the site.

3. **Optional**: Update repo URL in `index.html` and `map.html`: replace `your-org` in the “Repository” link with your GitHub org or username.

4. Site URL: `https://<owner>.github.io/<repo>/` (e.g. `https://your-org.github.io/spring-2026-pesticide-exposure/`).

If you use a **branch + folder** instead of Actions: set Pages source to branch `gh-pages`, root. Then push the *contents* of `web/` to the root of `gh-pages` (e.g. with `git subtree push --prefix web origin gh-pages`).

## Other free hosting (alternatives)

- **Netlify** — Drag-and-drop the `web/` folder or connect the repo; instant HTTPS.
- **Vercel** — Connect repo, set root to `web/` (or publish directory to `web`).
- **Cloudflare Pages** — Connect repo, build command leave empty, output directory `web`.

All support custom domains and are free for small static sites.
