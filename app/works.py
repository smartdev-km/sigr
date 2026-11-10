from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import DateField, DecimalField, IntegerField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError

from . import db
from .models import MAINT_KINDS, MAINT_STATUS, WORK_KINDS, WORK_OPEN_STATUS, WORK_STATUS, Maintenance, Marche, Route, Work
from .routes import admin_required, route_geo

bp = Blueprint("works", __name__, url_prefix="/travaux")
PER_PAGE = 10


class WorkForm(FlaskForm):
    route_id = SelectField("Route", coerce=int, validators=[DataRequired()])
    title = StringField("Intitulé des travaux", validators=[DataRequired(), Length(max=160)],
                        render_kw={"placeholder": "Ex. Réhabilitation du tronçon Moroni – Itsandra"})
    kind = SelectField("Nature des travaux", choices=list(WORK_KINDS.items()))
    status = SelectField("Statut", choices=list(WORK_STATUS.items()))
    progress = IntegerField("Avancement (%)", default=0, validators=[NumberRange(min=0, max=100, message="Entre 0 et 100.")])
    pk_start = DecimalField("PK début", places=2, validators=[Optional(), NumberRange(min=0, max=2000)])
    pk_end = DecimalField("PK fin", places=2, validators=[Optional(), NumberRange(min=0, max=2000)])
    budget_kmf = IntegerField("Budget prévu", validators=[Optional(), NumberRange(min=0, max=10**13)])
    spent_kmf = IntegerField("Montant dépensé", validators=[Optional(), NumberRange(min=0, max=10**13)])
    marche_id = SelectField("Marché d'exécution", coerce=int, validators=[Optional()])
    funder = StringField("Financement / Bailleur", validators=[Optional(), Length(max=160)])
    contractor = StringField("Entreprise", validators=[Optional(), Length(max=160)])
    supervisor = StringField("Maître d'œuvre / Contrôle", validators=[Optional(), Length(max=160)])
    start_date = DateField("Début des travaux", validators=[Optional()])
    end_planned = DateField("Fin prévue", validators=[Optional()])
    end_actual = DateField("Réception / fin réelle", validators=[Optional()])
    description = TextAreaField("Description", validators=[Optional(), Length(max=3000)])

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.route_id.choices = [(r.id, f"{r.code} · {r.name}") for r in Route.query.order_by(Route.code)]
        self.marche_id.choices = [(0, "— Aucun marché —")] + [
            (m.id, f"{m.number} · {m.entreprise.name}") for m in Marche.query.order_by(Marche.number)]

    def validate_end_planned(self, field):
        if field.data and self.start_date.data and field.data < self.start_date.data:
            raise ValidationError("La fin prévue ne peut pas précéder le début.")

    def validate_end_actual(self, field):
        if field.data and self.start_date.data and field.data < self.start_date.data:
            raise ValidationError("La réception ne peut pas précéder le début.")

    def validate_pk_end(self, field):
        if field.data is not None and self.pk_start.data is not None and field.data < self.pk_start.data:
            raise ValidationError("Le PK de fin doit être supérieur ou égal au PK de début.")


def _num(v):
    return float(v) if v is not None else None


def _apply(form, w):
    w.route_id = form.route_id.data
    w.title = form.title.data.strip()
    w.kind = form.kind.data
    w.status = form.status.data
    w.progress = form.progress.data or 0
    w.pk_start, w.pk_end = _num(form.pk_start.data), _num(form.pk_end.data)
    w.budget_kmf, w.spent_kmf = form.budget_kmf.data, form.spent_kmf.data
    for f in ("funder", "contractor", "supervisor", "description"):
        setattr(w, f, (getattr(form, f).data or "").strip() or None)
    w.marche_id = form.marche_id.data or None
    mk = db.session.get(Marche, w.marche_id) if w.marche_id else None
    if mk:                              # pré-remplit l'entreprise et le financement depuis le marché
        w.contractor = w.contractor or mk.entreprise.name
        w.funder = w.funder or mk.funder
    w.start_date, w.end_planned, w.end_actual = form.start_date.data, form.end_planned.data, form.end_actual.data
    if w.status == "receptionne":      # un chantier réceptionné est achevé
        w.progress = 100
        w.end_actual = w.end_actual or date.today()
    elif w.status in ("etude", "appel_offres"):
        w.progress = 0
        w.end_actual = None
    else:
        w.end_actual = None


