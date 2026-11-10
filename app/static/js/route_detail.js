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
  var issues = []; try { issues = JSON.parse(el.dataset.issues || '[]'); } catch (_) {}
  var cached = []; try { cached = JSON.parse(el.dataset.geom || '[]'); } catch (_) {}
  var COLORS = { mineur: '#e0b020', important: '#e07a20', critique: '#c93a3a' };
  var issueLayer = L.layerGroup().addTo(map);

  function numIcon(n, color) {
    return L.divIcon({ className: '', iconSize: [26, 26], iconAnchor: [13, 13],
      html: '<div style="width:26px;height:26px;border-radius:50%;background:' + color + ';color:#fff;font:700 12px/20px sans-serif;text-align:center;border:3px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,.5)">' + n + '</div>' });
  }
  function drawIssues(routePts) {
    issueLayer.clearLayers();
    var line = routePts && routePts.length > 1 && window.SIGRGeo ? new SIGRGeo.Line(routePts) : null;
    issues.forEach(function (it, i) {
      var col = COLORS[it.severity] || '#e07a20', tip = (i + 1) + '. ' + it.label + (it.text ? ' — ' + it.text : '') + ' (' + it.where + ')';
      var a = it.start_lat != null ? L.latLng(it.start_lat, it.start_lng) : (line && it.pk_start != null ? line.at(it.pk_start) : null);
      if (!a) return;
      if (it.pk_end != null && it.pk_end > it.pk_start) {
        var b2 = it.end_lat != null ? L.latLng(it.end_lat, it.end_lng) : (line ? line.at(it.pk_end) : null);
        var seg = line ? line.slice(it.pk_start, it.pk_end) : [a, b2];
        L.polyline(seg, { color: '#fff', weight: 11, opacity: .9, interactive: false }).addTo(issueLayer);
        L.polyline(seg, { color: col, weight: 7 }).bindTooltip(tip).addTo(issueLayer);
        L.marker(seg[Math.floor(seg.length / 2)], { icon: numIcon(i + 1, col) }).bindTooltip(tip).addTo(issueLayer);
      } else {
        L.marker(a, { icon: numIcon(i + 1, col) }).bindTooltip(tip).addTo(issueLayer);
      }
    });
  }

  if (cached.length > 1) {                       // tracé routier enregistré : aucun appel réseau
    var cpts = cached.map(function (c) { return L.latLng(c[0], c[1]); });
    L.polyline(cpts, { color: '#1d6fa5', weight: 5 }).addTo(map);
    map.fitBounds(L.latLngBounds(cpts).pad(0.2));
    drawIssues(cpts);
    return;
  }
  var fallback = L.polyline(pts, { color: '#1d6fa5', weight: 4, dashArray: '6 8' }).addTo(map);
  map.fitBounds(L.latLngBounds(pts).pad(0.3));
  drawIssues(pts);
  SIGR.route(pts).then(function (r) {
    if (!r.best) return;
    map.removeLayer(fallback);
    var l = L.geoJSON(r.best.geometry, { style: { color: '#1d6fa5', weight: 5 } }).addTo(map);
    map.fitBounds(l.getBounds().pad(0.2));
    drawIssues(r.best.geometry.coordinates.map(function (c) { return L.latLng(c[1], c[0]); }));
  });
})();
