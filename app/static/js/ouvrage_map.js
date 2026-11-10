(function () {
  var R = window.ROUTES, OTH = window.OTHERS, B = window.ISLAND_BOUNDS, CUR = window.CUR_ID;
  var sel = document.querySelector('[name=route_id]'), latF = document.querySelector('[name=lat]'),
      lngF = document.querySelector('[name=lng]'), pkF = document.querySelector('[name=pk_km]');
  var map = L.map('ov-map', { zoomSnap: 0.1, zoomDelta: 0.5 }).setView([-11.9, 43.8], 8);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '&copy; contributeurs <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(map);
  var routeLayer = L.layerGroup().addTo(map), otherLayer = L.layerGroup().addTo(map);
  var marker = null, pts = [], bbox = null;
  var status = document.getElementById('ov-status');

  var pin = L.divIcon({ className: '', iconSize: [28, 28], iconAnchor: [14, 14],
    html: '<div style="width:28px;height:28px;border-radius:50%;background:#1d6fa5;color:#fff;display:grid;place-items:center;border:3px solid #fff;box-shadow:0 1px 6px rgba(0,0,0,.5);font-size:14px">⬢</div>' });

  function route() { return R[sel.value]; }

  function drawRoute() {
    routeLayer.clearLayers(); otherLayer.clearLayers(); pts = [];
    var r = route();
    if (!r) return;
    document.getElementById('ov-title').textContent = r.code + ' · ' + r.name;
    document.getElementById('ov-meta').textContent = ' ' + r.island + ' · ' + r.km + ' km';
    var b = B[r.island];
    bbox = b ? L.latLngBounds([b[0], b[1]], [b[2], b[3]]) : null;
    if (r.geom && r.geom.length > 1) pts = r.geom.map(function (c) { return L.latLng(c[0], c[1]); });
    else if (r.a) pts = [L.latLng(r.a)].concat((r.vias || []).map(function (v) { return L.latLng(v); }), [L.latLng(r.b)]);
    if (pts.length > 1) {
      L.polyline(pts, { color: '#fff', weight: 8, opacity: .9, interactive: false }).addTo(routeLayer);
      L.polyline(pts, { color: '#0b6e4f', weight: 4, dashArray: r.geom ? null : '6 8', interactive: false }).addTo(routeLayer);
      L.marker(pts[0], { icon: L.divIcon({ className: '', iconSize: [20, 20], iconAnchor: [10, 10], html: '<div style="width:20px;height:20px;border-radius:50%;background:#0b6e4f;color:#fff;font:700 11px/20px sans-serif;text-align:center;border:2px solid #fff">A</div>' }), interactive: false }).addTo(routeLayer);
      L.marker(pts[pts.length - 1], { icon: L.divIcon({ className: '', iconSize: [20, 20], iconAnchor: [10, 10], html: '<div style="width:20px;height:20px;border-radius:50%;background:#c93a3a;color:#fff;font:700 11px/20px sans-serif;text-align:center;border:2px solid #fff">B</div>' }), interactive: false }).addTo(routeLayer);
      status.textContent = 'Cliquez sur la carte pour placer l’ouvrage.';
    } else {
      status.textContent = 'Cette route n’a pas de tracé : cliquez sur la carte pour placer l’ouvrage (le PK reste à saisir).';
    }
    (OTH[sel.value] || []).forEach(function (o) {
      if (o.id === CUR) return;
      L.circleMarker([o.lat, o.lng], { radius: 5, color: '#fff', weight: 1.5, fillColor: '#8896a0', fillOpacity: 1 })
        .bindTooltip(o.ref + ' · ' + o.kind).addTo(otherLayer);
    });
  }

  function fit() {
    if (marker) { map.setView(marker.getLatLng(), Math.max(map.getZoom(), 15)); return; }
    if (pts.length > 1) map.fitBounds(L.latLngBounds(pts).pad(0.25));
    else if (bbox) map.fitBounds(bbox);
  }

  // point le plus proche sur le tracé : distance et PK (km depuis le début)
  function locate(ll) {
    if (pts.length < 2) return null;
    var z = Math.max(map.getZoom(), 12), p = map.project(ll, z), best = Infinity, bestKm = 0, acc = 0;
    for (var i = 0; i < pts.length - 1; i++) {
      var a = map.project(pts[i], z), b = map.project(pts[i + 1], z), c = L.LineUtil.closestPointOnSegment(p, a, b);
      var d = p.distanceTo(c), cl = map.unproject(c, z);
      if (d < best) { best = d; bestKm = (acc + pts[i].distanceTo(cl)) / 1000; bestD = ll.distanceTo(cl); }
      acc += pts[i].distanceTo(pts[i + 1]);
    }
    return { km: bestKm, dist: bestD };
  }
  var bestD = 0;

  function report(fromClick) {
    if (!marker) { status.textContent = 'Cliquez sur la carte pour placer l’ouvrage.'; return; }
    var ll = marker.getLatLng(), loc = locate(ll);
    latF.value = ll.lat.toFixed(6); lngF.value = ll.lng.toFixed(6);
    if (loc) {
      if (fromClick) pkF.value = loc.km.toFixed(3);
      status.textContent = 'Position enregistrée · PK ≈ ' + loc.km.toFixed(3) + ' km · à ' + Math.round(loc.dist) + ' m de la route' +
        (loc.dist > 300 ? ' ⚠ loin de la route' : '');
    } else status.textContent = 'Position enregistrée : ' + ll.lat.toFixed(5) + ', ' + ll.lng.toFixed(5);
  }

  function place(ll, fromClick) {
    if (bbox && !bbox.contains(ll)) { status.textContent = 'Ce point est en dehors de l’île de la route.'; return; }
    if (marker) marker.setLatLng(ll);
    else {
      marker = L.marker(ll, { icon: pin, draggable: true }).addTo(map);
      marker.on('dragend', function () { report(true); });
    }
    report(fromClick);
  }

  map.on('click', function (e) { if (route()) place(e.latlng, true); });
  document.getElementById('ov-clear').addEventListener('click', function () {
    if (marker) { map.removeLayer(marker); marker = null; }
    latF.value = ''; lngF.value = ''; report(false);
  });
  sel.addEventListener('change', function () {
    if (marker) { map.removeLayer(marker); marker = null; latF.value = ''; lngF.value = ''; }
    drawRoute(); fit();
  });

  // initialisation (lecture des valeurs enregistrées avant tout placement)
  var initLat = parseFloat(latF.value), initLng = parseFloat(lngF.value), initPk = pkF.value;
  drawRoute();
  if (!isNaN(initLat) && !isNaN(initLng)) {
    marker = L.marker([initLat, initLng], { icon: pin, draggable: true }).addTo(map);
    marker.on('dragend', function () { report(true); });
    var loc = locate(marker.getLatLng());
    status.textContent = loc ? 'Position enregistrée · PK ≈ ' + loc.km.toFixed(3) + ' km · à ' + Math.round(loc.dist) + ' m de la route' : 'Position enregistrée.';
    pkF.value = initPk;
  }
  fit();
})();