def _stats():
    today = date.today()
    works = Work.query.all()
    open_ = [w for w in works if w.status in WORK_OPEN_STATUS]
    budget = sum(w.budget_kmf or 0 for w in works if w.status != "annule")
    spent = sum(w.spent_kmf or 0 for w in works if w.status != "annule")
    # avancement moyen pondéré par le budget (à défaut, moyenne simple) sur les chantiers en cours
    active = [w for w in works if w.status == "en_cours"]
    wsum = sum((w.budget_kmf or 0) for w in active)
    avg = (sum(w.progress * (w.budget_kmf or 0) for w in active) / wsum) if wsum else (
        sum(w.progress for w in active) / len(active) if active else 0)
    return {
        "total": len(works),
        "active": len(active),
        "late": sum(1 for w in open_ if w.is_late),
        "done": sum(1 for w in works if w.status == "receptionne"),
        "budget": budget, "spent": spent, "avg": round(avg),
        "over": sum(1 for w in works if w.over_budget),
        "today": today,
    }


@bp.route("/")
@login_required
def index():
    status = request.args.get("status", "")
    kind = request.args.get("kind", "")
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    query = Work.query.join(Route)
    if status in WORK_STATUS:
        query = query.filter(Work.status == status)
    if kind in WORK_KINDS:
        query = query.filter(Work.kind == kind)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Route.code.ilike(like), Work.title.ilike(like), Work.contractor.ilike(like),
                                    Work.funder.ilike(like)))
    pagination = query.order_by(Work.start_date.is_(None), Work.start_date.desc(), Work.id.desc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False)
    counts = dict(db.session.query(Work.status, func.count()).group_by(Work.status))
    args = {k: v for k, v in {"q": q, "status": status, "kind": kind}.items() if v}
    return render_template("works_list.html", pagination=pagination, args=args, q=q, status=status, kind=kind,
                           st=_stats(), counts=counts, kinds=WORK_KINDS, statuses=WORK_STATUS)


@bp.route("/nouveau", methods=["GET", "POST"])
@login_required
def create():
    form = WorkForm()
    if request.method == "GET":
        rid = request.args.get("route_id", type=int)
        if rid and db.session.get(Route, rid):
            form.route_id.data = rid
    if form.validate_on_submit():
        w = Work(created_by_id=current_user.id)
        _apply(form, w)
        db.session.add(w)
        db.session.commit()
        flash("Chantier enregistré.", "success")
        return redirect(url_for("works.index"))
    return render_template("work_form.html", form=form, item=None, route_geo=route_geo())


@bp.route("/<int:item_id>", methods=["GET", "POST"])
@login_required
def edit(item_id):
    w = db.get_or_404(Work, item_id)
    form = WorkForm(obj=w)
    if form.validate_on_submit():
        _apply(form, w)
        db.session.commit()
        flash("Chantier mis à jour.", "success")
        return redirect(url_for("works.index"))
    return render_template("work_form.html", form=form, item=w, route_geo=route_geo())


@bp.route("/<int:item_id>/supprimer", methods=["POST"])
@admin_required
def delete(item_id):
    w = db.get_or_404(Work, item_id)
    Maintenance.query.filter_by(work_id=w.id).update({"work_id": None})   # les interventions sont conservées
    db.session.delete(w)
    db.session.commit()
    flash("Chantier supprimé.", "info")
    return redirect(url_for("works.index"))


@bp.route("/entretien")
@login_required
def maintenance_tab():
    """Interventions d'entretien vues depuis les Travaux (lecture seule ; la gestion reste dans le module Entretien)."""
    if not current_user.can("entretien"):
        abort(403)
    status = request.args.get("status", "")
    link = request.args.get("link", "")           # "oui" = rattachées à un chantier, "non" = non rattachées
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    query = Maintenance.query.join(Route)
    if status in MAINT_STATUS:
        query = query.filter(Maintenance.status == status)
    if link == "oui":
        query = query.filter(Maintenance.work_id.isnot(None))
    elif link == "non":
        query = query.filter(Maintenance.work_id.is_(None))
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Route.code.ilike(like), Maintenance.title.ilike(like), Maintenance.contractor.ilike(like)))
    pagination = query.order_by(Maintenance.planned_date.desc(), Maintenance.id.desc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False)
    allm = Maintenance.query.all()
    st = {"total": len(allm), "planned": sum(1 for m in allm if m.status == "planifie"),
          "ongoing": sum(1 for m in allm if m.status == "en_cours"), "late": sum(1 for m in allm if m.is_late),
          "done": sum(1 for m in allm if m.status == "termine"), "linked": sum(1 for m in allm if m.work_id)}
    args = {k: v for k, v in {"q": q, "status": status, "link": link}.items() if v}
    return render_template("works_maintenance.html", pagination=pagination, args=args, q=q, status=status, link=link,
                           st=st, kinds=MAINT_KINDS, statuses=MAINT_STATUS)
