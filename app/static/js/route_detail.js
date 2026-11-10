(function () {
  var el = document.getElementById('detail-map');
  var a = L.latLng(+el.dataset.slat, +el.dataset.slng), b = L.latLng(+el.dataset.elat, +el.dataset.elng);
  var vias = []; try { vias = JSON.parse(el.dataset.vias || '[]'); } catch (_) {}
  var pts = [a].concat(vias.map(function (v) { return L.latLng(v.lat, v.lng); }), [b]);
  var map = L.map(el, { scrollWheelZoom: false, zoomSnap: 0.1 });
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18, attribution: '&copy; contributeurs <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(map);
  function icon(letter, color) {
    return L.divIcon({ className: '', iconSize: [30, 30], iconAnchor: [15, 15],
      html: '<div style="width:30px;height:30px;border-radius:50%;background:' + color + ';color:#fff;font-weight:700;display:grid;place-items:center;border:3px solid #fff;box-shadow:0 1px 6px rgba(0,0,0,.5)">' + letter + '</div>' });
  }
  L.marker(a, { icon: icon('A', '#0b6e4f') }).addTo(map);
  vias.forEach(function (v, i) { L.marker([v.lat, v.lng], { icon: icon(String(i + 1), '#c98a12'), title: v.name || '' }).addTo(map); });
  L.marker(b, { icon: icon('B', '#c93a3a') }).addTo(map);
  var fallback = L.polyline(pts, { color: '#1d6fa5', weight: 4, dashArray: '6 8' }).addTo(map);
  map.fitBounds(L.latLngBounds(pts).pad(0.3));
  SIGR.route(pts).then(function (r) {
    if (!r.best) return;
    map.removeLayer(fallback);
    var l = L.geoJSON(r.best.geometry, { style: { color: '#1d6fa5', weight: 5 } }).addTo(map);
    map.fitBounds(l.getBounds().pad(0.2));
  });
})();
