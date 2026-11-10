import json
from datetime import date, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import BooleanField, DateField, SelectField, SelectMultipleField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, Optional, ValidationError
from wtforms.widgets import CheckboxInput, ListWidget

from . import db
from .models import CONDITIONS, DEFECTS, RECOMMENDATIONS, SURFACES, Diagnostic, Route
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
    apply_condition = BooleanField("Mettre à jour l'état de la route avec ce diagnostic", default=True)

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.route_id.choices = [(r.id, f"{r.code} · {r.name}") for r in Route.query.order_by(Route.code)]

    def validate_inspected_on(self, field):
        if field.data and field.data > date.today():
            raise ValidationError("La date d'inspection ne peut pas être dans le futur.")


def _apply(form, d):
    d.route_id = form.route_id.data
    d.inspected_on = form.inspected_on.data
    d.inspector = (form.inspector.data or "").strip() or None
    d.condition = form.condition.data
    d.surface = form.surface.data or None
    d.defects = json.dumps([x for x in form.defects.data if x in DEFECTS])
    d.recommendation = form.recommendation.data
    d.notes = (form.notes.data or "").strip() or None
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
    return render_template("diagnostic_form.html", form=form, item=None, route_geo=route_geo())


@bp.route("/<int:item_id>", methods=["GET", "POST"])
@login_required
def edit(item_id):
    d = db.get_or_404(Diagnostic, item_id)
    form = DiagnosticForm(obj=d)
    if request.method == "GET":
        form.defects.data = d.defect_list
        form.surface.data = d.surface or ""
        form.apply_condition.data = False
    if form.validate_on_submit():
        _apply(form, d)
        db.session.commit()
        flash("Diagnostic mis à jour.", "success")
        return redirect(url_for("diagnostic.index"))
    return render_template("diagnostic_form.html", form=form, item=d, route_geo=route_geo())


@bp.route("/<int:item_id>/supprimer", methods=["POST"])
@admin_required
def delete(item_id):
    d = db.get_or_404(Diagnostic, item_id)
    db.session.delete(d)
    db.session.commit()
    flash("Diagnostic supprimé.", "info")
    return redirect(url_for("diagnostic.index"))
