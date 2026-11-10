import json

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required

from . import db
from .models import (CONDITIONS, ISLAND_BOUNDS, ISLANDS, ROUTE_TYPES, STRUCTURE_KINDS, WORK_OPEN_STATUS, Ouvrage,
                     Route)
from .routes import clean_geometry

bp = Blueprint("map", __name__, url_prefix="/carte")


def _payload():
    out = []
    for r in Route.query.order_by(Route.code):
        open_w = [w for w in r.works if w.status in WORK_OPEN_STATUS]
        open_m = [m for m in r.maintenances if m.status in ("planifie", "en_cours")]
        out.append({
            "id": r.id, "code": r.code, "name": r.name, "type": r.type, "island": r.island,
            "km": round(r.length_km or 0, 1), "cond": r.condition,
            "start": r.start_point, "end": r.end_point,
            "a": [r.start_lat, r.start_lng] if r.has_points else None,
            "b": [r.end_lat, r.end_lng] if r.has_points else None,
            "vias": [[v["lat"], v["lng"]] for v in r.waypoint_list] if r.has_points else [],
            "geom": json.loads(r.geometry) if r.geometry else None,
            "works": len(open_w), "maint": len(open_m),
        })
    return out


def _structures():
    if not current_user.can("ouvrages"):
        return []
    return [{"id": o.id, "ref": o.ref or f"#{o.id}", "kind": STRUCTURE_KINDS.get(o.kind, o.kind), "lat": o.lat,
             "lng": o.lng, "cond": o.condition, "route": o.route.code,
             "pk": round(o.pk_km, 3) if o.pk_km is not None else None}
            for o in Ouvrage.query.filter(Ouvrage.lat.isnot(None), Ouvrage.lng.isnot(None)).all()]


@bp.route("/")
@login_required
def index():
    return render_template("map.html", routes=_payload(), structures=_structures(), bounds=ISLAND_BOUNDS, islands=ISLANDS,
                           route_types=ROUTE_TYPES, conditions=CONDITIONS)


@bp.route("/geometry/<int:route_id>", methods=["POST"])
@login_required
def save_geometry(route_id):
    """Met en cache le tracé routier calculé par le navigateur (routes saisies avant la mise en cache)."""
    route = db.get_or_404(Route, route_id)
    if not route.has_points:
        abort(400)
    g = clean_geometry(json.dumps((request.get_json(silent=True) or {}).get("geometry")))
    if not g:
        abort(400)
    if not route.geometry:  # ne remplace jamais un tracé existant
        route.geometry = g
        db.session.commit()
    return jsonify(ok=True)
