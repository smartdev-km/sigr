(function () {
  // ---- info-bulles au survol ([data-tip]) ----
  var tip = document.createElement('div');
  tip.className = 'viz-tip'; tip.hidden = true; document.body.appendChild(tip);
  function move(e) {
    var x = e.clientX + 14, y = e.clientY + 14, w = tip.offsetWidth, h = tip.offsetHeight;
    if (x + w > window.innerWidth - 8) x = e.clientX - w - 14;
    if (y + h > window.innerHeight - 8) y = e.clientY - h - 14;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  }
  document.addEventListener('mouseover', function (e) {
    var el = e.target.closest('[data-tip]');
    if (!el) return;
    tip.textContent = el.getAttribute('data-tip'); tip.hidden = false; move(e);
  });
  document.addEventListener('mousemove', function (e) { if (!tip.hidden) move(e); });
  document.addEventListener('mouseout', function (e) {
    if (e.target.closest('[data-tip]') && !(e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest('[data-tip]') === e.target.closest('[data-tip]'))) tip.hidden = true;
  });

  // ---- mini-carte ----
  var el = document.getElementById('mini-map');
  if (!el || !window.L || !window.MINI) return;
  var COL = { bon: '#2e9e5b', moyen: '#e0b020', mauvais: '#e07a20', critique: '#c93a3a' };
  var map = L.map(el, { zoomSnap: 0.1, scrollWheelZoom: false, attributionControl: true });
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18, attribution: '&copy; contributeurs <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(map);
  var all = [];
  window.MINI.forEach(function (r) {
    var pts = r.geom ? r.geom.coordinates.map(function (c) { return [c[1], c[0]]; }) : [r.a].concat(r.vias || [], [r.b]);
    all = all.concat(pts);
    L.polyline(pts, { color: '#fff', weight: 7, opacity: .9, interactive: false }).addTo(map);
    var line = L.polyline(pts, { color: COL[r.cond], weight: 4, dashArray: r.geom ? null : '6 8' }).addTo(map);
    line.bindTooltip(r.code + ' · ' + r.name + ' (' + r.km + ' km)', { sticky: true });
    line.on('click', function () { window.location = window.MINI_URL.replace(/0$/, r.id); });
  });
  if (all.length) map.fitBounds(L.latLngBounds(all).pad(0.12)); else map.setView([-11.85, 43.9], 8);
  el.addEventListener('click', function () { map.scrollWheelZoom.enable(); }, { once: true });
})();
