/* Formulaire d'entretien : la liste des chantiers est limitée à ceux de la route choisie. */
(function () {
  var sel = document.querySelector('[name=work_id]'), route = document.querySelector('[name=route_id]'), note = document.getElementById('work-note');
  if (!sel || sel.hidden || !note) return;
  var ALL = Array.prototype.map.call(sel.options, function (o) {
    return { value: o.value, text: o.text, route: o.getAttribute('data-route') || '' };
  });
  function render() {
    var r = route.value, current = sel.value;
    var kept = ALL.filter(function (o) { return o.value === '0' || o.route === r; });
    sel.innerHTML = '';
    kept.forEach(function (o) {
      var op = document.createElement('option'); op.value = o.value; op.textContent = o.text; op.setAttribute('data-route', o.route); sel.appendChild(op);
    });
    sel.value = current; if (sel.value !== current) sel.value = '0';
    var n = kept.length - 1;
    note.textContent = n > 0 ? n + ' chantier' + (n > 1 ? 's' : '') + ' sur cette route. Facultatif.' : 'Aucun chantier enregistré sur cette route.';
  }
  route.addEventListener('change', function () { sel.value = '0'; render(); });
  render();
})();
