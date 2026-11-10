/* Outils géométriques le long d'une route : PK (km depuis le début), projection d'un point, extraction d'un secteur. */
window.SIGRGeo = (function () {
  function Line(pts) {                       // pts : tableau de L.LatLng
    this.pts = pts; this.cum = [0];
    for (var i = 1; i < pts.length; i++) this.cum[i] = this.cum[i - 1] + pts[i - 1].distanceTo(pts[i]);
    this.length = this.cum[this.cum.length - 1] || 0;   // mètres
  }
  // point le plus proche de `ll` : { km, dist (m), latlng }
  Line.prototype.project = function (map, ll) {
    if (this.pts.length < 2) return null;
    var z = Math.max(map.getZoom(), 12), p = map.project(ll, z), best = Infinity, out = null;
    for (var i = 0; i < this.pts.length - 1; i++) {
      var a = map.project(this.pts[i], z), b = map.project(this.pts[i + 1], z),
          c = L.LineUtil.closestPointOnSegment(p, a, b), d = p.distanceTo(c);
      if (d < best) {
        best = d; var cl = map.unproject(c, z);
        out = { km: (this.cum[i] + this.pts[i].distanceTo(cl)) / 1000, dist: ll.distanceTo(cl), latlng: cl };
      }
    }
    return out;
  };
  // position à `km` depuis le début
  Line.prototype.at = function (km) {
    var m = Math.max(0, Math.min(km * 1000, this.length));
    for (var i = 0; i < this.pts.length - 1; i++) {
      if (m <= this.cum[i + 1] || i === this.pts.length - 2) {
        var seg = this.cum[i + 1] - this.cum[i], t = seg ? (m - this.cum[i]) / seg : 0;
        return L.latLng(this.pts[i].lat + t * (this.pts[i + 1].lat - this.pts[i].lat),
                        this.pts[i].lng + t * (this.pts[i + 1].lng - this.pts[i].lng));
      }
    }
    return this.pts[this.pts.length - 1];
  };
  // portion de la route entre deux PK (suit le tracé)
  Line.prototype.slice = function (k1, k2) {
    var a = Math.min(k1, k2) * 1000, b = Math.max(k1, k2) * 1000, out = [this.at(a / 1000)];
    for (var i = 1; i < this.pts.length - 1; i++) if (this.cum[i] > a && this.cum[i] < b) out.push(this.pts[i]);
    out.push(this.at(b / 1000));
    return out;
  };
  return { Line: Line };
})();
