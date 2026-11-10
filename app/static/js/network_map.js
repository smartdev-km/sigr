(function () {
  var NET = window.NET, B = window.ISLAND_BOUNDS, COND = window.COND, TYPES = window.TYPES, U = window.URLS;
  var COLORS = {
    cond: { bon: '#2e9e5b', moyen: '#e0b020', mauvais: '#e07a20', critique: '#c93a3a' },
    type: { RN: '#0b6e4f', RR: '#1d6fa5', SR: '#c98a12' }
  };
  var ORDER = { cond: ['bon', 'moyen', 'mauvais', 'critique'], type: ['RN', 'RR', 'SR'] };  // tojson trie les clés
  var mode = 'cond', island = '', selected = null;
  var map = L.map('net-map', { zoomSnap: 0.1, zoomDelta: 0.5 }).setView([-11.85, 43.9], 8);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18, attribution: '&copy; contributeurs <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(map);
  var layerGroup = L.layerGroup().addTo(map), structLayer = L.layerGroup().addTo(map);
  var csrf = (document.querySelector('meta[name=csrf-token]') || {}).content;

  function esc(s) { var d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML; }
  function colorOf(r) { return COLORS[mode][mode === 'cond' ? r.cond : r.type]; }
  function url(t, id) { return U[t].replace(/0$/, id); }
  function latlngs(r) {
    if (r.geom) return r.geom.coordinates.map(function (c) { return [c[1], c[0]]; });
    return [r.a].concat(r.vias, [r.b]);
  }
  function checked(sel) {
    return Array.prototype.map.call(document.querySelectorAll(sel + ' input:checked'), function (i) { return i.value; });
  }
  function visible(r) {
    return (!island || r.island === island) && checked('#f-type').indexOf(r.type) >= 0 &&
      checked('#f-cond').indexOf(r.cond) >= 0 && (!document.getElementById('f-active').checked || r.works + r.maint > 0);
  }
  function popup(r) {
    return '<div class="pop"><strong>' + esc(r.code) + '</strong> · ' + esc(r.name) +
      '<div class="pop-meta">' + esc(TYPES[r.type]) + ' · ' + esc(r.island) + ' · ' + r.km + ' km</div>' +
      '<div><span class="badge" style="background:' + COLORS.cond[r.cond] + '">' + esc(COND[r.cond]) + '</span></div>' +
      (r.start || r.end ? '<div class="pop-meta">' + esc(r.start || '?') + ' → ' + esc(r.end || '?') + '</div>' : '') +
      (r.works || r.maint ? '<div class="pop-meta">' + (r.works ? r.works + ' chantier(s) ' : '') + (r.maint ? r.maint + ' entretien(s) ' : '') + 'en cours</div>' : '') +
      '<a class="btn" style="margin-top:.5rem;color:#fff" href="' + url('detail', r.id) + '">Voir le détail</a></div>';
  }
  function icon(label, color) {
    return L.divIcon({ className: '', iconSize: [24, 24], iconAnchor: [12, 12],
      html: '<div style="width:24px;height:24px;border-radius:50%;background:' + color + ';color:#fff;font-size:12px;font-weight:700;display:grid;place-items:center;border:2px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,.5)">' + label + '</div>' });
  }

  var layers = {};
  function draw() {
    layerGroup.clearLayers(); layers = {};
    var shown = NET.filter(function (r) { return r.a && visible(r); });
    shown.forEach(function (r) {
      var isSel = selected === r.id, col = colorOf(r), pts = latlngs(r);
      // fine bordure blanche pour la lisibilité, puis le trait coloré
      L.polyline(pts, { color: '#fff', weight: isSel ? 9 : 7, opacity: .9, interactive: false }).addTo(layerGroup);
      var line = L.polyline(pts, { color: col, weight: isSel ? 6 : 4, opacity: 1, dashArray: r.geom ? null : '6 8' }).addTo(layerGroup);
      line.bindPopup(popup(r));
      line.bindTooltip(esc(r.code) + ' · ' + esc(r.name), { sticky: true });
      line.on('click', function () { select(r.id, false); });
      line.on('mouseover', function () { line.setStyle({ weight: 7 }); });
      line.on('mouseout', function () { line.setStyle({ weight: selected === r.id ? 6 : 4 }); });
      layers[r.id] = line;
      if (r.works) L.polyline(pts, { color: '#000', weight: 1.5, dashArray: '2 8', interactive: false }).addTo(layerGroup);
      if (isSel) {
        L.marker(r.a, { icon: icon('A', '#0b6e4f') }).addTo(layerGroup);
        L.marker(r.b, { icon: icon('B', '#c93a3a') }).addTo(layerGroup);
        r.vias.forEach(function (v, i) { L.marker(v, { icon: icon(String(i + 1), '#c98a12') }).addTo(layerGroup); });
      }
    });
    renderList(shown); renderLegend();
    var total = NET.filter(visible).length, noTrace = NET.filter(function (r) { return visible(r) && !r.a; }).length;
    document.getElementById('map-count').textContent = total + ' route' + (total > 1 ? 's' : '') + ' affichée' + (total > 1 ? 's' : '') +
      (noTrace ? ' · ' + noTrace + ' sans tracé' : '');
  }

  function renderLegend() {
    var el = document.getElementById('legend'), items = [];
    if (mode === 'cond') ORDER.cond.forEach(function (k) { items.push([COLORS.cond[k], COND[k]]); });
    else ORDER.type.forEach(function (k) { items.push([COLORS.type[k], k + ' · ' + TYPES[k]]); });
    items.push(['#fff', 'pointillé fin noir : chantier en cours', true]);
    el.innerHTML = items.map(function (i) {
      return '<span><i class="dot" style="background:' + i[0] + (i[2] ? ';border:1px dashed #000' : '') + '"></i>' + esc(i[1]) + '</span>';
    }).join('');
  }

  function renderList() {
    var ul = document.getElementById('route-list'); ul.innerHTML = '';
    NET.filter(visible).forEach(function (r) {
      var li = document.createElement('li');
      li.className = (selected === r.id ? 'sel ' : '') + (r.a ? '' : 'notrace');
      li.innerHTML = '<i class="dot" style="background:' + colorOf(r) + '"></i><span><strong>' + esc(r.code) + '</strong> ' + esc(r.name) +
        (r.a ? '' : '<em> — sans tracé</em>') + '</span>';
      li.addEventListener('click', function () {
        if (r.a) select(r.id, true); else window.location = url('edit', r.id);
      });
      ul.appendChild(li);
    });
    if (!ul.children.length) ul.innerHTML = '<li class="none">Aucune route pour ces filtres.</li>';
  }

  function select(id, zoom) {
    selected = id; draw();
    var r = NET.filter(function (x) { return x.id === id; })[0], l = layers[id];
    if (zoom && l) { map.fitBounds(l.getBounds().pad(0.3)); l.openPopup(); }
  }

  function fitAll() {
    var b = island ? B[island] : null;
    if (b) { map.fitBounds([[b[0], b[1]], [b[2], b[3]]]); return; }
    var all = [];
    NET.forEach(function (r) { if (r.a && visible(r)) all = all.concat(latlngs(r)); });
    map.fitBounds(all.length ? L.latLngBounds(all).pad(0.15) : [[-12.5, 43.1], [-11.3, 44.7]]);
  }

  // ---- contrôles ----
  document.querySelectorAll('[data-color]').forEach(function (b) {
    b.addEventListener('click', function () {
      mode = b.dataset.color;
      document.querySelectorAll('[data-color]').forEach(function (x) { x.classList.toggle('on', x === b); });
      draw();
    });
  });
  document.querySelectorAll('[data-island]').forEach(function (b) {
    b.addEventListener('click', function () {
      island = b.dataset.island;
      document.querySelectorAll('[data-island]').forEach(function (x) { x.classList.toggle('on', x === b); });
      selected = null; draw(); fitAll();
    });
  });
  ['#f-type', '#f-cond', '#f-active'].forEach(function (s) {
    var el = document.querySelector(s);
    el.addEventListener('change', function () { draw(); });
  });

  // ---- ouvrages (couche facultative) ----
  function drawStructs() {
    structLayer.clearLayers();
    var cb = document.getElementById('f-struct');
    if (!cb || !cb.checked) return;
    (window.STRUCTS || []).forEach(function (o) {
      var m = L.circleMarker([o.lat, o.lng], { radius: 7, color: '#fff', weight: 2, fillColor: COLORS.cond[o.cond], fillOpacity: 1 });
      m.bindPopup('<div class="pop"><strong>' + esc(o.ref) + '</strong> · ' + esc(o.kind) +
        '<div class="pop-meta">' + esc(o.route) + (o.pk != null ? ' · PK ' + o.pk + ' km' : '') + '</div>' +
        '<div><span class="badge" style="background:' + COLORS.cond[o.cond] + '">' + esc(COND[o.cond]) + '</span></div>' +
        '<a class="btn" style="margin-top:.5rem;color:#fff" href="' + url('ouvrage', o.id) + '">Voir l\u2019ouvrage</a></div>');
      m.bindTooltip(esc(o.ref) + ' · ' + esc(o.kind));
      m.addTo(structLayer);
    });
  }
  var sc = document.getElementById('f-struct');
  if (sc) sc.addEventListener('change', drawStructs);

  draw(); fitAll();

  // ---- tracés manquants : calcul + mise en cache côté serveur, un par un (services publics) ----
  var todo = NET.filter(function (r) { return r.a && !r.geom; });
  (function next() {
    var r = todo.shift();
    if (!r) return;
    var pts = [r.a].concat(r.vias, [r.b]).map(function (p) { return L.latLng(p[0], p[1]); });
    SIGR.route(pts).then(function (res) {
      if (res.best) {
        r.geom = JSON.parse(SIGR.compact(res.best.geometry));
        draw();
        fetch(url('geom', r.id), { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
          body: JSON.stringify({ geometry: r.geom }) }).catch(function () {});
      }
      setTimeout(next, 600);
    });
  })();
})();
