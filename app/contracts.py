"""Marchés, entreprises, avenants et paiements (suivi des marchés et des dépenses)."""
import csv
import io
from datetime import date, timedelta

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import (BooleanField, DateField, IntegerField, SelectField, StringField, TextAreaField)
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional, ValidationError

from . import db
from .models import (ISLANDS, MARCHE_MODES, MARCHE_OPEN_STATUS, MARCHE_STATUS, PAIEMENT_KINDS, PAIEMENT_STATUS,
                     Avenant, Entreprise, Marche, Paiement, Work)

bp = Blueprint("marches", __name__, url_prefix="/marches")
bp_e = Blueprint("entreprises", __name__, url_prefix="/entreprises")
PER_PAGE = 10
BIG = 10 ** 13


def _flash_errors(form, prefix=""):
    for field, errs in form.errors.items():
        label = getattr(getattr(form, field, None), "label", None)
        flash(f"{prefix}{label.text + ' : ' if label else ''}{' '.join(errs)}", "danger")


def _kmf(n):
    return f"{int(n or 0):,}".replace(",", " ") + " KMF"


# =====================================================================================
#  Entreprises
# =====================================================================================
class EntrepriseForm(FlaskForm):
    name = StringField("Raison sociale", validators=[DataRequired(), Length(max=160)])
    acronym = StringField("Sigle", validators=[Optional(), Length(max=30)])
    registration = StringField("RCCM / NIF", validators=[Optional(), Length(max=60)])
    contact_name = StringField("Personne à contacter", validators=[Optional(), Length(max=120)])
    phone = StringField("Téléphone", validators=[Optional(), Length(max=40)])
    email = StringField("E-mail", validators=[Optional(), Length(max=120)])
    address = StringField("Adresse", validators=[Optional(), Length(max=200)])
    island = SelectField("Île", choices=[("", "— Non précisée —")] + [(i, i) for i in ISLANDS], validators=[Optional()])
    specialties = StringField("Spécialités", validators=[Optional(), Length(max=200)],
                              render_kw={"placeholder": "Ex. terrassement, ouvrages d'art, enrobés"})
    approved = BooleanField("Entreprise agréée / référencée", default=True)
    active = BooleanField("Active", default=True)
    notes = TextAreaField("Observations", validators=[Optional(), Length(max=3000)])

    def __init__(self, *a, entreprise=None, **kw):
        super().__init__(*a, **kw)
        self._e = entreprise

    def validate_name(self, field):
        field.data = field.data.strip()
        q = Entreprise.query.filter(func.lower(Entreprise.name) == field.data.lower())
        if self._e is not None:
            q = q.filter(Entreprise.id != self._e.id)
        if q.first():
            raise ValidationError("Cette entreprise existe déjà.")

    def validate_email(self, field):
        v = (field.data or "").strip()
        if v and ("@" not in v or "." not in v.split("@")[-1] or " " in v):
            raise ValidationError("Adresse e-mail invalide.")


def _apply_entreprise(form, e):
    for f in ("name", "acronym", "registration", "contact_name", "phone", "email", "address", "island",
              "specialties", "notes"):
        v = getattr(form, f).data
        setattr(e, f, (v or "").strip() or None)
    e.name = form.name.data.strip()
    e.approved, e.active = form.approved.data, form.active.data


@bp_e.route("/")
@login_required
def index():
    q = request.args.get("q", "").strip()
    state = request.args.get("state", "")
    query = Entreprise.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Entreprise.name.ilike(like), Entreprise.acronym.ilike(like),
                                    Entreprise.specialties.ilike(like), Entreprise.contact_name.ilike(like)))
    if state == "active":
        query = query.filter(Entreprise.active.is_(True))
    elif state == "inactive":
        query = query.filter(Entreprise.active.is_(False))
    items = query.order_by(Entreprise.name).all()
    return render_template("entreprises_list.html", items=items, q=q, state=state, kmf=_kmf)


@bp_e.route("/nouvelle", methods=["GET", "POST"])
@login_required
def create():
    form = EntrepriseForm()
    if form.validate_on_submit():
        e = Entreprise()
        _apply_entreprise(form, e)
        db.session.add(e)
        db.session.commit()
        flash(f"Entreprise « {e.name} » enregistrée.", "success")
        return redirect(url_for("entreprises.detail", item_id=e.id))
    return render_template("entreprise_form.html", form=form, item=None)


