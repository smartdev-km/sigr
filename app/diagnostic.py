import json
from datetime import date, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import BooleanField, DateField, SelectField, SelectMultipleField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError
from wtforms.widgets import CheckboxInput, HiddenInput, ListWidget

from . import db
from .models import (CONDITIONS, DEFECTS, ISLAND_BOUNDS, ISSUE_SEVERITY, RECOMMENDATIONS, SURFACES, Diagnostic,
                     DiagnosticIssue, Route)
from .routes import admin_required, route_geo

bp = Blueprint("diagnostic", __name__, url_prefix="/diagnostic")
PER_PAGE = 10
STALE_DAYS = 365  # au-delà, une route est « à réinspecter »


class DiagnosticForm(FlaskForm):
    route_id = SelectField("Route", coerce=int, validators=[DataRequired()])
    inspected_on = DateField("Date d'inspection", validators=[DataRequired(message="Date requise.")])
    inspector = StringField("Inspecteur", validators=[Optional(), Length(max=120)])
    condition = SelectField("État constaté", choices=list(CONDITIONS.items()), validators=[DataRequired()])
    surface = SelectField("Type de revêtement", choices=[("", "— Non précisé —")] + list(SURFACES.items()),
                          validators=[Optional()])
    defects = SelectMultipleField("Désordres observés", choices=list(DEFECTS.items()),
                                  widget=ListWidget(prefix_label=False), option_widget=CheckboxInput())
    recommendation = SelectField("Action recommandée", choices=list(RECOMMENDATIONS.items()))
    notes = TextAreaField("Observations", validators=[Optional(), Length(max=3000)])
    issues = StringField(widget=HiddenInput(), validators=[Optional(), Length(max=60000)])
    apply_condition = BooleanField("Mettre à jour l'état de la route avec ce diagnostic", default=True)

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.route_id.choices = [(r.id, f"{r.code} · {r.name}") for r in Route.query.order_by(Route.code)]

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators)
        # Optional() court-circuite « validate_<champ> » quand le champ est vide : contrôle ici
        self._parsed_issues = []
        try:
            route = db.session.get(Route, self.route_id.data) if self.route_id.data else None
            self._parsed_issues = parse_issues(self.issues.data, route)
        except ValueError as e:
            self.issues.errors = list(self.issues.errors) + [str(e)]
            ok = False
        return ok

    def validate_inspected_on(self, field):
        if field.data and field.data > date.today():
            raise ValidationError("La date d'inspection ne peut pas être dans le futur.")


MAX_ISSUES = 40


def _issue_lists():
    """Listes ordonnées (clé, libellé) pour les menus du formulaire (tojson trie les dictionnaires)."""
    return {"issue_kinds": [[k, v] for k, v in DEFECTS.items()],
            "issue_severity": [[k, v] for k, v in ISSUE_SEVERITY.items()]}


def _num(v, lo=None, hi=None):
    if v in (None, ""):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ValueError
    if x != x or (lo is not None and x < lo) or (hi is not None and x > hi):
        raise ValueError
    return x


def parse_issues(raw, route):
    """Valide la liste JSON des points / secteurs à problème. Lève ValueError(message) si invalide."""
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        assert isinstance(data, list)
    except (ValueError, AssertionError):
        raise ValueError("Liste des points à problème invalide.")
    if len(data) > MAX_ISSUES:
        raise ValueError(f"{MAX_ISSUES} points ou secteurs maximum.")
    s_, w_, n_, e_ = ISLAND_BOUNDS.get(route.island, (-90, -180, 90, 180)) if route else (-90, -180, 90, 180)
    out = []
    for i, it in enumerate(data, 1):
        try:
            kind, sev = it.get("kind"), it.get("severity")
            if kind not in DEFECTS or sev not in ISSUE_SEVERITY:
                raise ValueError
            pk1, pk2 = _num(it.get("pk_start"), 0, 5000), _num(it.get("pk_end"), 0, 5000)
            lat1, lng1 = _num(it.get("start_lat"), -90, 90), _num(it.get("start_lng"), -180, 180)
            lat2, lng2 = _num(it.get("end_lat"), -90, 90), _num(it.get("end_lng"), -180, 180)
        except (ValueError, AttributeError, TypeError):
            raise ValueError(f"Point à problème n° {i} : données invalides.")
        for la, ln in ((lat1, lng1), (lat2, lng2)):
            if (la is None) != (ln is None):
                raise ValueError(f"Point à problème n° {i} : position incomplète.")
            if la is not None and not (s_ <= la <= n_ and w_ <= ln <= e_):
                raise ValueError(f"Point à problème n° {i} : la position doit être sur l'île de {route.island}.")
        text = str(it.get("text") or "").strip()[:300]
        if pk1 is None and lat1 is None and not text:
            raise ValueError(f"Point à problème n° {i} : indiquez un PK, une position sur la carte ou une description.")
        if pk1 is not None and pk2 is not None and pk2 < pk1:
            pk1, pk2 = pk2, pk1
            lat1, lng1, lat2, lng2 = lat2, lng2, lat1, lng1
        if pk2 is not None and pk1 is None:
            pk1, pk2 = pk2, None
        out.append(DiagnosticIssue(kind=kind, severity=sev, text=text or None, pk_start=pk1, pk_end=pk2,
                                   start_lat=lat1, start_lng=lng1, end_lat=lat2, end_lng=lng2))
    return out


