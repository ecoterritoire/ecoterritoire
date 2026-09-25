const state = {
  stations: [],
  timeline: [],
  map: null,
  markers: [],
  day: '2025-01-02',
};
let refreshTimer;

const $ = (selector) => document.querySelector(selector);
const API_BASE = '/api';

function formatDate(value) {
  return new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
    .format(new Date(`${value}T12:00:00Z`)).toUpperCase();
}

function dateFromOffset(offset) {
  const date = new Date(Date.UTC(2025, 0, 1 + Number(offset)));
  return date.toISOString().slice(0, 10);
}

function offsetFromDate(value) {
  return Math.round((Date.parse(`${value}T00:00:00Z`) - Date.parse('2025-01-01T00:00:00Z')) / 86400000);
}

async function getJson(url) {
  const response = await fetch(`${API_BASE}${url}`);
  if (!response.ok) throw new Error(`Erreur API (${response.status})`);
  return response.json();
}

function initMap() {
  state.map = L.map('map', { zoomControl: false, attributionControl: false }).setView([46.6, 2.4], 5.5);
  L.control.zoom({ position: 'bottomright' }).addTo(state.map);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18 }).addTo(state.map);
}

function markerColor(value, values) {
  if (!Number.isFinite(value)) return '#9aa8a1';
  const numeric = values.filter(Number.isFinite);
  const min = Math.min(...numeric);
  const max = Math.max(...numeric);
  const ratio = (value - min) / (max - min || 1);
  if (ratio < 0.34) return '#2d9b72';
  if (ratio < 0.67) return '#e9a23b';
  return '#d65345';
}

function drawMap(data) {
  state.markers.forEach((marker) => marker.remove());
  state.markers = [];
  const mapped = data.filter((point) => point.latitude !== null && point.longitude !== null);
  const values = mapped.map((point) => Number(point.value)).filter(Number.isFinite);
  const measured = mapped.filter((point) => Number.isFinite(Number(point.value)) || point.measurement_count > 0);
  $('#map-note').textContent = mapped.length ? `${measured.length} stations mesurees · ${mapped.length} stations` : 'Aucun point geocode';
  $('#empty-map').hidden = mapped.length > 0;

  mapped.forEach((point) => {
    const hasIndex = point.map_index !== undefined && point.map_index !== null;
    const color = markerColor(Number(hasIndex ? point.map_index : point.value), hasIndex ? [0, 100] : values);
    const marker = L.circleMarker([point.latitude, point.longitude], { radius: 7, color, fillColor: color, fillOpacity: .82, weight: 2 })
      .bindPopup(`<strong>${point.nom_site}</strong><br>${point.map_index !== undefined && point.map_index !== null ? `Indice multi-polluants · ${point.map_index}/100` : Number.isFinite(Number(point.value)) ? `${point.Polluant || point.pollutant || ''} · ${point.value} µg/m³` : point.measurement_count ? `${point.measurement_count} polluants mesures ce jour` : 'Pas de mesure pour ce jour'} `)
      .addTo(state.map);
    state.markers.push(marker);
  });
}

function drawSummary(data) {
  const content = $('#summary-content');
  if (!data.length) {
    content.innerHTML = '<p class="summary-empty">Aucune mesure disponible pour cette date.</p>';
    return;
  }
  content.innerHTML = data.map((summary) => `
    <article class="summary-card">
      <span>${summary.pollutant}</span>
      <strong>${summary.average.toFixed(2)} <small>µg/m³</small></strong>
      <dl><div><dt>Min</dt><dd>${summary.minimum.toFixed(2)}</dd></div><div><dt>Max</dt><dd>${summary.maximum.toFixed(2)}</dd></div><div><dt>Stations</dt><dd>${summary.stations}</dd></div></dl>
    </article>`).join('');
}

async function refreshDashboard() {
  const summaryPollutant = $('#summary-pollutant-select').value;
  const day = state.day;
  $('#selected-date').textContent = formatDate(day);
  try {
    const map = await getJson(`/pollution/map?day=${day}${summaryPollutant ? `&pollutant=${encodeURIComponent(summaryPollutant)}` : ''}`);
    drawMap(map.data);
    const summary = await getJson(`/pollution/summary?day=${day}${summaryPollutant ? `&pollutant=${encodeURIComponent(summaryPollutant)}` : ''}`);
    drawSummary(summary.data);
    $('#scrubber-date').textContent = formatDate(day);
    $('#scrubber-index').textContent = `Jour ${offsetFromDate(day) + 1} sur 365`;
    $('#chart-value').textContent = `${map.data.filter((point) => Number.isFinite(Number(point.value)) || point.measurement_count > 0).length} stations mesurees`;
    $('.scrubber-track span').style.width = `${(offsetFromDate(day) + 1) / 365 * 100}%`;
  } catch (error) {
    $('#map-note').textContent = error.message;
    $('#scrubber-index').textContent = 'Donnees indisponibles';
  } finally {
  }
}

async function bootstrap() {
  initMap();
  const [stations, pollutants] = await Promise.all([getJson('/stations'), getJson('/pollutants')]);
  state.stations = stations.data;
  pollutants.data.forEach((pollutant) => $('#summary-pollutant-select').insertAdjacentHTML('beforeend', `<option value="${pollutant}">${pollutant}</option>`));
  $('#timeline-input').addEventListener('input', (event) => {
    state.day = dateFromOffset(event.target.value);
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(refreshDashboard, 120);
  });
  $('#summary-pollutant-select').addEventListener('change', refreshDashboard);
  $('#timeline-input').value = offsetFromDate(state.day);
  await refreshDashboard();
}

bootstrap().catch((error) => {
  $('#map-note').textContent = error.message;
  $('#summary-content').innerHTML = `<p class="summary-empty">${error.message}</p>`;
});