@bp_e.route("/<int:item_id>")
@login_required
def detail(item_id):
    e = db.get_or_404(Entreprise, item_id)
    marches = sorted(e.marches, key=lambda m: (m.signed_on or date.min), reverse=True)
    totals = {"count": len(marches), "amount": sum(m.current_amount for m in marches),
              "paid": sum(m.paid for m in marches), "late": sum(1 for m in marches if m.is_late),
              "open": sum(1 for m in marches if m.status in MARCHE_OPEN_STATUS)}
    return render_template("entreprise_detail.html", e=e, marches=marches, totals=totals, statuses=MARCHE_STATUS,
                           kmf=_kmf)


@bp_e.route("/<int:item_id>/modifier", methods=["GET", "POST"])
@login_required
def edit(item_id):
    e = db.get_or_404(Entreprise, item_id)
    form = EntrepriseForm(obj=e, entreprise=e)
    if request.method == "GET":
        form.island.data = e.island or ""
    if form.validate_on_submit():
        _apply_entreprise(form, e)
        db.session.commit()
        flash("Entreprise mise à jour.", "success")
        return redirect(url_for("entreprises.detail", item_id=e.id))
    return render_template("entreprise_form.html", form=form, item=e)


@bp_e.route("/<int:item_id>/supprimer", methods=["POST"])
@login_required
def delete(item_id):
    e = db.get_or_404(Entreprise, item_id)
    if e.marches:
        flash("Impossible de supprimer une entreprise qui a des marchés : désactivez-la plutôt.", "danger")
        return redirect(url_for("entreprises.detail", item_id=e.id))
    db.session.delete(e)
    db.session.commit()
    flash("Entreprise supprimée.", "info")
    return redirect(url_for("entreprises.index"))


# =====================================================================================
#  Marchés
# =====================================================================================
class MarcheForm(FlaskForm):
    number = StringField("N° du marché", validators=[DataRequired(), Length(max=40)],
                         render_kw={"placeholder": "Ex. M-2026-001"})
    title = StringField("Objet du marché", validators=[DataRequired(), Length(max=200)])
    entreprise_id = SelectField("Entreprise titulaire", coerce=int, validators=[DataRequired()])
    funder = StringField("Financement / Bailleur", validators=[Optional(), Length(max=160)])
    mode = SelectField("Mode de passation", choices=[("", "— Non précisé —")] + list(MARCHE_MODES.items()),
                       validators=[Optional()])
    status = SelectField("Statut", choices=list(MARCHE_STATUS.items()))
    amount_kmf = IntegerField("Montant initial", validators=[DataRequired(message="Montant requis."),
                                                             NumberRange(min=0, max=BIG)])
    signed_on = DateField("Date de signature", validators=[Optional()])
    start_order_on = DateField("Ordre de service de démarrage", validators=[Optional()])
    duration_days = IntegerField("Délai d'exécution", validators=[Optional(), NumberRange(min=0, max=5000)])
    description = TextAreaField("Observations", validators=[Optional(), Length(max=3000)])

    def __init__(self, *a, marche=None, **kw):
        super().__init__(*a, **kw)
        self._m = marche
        self.entreprise_id.choices = [(e.id, e.label) for e in Entreprise.query.order_by(Entreprise.name)]

    def validate_number(self, field):
        field.data = field.data.strip()
        q = Marche.query.filter(func.lower(Marche.number) == field.data.lower())
        if self._m is not None:
            q = q.filter(Marche.id != self._m.id)
        if q.first():
            raise ValidationError("Ce numéro de marché existe déjà.")

    def validate_start_order_on(self, field):
        if field.data and self.signed_on.data and field.data < self.signed_on.data:
            raise ValidationError("L'ordre de service ne peut pas précéder la signature.")


def _apply_marche(form, m):
    m.number = form.number.data.strip()
    m.title = form.title.data.strip()
    m.entreprise_id = form.entreprise_id.data
    m.funder = (form.funder.data or "").strip() or None
    m.mode = form.mode.data or None
    m.status = form.status.data
    m.amount_kmf = form.amount_kmf.data or 0
    m.signed_on, m.start_order_on = form.signed_on.data, form.start_order_on.data
    m.duration_days = form.duration_days.data
    m.description = (form.description.data or "").strip() or None


class AvenantForm(FlaskForm):
    class Meta:
        csrf = True
    number = IntegerField("N°", validators=[Optional(), NumberRange(min=1, max=99)])
    signed_on = DateField("Date", validators=[Optional()])
    purpose = StringField("Objet", validators=[Optional(), Length(max=200)])
    amount_kmf = IntegerField("Montant (+/−)", default=0, validators=[Optional(), NumberRange(min=-BIG, max=BIG)])
    extra_days = IntegerField("Prolongation (jours)", default=0, validators=[Optional(), NumberRange(min=-5000, max=5000)])


