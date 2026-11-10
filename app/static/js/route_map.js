(function () {
  var B = window.ISLAND_BOUNDS;
  var $ = function (id) { return document.getElementById(id); };
  var islandSel = document.querySelector('[name=island]');
  var f = {
    sLat: document.querySelector('[name=start_lat]'), sLng: document.querySelector('[name=start_lng]'),
    eLat: document.querySelector('[name=end_lat]'), eLng: document.querySelector('[name=end_lng]'),
    wp: document.querySelector('[name=waypoints]'),
    geom: document.querySelector('[name=geometry]')
  };
  var MAX_VIAS = 20, MAX_NAME_DIST = 6000; // mètres
  var map = L.map('map', { zoomControl: true, zoomSnap: 0.1, zoomDelta: 0.5 });
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18, attribution: '&copy; contributeurs <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(map);

  // ---- Modèle : un « point » = { role, marker, input, seq } ----
  var startPt, endPt, vias = [], active = null, line = null, bbox = null;

  function icon(label, color) {
    return L.divIcon({
      className: '', iconSize: [30, 30], iconAnchor: [15, 15],
      html: '<div style="width:30px;height:30px;border-radius:50%;background:' + color +
        ';color:#fff;font-weight:700;display:grid;place-items:center;border:3px solid #fff;box-shadow:0 1px 6px rgba(0,0,0,.5)">' + label + '</div>'
    });
  }
  function iconFor(p) {
    if (p.role === 'start') return icon('A', '#0b6e4f');
    if (p.role === 'end') return icon('B', '#c93a3a');
    return icon(String(vias.indexOf(p) + 1), '#c98a12');
  }
  function allPoints() { return [startPt].concat(vias, [endPt]); }
  function placed() { return allPoints().filter(function (p) { return p.marker; }); }
  function ll(p) { return p.marker.getLatLng(); }
  function inBounds(x) { return bbox && bbox.contains(x); }
  function warn() { $('map-hint').textContent = 'Ce point est en dehors de l’île sélectionnée.'; }

  function setActive(p) {
    active = p;
    document.querySelectorAll('[data-pick]').forEach(function (b) {
      b.classList.toggle('on', (b.dataset.pick === 'start' && p === startPt) || (b.dataset.pick === 'end' && p === endPt));
    });
    allPoints().forEach(function (v) { v.row.classList.toggle('active', v === p); });
  }

  // ---- Synchronisation formulaire / carte ----
  var ready = false, routeSeq = 0, timer = null, lengthDirty = false;
  var lengthInput = document.querySelector('[name=length_km]');
  lengthInput.addEventListener('input', function (ev) { if (ev.isTrusted) lengthDirty = true; });

  var lastSig = null;
  function sync() {
    var s = startPt.marker, e = endPt.marker;
    f.sLat.value = s ? ll(startPt).lat.toFixed(6) : ''; f.sLng.value = s ? ll(startPt).lng.toFixed(6) : '';
    f.eLat.value = e ? ll(endPt).lat.toFixed(6) : ''; f.eLng.value = e ? ll(endPt).lng.toFixed(6) : '';
    f.wp.value = JSON.stringify(vias.filter(function (v) { return v.marker; }).map(function (v) {
      return { lat: +ll(v).lat.toFixed(6), lng: +ll(v).lng.toFixed(6), name: v.input.value.trim() };
    }));
    $('coord-start').textContent = 'A : ' + (s ? f.sLat.value + ', ' + f.sLng.value : '—');
    $('coord-end').textContent = 'B : ' + (e ? f.eLat.value + ', ' + f.eLng.value : '—');
    var nv = vias.filter(function (v) { return v.marker; }).length;
    $('coord-vias').textContent = nv ? nv + ' point' + (nv > 1 ? 's' : '') + ' intermédiaire' + (nv > 1 ? 's' : '') : '';
    vias.forEach(function (v) { if (v.marker) v.marker.setIcon(iconFor(v)); });
    if (line) { map.removeLayer(line); line = null; }
    $('coord-dist').textContent = '';
    var sig = placed().map(function (p) { return ll(p).lat.toFixed(6) + ',' + ll(p).lng.toFixed(6); }).join('|');
    var moved = ready && sig !== lastSig;
    lastSig = sig;
    if (moved) f.geom.value = '';   // l'ancien tracé ne correspond plus aux points
    if (s && e) {
      line = L.polyline(placed().map(ll), { color: '#1d6fa5', weight: 4, dashArray: '6 8' }).addTo(map);
      if (moved) scheduleRoute();
    } else {
      routeSeq++;
    }
  }

  // ---- Longueur dynamique : distance routière (OSRM) via tous les points ----
  function setLength(km, text, drawn) {
    $('coord-dist').textContent = text;
    if (drawn) { if (line) map.removeLayer(line); line = drawn.addTo(map); }
    if (lengthDirty) return;
    lengthInput.value = km.toFixed(1);
    lengthInput.classList.add('auto');
    setTimeout(function () { lengthInput.classList.remove('auto'); }, 900);
  }
  function scheduleRoute() { clearTimeout(timer); timer = setTimeout(computeRoute, 350); }
  function computeRoute() {
    var pts = placed().map(ll), seq = ++routeSeq, air = 0;
    for (var i = 1; i < pts.length; i++) air += pts[i - 1].distanceTo(pts[i]) / 1000;
    $('coord-dist').textContent = 'Calcul de la distance…';
    SIGR.route(pts).then(function (r) {
      if (seq !== routeSeq) return;
      if (r.best) f.geom.value = SIGR.compact(r.best.geometry);
      if (!r.best) { setLength(air, 'Distance à vol d\u2019oiseau : ' + air.toFixed(1) + ' km (itinéraire indisponible)'); return; }
      setLength(r.best.km, SIGR.describe(r),
        L.geoJSON(r.best.geometry, { style: { color: '#1d6fa5', weight: 5 } }));
    });
  }

  // ---- Nom du lieu depuis la carte (géocodage inverse) ----
  function reverseName(p, pos) {
    var seq = ++p.seq;
    p.input.classList.add('loading');
    p.input.value = '';
    p.input.placeholder = 'Recherche du lieu…';
    var url = 'https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=14&accept-language=fr&lat=' + pos.lat + '&lon=' + pos.lng;
    fetch(url).then(function (r) { return r.json(); }).then(function (d) {
      if (seq !== p.seq) return;
      var a = (d && d.address) || {};
      var name = (d && !d.error) ? (d.name || a.village || a.hamlet || a.suburb || a.neighbourhood || a.town || a.city || a.municipality || '') : '';
      if (name && d.lat && pos.distanceTo(L.latLng(parseFloat(d.lat), parseFloat(d.lon))) > MAX_NAME_DIST) name = '';
      p.input.value = name;
    }).catch(function () {}).then(function () {
      if (seq !== p.seq) return;
      p.input.classList.remove('loading');
      p.input.placeholder = p.input.value ? '' : 'Lieu non reconnu : saisissez un nom';
      sync();
    });
  }

  function place(p, pos) {
    if (p.marker) { p.marker.setLatLng(pos); }
    else {
      p.marker = L.marker(pos, { icon: iconFor(p), draggable: true }).addTo(map);
      p.marker.on('drag', sync);
      p.marker.on('dragend', function () {
        if (!inBounds(ll(p))) warn(); else reverseName(p, ll(p));
        sync();
      });
      p.marker.on('click', function () { setActive(p); });
    }
    sync();
  }
  function unplace(p) { if (p.marker) { map.removeLayer(p.marker); p.marker = null; } }

  // ---- Recherche d'un lieu par son nom (Nominatim) ----
  function attachSearch(p, box) {
    var input = p.input, list = box.querySelector('.geo-results'), btn = box.querySelector('.geo-btn'), lastQ = '';
    function close() { list.hidden = true; list.innerHTML = ''; }
    function choose(r) {
      var pos = L.latLng(parseFloat(r.lat), parseFloat(r.lon));
      if (!inBounds(pos)) { warn(); return; }
      p.seq++;
      place(p, pos);
      if (placed().length >= 2) map.fitBounds(L.latLngBounds(placed().map(ll)).pad(0.3));
      else map.setView(pos, Math.max(map.getZoom(), 13));
      if (p === startPt && !endPt.marker) setActive(endPt);
      close();
    }
    function show(items, q) {
      list.innerHTML = '';
      if (!items.length) {
        var li = document.createElement('li'); li.className = 'none';
        li.textContent = 'Aucun lieu trouvé pour « ' + q + ' » sur cette île. Cliquez directement sur la carte.';
        list.appendChild(li);
      }
      items.forEach(function (r) {
        var li = document.createElement('li'); li.tabIndex = 0;
        li.textContent = r.display_name.split(',').slice(0, 3).join(', ');
        li.addEventListener('click', function () { choose(r); });
        li.addEventListener('keydown', function (e) { if (e.key === 'Enter') choose(r); });
        list.appendChild(li);
      });
      list.hidden = false;
    }
    function search() {
      var q = input.value.trim();
      if (q.length < 2 || q === lastQ) return;
      lastQ = q;
      var b = B[islandSel.value];
      var url = 'https://nominatim.openstreetmap.org/search?format=jsonv2&limit=5&accept-language=fr&countrycodes=km' +
        '&viewbox=' + [b[1], b[2], b[3], b[0]].join(',') + '&bounded=1&q=' + encodeURIComponent(q);
      list.innerHTML = '<li class="none">Recherche…</li>'; list.hidden = false;
      fetch(url).then(function (r) { return r.json(); }).then(function (items) {
        var seen = {};
        items = items.filter(function (r) {
          var k = r.display_name.split(',').slice(0, 3).join(',');
          return seen[k] ? false : (seen[k] = true);
        });
        show(items, q);
        if (items.length === 1) choose(items[0]);
      }).catch(function () {
        list.innerHTML = '<li class="none">Recherche indisponible (connexion ?). Cliquez sur la carte.</li>';
      });
    }
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); lastQ = ''; search(); }
      if (e.key === 'Escape') close();
    });
    input.addEventListener('input', function () { sync(); });
    input.addEventListener('focus', function () { setActive(p); });
    input.addEventListener('blur', function () { setTimeout(function () { if (list.hidden) search(); }, 200); });
    btn.addEventListener('click', function () { lastQ = ''; search(); });
    document.addEventListener('click', function (e) { if (!box.contains(e.target)) close(); });
  }

  // ---- Points intermédiaires (lignes dynamiques) ----
  function renumber() {
    vias.forEach(function (v, i) {
      v.row.querySelector('.via-num').textContent = i + 1;
      v.row.querySelector('[data-up]').disabled = i === 0;
      v.row.querySelector('[data-down]').disabled = i === vias.length - 1;
    });
    $('add-via').disabled = $('map-add-via').disabled = vias.length >= MAX_VIAS;
    sync();
  }
  function addVia(init) {
    if (vias.length >= MAX_VIAS) return null;
    var row = document.createElement('div');
    row.className = 'via-row';
    row.innerHTML =
      '<span class="via-num"></span>' +
      '<div class="geo via-geo"><div class="input-group"><input type="text" placeholder="Nom du point intermédiaire (ex. Itsandra)" autocomplete="off" maxlength="120">' +
      '<button type="button" class="suffix geo-btn" title="Localiser sur la carte" aria-label="Localiser sur la carte">🔍</button></div>' +
      '<ul class="geo-results" hidden></ul></div>' +
      '<div class="via-actions">' +
      '<button type="button" class="btn ghost" data-pick-via title="Placer sur la carte">📍</button>' +
      '<button type="button" class="btn ghost" data-up title="Monter" aria-label="Monter">↑</button>' +
      '<button type="button" class="btn ghost" data-down title="Descendre" aria-label="Descendre">↓</button>' +
      '<button type="button" class="btn ghost danger-text" data-del title="Supprimer" aria-label="Supprimer">✕</button></div>';
    $('vias').appendChild(row);
    var p = { role: 'via', marker: null, input: row.querySelector('input'), seq: 0, row: row };
    vias.push(p);
    attachSearch(p, row.querySelector('.geo'));
    row.querySelector('[data-pick-via]').addEventListener('click', function () { setActive(p); });
    row.querySelector('[data-del]').addEventListener('click', function () {
      unplace(p); vias.splice(vias.indexOf(p), 1); row.remove();
      if (active === p) setActive(startPt.marker && !endPt.marker ? endPt : startPt);
      renumber();
    });
    row.querySelector('[data-up]').addEventListener('click', function () { move(p, -1); });
    row.querySelector('[data-down]').addEventListener('click', function () { move(p, 1); });
    if (init) {
      p.input.value = init.name || '';
      place(p, L.latLng(init.lat, init.lng));
    }
    renumber();
    return p;
  }
  function move(p, d) {
    var i = vias.indexOf(p), j = i + d;
    if (j < 0 || j >= vias.length) return;
    vias.splice(i, 1); vias.splice(j, 0, p);
    var box = $('vias');
    if (d < 0) box.insertBefore(p.row, vias[j + 1].row); else box.insertBefore(p.row, vias[j - 1].row.nextSibling);
    renumber();
  }

  // ---- Masque / cadre de l'île ----
  var mask = null, frame = null;
  function maskColor() { return getComputedStyle(document.documentElement).getPropertyValue('--card').trim() || '#fff'; }
  document.addEventListener('click', function (e) {
    if (e.target.closest('[data-theme-toggle]')) setTimeout(function () { if (mask) mask.setStyle({ fillColor: maskColor() }); }, 0);
  });
  function fitIsland() {
    var b = B[islandSel.value];
    if (!b) return;
    bbox = L.latLngBounds([b[0], b[1]], [b[2], b[3]]);
    map.setMinZoom(0);
    map.fitBounds(bbox, { animate: false, padding: [4, 4] });
    map.setMinZoom(map.getZoom());
    map.setMaxBounds(bbox);
    map.options.maxBoundsViscosity = 1.0;
    if (mask) map.removeLayer(mask);
    if (frame) map.removeLayer(frame);
    mask = L.polygon([
      [[-85, -180], [-85, 180], [85, 180], [85, -180]],
      [[b[0], b[1]], [b[0], b[3]], [b[2], b[3]], [b[2], b[1]]]
    ], { stroke: false, fillColor: maskColor(), fillOpacity: 1, interactive: false }).addTo(map);
    mask.bringToBack();
    frame = L.rectangle(bbox, { color: '#0b6e4f', weight: 2, fill: false, interactive: false }).addTo(map);
  }

  // ---- Interactions ----
  map.on('click', function (ev) {
    if (!inBounds(ev.latlng)) { warn(); return; }
    $('map-hint').textContent = 'Cliquez pour placer ou déplacez les marqueurs.';
    var p = active;
    place(p, ev.latlng);
    reverseName(p, ev.latlng);
    if (p === startPt && !endPt.marker) setActive(endPt);
  });
  document.querySelectorAll('[data-pick]').forEach(function (b) {
    b.addEventListener('click', function () { setActive(b.dataset.pick === 'start' ? startPt : endPt); });
  });
  function newVia() { var p = addVia(); if (p) { setActive(p); p.input.focus(); } }
  $('add-via').addEventListener('click', newVia);
  $('map-add-via').addEventListener('click', newVia);

  function clearAll() {
    allPoints().forEach(unplace);
    vias.slice().forEach(function (v) { v.row.remove(); });
    vias.length = 0;
    [startPt, endPt].forEach(function (p) { p.input.value = ''; });
    lengthDirty = false;
    renumber();
    setActive(startPt);
  }
  $('map-clear').addEventListener('click', clearAll);

  var last = islandSel.value;
  islandSel.addEventListener('change', function () {
    if (placed().length && !confirm('Changer d’île efface les points placés. Continuer ?')) { islandSel.value = last; return; }
    last = islandSel.value;
    clearAll();
    fitIsland();
  });

  // ---- Initialisation ----
  startPt = { role: 'start', marker: null, input: document.querySelector('[name=start_point]'), seq: 0, row: document.querySelector('.step-start') };
  endPt = { role: 'end', marker: null, input: document.querySelector('[name=end_point]'), seq: 0, row: document.querySelector('.step-end') };
  document.querySelectorAll('.geo[data-kind]').forEach(function (box) {
    attachSearch(box.dataset.kind === 'start' ? startPt : endPt, box);
  });
  fitIsland();
  // valeurs enregistrées : à lire AVANT de placer quoi que ce soit (place() → sync() réécrit les champs cachés)
  var init = {
    s: f.sLat.value && f.sLng.value ? [parseFloat(f.sLat.value), parseFloat(f.sLng.value)] : null,
    e: f.eLat.value && f.eLng.value ? [parseFloat(f.eLat.value), parseFloat(f.eLng.value)] : null,
    v: []
  };
  try { init.v = JSON.parse(f.wp.value || '[]'); } catch (_) {}
  if (init.s) place(startPt, init.s);
  if (init.e) place(endPt, init.e);
  init.v.forEach(function (v) { addVia(v); });
  if (placed().length >= 2) map.fitBounds(L.latLngBounds(placed().map(ll)).pad(0.3));
  ready = true;
  lastSig = placed().map(function (p) { return ll(p).lat.toFixed(6) + ',' + ll(p).lng.toFixed(6); }).join('|');
  sync();
  if (lengthInput.value && parseFloat(lengthInput.value) > 0 && startPt.marker) lengthDirty = true;
  setActive(startPt.marker && !endPt.marker ? endPt : startPt);
})();
