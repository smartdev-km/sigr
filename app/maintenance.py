from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import DateField, IntegerField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from . import db
from .models import CONDITIONS, MAINT_KINDS, MAINT_STATUS, ROUTE_TYPES, Maintenance, Route
from .routes import admin_required, route_geo as _route_geo

bp = Blueprint("maintenance", __name__, url_prefix="/entretien")
PER_PAGE = 10


class MaintenanceForm(FlaskForm):
    route_id = SelectField("Route", coerce=int, validators=[DataRequired()])
    kind = SelectField("Type d'intervention", choices=list(MAINT_KINDS.items()))
    status = SelectField("Statut", choices=list(MAINT_STATUS.items()))
    title = StringField("Intitulé", validators=[Optional(), Length(max=160)],
                        render_kw={"placeholder": "Facultatif : par défaut, le type d'intervention"})
    planned_date = DateField("Date prévue", validators=[DataRequired(message="Date requise.")])
    done_date = DateField("Date de réalisation", validators=[Optional()])
    cost_kmf = IntegerField("Coût estimé / réel", validators=[Optional(), NumberRange(min=0, max=10**12)])
    contractor = StringField("Entreprise / Intervenant", validators=[Optional(), Length(max=160)])
    condition_after = SelectField("État de la route après travaux",
                                  choices=[("", "— Ne pas modifier —")] + list(CONDITIONS.items()),
                                  validators=[Optional()])
    description = TextAreaField("Description", validators=[Optional(), Length(max=3000)])

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.route_id.choices = [(r.id, f"{r.code} – {r.name}") for r in Route.query.order_by(Route.code)]

    def validate_done_date(self, field):
        if field.data and self.planned_date.data and field.data < self.planned_date.data:
            raise ValidationError("La réalisation ne peut pas précéder la date prévue.")


def _apply(form, m):
    m.route_id = form.route_id.data
    m.kind = form.kind.data
    m.status = form.status.data
    m.title = (form.title.data or "").strip() or MAINT_KINDS.get(m.kind, "Intervention")
    m.description = (form.description.data or "").strip() or None
    m.planned_date = form.planned_date.data
    m.done_date = form.done_date.data
    m.cost_kmf = form.cost_kmf.data
    m.contractor = (form.contractor.data or "").strip() or None
    m.condition_after = form.condition_after.data or None
    if m.status == "termine":
        m.done_date = m.done_date or date.today()
        if m.condition_after:  # met à jour l'état de la route
            db.session.get(Route, m.route_id).condition = m.condition_after
    elif m.status != "annule":
        m.done_date = None  # pas de date de réalisation tant que ce n'est pas terminé


def _kind_stats():
    """Suivi par type d'intervention : volumes par statut, retards, coûts, dernière réalisation."""
    stats = {k: {"total": 0, "by_status": {s: 0 for s in MAINT_STATUS}, "late": 0, "cost": 0,
                 "avg_cost": 0, "rate": 0, "last_done": None} for k in MAINT_KINDS}
    for kind, st, n, cost in db.session.query(
            Maintenance.kind, Maintenance.status, func.count(), func.coalesce(func.sum(Maintenance.cost_kmf), 0)
    ).group_by(Maintenance.kind, Maintenance.status):
        if kind not in stats:
            continue
        d = stats[kind]
        d["total"] += n
        d["by_status"][st] = n
        if st == "termine":
            d["cost"] = int(cost)
    for kind, n in db.session.query(Maintenance.kind, func.count()).filter(
            Maintenance.status == "planifie", Maintenance.planned_date < date.today()).group_by(Maintenance.kind):
        stats[kind]["late"] = n
    for kind, last in db.session.query(Maintenance.kind, func.max(Maintenance.done_date)).filter(
            Maintenance.status == "termine").group_by(Maintenance.kind):
        stats[kind]["last_done"] = last
    for d in stats.values():
        done = d["by_status"]["termine"]
        active = d["total"] - d["by_status"]["annule"]
        d["avg_cost"] = round(d["cost"] / done) if done else 0
        d["rate"] = round(100 * done / active) if active else 0
    return stats


@bp.route("/")
@login_required
def index():
    status = request.args.get("status", "")
    kind = request.args.get("kind", "")
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)

    query = Maintenance.query.join(Route)
    if status in MAINT_STATUS:
        query = query.filter(Maintenance.status == status)
    if kind in MAINT_KINDS:
        query = query.filter(Maintenance.kind == kind)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Route.code.ilike(like), Maintenance.title.ilike(like), Maintenance.contractor.ilike(like)))
    pagination = query.order_by(Maintenance.planned_date.desc(), Maintenance.id.desc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False)

    counts = dict(db.session.query(Maintenance.status, func.count()).group_by(Maintenance.status))
    late = Maintenance.query.filter(Maintenance.status == "planifie", Maintenance.planned_date < date.today()).count()
    spent = db.session.query(func.coalesce(func.sum(Maintenance.cost_kmf), 0)).filter(
        Maintenance.status == "termine").scalar()
    args = {k: v for k, v in {"q": q, "status": status, "kind": kind}.items() if v}
    return render_template("maintenance_list.html", pagination=pagination, args=args, q=q, status=status,
                           kind=kind, counts=counts, late=late, spent=spent, kind_stats=_kind_stats(),
                           kinds=MAINT_KINDS,
                           statuses=MAINT_STATUS, conditions=CONDITIONS)


@bp.route("/nouvel", methods=["GET", "POST"])
@login_required
def create():
    form = MaintenanceForm()
    if request.method == "GET":
        rid = request.args.get("route_id", type=int)
        if rid and db.session.get(Route, rid):
            form.route_id.data = rid
        form.planned_date.data = date.today()
        k = request.args.get("kind", "")
        if k in MAINT_KINDS:
            form.kind.data = k
        form.title.data = request.args.get("title", "")[:160]
    if form.validate_on_submit():
        m = Maintenance(created_by_id=current_user.id)
        _apply(form, m)
        db.session.add(m)
        db.session.commit()
        flash("Intervention enregistrée.", "success")
        return redirect(url_for("maintenance.index"))
    return render_template("maintenance_form.html", form=form, item=None, route_geo=_route_geo())


@bp.route("/<int:item_id>", methods=["GET", "POST"])
@login_required
def edit(item_id):
    m = db.get_or_404(Maintenance, item_id)
    form = MaintenanceForm(obj=m)
    if form.validate_on_submit():
        _apply(form, m)
        db.session.commit()
        flash("Intervention mise à jour.", "success")
        return redirect(url_for("maintenance.index"))
    return render_template("maintenance_form.html", form=form, item=m, route_geo=_route_geo())


@bp.route("/<int:item_id>/supprimer", methods=["POST"])
@admin_required
def delete(item_id):
    m = db.get_or_404(Maintenance, item_id)
    db.session.delete(m)
    db.session.commit()
    flash("Intervention supprimée.", "info")
    return redirect(url_for("maintenance.index"))
