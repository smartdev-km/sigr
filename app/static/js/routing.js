/* Calcul d'itinéraire partagé (formulaire, détail, aperçu entretien).
 * Les données OpenStreetMap des Comores sont incomplètes pour la voiture : certaines routes
 * existantes ne sont pas « roulables » dans la base, ce qui impose de grands détours.
 * On interroge donc deux profils (voiture et vélo, qui accepte plus de pistes/routes) et on
 * retient le trajet le plus court. */
window.SIGR = window.SIGR || {};
(function () {
  var URLS = {
    car: 'https://router.project-osrm.org/route/v1/driving/',
    bike: 'https://routing.openstreetmap.de/routed-bike/route/v1/driving/'
  };
  function one(profile, pts) {
    var coords = pts.map(function (p) { return p.lng + ',' + p.lat; }).join(';');
    return fetch(URLS[profile] + coords + '?overview=full&geometries=geojson&continue_straight=true')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.code !== 'Ok' || !d.routes || !d.routes.length) return null;
        return { km: d.routes[0].distance / 1000, geometry: d.routes[0].geometry, profile: profile };
      }).catch(function () { return null; });
  }
  // Renvoie { best, car, bike } (best = null si aucun service ne répond)
  SIGR.route = function (pts) {
    return Promise.all([one('car', pts), one('bike', pts)]).then(function (res) {
      var car = res[0], bike = res[1], best = null;
      [car, bike].forEach(function (r) { if (r && (!best || r.km < best.km)) best = r; });
      return { best: best, car: car, bike: bike };
    });
  };
  // Réduit un tracé GeoJSON (≤ 500 points, 5 décimales) pour le stocker
  SIGR.compact = function (geom) {
    var c = (geom && geom.coordinates) || [], step = Math.max(1, Math.ceil(c.length / 500)), out = [];
    for (var i = 0; i < c.length; i += step) out.push([+c[i][0].toFixed(5), +c[i][1].toFixed(5)]);
    var last = c[c.length - 1];
    if (last && (out[out.length - 1][0] !== +last[0].toFixed(5) || out[out.length - 1][1] !== +last[1].toFixed(5))) out.push([+last[0].toFixed(5), +last[1].toFixed(5)]);
    return JSON.stringify({ type: 'LineString', coordinates: out });
  };
  // Texte d'explication quand les deux profils divergent nettement
  SIGR.describe = function (r) {
    if (!r.best) return '';
    var t = 'Distance par la route (estimation) : ' + r.best.km.toFixed(1) + ' km';
    if (r.car && r.bike && Math.abs(r.car.km - r.bike.km) / Math.max(r.car.km, r.bike.km) > 0.1) {
      t += ' — voiture ' + r.car.km.toFixed(1) + ' km · vélo ' + r.bike.km.toFixed(1) + ' km';
    }
    return t;
  };
})();
