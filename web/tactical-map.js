import maplibregl from 'https://unpkg.com/maplibre-gl@6.7.0/dist/maplibre-gl.mjs';

const center = [-117.1611, 32.7157];

// Development fixture only. Replace this with authenticated RF measurement data.
const detections = [
  { id: 'RF-001', frequencyMHz: 915.2, powerDbm: -48, lat: 32.7165, lon: -117.1602 },
  { id: 'RF-002', frequencyMHz: 433.9, powerDbm: -67, lat: 32.7149, lon: -117.1624 },
  { id: 'RF-003', frequencyMHz: 2400.0, powerDbm: -55, lat: 32.7171, lon: -117.1631 }
];

const toGeoJSON = (items) => ({
  type: 'FeatureCollection',
  features: items.map((d) => ({
    type: 'Feature',
    geometry: { type: 'Point', coordinates: [d.lon, d.lat] },
    properties: d
  }))
});

const map = new maplibregl.Map({
  container: 'map',
  center,
  zoom: 13,
  style: {
    version: 8,
    sources: {
      osm: {
        type: 'raster',
        tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
        tileSize: 256,
        maxzoom: 19,
        attribution: '© OpenStreetMap contributors'
      }
    },
    layers: [{ id: 'osm', type: 'raster', source: 'osm' }]
  },
  attributionControl: true
});

map.addControl(new maplibregl.NavigationControl(), 'top-right');
map.addControl(new maplibregl.ScaleControl({ unit: 'imperial' }));

map.on('load', () => {
  map.addSource('rf-detections', {
    type: 'geojson',
    data: toGeoJSON(detections)
  });

  map.addLayer({
    id: 'rf-radius',
    type: 'circle',
    source: 'rf-detections',
    paint: {
      'circle-radius': 28,
      'circle-color': '#22d3ee',
      'circle-opacity': 0.10,
      'circle-stroke-color': '#22d3ee',
      'circle-stroke-width': 1,
      'circle-stroke-opacity': 0.55
    }
  });

  map.addLayer({
    id: 'rf-points',
    type: 'circle',
    source: 'rf-detections',
    paint: {
      'circle-radius': 7,
      'circle-color': [
        'interpolate', ['linear'], ['get', 'powerDbm'],
        -90, '#38bdf8',
        -65, '#facc15',
        -40, '#fb7185'
      ],
      'circle-stroke-color': '#ffffff',
      'circle-stroke-width': 1.5
    }
  });

  map.on('click', 'rf-points', (event) => {
    const p = event.features[0].properties;
    new maplibregl.Popup()
      .setLngLat(event.lngLat)
      .setHTML(`<strong>${p.id}</strong><br>${Number(p.frequencyMHz).toFixed(1)} MHz<br>${p.powerDbm} dBm`)
      .addTo(map);
  });

  map.on('mouseenter', 'rf-points', () => { map.getCanvas().style.cursor = 'pointer'; });
  map.on('mouseleave', 'rf-points', () => { map.getCanvas().style.cursor = ''; });

  renderDetections();
});

function renderDetections() {
  const container = document.querySelector('#detections');
  container.innerHTML = detections.map((d) => `
    <button class="detection" data-id="${d.id}">
      <span><b>${d.id}</b><small>${d.frequencyMHz.toFixed(1)} MHz</small></span>
      <strong>${d.powerDbm} dBm</strong>
    </button>
  `).join('');

  container.querySelectorAll('.detection').forEach((button) => {
    button.addEventListener('click', () => {
      const d = detections.find((item) => item.id === button.dataset.id);
      map.flyTo({ center: [d.lon, d.lat], zoom: 16, essential: true });
    });
  });
}

function updateHud() {
  const c = map.getCenter();
  document.querySelector('#lat').textContent = c.lat.toFixed(4);
  document.querySelector('#lon').textContent = c.lng.toFixed(4);
  document.querySelector('#zoom').textContent = map.getZoom().toFixed(1);
}

map.on('move', updateHud);
updateHud();
