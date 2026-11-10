import json
from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy import or_
from wtforms import DecimalField, FloatField, SelectField, StringField, TextAreaField
from wtforms.widgets import HiddenInput
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from . import db
from .models import CONDITIONS, ISLAND_BOUNDS, ISLANDS, ROUTE_TYPES, Route

bp = Blueprint("routes", __name__, url_prefix="/routes")

PER_PAGE = 10
MAX_WAYPOINTS = 20
SORTS = {
    "code": Route.code, "name": Route.name, "type": Route.type,
    "island": Route.island, "length": Route.length_km, "condition": Route.condition,
}


def admin_required(view):
    """Suppression : réservée aux administrateurs et aux comptes disposant du droit de suppression."""
    @wraps(view)
    @login_required
    def wrapped(*a, **kw):
        if not current_user.may_delete:
            abort(403)
        return view(*a, **kw)
    return wrapped


class RouteForm(FlaskForm):
    type = SelectField("Type", choices=list(ROUTE_TYPES.items()), validators=[DataRequired()])
    code = StringField("Code", validators=[DataRequired(), Length(max=20)],
                       render_kw={"placeholder": "ex. RN1, RR12, SR3"})
    name = StringField("Nom / Tronçon", validators=[DataRequired(), Length(max=160)])
    island = SelectField("Île", choices=[(i, i) for i in ISLANDS], validators=[DataRequired()])
    length_km = DecimalField("Longueur (km)", places=2, validators=[DataRequired(), NumberRange(min=0.01, max=2000)])
    condition = SelectField("État", choices=list(CONDITIONS.items()), validators=[DataRequired()])
    start_point = StringField("Point de départ", validators=[Optional(), Length(max=120)])
    end_point = StringField("Point d'arrivée", validators=[Optional(), Length(max=120)])
    start_lat = FloatField(widget=HiddenInput(), validators=[Optional()])
    start_lng = FloatField(widget=HiddenInput(), validators=[Optional()])
    end_lat = FloatField(widget=HiddenInput(), validators=[Optional()])
    end_lng = FloatField(widget=HiddenInput(), validators=[Optional()])
    waypoints = StringField(widget=HiddenInput(), validators=[Optional(), Length(max=8000)])
    geometry = StringField(widget=HiddenInput(), validators=[Optional(), Length(max=80000)])
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=2000)])

    def __init__(self, *args, route=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._route = route

    def validate_code(self, field):
        field.data = field.data.strip().upper().replace(" ", "")
        if not field.data.startswith(self.type.data or ""):
            raise ValidationError(f"Le code doit commencer par {self.type.data} (ex. {self.type.data}1).")
        q = Route.query.filter(Route.code == field.data)
        if self._route is not None:
            q = q.filter(Route.id != self._route.id)
        if q.first():
            raise ValidationError("Ce code existe déjà.")


    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators)
        try:
            self._check_points()
        except ValidationError as e:
            self.end_lng.errors = list(self.end_lng.errors) + [str(e)]
            ok = False
        return ok

    def _check_points(self):
        pts = [self.start_lat.data, self.start_lng.data, self.end_lat.data, self.end_lng.data]
        vias = self._parse_waypoints()
        if all(p is None for p in pts) and not vias:
            return
        if any(p is None for p in pts):
            raise ValidationError("Placez le point de départ ET le point d'arrivée sur la carte.")
        s, w, n, e = ISLAND_BOUNDS.get(self.island.data, (-90, -180, 90, 180))
        coords = [(pts[0], pts[1]), (pts[2], pts[3])] + [(v["lat"], v["lng"]) for v in vias]
        for lat, lng in coords:
            if not (s <= lat <= n and w <= lng <= e):
                raise ValidationError(f"Les points doivent se trouver sur l'île de {self.island.data}.")

    def _parse_waypoints(self):
        """Liste nettoyée des points intermédiaires (ignore les lignes sans position)."""
        raw = (self.waypoints.data or "").strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
            assert isinstance(data, list)
        except (ValueError, AssertionError):
            raise ValidationError("Points intermédiaires invalides.")
        if len(data) > MAX_WAYPOINTS:
            raise ValidationError(f"{MAX_WAYPOINTS} points intermédiaires maximum.")
        out = []
        for v in data:
            try:
                lat, lng = float(v["lat"]), float(v["lng"])
            except (KeyError, TypeError, ValueError):
                raise ValidationError("Points intermédiaires invalides.")
            out.append({"lat": round(lat, 6), "lng": round(lng, 6), "name": str(v.get("name") or "").strip()[:120]})
        return out


def route_has_points(form):
    return None not in (form.start_lat.data, form.start_lng.data, form.end_lat.data, form.end_lng.data)


FIELDS = ("type", "code", "name", "island", "length_km", "condition", "start_point", "end_point",
          "start_lat", "start_lng", "end_lat", "end_lng", "notes")  # + waypoints (traité à part)


def clean_geometry(raw):
    """Valide un tracé GeoJSON (LineString) reçu du navigateur ; renvoie le JSON compact ou None."""
    try:
        g = json.loads(raw or "")
        coords = g["coordinates"]
        if g.get("type") != "LineString" or not (2 <= len(coords) <= 1500):
            return None
        out = [[round(float(x), 5), round(float(y), 5)] for x, y in coords]
        if any(not (-180 <= x <= 180 and -90 <= y <= 90) for x, y in out):
            return None
        return json.dumps({"type": "LineString", "coordinates": out}, separators=(",", ":"))
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


