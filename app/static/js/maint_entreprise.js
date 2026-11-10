/* Formulaire d'entretien : la liste des entreprises est limitée à l'île de la route choisie. */
(function () {
  var sel = document.querySelector('[name=entreprise_id]'), route = document.querySelector('[name=route_id]'),
      all = document.getElementById('ent-all'), note = document.getElementById('ent-filter-note'), G = window.ROUTE_GEO || {};
  if (!sel || !all) return;
  // liste complète, lue une fois : valeur, libellé, île
  var ALL = Array.prototype.map.call(sel.options, function (o) {
    return { value: o.value, text: o.text, island: o.getAttribute('data-island') || '' };
  });
  function island() { var r = G[route.value]; return r ? r.island : ''; }
  function render() {
    var isl = island(), current = sel.value, show = all.checked || !isl;
    var kept = ALL.filter(function (o) {
      return o.value === '0' || o.value === '-1' || o.value === current || show || !o.island || o.island === isl;
    });
    sel.innerHTML = '';
    kept.forEach(function (o) {
      var op = document.createElement('option'); op.value = o.value; op.textContent = o.text; op.setAttribute('data-island', o.island);
      if (o.island && isl && o.island !== isl) op.textContent += ' · ' + o.island;     // entreprise d'une autre île (affichée à la demande)
      sel.appendChild(op);
    });
    sel.value = current;
    if (sel.value !== current) sel.value = '0';
    var n = kept.filter(function (o) { return o.value !== '0' && o.value !== '-1'; }).length;
    note.textContent = isl && !all.checked
      ? 'Filtré sur ' + isl + ' : ' + n + ' entreprise' + (n > 1 ? 's' : '') + ' (les entreprises sans île y sont incluses).'
      : (isl ? 'Toutes les îles : ' + n + ' entreprise' + (n > 1 ? 's' : '') + '.' : '');
  }
  route.addEventListener('change', function () { sel.value = '0'; render(); });   // autre route : on repart d'une liste neuve
  all.addEventListener('change', render);
  render();
})();