class PaiementForm(FlaskForm):
    kind = SelectField("Nature", choices=list(PAIEMENT_KINDS.items()))
    number = StringField("N° décompte", validators=[Optional(), Length(max=20)])
    paid_on = DateField("Date", validators=[DataRequired(message="Date requise.")])
    amount_kmf = IntegerField("Montant", validators=[DataRequired(message="Montant requis."),
                                                     NumberRange(min=1, max=BIG, message="Montant positif requis.")])
    status = SelectField("Statut", choices=list(PAIEMENT_STATUS.items()))
    reference = StringField("Référence (mandat, virement…)", validators=[Optional(), Length(max=80)])
    notes = StringField("Observations", validators=[Optional(), Length(max=300)])

    def validate_paid_on(self, field):
        if field.data and self.status.data == "paye" and field.data > date.today():
            raise ValidationError("Un paiement effectué ne peut pas être daté du futur.")


def _marche_stats(marches):
    return {
        "count": len(marches),
        "active": sum(1 for m in marches if m.status == "en_cours"),
        "late": sum(1 for m in marches if m.is_late),
        "amount": sum(m.current_amount for m in marches if m.status != "resilie"),
        "paid": sum(m.paid for m in marches),
        "pending": sum(m.pending for m in marches),
        "over": sum(1 for m in marches if m.over_budget),
    }


def _filtered_marches():
    status = request.args.get("status", "")
    ent = request.args.get("entreprise", type=int)
    q = request.args.get("q", "").strip()
    query = Marche.query.join(Entreprise)
    if status in MARCHE_STATUS:
        query = query.filter(Marche.status == status)
    if ent:
        query = query.filter(Marche.entreprise_id == ent)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Marche.number.ilike(like), Marche.title.ilike(like), Entreprise.name.ilike(like),
                                    Marche.funder.ilike(like)))
    return query, {k: v for k, v in {"q": q, "status": status, "entreprise": ent or ""}.items() if v}


@bp.route("/")
@login_required
def index():
    query, args = _filtered_marches()
    page = request.args.get("page", 1, type=int)
    pagination = query.order_by(Marche.signed_on.is_(None), Marche.signed_on.desc(), Marche.id.desc()).paginate(
        page=page, per_page=PER_PAGE, error_out=False)
    stats = _marche_stats(Marche.query.all())
    return render_template("marches_list.html", pagination=pagination, args=args, st=stats, statuses=MARCHE_STATUS,
                           entreprises=Entreprise.query.order_by(Entreprise.name).all(), kmf=_kmf,
                           q=args.get("q", ""), status=args.get("status", ""), ent=args.get("entreprise", ""))


@bp.route("/export.csv")
@login_required
def export_csv():
    query, _ = _filtered_marches()
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["N° marché", "Objet", "Entreprise", "Bailleur", "Mode de passation", "Statut", "Signature",
                "Ordre de service", "Fin prévue", "Montant initial (KMF)", "Avenants (KMF)", "Montant actuel (KMF)",
                "Payé (KMF)", "En attente (KMF)", "Reste à payer (KMF)", "Taux payé (%)", "En retard"])
    for m in query.order_by(Marche.number).all():
        d = lambda x: x.strftime("%d/%m/%Y") if x else ""
        w.writerow([m.number, m.title, m.entreprise.name, m.funder or "", MARCHE_MODES.get(m.mode, ""),
                    MARCHE_STATUS[m.status], d(m.signed_on), d(m.start_order_on), d(m.planned_end), m.amount_kmf,
                    m.amendments_total, m.current_amount, m.paid, m.pending, m.remaining, m.paid_rate,
                    "oui" if m.is_late else "non"])
    return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="marches-sigr.csv"'})


@bp.route("/nouveau", methods=["GET", "POST"])
@login_required
def create():
    if not Entreprise.query.count():
        flash("Enregistrez d'abord une entreprise pour pouvoir créer un marché.", "warning")
        return redirect(url_for("entreprises.create"))
    form = MarcheForm()
    if request.method == "GET":
        eid = request.args.get("entreprise_id", type=int)
        if eid and db.session.get(Entreprise, eid):
            form.entreprise_id.data = eid
    if form.validate_on_submit():
        m = Marche(created_by_id=current_user.id)
        _apply_marche(form, m)
        db.session.add(m)
        db.session.commit()
        flash(f"Marché {m.number} enregistré.", "success")
        return redirect(url_for("marches.detail", item_id=m.id))
    return render_template("marche_form.html", form=form, item=None)


