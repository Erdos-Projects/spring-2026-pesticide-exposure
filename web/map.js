/**
 * County map: XGBoost predicted prevalence (2019) from data/xgboost_map_data.json.
 * Regenerate data: python web/scripts/build_xgboost_map_data.py
 */
(function () {
  const COUNTIES_GEOJSON_URL =
    'https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json';
  const DATA_URL = 'data/xgboost_map_data.json';

  const RISK_COLORS = [
    '#0d1117', '#161b22', '#21262d', '#30363d', '#484f58',
    '#6e7681', '#8b949e', '#b1bac4', '#c9d1d9', '#f0f6fc'
  ];
  const NO_DATA_COLOR = '#21262d';

  const OUTCOME_LABELS = {
    casthma: 'Asthma (CASTHMA) — predicted prevalence %',
    copd: 'COPD — predicted prevalence %'
  };

  let riskByFips = {};
  let geojsonLayer = null;
  let currentOutcome = 'casthma';
  const stats = { casthma: { min: 0, max: 0 }, copd: { min: 0, max: 0 } };

  function computeStats(data) {
    ['casthma', 'copd'].forEach(function (outcome) {
      const preds = [];
      Object.keys(data).forEach(function (fips) {
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
      weight: 1,
      opacity: 0.85,
      color: '#30363d',
      fillOpacity: 0.72
    };
  }

  function updateLegend() {
    const el = document.querySelector('.map-legend');
    if (!el) return;
    const s = stats[currentOutcome];
    const label = OUTCOME_LABELS[currentOutcome];
    el.innerHTML =
      '<strong>' + label + '</strong> (2019). Colors are ranked within counties with a model: ' +
      'lighter = higher predicted prevalence. Range this year: <strong>' +
      s.min.toFixed(1) + '%</strong> – <strong>' + s.max.toFixed(1) + '%</strong>. ' +
      'Click a county for predicted vs. observed (CDC PLACES).';
  }

  function bindPopup(feature, layer) {
    const fips = fipsKey(feature) || '—';
    const name = (feature.properties && feature.properties.NAME) ? feature.properties.NAME : 'County';
    const state = (feature.properties && feature.properties.STATE) ? feature.properties.STATE : '';
    const countyLabel = state ? name + ', ' + state : name;
    const row = riskByFips[fips];
    const year = row && row.year ? row.year : '—';

    let content = '<div class="info-panel"><h3>' + countyLabel + '</h3><p class="fips">FIPS ' + fips + '</p>';

    function block(title, o) {
      if (!o) return '<p class="muted">' + title + ': no estimate</p>';
      return (
        '<p><strong>' + title + '</strong> (' + year + ')</p>' +
        '<p>Predicted: ' + o.prediction.toFixed(2) + '%</p>' +
        '<p>Observed: ' + o.actual.toFixed(2) + '%</p>'
      );
    }

    content += block('Asthma (CASTHMA)', row && row.casthma);
    content += block('COPD', row && row.copd);
    content += '</div>';
    layer.bindPopup(content);
  }

  function onEachFeature(feature, layer) {
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
    computeStats(riskByFips);

    geojsonLayer = L.geoJSON(geojson, {
      style: styleFeature,
      onEachFeature: onEachFeature
    }).addTo(map);

    if (select) currentOutcome = select.value;
    updateLegend();
  }).catch(function (err) {
    console.error('Failed to load map data:', err);
    const leg = document.querySelector('.map-legend');
    if (leg) {
      leg.innerHTML =
        '<strong>Error loading data.</strong> Serve the site over HTTP (e.g. <code>python -m http.server</code> from the repo root) and ensure <code>web/data/xgboost_map_data.json</code> exists. Run <code>python web/scripts/build_xgboost_map_data.py</code> to generate it.';
    }
  });
})();