def _apply(form, route):
    route.geometry = clean_geometry(form.geometry.data) if route_has_points(form) else None
    vias = form._parse_waypoints()
    route.waypoints = json.dumps(vias, ensure_ascii=False) if vias else None
    for f in FIELDS:
        v = getattr(form, f).data
        if isinstance(v, str):
            v = v.strip() or None
        if f == "length_km":
            v = float(v)
        setattr(route, f, v)


def route_geo(with_geom=False):
    """Données des routes pour l'aperçu cartographique du formulaire."""
    out = {}
    for r in Route.query.all():
        out[r.id] = {
            "code": r.code, "name": r.name, "island": r.island, "km": round(r.length_km, 1),
            "type": ROUTE_TYPES[r.type], "condition": CONDITIONS[r.condition], "cond_key": r.condition,
            "start": r.start_point, "end": r.end_point,
            "vias": [[v["lat"], v["lng"]] for v in r.waypoint_list],
            "geom": ([[c[1], c[0]] for c in json.loads(r.geometry)["coordinates"]] if (with_geom and r.geometry) else None),
            "a": [r.start_lat, r.start_lng] if r.start_lat is not None and r.end_lat is not None else None,
            "b": [r.end_lat, r.end_lng] if r.start_lat is not None and r.end_lat is not None else None,
        }
    return out


@bp.route("/")
@login_required
def index():
    q = request.args.get("q", "").strip()
    rtype = request.args.get("type", "")
    island = request.args.get("island", "")
    cond = request.args.get("condition", "")
    sort = request.args.get("sort", "code")
    order = request.args.get("order", "asc")
    page = request.args.get("page", 1, type=int)

    query = Route.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Route.code.ilike(like), Route.name.ilike(like),
                                 Route.start_point.ilike(like), Route.end_point.ilike(like)))
    if rtype in ROUTE_TYPES:
        query = query.filter(Route.type == rtype)
    if island in ISLANDS:
        query = query.filter(Route.island == island)
    if cond in CONDITIONS:
        query = query.filter(Route.condition == cond)

    col = SORTS.get(sort, Route.code)
    query = query.order_by(col.desc() if order == "desc" else col.asc(), Route.id)
    pagination = query.paginate(page=page, per_page=PER_PAGE, error_out=False)

    args = {k: v for k, v in {"q": q, "type": rtype, "island": island, "condition": cond,
                               "sort": sort, "order": order}.items() if v}
    return render_template("routes_list.html", pagination=pagination, args=args, q=q, rtype=rtype,
                           island=island, cond=cond, sort=sort, order=order,
                           route_types=ROUTE_TYPES, islands=ISLANDS, conditions=CONDITIONS)


@bp.route("/nouvelle", methods=["GET", "POST"])
@login_required
def create():
    form = RouteForm()
    if form.validate_on_submit():
        route = Route()
        _apply(form, route)
        db.session.add(route)
        db.session.commit()
        flash(f"Route {route.code} ajoutée.", "success")
        return redirect(url_for("routes.index"))
    return render_template("route_form.html", form=form, route=None, bounds=ISLAND_BOUNDS)


@bp.route("/<int:route_id>/detail")
@login_required
def detail(route_id):
    route = db.get_or_404(Route, route_id)
    from .models import DEFECTS, ISSUE_SEVERITY
    last_diag = route.diagnostics[0] if route.diagnostics else None   # le plus récent (tri par date décroissante)
    show_issues = bool(last_diag and last_diag.issues and current_user.can("diagnostic"))
    issues_js = [{**i.as_dict(), "label": DEFECTS.get(i.kind, i.kind), "where": i.where}
                 for i in (last_diag.issues if show_issues else [])]
    geom_pts = [[c[1], c[0]] for c in json.loads(route.geometry)["coordinates"]] if route.geometry else []
    # interventions (non annulées) dont les PK recouvrent un point / secteur du diagnostic
    cover = {}
    if show_issues:
        for it in last_diag.issues:
            lo, hi = it.pk_start, (it.pk_end if it.pk_end is not None else it.pk_start)
            for m in route.maintenances:
                if m.status == "annule" or m.pk_start is None or lo is None:
                    continue
                m_hi = m.pk_end if m.pk_end is not None else m.pk_start
                if m_hi >= lo - 0.05 and m.pk_start <= hi + 0.05:
                    cover.setdefault(it.id, []).append(m)
    return render_template("route_detail.html", route=route, route_types=ROUTE_TYPES, conditions=CONDITIONS,
                           cover=cover, last_diag=last_diag if show_issues else None, issues_js=issues_js, geom_pts=geom_pts,
                           defects=DEFECTS, severities=ISSUE_SEVERITY,
                           sev_colors={"mineur": "var(--moyen)", "important": "var(--mauvais)", "critique": "var(--critique)"})


@bp.route("/<int:route_id>", methods=["GET", "POST"])
@login_required
def edit(route_id):
    route = db.get_or_404(Route, route_id)
    form = RouteForm(obj=route, route=route)
    if form.validate_on_submit():
        _apply(form, route)
        db.session.commit()
        flash(f"Route {route.code} mise à jour.", "success")
        return redirect(url_for("routes.index"))
    return render_template("route_form.html", form=form, route=route, bounds=ISLAND_BOUNDS)


@bp.route("/<int:route_id>/supprimer", methods=["POST"])
@admin_required
def delete(route_id):
    route = db.get_or_404(Route, route_id)
    db.session.delete(route)
    db.session.commit()
    flash(f"Route {route.code} supprimée.", "info")
    return redirect(url_for("routes.index"))
