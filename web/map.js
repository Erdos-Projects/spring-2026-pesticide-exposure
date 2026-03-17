/**
 * County-level risk map: loads US counties GeoJSON and risk_estimates.json,
 * colors counties by risk_index, shows popup on click.
 * Replace data/risk_estimates.json with your model output (see web/README.md).
 */

(function () {
  const COUNTIES_GEOJSON_URL =
    'https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json';
  const RISK_DATA_URL = 'data/risk_estimates.json';

  const RISK_COLORS = [
    '#0d1117', '#161b22', '#21262d', '#30363d', '#484f58',
    '#6e7681', '#8b949e', '#b1bac4', '#c9d1d9', '#f0f6fc'
  ];
  const NO_DATA_COLOR = '#21262d';

  function getColor(risk) {
    if (risk == null || isNaN(risk)) return NO_DATA_COLOR;
    const i = Math.min(Math.floor(risk * (RISK_COLORS.length - 1)), RISK_COLORS.length - 1);
    return RISK_COLORS[i];
  }

  function style(feature, riskByFips) {
    const fips = feature.id;
    const r = riskByFips[fips];
    const risk = r && typeof r.risk_index === 'number' ? r.risk_index : null;
    return {
      fillColor: getColor(risk),
      weight: 1,
      opacity: 0.8,
      color: '#30363d',
      fillOpacity: 0.7
    };
  }

  function onEachFeature(feature, layer, riskByFips) {
    const fips = feature.id;
    const r = riskByFips[fips];
    const name = (feature.properties && feature.properties.NAME) ? feature.properties.NAME : 'County';
    const state = (feature.properties && feature.properties.STATE) ? feature.properties.STATE : '';
    const countyLabel = state ? name + ', ' + state : name;

    layer.on({
      mouseover: function (e) {
        const l = e.target;
        l.setStyle({ weight: 2, color: '#58a6ff', fillOpacity: 0.85 });
        l.bringToFront();
      },
      mouseout: function (e) {
        e.target.setStyle(style(feature, riskByFips));
      }
    });

    let content = '<div class="info-panel"><h3>' + countyLabel + '</h3>';
    if (r) {
      content += '<p><strong>Risk index:</strong> ' + (r.risk_index != null ? r.risk_index.toFixed(3) : '—') + '</p>';
      if (r.CASTHMA_prev != null) content += '<p>Asthma prev. %: ' + r.CASTHMA_prev.toFixed(1) + '</p>';
      if (r.COPD_prev != null) content += '<p>COPD prev. %: ' + r.COPD_prev.toFixed(1) + '</p>';
    } else {
      content += '<p>No risk data for this county.</p>';
    }
    content += '</div>';
    layer.bindPopup(content);
  }

  const map = L.map('map', { preferCanvas: true }).setView([39.5, -98.35], 4);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 19
  }).addTo(map);

  Promise.all([
    fetch(COUNTIES_GEOJSON_URL).then(function (res) { return res.json(); }),
    fetch(RISK_DATA_URL).then(function (res) { return res.json(); })
  ]).then(function (results) {
    const geojson = results[0];
    const riskByFips = results[1];

    L.geoJSON(geojson, {
      style: function (feature) { return style(feature, riskByFips); },
      onEachFeature: function (feature, layer) { onEachFeature(feature, layer, riskByFips); }
    }).addTo(map);
  }).catch(function (err) {
    console.error('Failed to load map data:', err);
    document.querySelector('.map-legend').innerHTML =
      '<strong>Error loading data.</strong> If opening from file://, use a local server or deploy to GitHub Pages. Ensure <code>data/risk_estimates.json</code> exists.';
  });
})();