def _apply(form, d):
    d.route_id = form.route_id.data
    d.inspected_on = form.inspected_on.data
    d.inspector = (form.inspector.data or "").strip() or None
    d.condition = form.condition.data
    d.surface = form.surface.data or None
    d.defects = json.dumps([x for x in form.defects.data if x in DEFECTS])
    d.recommendation = form.recommendation.data
    d.notes = (form.notes.data or "").strip() or None
    d.issues = form._parsed_issues          # remplace la liste (les anciens points sont supprimés)
    db.session.flush()
    # l'état de la route suit le diagnostic le plus récent
    if form.apply_condition.data:
        latest = (Diagnostic.query.filter_by(route_id=d.route_id)
                  .order_by(Diagnostic.inspected_on.desc(), Diagnostic.id.desc()).first())
        if latest and latest.id == d.id:
            db.session.get(Route, d.route_id).condition = d.condition


def _overview():
    today = date.today()
    last = dict(db.session.query(Diagnostic.route_id, func.max(Diagnostic.inspected_on)).group_by(Diagnostic.route_id))
    routes = Route.query.order_by(Route.code).all()
    never = [r for r in routes if r.id not in last]
    stale = [r for r in routes if r.id in last and (today - last[r.id]).days > STALE_DAYS]
    # état du dernier diagnostic de chaque route
    latest_cond = {}
    for d in Diagnostic.query.order_by(Diagnostic.inspected_on, Diagnostic.id):
        latest_cond[d.route_id] = d
    critical = [d for d in latest_cond.values() if d.condition == "critique"]
    to_inspect = sorted(never + stale, key=lambda r: (last.get(r.id) or date.min, r.code))
    return {"total_routes": len(routes), "inspected": len(last), "never": len(never), "stale": len(stale),
            "critical": len(critical), "to_inspect": to_inspect[:8], "last": last, "today": today}


@bp.route("/")
@login_required
def index():
    cond = request.args.get("condition", "")
    reco = request.args.get("reco", "")
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)

    query = Diagnostic.query.join(Route)
    if cond in CONDITIONS:
        query = query.filter(Diagnostic.condition == cond)
    if reco in RECOMMENDATIONS:
        query = query.filter(Diagnostic.recommendation == reco)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Route.code.ilike(like), Route.name.ilike(like), Diagnostic.inspector.ilike(like)))
    pagination = query.order_by(Diagnostic.inspected_on.desc(), Diagnostic.id.desc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False)

    by_cond = {k: 0 for k in CONDITIONS}
    for k, n in db.session.query(Diagnostic.condition, func.count()).group_by(Diagnostic.condition):
        by_cond[k] = n
    args = {k: v for k, v in {"q": q, "condition": cond, "reco": reco}.items() if v}
    return render_template("diagnostic_list.html", pagination=pagination, args=args, q=q, cond=cond, reco=reco,
                           by_cond=by_cond, ov=_overview(), conditions=CONDITIONS, recos=RECOMMENDATIONS,
                           defects=DEFECTS, stale_days=STALE_DAYS)


@bp.route("/nouveau", methods=["GET", "POST"])
@login_required
def create():
    form = DiagnosticForm()
    if request.method == "GET":
        rid = request.args.get("route_id", type=int)
        r = db.session.get(Route, rid) if rid else None
        if r:
            form.route_id.data = r.id
            form.condition.data = r.condition
        form.inspected_on.data = date.today()
        form.inspector.data = current_user.full_name
    if form.validate_on_submit():
        d = Diagnostic(created_by_id=current_user.id)
        db.session.add(d)  # avant _apply : il a besoin de l'id du diagnostic
        _apply(form, d)
        db.session.commit()
        flash("Diagnostic enregistré.", "success")
        return redirect(url_for("diagnostic.index"))
    return render_template("diagnostic_form.html", form=form, item=None, route_geo=route_geo(with_geom=True), **_issue_lists())


@bp.route("/<int:item_id>", methods=["GET", "POST"])
@login_required
def edit(item_id):
    d = db.get_or_404(Diagnostic, item_id)
    form = DiagnosticForm(obj=d)
    if request.method == "GET":
        form.issues.data = json.dumps([i.as_dict() for i in d.issues])
        form.defects.data = d.defect_list
        form.surface.data = d.surface or ""
        form.apply_condition.data = False
    if form.validate_on_submit():
        _apply(form, d)
        db.session.commit()
        flash("Diagnostic mis à jour.", "success")
        return redirect(url_for("diagnostic.index"))
    return render_template("diagnostic_form.html", form=form, item=d, route_geo=route_geo(with_geom=True), **_issue_lists())


@bp.route("/<int:item_id>/supprimer", methods=["POST"])
@admin_required
def delete(item_id):
    d = db.get_or_404(Diagnostic, item_id)
    db.session.delete(d)
    db.session.commit()
    flash("Diagnostic supprimé.", "info")
    return redirect(url_for("diagnostic.index"))
