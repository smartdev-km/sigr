/* Formulaire d'entretien : affiche les points / secteurs du dernier diagnostic de la route et préremplit l'intervention. */
(function () {
  var DATA = window.ISSUES_BY_ROUTE || {}, RP = window.RP;
  if (!RP) return;
  var map = RP.map, box = document.getElementById('diag-points'), list = document.getElementById('dp-list'),
      meta = document.getElementById('dp-meta'), sel = document.querySelector('[name=route_id]'),
      kindSel = document.querySelector('[name=kind]'), titleIn = document.querySelector('[name=title]'),
      descIn = document.querySelector('[name=description]'), pks = document.querySelector('[name=pk_start]'),
      pke = document.querySelector('[name=pk_end]');
  var COLORS = { mineur: '#e0b020', important: '#e07a20', critique: '#c93a3a' };
  // désordre constaté → type d'intervention le plus adapté
  var KIND = { nids_de_poule: 'nids_de_poule', fissures: 'roulement', affaissement: 'reprofilage', erosion: 'rechargement',
               drainage: 'caniveaux', accotements: 'accotements', signalisation: 'signalisation', vegetation: 'accotements',
               eboulement: 'curatif', ouvrage: 'assainissement' };
  var layer = L.layerGroup().addTo(map), shapes = [];

  function numIcon(n, color) {
    return L.divIcon({ className: '', iconSize: [26, 26], iconAnchor: [13, 13],
      html: '<div style="width:26px;height:26px;border-radius:50%;background:' + color + ';color:#fff;font:700 12px/20px sans-serif;text-align:center;border:3px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,.5)">' + n + '</div>' });
  }
  function fmt(x) { return x == null ? '' : String(Math.round(x * 1000) / 1000); }
  function flash(el) { if (!el) return; el.classList.remove('flash-field'); void el.offsetWidth; el.classList.add('flash-field'); }

  function geometry(it) {                      // points de la carte correspondant au point / secteur
    var line = RP.line, a = it.start_lat != null ? L.latLng(it.start_lat, it.start_lng) : (line && it.pk_start != null ? line.at(it.pk_start) : null);
    if (!a) return null;
    if (it.pk_end != null && it.pk_end > it.pk_start) {
      var seg = line ? line.slice(it.pk_start, it.pk_end) : [a, L.latLng(it.end_lat, it.end_lng)];
      return { seg: seg, mid: seg[Math.floor(seg.length / 2)] };
    }
    return { seg: null, mid: a };
  }

  function use(it) {                           // préremplit l'intervention
    var k = KIND[it.kind];
    if (k && kindSel.querySelector('option[value="' + k + '"]')) kindSel.value = k;
    var where = it.where || '';
    if (!titleIn.value.trim()) titleIn.value = 'Traitement : ' + it.label.toLowerCase() + (where && where !== '—' ? ' (' + where.replace(/ \(.*\)$/, '') + ')' : '');
    var line = '• ' + it.label + (where && where !== '—' ? ' — ' + where : '') + (it.text ? ' : ' + it.text : '');
    if (descIn.value.indexOf(line) < 0) descIn.value = (descIn.value.trim() ? descIn.value.trim() + '\n' : '') + line;
    // localisation : on étend les PK pour couvrir tous les points choisis
    var lo = it.pk_start, hi = it.pk_end != null ? it.pk_end : it.pk_start;
    if (lo != null) {
      var curLo = parseFloat(pks.value), curHi = parseFloat(pke.value);
      var newLo = isNaN(curLo) ? lo : Math.min(curLo, lo), newHi = Math.max(isNaN(curHi) ? (isNaN(curLo) ? hi : curLo) : curHi, hi);
      pks.value = fmt(newLo); pke.value = newHi > newLo ? fmt(newHi) : '';
      flash(pks); flash(pke);
    }
    flash(kindSel); flash(titleIn); flash(descIn);
    titleIn.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function focusOn(i) {
    list.querySelectorAll('li').forEach(function (li, j) { li.classList.toggle('on', i === j); });
    var s = shapes[i]; if (!s) return;
    if (s.seg) map.fitBounds(L.latLngBounds(s.seg).pad(0.6)); else map.setView(s.mid, Math.max(map.getZoom(), 15));
  }

  function render() {
    list.innerHTML = ''; layer.clearLayers(); shapes = [];
    var d = DATA[sel.value];
    if (!d) { box.hidden = true; return; }
    box.hidden = false;
    meta.textContent = 'du ' + d.date + (d.inspector ? ' · ' + d.inspector : '') + ' · ' + d.items.length + ' point' + (d.items.length > 1 ? 's' : '') + ' ou secteur' + (d.items.length > 1 ? 's' : '');
    d.items.forEach(function (it, i) {
      var col = COLORS[it.severity] || '#e07a20', g = geometry(it), tip = (i + 1) + '. ' + it.label + (it.text ? ' — ' + it.text : '');
      shapes.push(g);
      if (g) {
        if (g.seg) {
          L.polyline(g.seg, { color: '#fff', weight: 11, opacity: .9, interactive: false }).addTo(layer);
          L.polyline(g.seg, { color: col, weight: 7 }).bindTooltip(tip).addTo(layer).on('click', function () { focusOn(i); });
        }
        L.marker(g.mid, { icon: numIcon(i + 1, col) }).bindTooltip(tip).addTo(layer).on('click', function () { focusOn(i); });
      }
      var li = document.createElement('li');
      li.innerHTML = '<span class="iss-dot" style="background:' + col + '">' + (i + 1) + '</span>' +
        '<div class="dp-text"><strong>' + it.label + '</strong> <span class="badge" style="background:' + col + '">' + it.severity_label + '</span>' +
        '<div class="hint">' + (it.where !== '—' ? it.where : 'Localisation non précisée') + (it.text ? ' · ' + it.text.replace(/</g, '&lt;') : '') + '</div></div>' +
        '<button type="button" class="btn ghost">Planifier</button>';
      li.addEventListener('click', function (e) { if (e.target.closest('button')) use(it); else focusOn(i); });
      list.appendChild(li);
    });
  }

  document.addEventListener('rp:route', render);   // tracé (re)calculé : on repositionne les points
  render();
})();
