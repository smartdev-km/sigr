from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import DateField, DecimalField, IntegerField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from . import db
from .models import CONDITIONS, MAINT_KINDS, Entreprise, Work, MAINT_STATUS, ROUTE_TYPES, Maintenance, Route
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
    pk_start = DecimalField("PK début", places=3, validators=[Optional(), NumberRange(min=0, max=5000)])
    pk_end = DecimalField("PK fin", places=3, validators=[Optional(), NumberRange(min=0, max=5000)])
    cost_kmf = IntegerField("Coût estimé / réel", validators=[Optional(), NumberRange(min=0, max=10**12)])
    entreprise_id = SelectField("Entreprise / Intervenant", coerce=int, validators=[Optional()])
    work_id = SelectField("Chantier associé", coerce=int, validators=[Optional()])
    condition_after = SelectField("État de la route après travaux",
                                  choices=[("", "— Ne pas modifier —")] + list(CONDITIONS.items()),
                                  validators=[Optional()])
    description = TextAreaField("Description", validators=[Optional(), Length(max=3000)])

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.route_id.choices = [(r.id, f"{r.code} – {r.name}") for r in Route.query.order_by(Route.code)]
        # entreprises enregistrées (actives, plus celle déjà choisie si elle a été désactivée depuis)
        cur = kw.get("obj")
        keep = getattr(cur, "entreprise_id", None)
        q = Entreprise.query.filter(db.or_(Entreprise.active.is_(True), Entreprise.id == keep)).order_by(Entreprise.name)
        # 3e élément = attributs de l'option : l'île sert au filtrage côté navigateur
        self.entreprise_id.choices = [(0, "— Aucune —", {"data-island": ""})] + [
            (e.id, e.label, {"data-island": e.island or ""}) for e in q]
        # chantiers (non annulés) : le navigateur n'affiche que ceux de la route choisie (data-route)
        keep_w = getattr(cur, "work_id", None)
        wq = Work.query.filter(db.or_(Work.status != "annule", Work.id == keep_w)).order_by(Work.route_id, Work.title)
        if not current_user.can("travaux"):         # pas d'accès aux chantiers : on ne garde que le chantier déjà rattaché
            wq = Work.query.filter(Work.id == keep_w) if keep_w else Work.query.filter(Work.id == -1)
        self.work_id.choices = [(0, "— Aucun chantier —", {"data-route": ""})] + [
            (w.id, f"{w.route.code} · {w.title}", {"data-route": str(w.route_id)}) for w in wq]
        self.has_works = wq.count() > 0
        legacy = getattr(cur, "contractor", None)
        self.has_entreprises = q.count() > 0
        if cur is not None and legacy and not keep:   # ancienne saisie libre : on la conserve
            self.entreprise_id.choices.append((-1, f"{legacy} (non référencée)", {"data-island": ""}))

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators)
        w = db.session.get(Work, self.work_id.data) if self.work_id.data else None
        if w is not None and w.route_id != self.route_id.data:
            self.work_id.errors = list(self.work_id.errors) + ["Le chantier doit appartenir à la même route que l'intervention."]
            ok = False
        return ok

    def validate_pk_end(self, field):
        if field.data is not None and self.pk_start.data is not None and field.data < self.pk_start.data:
            raise ValidationError("Le PK de fin doit être supérieur ou égal au PK de début.")

    def validate_done_date(self, field):
        if field.data and self.planned_date.data and field.data < self.planned_date.data:
            raise ValidationError("La réalisation ne peut pas précéder la date prévue.")


def issues_by_route():
    """Points / secteurs à problème du DERNIER diagnostic de chaque route (si l'utilisateur voit les diagnostics)."""
    from .models import DEFECTS, ISSUE_SEVERITY, Diagnostic
    if not current_user.can("diagnostic"):
        return {}
    latest = {}
    for dg in Diagnostic.query.order_by(Diagnostic.inspected_on, Diagnostic.id):
        latest[dg.route_id] = dg
    out = {}
    for rid, dg in latest.items():
        if dg.issues:
            out[rid] = {"date": dg.inspected_on.strftime("%d/%m/%Y"), "inspector": dg.inspector or "",
                        "diagnostic_id": dg.id,
                        "items": [{**i.as_dict(), "id": i.id, "label": DEFECTS.get(i.kind, i.kind),
                                   "severity_label": ISSUE_SEVERITY.get(i.severity, i.severity), "where": i.where}
                                  for i in dg.issues]}
    return out


def _apply(form, m):
    m.route_id = form.route_id.data
    m.kind = form.kind.data
    m.status = form.status.data
    m.title = (form.title.data or "").strip() or MAINT_KINDS.get(m.kind, "Intervention")
    m.description = (form.description.data or "").strip() or None
    m.planned_date = form.planned_date.data
    m.done_date = form.done_date.data
    m.pk_start = float(form.pk_start.data) if form.pk_start.data is not None else None
    m.pk_end = float(form.pk_end.data) if form.pk_end.data is not None else None
    m.cost_kmf = form.cost_kmf.data
    m.work_id = form.work_id.data or None
    eid = form.entreprise_id.data
    if eid and eid > 0:                      # entreprise choisie dans la liste
        e = db.session.get(Entreprise, eid)
        m.entreprise_id, m.contractor = e.id, e.name
    elif eid == -1:                          # ancienne saisie libre conservée telle quelle
        m.entreprise_id = None
    else:
        m.entreprise_id, m.contractor = None, None
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
        wid = request.args.get("work_id", type=int)
        wk = db.session.get(Work, wid) if wid else None
        if wk:                                     # « + Planifier une intervention » depuis la fiche d'un chantier
            form.route_id.data, form.work_id.data = wk.route_id, wk.id
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
    return render_template("maintenance_form.html", form=form, item=None, route_geo=_route_geo(with_geom=True), issues_by_route=issues_by_route())


@bp.route("/<int:item_id>", methods=["GET", "POST"])
@login_required
def edit(item_id):
    m = db.get_or_404(Maintenance, item_id)
    form = MaintenanceForm(obj=m)
    if request.method == "GET":
        form.entreprise_id.data = m.entreprise_id or (-1 if m.contractor else 0)
        form.work_id.data = m.work_id or 0
    if form.validate_on_submit():
        _apply(form, m)
        db.session.commit()
        flash("Intervention mise à jour.", "success")
        return redirect(url_for("maintenance.index"))
    return render_template("maintenance_form.html", form=form, item=m, route_geo=_route_geo(with_geom=True), issues_by_route=issues_by_route())


@bp.route("/<int:item_id>/supprimer", methods=["POST"])
@admin_required
def delete(item_id):
    m = db.get_or_404(Maintenance, item_id)
    db.session.delete(m)
    db.session.commit()
    flash("Intervention supprimée.", "info")
    return redirect(url_for("maintenance.index"))
