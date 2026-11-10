/* Points et secteurs à problème d'un diagnostic : saisie, placement sur la carte, calcul du PK. */
(function () {
  var KINDS = window.ISSUE_KINDS, SEV = window.ISSUE_SEVERITY;           // [[clé, libellé], …]
  var COLORS = { mineur: '#e0b020', important: '#e07a20', critique: '#c93a3a' };
  var hidden = document.querySelector('[name=issues]'), box = document.getElementById('issue-list'),
      sel = document.querySelector('[name=route_id]'), status = document.getElementById('iss-status'),
      addBtn = document.getElementById('add-issue');
  var RP = window.RP, map = RP.map, layer = L.layerGroup().addTo(map);
  var issues = [], armed = null, prevRoute = sel.value;

  function el(html) { var d = document.createElement('div'); d.innerHTML = html.trim(); return d.firstChild; }
  function opts(list, cur) {
    return list.map(function (o) { return '<option value="' + o[0] + '"' + (o[0] === cur ? ' selected' : '') + '>' + o[1] + '</option>'; }).join('');
  }
  function num(v) { var x = parseFloat(v); return isNaN(x) ? null : x; }
  function fmt(x) { return x == null ? '' : String(Math.round(x * 1000) / 1000); }

  // ---------- sérialisation ----------
  function save() {
    hidden.value = JSON.stringify(issues.map(function (i) {
      return { kind: i.kind, severity: i.severity, text: i.text, pk_start: i.pk_start,
               pk_end: i.mode === 'sector' ? i.pk_end : null,
               start_lat: i.a ? +i.a.lat.toFixed(6) : null, start_lng: i.a ? +i.a.lng.toFixed(6) : null,
               end_lat: i.mode === 'sector' && i.b ? +i.b.lat.toFixed(6) : null, end_lng: i.mode === 'sector' && i.b ? +i.b.lng.toFixed(6) : null };
    }));
  }

  // ---------- carte ----------
  function numIcon(n, color) {
    return L.divIcon({ className: '', iconSize: [26, 26], iconAnchor: [13, 13],
      html: '<div style="width:26px;height:26px;border-radius:50%;background:' + color + ';color:#fff;font:700 12px/20px sans-serif;text-align:center;border:3px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,.5)">' + n + '</div>' });
  }
  function draw() {
    layer.clearLayers();
    issues.forEach(function (it, idx) {
      var col = COLORS[it.severity] || '#e07a20', n = idx + 1, tip = n + '. ' + (it.kindLabel || '') + (it.text ? ' — ' + it.text : '');
      if (it.mode === 'sector' && it.a && it.b) {
        var seg = RP.line && it.pk_start != null && it.pk_end != null ? RP.line.slice(it.pk_start, it.pk_end) : [it.a, it.b];
        L.polyline(seg, { color: '#fff', weight: 11, opacity: .9, interactive: false }).addTo(layer);
        L.polyline(seg, { color: col, weight: 7, opacity: .95 }).bindTooltip(tip).addTo(layer);
        L.marker(seg[Math.floor(seg.length / 2)], { icon: numIcon(n, col) }).bindTooltip(tip).addTo(layer);
      } else if (it.a) {
        L.marker(it.a, { icon: numIcon(n, col) }).bindTooltip(tip).addTo(layer);
      }
    });
    if (armed && armed.step === 'b' && armed.issue.a) {
      L.circleMarker(armed.issue.a, { radius: 8, color: '#fff', weight: 2, fillColor: COLORS[armed.issue.severity], fillOpacity: 1 }).addTo(layer);
    }
  }

  // ---------- lignes de saisie ----------
  function refreshRow(it) {
    var r = it.row;
    r.querySelector('.iss-pke').style.display = it.mode === 'sector' ? '' : 'none';
    r.querySelector('.iss-num').style.background = COLORS[it.severity];
    r.querySelector('.iss-num').textContent = issues.indexOf(it) + 1;
    r.querySelector('.iss-where').textContent = it.a
      ? (it.mode === 'sector' && it.b ? 'Secteur placé sur la carte' : (it.mode === 'sector' ? 'Début placé : cliquez sur la fin' : 'Point placé sur la carte'))
      : (RP.line ? 'Pas encore placé sur la carte' : 'Route sans tracé : saisissez les PK');
  }
  function renumber() { issues.forEach(refreshRow); }

  function addIssue(init, focusText) {
    var it = { kind: init.kind || KINDS[0][0], severity: init.severity || 'important', text: init.text || '',
               mode: init.pk_end != null && init.pk_end > init.pk_start ? 'sector' : (init.mode || 'point'),
               pk_start: init.pk_start != null ? init.pk_start : null, pk_end: init.pk_end != null ? init.pk_end : null,
               a: init.start_lat != null ? L.latLng(init.start_lat, init.start_lng) : null,
               b: init.end_lat != null ? L.latLng(init.end_lat, init.end_lng) : null };
    it.kindLabel = (KINDS.filter(function (k) { return k[0] === it.kind; })[0] || [0, ''])[1];
    it.row = el('<div class="issue-row"><span class="iss-num"></span><div class="iss-main">' +
      '<div class="iss-line"><select class="iss-kind" aria-label="Désordre">' + opts(KINDS, it.kind) + '</select>' +
      '<select class="iss-sev" aria-label="Gravité">' + opts(SEV, it.severity) + '</select>' +
      '<select class="iss-mode" aria-label="Type de localisation"><option value="point">Point</option><option value="sector">Secteur</option></select></div>' +
      '<div class="iss-line"><div class="input-group iss-pk"><input class="iss-pks" type="number" step="0.001" min="0" placeholder="PK" aria-label="PK début"><span class="suffix">km</span></div>' +
      '<div class="input-group iss-pk iss-pke"><input class="iss-pkeinp" type="number" step="0.001" min="0" placeholder="PK fin" aria-label="PK fin"><span class="suffix">km</span></div>' +
      '<button type="button" class="btn ghost iss-place" title="Placer sur la carte">📍 Placer</button></div>' +
      '<input class="iss-text" type="text" maxlength="300" placeholder="Description : ex. affaissement de la chaussée sur 40 m" aria-label="Description">' +
      '<div class="hint iss-where"></div></div>' +
      '<button type="button" class="btn ghost danger-text iss-del" title="Supprimer" aria-label="Supprimer">✕</button></div>');
    var r = it.row;
    r.querySelector('.iss-mode').value = it.mode;
    r.querySelector('.iss-pks').value = fmt(it.pk_start);
    r.querySelector('.iss-pkeinp').value = fmt(it.pk_end);
    r.querySelector('.iss-text').value = it.text;
    r.querySelector('.iss-kind').addEventListener('change', function (e) {
      it.kind = e.target.value; it.kindLabel = e.target.options[e.target.selectedIndex].text; draw(); save();
    });
    r.querySelector('.iss-sev').addEventListener('change', function (e) { it.severity = e.target.value; refreshRow(it); draw(); save(); });
    r.querySelector('.iss-mode').addEventListener('change', function (e) {
      it.mode = e.target.value; if (it.mode === 'point') { it.b = null; it.pk_end = null; r.querySelector('.iss-pkeinp').value = ''; }
      refreshRow(it); draw(); save();
    });
    r.querySelector('.iss-text').addEventListener('input', function (e) { it.text = e.target.value; draw(); save(); });
    // PK saisis à la main : le point se place tout seul sur le tracé
    r.querySelector('.iss-pks').addEventListener('input', function (e) {
      it.pk_start = num(e.target.value); it.a = RP.line && it.pk_start != null ? RP.line.at(it.pk_start) : null; refreshRow(it); draw(); save();
    });
    r.querySelector('.iss-pkeinp').addEventListener('input', function (e) {
      it.pk_end = num(e.target.value); it.b = RP.line && it.pk_end != null ? RP.line.at(it.pk_end) : null; refreshRow(it); draw(); save();
    });
    r.querySelector('.iss-place').addEventListener('click', function () { arm(it); });
    r.querySelector('.iss-del').addEventListener('click', function () {
      issues.splice(issues.indexOf(it), 1); r.remove(); if (armed && armed.issue === it) disarm(); renumber(); draw(); save();
    });
    issues.push(it); box.appendChild(r); refreshRow(it);
    if (focusText) r.querySelector('.iss-text').focus({ preventScroll: true });
    return it;
  }

  // ---------- placement sur la carte ----------
  function arm(it) {
    if (!RP.line) { status.textContent = 'Cette route n’a pas de tracé : saisissez les PK à la main.'; return; }
    armed = { issue: it, step: 'a' };
    issues.forEach(function (x) { x.row.classList.toggle('armed', x === it); });
    map.getContainer().classList.add('placing');
    status.textContent = it.mode === 'sector' ? 'Cliquez sur la carte : DÉBUT du secteur.' : 'Cliquez sur la carte : emplacement du point.';
  }
  function disarm() {
    armed = null; map.getContainer().classList.remove('placing');
    issues.forEach(function (x) { x.row.classList.remove('armed'); });
    status.textContent = 'Cliquez sur « Placer » d’une ligne, puis sur la carte.';
  }
  map.on('click', function (ev) {
    if (!armed || !RP.line) return;
    var it = armed.issue, p = RP.line.project(map, ev.latlng);
    if (!p) return;
    var snapped = p.dist < 400 ? p.latlng : ev.latlng, km = Math.round(p.km * 1000) / 1000;
    if (armed.step === 'a') {
      it.a = snapped; it.pk_start = km; it.row.querySelector('.iss-pks').value = fmt(km);
      if (it.mode === 'sector') { it.b = null; it.pk_end = null; it.row.querySelector('.iss-pkeinp').value = ''; armed.step = 'b'; status.textContent = 'Cliquez maintenant sur la FIN du secteur.'; }
      else { disarm(); status.textContent = 'Point placé · PK ≈ ' + fmt(km) + ' km' + (p.dist > 150 ? ' (⚠ à ' + Math.round(p.dist) + ' m de la route)' : ''); }
    } else {
      it.b = snapped; it.pk_end = km;
      if (it.pk_end < it.pk_start) { var t = it.a; it.a = it.b; it.b = t; var k = it.pk_start; it.pk_start = it.pk_end; it.pk_end = k; }
      it.row.querySelector('.iss-pks').value = fmt(it.pk_start); it.row.querySelector('.iss-pkeinp').value = fmt(it.pk_end);
      disarm(); status.textContent = 'Secteur placé : PK ' + fmt(it.pk_start) + ' → ' + fmt(it.pk_end) + ' km (' + Math.round((it.pk_end - it.pk_start) * 1000) + ' m)';
    }
    refreshRow(it); draw(); save();
  });

  // ---------- changement de route : les points ne sont plus valables ----------
  document.addEventListener('change', function (e) {
    if (e.target !== sel) return;
    if (issues.length && !confirm('Changer de route efface les points et secteurs à problème saisis. Continuer ?')) {
      e.stopImmediatePropagation(); sel.value = prevRoute; return;
    }
    prevRoute = sel.value; issues.slice().forEach(function (x) { x.row.remove(); }); issues = []; disarm(); draw(); save();
  }, true);
  document.addEventListener('rp:route', function () {   // tracé (re)calculé : repositionne les secteurs
    issues.forEach(function (it) {
      if (RP.line && it.pk_start != null) it.a = it.a || RP.line.at(it.pk_start);
      if (RP.line && it.pk_end != null && it.mode === 'sector') it.b = it.b || RP.line.at(it.pk_end);
      refreshRow(it);
    });
    draw();
  });

  addBtn.addEventListener('click', function () { arm(addIssue({}, true)); });

  // ---------- initialisation : valeurs enregistrées ----------
  try { (JSON.parse(hidden.value || '[]') || []).forEach(function (it) { addIssue(it, false); }); } catch (_) {}
  renumber(); draw(); save();
  status.textContent = 'Cliquez sur « Placer » d’une ligne, puis sur la carte.';
})();
