(function () {
  var G = window.ROUTE_GEO, sel = document.querySelector('[name=route_id]');
  var mapEl = document.getElementById('rp-map'), emptyEl = document.getElementById('rp-empty');
  var map = L.map(mapEl, { scrollWheelZoom: false, zoomSnap: 0.1 }).setView([-11.9, 43.8], 8);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18, attribution: '&copy; contributeurs <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(map);
  var layer = L.layerGroup().addTo(map), seq = 0;

  function icon(letter, color) {
    return L.divIcon({ className: '', iconSize: [30, 30], iconAnchor: [15, 15],
      html: '<div style="width:30px;height:30px;border-radius:50%;background:' + color + ';color:#fff;font-weight:700;display:grid;place-items:center;border:3px solid #fff;box-shadow:0 1px 6px rgba(0,0,0,.5)">' + letter + '</div>' });
  }

  function show() {
    var r = G[sel.value], my = ++seq;
    layer.clearLayers();
    if (!r) { mapEl.hidden = true; emptyEl.hidden = false; return; }
    document.getElementById('rp-title').textContent = r.code + ' · ' + r.name;
    document.getElementById('rp-meta').textContent = ' ' + r.type + ' · ' + r.island + ' · ' + r.km + ' km · état : ' + r.condition;
    if (!r.a) { mapEl.hidden = true; emptyEl.hidden = false; return; }
    emptyEl.hidden = true; mapEl.hidden = false;
    map.invalidateSize();
    var a = L.latLng(r.a), b = L.latLng(r.b);
    L.marker(a, { icon: icon('A', '#0b6e4f'), title: r.start || '' }).addTo(layer);
    L.marker(b, { icon: icon('B', '#c93a3a'), title: r.end || '' }).addTo(layer);
    var pts = [a].concat((r.vias || []).map(function (v) { return L.latLng(v); }), [b]);
    (r.vias || []).forEach(function (v, i) { L.marker(v, { icon: icon(String(i + 1), '#c98a12') }).addTo(layer); });
    var line = L.polyline(pts, { color: '#1d6fa5', weight: 4, dashArray: '6 8' }).addTo(layer);
    map.fitBounds(L.latLngBounds(pts).pad(0.3));
    SIGR.route(pts).then(function (res) {
      if (my !== seq || !res.best) return;
      layer.removeLayer(line);
      var l = L.geoJSON(res.best.geometry, { style: { color: '#1d6fa5', weight: 5 } }).addTo(layer);
      map.fitBounds(l.getBounds().pad(0.2));
    });
  }
  sel.addEventListener('change', show);
  show();
})();
