(function () {
  function iso(d) {
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }
  document.querySelectorAll('.date-field').forEach(function (box) {
    var input = box.querySelector('input[type=date]');
    box.querySelector('.date-btn').addEventListener('click', function () {
      if (input.showPicker) { try { input.showPicker(); return; } catch (_) {} }
      input.focus();
    });
    box.querySelectorAll('[data-add]').forEach(function (b) {
      b.addEventListener('click', function () {
        var d = new Date(); d.setDate(d.getDate() + parseInt(b.dataset.add, 10));
        input.value = iso(d); input.dispatchEvent(new Event('change', { bubbles: true }));
      });
    });
    box.querySelectorAll('[data-clear]').forEach(function (b) {
      b.addEventListener('click', function () { input.value = ''; });
    });
  });
})();
