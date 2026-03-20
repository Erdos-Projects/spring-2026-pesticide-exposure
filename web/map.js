/**
 * County map: county predictions for 2019 from data/xgboost_map_data.json (default) or
 * data/validation_map_data.json (?source=validation). Both are built by
 * web/scripts/build_xgboost_map_data.py from validate_model_accuracy exports
 * (prefer predictions_all_counties.csv — same tuned XGBoost as external holdout metrics).
 */
(function () {
  const COUNTIES_GEOJSON_URL =
    'https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json';
  const params = new URLSearchParams(window.location.search);
  const source = (params.get('source') || '').toLowerCase();
  // Build absolute URLs so this works at /map.html and /web/map.html.
  const baseUrl = new URL('.', window.location.href);
  const dataPath = source === 'validation'
    ? 'data/validation_map_data.json'
    : 'data/xgboost_map_data.json';
  const DATA_URL = new URL(dataPath, baseUrl).toString();

  // High-contrast, colorblind-friendly sequential palette (Viridis-like).
  // Dark purple -> teal/green -> bright yellow for "drama" while remaining readable.
  const RISK_COLORS = [
    '#440154', '#482878', '#3E4A89', '#31688E', '#26828E',
    '#1F9E89', '#35B779', '#6CCE59', '#B4DE2C', '#FDE725'
  ];
  const NO_DATA_COLOR = '#2b2f36';

  const OUTCOME_LABELS = {
    casthma: 'Asthma (CASTHMA) — predicted prevalence %',
    copd: 'COPD — predicted prevalence %'
  };

  const STATE_FIPS_TO_ABBR = {
    '01': 'AL', '02': 'AK', '04': 'AZ', '05': 'AR', '06': 'CA', '08': 'CO', '09': 'CT', '10': 'DE', '11': 'DC',
    '12': 'FL', '13': 'GA', '15': 'HI', '16': 'ID', '17': 'IL', '18': 'IN', '19': 'IA', '20': 'KS', '21': 'KY',
    '22': 'LA', '23': 'ME', '24': 'MD', '25': 'MA', '26': 'MI', '27': 'MN', '28': 'MS', '29': 'MO', '30': 'MT',
    '31': 'NE', '32': 'NV', '33': 'NH', '34': 'NJ', '35': 'NM', '36': 'NY', '37': 'NC', '38': 'ND', '39': 'OH',
    '40': 'OK', '41': 'OR', '42': 'PA', '44': 'RI', '45': 'SC', '46': 'SD', '47': 'TN', '48': 'TX', '49': 'UT',
    '50': 'VT', '51': 'VA', '53': 'WA', '54': 'WV', '55': 'WI', '56': 'WY'
  };

  const STATE_ABBR_TO_FIPS = Object.keys(STATE_FIPS_TO_ABBR).reduce(function (acc, f) {
    acc[STATE_FIPS_TO_ABBR[f].toLowerCase()] = f;
    return acc;
  }, {});

  let riskByFips = {};
  let geojsonLayer = null;
  const layerByFips = {};
  let currentOutcome = 'casthma';
  const stats = { casthma: { min: 0, max: 0 }, copd: { min: 0, max: 0 } };
  const META_KEY = '_meta';

  function countyFipsKeys(data) {
    return Object.keys(data || {}).filter(function (k) { return k !== META_KEY; });
  }

  function addRiskRanks(data) {
    // Adds per-outcome rank + percentile based on predicted prevalence across counties.
    // rank: 1 = highest predicted prevalence (highest "risk")
    // percentile: 0..100 where 100 = highest predicted prevalence
    ['casthma', 'copd'].forEach(function (outcome) {
      const preds = [];
      countyFipsKeys(data).forEach(function (fips) {
        const o = data[fips] && data[fips][outcome];
        if (o && typeof o.prediction === 'number' && isFinite(o.prediction)) {
          preds.push({ fips: fips, pred: o.prediction });
        }
      });
      if (!preds.length) return;
      preds.sort(function (a, b) { return b.pred - a.pred; });
      const n = preds.length;
      for (let i = 0; i < n; i++) {
        const item = preds[i];
        const o = data[item.fips][outcome];
        const rank = i + 1;
        const pct = n === 1 ? 100 : (1 - (i / (n - 1))) * 100; // top = 100
        o.risk_rank = rank;
        o.risk_percentile = pct;
        o.n_ranked = n;
      }
    });
  }

  function computeStats(data) {
    ['casthma', 'copd'].forEach(function (outcome) {
      const preds = [];
      countyFipsKeys(data).forEach(function (fips) {
        const o = data[fips][outcome];
        if (o && typeof o.prediction === 'number') preds.push(o.prediction);
      });
      if (preds.length) {
        stats[outcome].min = Math.min.apply(null, preds);
        stats[outcome].max = Math.max.apply(null, preds);
      }
    });
  }

  function fipsKey(feature) {
    if (feature == null || feature.id == null) return null;
    return String(feature.id).padStart(5, '0');
  }

  function getOutcomeRow(feature) {
    const fips = fipsKey(feature);
    if (!fips) return null;
    const row = riskByFips[fips];
    if (!row || !row[currentOutcome]) return null;
    return row[currentOutcome];
  }

  function getColor(risk) {
    if (risk == null || isNaN(risk)) return NO_DATA_COLOR;
    const i = Math.min(Math.floor(risk * (RISK_COLORS.length - 1)), RISK_COLORS.length - 1);
    return RISK_COLORS[i];
  }

  function styleFeature(feature) {
    const o = getOutcomeRow(feature);
    const risk = o && typeof o.risk_index === 'number' ? o.risk_index : null;
    return {
      fillColor: getColor(risk),
      weight: 1.1,
      opacity: 0.95,
      color: '#3a424c',
      fillOpacity: 0.82
    };
  }

  function updateLegend() {
    const el = document.querySelector('.map-legend');
    if (!el) return;
    const s = stats[currentOutcome];
    const label = OUTCOME_LABELS[currentOutcome];
    const meta = riskByFips && riskByFips[META_KEY];
    let provenance = '';
    const note = meta && (meta.legend_note || meta.pipeline_detail || meta.pipeline);
    if (note) {
      provenance =
        '<p class="map-legend-meta"><strong>Model / validation data:</strong> ' +
        escapeHtml(note) + '</p>';
    }
    el.innerHTML =
      '<strong>' + label + '</strong> (2019). Colors are ranked within counties with a model: ' +
      'lighter = higher predicted prevalence (among counties with estimates). Range this year: <strong>' +
      s.min.toFixed(1) + '%</strong> – <strong>' + s.max.toFixed(1) + '%</strong>. ' +
      'Click a county for predicted vs. observed (CDC PLACES) and its risk rank/percentile (relative to other counties).' +
      provenance;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function bindPopup(feature, layer) {
    const fips = fipsKey(feature) || '—';
    const name = (feature.properties && feature.properties.NAME) ? feature.properties.NAME : 'County';
    const stateFips2 = (feature.properties && feature.properties.STATE != null) ? String(feature.properties.STATE).padStart(2, '0') : '';
    const stateAbbr = stateFips2 ? (STATE_FIPS_TO_ABBR[stateFips2] || '') : '';
    const countyLabel = stateAbbr ? name + ', ' + stateAbbr : name;
    const row = riskByFips[fips];
    const year = row && row.year ? row.year : '—';

    let content = '<div class="info-panel"><h3>' + countyLabel + '</h3>';

    function block(title, o) {
      if (!o) return '<p class="muted">' + title + ': no estimate</p>';
      const rankLine = (typeof o.risk_rank === 'number' && typeof o.n_ranked === 'number')
        ? ('<p>Risk rank: <strong>#' + o.risk_rank + '</strong> of ' + o.n_ranked +
           ' (<strong>' + (o.risk_percentile != null ? o.risk_percentile.toFixed(0) : '—') + 'th</strong> percentile)</p>')
        : '';
      const obs = (typeof o.actual === 'number' && isFinite(o.actual))
        ? (o.actual.toFixed(2) + '%')
        : '—';
      return (
        '<p><strong>' + title + '</strong> (' + year + ')</p>' +
        '<p>Predicted: ' + o.prediction.toFixed(2) + '%</p>' +
        '<p>Observed (PLACES): ' + obs + '</p>' +
        rankLine
      );
    }

    content += block('Asthma (CASTHMA)', row && row.casthma);
    content += block('COPD', row && row.copd);
    content += '</div>';
    layer.bindPopup(content);
  }

  function onEachFeature(feature, layer) {
    const f = fipsKey(feature);
    if (f) layerByFips[f] = layer;
    layer.on({
      mouseover: function (e) {
        const l = e.target;
        l.setStyle({ weight: 2, color: '#58a6ff', fillOpacity: 0.88 });
        l.bringToFront();
      },
      mouseout: function (e) {
        e.target.setStyle(styleFeature(feature));
      }
    });
    bindPopup(feature, layer);
  }

  function downloadBlob(filename, mime, text) {
    const blob = new Blob([text], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function toCsv(data) {
    const header = [
      'fips', 'year',
      'casthma_actual', 'casthma_prediction', 'casthma_risk_index', 'casthma_risk_rank', 'casthma_risk_percentile',
      'copd_actual', 'copd_prediction', 'copd_risk_index', 'copd_risk_rank', 'copd_risk_percentile'
    ];
    const lines = [header.join(',')];
    countyFipsKeys(data).sort().forEach(function (fips) {
      const row = data[fips] || {};
      const y = row.year != null ? row.year : '';
      const ca = row.casthma || {};
      const co = row.copd || {};
      function num(v) { return (typeof v === 'number' && isFinite(v)) ? String(v) : ''; }
      const values = [
        fips, y,
        num(ca.actual), num(ca.prediction), num(ca.risk_index), num(ca.risk_rank), num(ca.risk_percentile),
        num(co.actual), num(co.prediction), num(co.risk_index), num(co.risk_rank), num(co.risk_percentile)
      ];
      lines.push(values.join(','));
    });
    return lines.join('\n');
  }

  function normalizeQuery(q) {
    return String(q || '')
      .trim()
      .toLowerCase()
      .replace(/\s+/g, ' ');
  }

  function findFipsFromQuery(query, geojson) {
    const q = normalizeQuery(query);
    if (!q) return null;
    // "county, state" where state is a 2-letter abbreviation (preferred)
    const parts = q.split(',').map(function (s) { return s.trim(); }).filter(Boolean);
    const countyPart = parts[0] || '';
    const statePart = parts[1] || '';
    const countyName = countyPart.replace(/\s+county$/, '').trim();
    const stateFips2 = statePart.match(/^[a-z]{2}$/) ? (STATE_ABBR_TO_FIPS[statePart] || '') : '';

    // Find first matching feature
    const feats = (geojson && geojson.features) ? geojson.features : [];
    for (let i = 0; i < feats.length; i++) {
      const f = feats[i];
      const name = (f.properties && f.properties.NAME) ? String(f.properties.NAME).toLowerCase() : '';
      const st = (f.properties && f.properties.STATE) ? String(f.properties.STATE).padStart(2, '0') : '';
      if (countyName && name === countyName && (!stateFips2 || st === stateFips2)) {
        return String(f.id).padStart(5, '0');
      }
    }

    // Fallback: county-only exact match
    for (let i = 0; i < feats.length; i++) {
      const f = feats[i];
      const name = (f.properties && f.properties.NAME) ? String(f.properties.NAME).toLowerCase() : '';
      if (countyName && name === countyName) {
        return String(f.id).padStart(5, '0');
      }
    }

    return null;
  }

  function zoomToFips(fips) {
    const layer = layerByFips[fips];
    if (!layer) return false;
    try {
      map.fitBounds(layer.getBounds(), { maxZoom: 9 });
      layer.openPopup();
      return true;
    } catch (e) {
      return false;
    }
  }

  function zoomToState(stateFips2, geojson) {
    const st = String(stateFips2 || '').padStart(2, '0');
    if (!st || !geojsonLayer) return false;
    const layers = [];
    geojsonLayer.eachLayer(function (layer) {
      const f = layer.feature;
      const s = (f && f.properties && f.properties.STATE != null) ? String(f.properties.STATE).padStart(2, '0') : '';
      if (s === st) layers.push(layer);
    });
    if (!layers.length) return false;
    try {
      const group = L.featureGroup(layers);
      map.fitBounds(group.getBounds(), { maxZoom: 6 });
      return true;
    } catch (e) {
      return false;
    }
  }

  async function geocodeToCountyFips(query, geojson) {
    const q = normalizeQuery(query);
    if (!q) return null;

    // Nominatim (OpenStreetMap) geocoding. No key required, but rate-limited.
    // We request JSON with addressdetails so we can pick out county/state.
    const url = new URL('https://nominatim.openstreetmap.org/search');
    url.searchParams.set('format', 'jsonv2');
    url.searchParams.set('q', q);
    url.searchParams.set('addressdetails', '1');
    url.searchParams.set('limit', '1');

    const res = await fetch(url.toString(), {
      headers: {
        Accept: 'application/json',
        // Nominatim usage policy: identify the application
        'User-Agent': 'spring-2026-pesticide-exposure-map/1.0 (educational; GitHub Erdos-Projects/spring-2026-pesticide-exposure)'
      }
    });
    if (!res.ok) return null;
    const arr = await res.json();
    if (!Array.isArray(arr) || !arr.length) return null;
    const hit = arr[0];
    const addr = hit.address || {};

    // County names vary; try a few fields.
    const county = (addr.county || addr.city_district || addr.state_district || '').toString();
    const state = (addr.state || addr.region || '').toString();
    const countyName = county.replace(/\s+county$/i, '').trim();
    if (!countyName) return null;

    // We don't have state abbreviation in the GeoJSON; it uses STATE FIPS.
    // Best-effort: match by county name only first; if multiple, user can specify "County, NN".
    // But if Nominatim returns a US state name, we can map to state FIPS using a small table.
    const STATE_NAME_TO_FIPS = {
      'alabama': '01', 'alaska': '02', 'arizona': '04', 'arkansas': '05', 'california': '06',
      'colorado': '08', 'connecticut': '09', 'delaware': '10', 'district of columbia': '11',
      'florida': '12', 'georgia': '13', 'hawaii': '15', 'idaho': '16', 'illinois': '17',
      'indiana': '18', 'iowa': '19', 'kansas': '20', 'kentucky': '21', 'louisiana': '22',
      'maine': '23', 'maryland': '24', 'massachusetts': '25', 'michigan': '26', 'minnesota': '27',
      'mississippi': '28', 'missouri': '29', 'montana': '30', 'nebraska': '31', 'nevada': '32',
      'new hampshire': '33', 'new jersey': '34', 'new mexico': '35', 'new york': '36',
      'north carolina': '37', 'north dakota': '38', 'ohio': '39', 'oklahoma': '40', 'oregon': '41',
      'pennsylvania': '42', 'rhode island': '44', 'south carolina': '45', 'south dakota': '46',
      'tennessee': '47', 'texas': '48', 'utah': '49', 'vermont': '50', 'virginia': '51',
      'washington': '53', 'west virginia': '54', 'wisconsin': '55', 'wyoming': '56'
    };
    const stateFips2 = state ? (STATE_NAME_TO_FIPS[state.toLowerCase()] || '') : '';

    // Reuse our existing matcher: "county, stateFips2"
    const stateAbbr2 = stateFips2 ? (STATE_FIPS_TO_ABBR[stateFips2] || '') : '';
    const query2 = stateAbbr2 ? (countyName + ', ' + stateAbbr2) : countyName;
    return findFipsFromQuery(query2, geojson);
  }

  function applyOutcome() {
    if (!geojsonLayer) return;
    geojsonLayer.eachLayer(function (layer) {
      const f = layer.feature;
      if (f) layer.setStyle(styleFeature(f));
    });
    updateLegend();
  }

  const map = L.map('map', { preferCanvas: true }).setView([39.5, -98.35], 4);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap &copy; CARTO',
    subdomains: 'abcd',
    maxZoom: 19
  }).addTo(map);

  const select = document.getElementById('outcome-select');
  if (select) {
    select.addEventListener('change', function () {
      currentOutcome = select.value;
      applyOutcome();
    });
  }

  Promise.all([
    fetch(COUNTIES_GEOJSON_URL).then(function (res) { return res.json(); }),
    fetch(DATA_URL).then(function (res) { return res.json(); })
  ]).then(function (results) {
    const geojson = results[0];
    riskByFips = results[1];
    // Debug helpers (inspect in DevTools console).
    window.__mapDataUrl = DATA_URL;
    window.__riskByFips = riskByFips;
    addRiskRanks(riskByFips);
    computeStats(riskByFips);

    geojsonLayer = L.geoJSON(geojson, {
      style: styleFeature,
      onEachFeature: onEachFeature
    }).addTo(map);

    if (select) currentOutcome = select.value;
    updateLegend();

    // Search wiring — always uses OpenStreetMap Nominatim (online), then maps hit to US county FIPS.
    const input = document.getElementById('county-search');
    const btn = document.getElementById('county-search-btn');
    async function runSearch() {
      const q = input && input.value ? input.value.trim() : '';
      if (!q) {
        if (input) input.setCustomValidity('Enter an address, city, or place to search.');
        if (input) input.reportValidity();
        return;
      }
      let fips = null;
      try {
        fips = await geocodeToCountyFips(q, geojson);
      } catch (e) {
        console.warn('Geocode failed:', e);
      }
      if (!fips) {
        if (input) {
          input.setCustomValidity(
            'No U.S. county match. Try a fuller query (e.g. city and state) or another spelling. Search uses OpenStreetMap online.'
          );
        }
        if (input) input.reportValidity();
        return;
      }
      if (input) input.setCustomValidity('');
      const ok = zoomToFips(fips);
      if (!ok && input) {
        input.setCustomValidity('Matched county but could not zoom.');
        input.reportValidity();
      }
    }
    if (btn) btn.addEventListener('click', runSearch);
    if (input) input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') runSearch();
    });

    // State jump wiring
    const stateSelect = document.getElementById('state-select');
    if (stateSelect) {
      // Populate with state FIPS codes present in the geojson.
      const seen = {};
      (geojson.features || []).forEach(function (f) {
        const st = (f.properties && f.properties.STATE != null) ? String(f.properties.STATE).padStart(2, '0') : '';
        if (st) seen[st] = true;
      });
      Object.keys(seen).sort().forEach(function (st) {
        const opt = document.createElement('option');
        opt.value = st;
        const ab = STATE_FIPS_TO_ABBR[st] || st;
        opt.textContent = ab;
        stateSelect.appendChild(opt);
      });
      stateSelect.addEventListener('change', function () {
        const st = stateSelect.value;
        if (!st) return;
        zoomToState(st, geojson);
      });
    }

    // Download wiring
    const dlJson = document.getElementById('download-json');
    const dlCsv = document.getElementById('download-csv');
    const prefix = source === 'validation' ? 'validation' : 'xgboost';
    if (dlJson) dlJson.addEventListener('click', function () {
      downloadBlob(prefix + '_map_data.json', 'application/json;charset=utf-8', JSON.stringify(riskByFips, null, 0));
    });
    if (dlCsv) dlCsv.addEventListener('click', function () {
      downloadBlob(prefix + '_map_data.csv', 'text/csv;charset=utf-8', toCsv(riskByFips));
    });
  }).catch(function (err) {
    console.error('Failed to load map data:', err);
    const leg = document.querySelector('.map-legend');
    if (leg) {
      leg.innerHTML =
        '<strong>Error loading data.</strong> Serve the site over HTTP (e.g. <code>python -m http.server</code> from the repo root) and ensure <code>web/data/xgboost_map_data.json</code> exists. Run <code>python web/scripts/build_xgboost_map_data.py</code> to generate it.';
    }
  });
})();