@bp.route("/<int:item_id>")
@login_required
def detail(item_id):
    m = db.get_or_404(Marche, item_id)
    nxt = (max([a.number for a in m.amendments] or [0]) + 1)
    return render_template("marche_detail.html", m=m, statuses=MARCHE_STATUS, modes=MARCHE_MODES,
                           kinds=PAIEMENT_KINDS, pay_status=PAIEMENT_STATUS, kmf=_kmf, today=date.today(),
                           av_form=AvenantForm(prefix="av", number=nxt, amount_kmf=0, extra_days=0),
                           pay_form=PaiementForm(prefix="pay", paid_on=date.today()))


@bp.route("/<int:item_id>/modifier", methods=["GET", "POST"])
@login_required
def edit(item_id):
    m = db.get_or_404(Marche, item_id)
    form = MarcheForm(obj=m, marche=m)
    if request.method == "GET":
        form.mode.data = m.mode or ""
    if form.validate_on_submit():
        _apply_marche(form, m)
        db.session.commit()
        flash("Marché mis à jour.", "success")
        return redirect(url_for("marches.detail", item_id=m.id))
    return render_template("marche_form.html", form=form, item=m)


@bp.route("/<int:item_id>/supprimer", methods=["POST"])
@login_required
def delete(item_id):
    m = db.get_or_404(Marche, item_id)
    Work.query.filter_by(marche_id=m.id).update({"marche_id": None})   # les chantiers restent
    db.session.delete(m)
    db.session.commit()
    flash(f"Marché {m.number} supprimé (avenants et paiements compris).", "info")
    return redirect(url_for("marches.index"))


@bp.route("/<int:item_id>/avenants", methods=["POST"])
@login_required
def add_amendment(item_id):
    m = db.get_or_404(Marche, item_id)
    form = AvenantForm(prefix="av")
    if form.validate_on_submit():
        nxt = max([a.number for a in m.amendments] or [0]) + 1
        db.session.add(Avenant(marche_id=m.id, number=form.number.data or nxt, signed_on=form.signed_on.data,
                               purpose=(form.purpose.data or "").strip() or None,
                               amount_kmf=form.amount_kmf.data or 0, extra_days=form.extra_days.data or 0))
        db.session.commit()
        flash("Avenant ajouté.", "success")
    else:
        _flash_errors(form, "Avenant — ")
    return redirect(url_for("marches.detail", item_id=m.id) + "#avenants")


@bp.route("/avenants/<int:av_id>/supprimer", methods=["POST"])
@login_required
def delete_amendment(av_id):
    a = db.get_or_404(Avenant, av_id)
    mid = a.marche_id
    db.session.delete(a)
    db.session.commit()
    flash("Avenant supprimé.", "info")
    return redirect(url_for("marches.detail", item_id=mid) + "#avenants")


@bp.route("/<int:item_id>/paiements", methods=["POST"])
@login_required
def add_payment(item_id):
    m = db.get_or_404(Marche, item_id)
    form = PaiementForm(prefix="pay")
    if form.validate_on_submit():
        db.session.add(Paiement(marche_id=m.id, kind=form.kind.data, number=(form.number.data or "").strip() or None,
                                paid_on=form.paid_on.data, amount_kmf=form.amount_kmf.data, status=form.status.data,
                                reference=(form.reference.data or "").strip() or None,
                                notes=(form.notes.data or "").strip() or None, created_by_id=current_user.id))
        db.session.commit()
        flash("Paiement enregistré.", "success")
        if m.paid > m.current_amount:
            flash(f"Attention : le total payé ({_kmf(m.paid)}) dépasse le montant du marché ({_kmf(m.current_amount)}).",
                  "warning")
    else:
        _flash_errors(form, "Paiement — ")
    return redirect(url_for("marches.detail", item_id=m.id) + "#paiements")


@bp.route("/paiements/<int:pay_id>/supprimer", methods=["POST"])
@login_required
def delete_payment(pay_id):
    p = db.get_or_404(Paiement, pay_id)
    mid = p.marche_id
    db.session.delete(p)
    db.session.commit()
    flash("Paiement supprimé.", "info")
    return redirect(url_for("marches.detail", item_id=mid) + "#paiements")


@bp.route("/paiements/<int:pay_id>/regler", methods=["POST"])
@login_required
def settle_payment(pay_id):
    """Passe un paiement « émis » à « payé » à la date du jour."""
    p = db.get_or_404(Paiement, pay_id)
    if p.status == "emis":
        p.status, p.paid_on = "paye", date.today()
        db.session.commit()
        flash("Paiement marqué comme payé.", "success")
    return redirect(url_for("marches.detail", item_id=p.marche_id) + "#paiements")
