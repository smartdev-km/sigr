import json
from datetime import date, timedelta

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from sqlalchemy import func
from wtforms import (DateField, DecimalField, FloatField, IntegerField, SelectField, SelectMultipleField,
                     StringField, TextAreaField)
from wtforms.validators import DataRequired, Length, NumberRange, Optional, ValidationError
from wtforms.widgets import CheckboxInput, HiddenInput, ListWidget

from . import db
from .models import (CONDITIONS, ISLAND_BOUNDS, ISLANDS, STRUCTURE_DEFECTS, STRUCTURE_KINDS, STRUCTURE_MATERIALS,
                     Ouvrage, Route)
from .routes import admin_required, route_geo

bp = Blueprint("ouvrages", __name__, url_prefix="/ouvrages")
PER_PAGE = 10
STALE_DAYS = 365


class OuvrageForm(FlaskForm):
    route_id = SelectField("Route", coerce=int, validators=[DataRequired()])
    kind = SelectField("Type d'ouvrage", choices=list(STRUCTURE_KINDS.items()))
    ref = StringField("Référence", validators=[Optional(), Length(max=30)],
                      render_kw={"placeholder": "Automatique si vide (OUV-0001)"})
    pk_km = DecimalField("Point kilométrique (PK)", places=3, validators=[Optional(), NumberRange(min=0, max=2000)])
    side = SelectField("Côté", choices=[("", "— Non précisé —"), ("gauche", "Gauche"), ("droite", "Droite"),
                                        ("axe", "Sous la chaussée (axe)")], validators=[Optional()])
    lat = FloatField(widget=HiddenInput(), validators=[Optional()])
    lng = FloatField(widget=HiddenInput(), validators=[Optional()])
    length_m = DecimalField("Longueur", places=2, validators=[Optional(), NumberRange(min=0.01, max=5000)])
    width_m = DecimalField("Largeur / diamètre", places=2, validators=[Optional(), NumberRange(min=0.01, max=1000)])
    quantity = IntegerField("Nombre de files / d'éléments", default=1,
                            validators=[NumberRange(min=1, max=50, message="Entre 1 et 50.")])
    material = SelectField("Matériau", choices=[("", "— Non précisé —")] + list(STRUCTURE_MATERIALS.items()),
                           validators=[Optional()])
    condition = SelectField("État", choices=list(CONDITIONS.items()), validators=[DataRequired()])
    defects = SelectMultipleField("Désordres observés", choices=list(STRUCTURE_DEFECTS.items()),
                                  widget=ListWidget(prefix_label=False), option_widget=CheckboxInput())
    built_year = IntegerField("Année de construction", validators=[Optional(), NumberRange(min=1850, max=date.today().year)])
    last_inspection = DateField("Dernière inspection", validators=[Optional()])
    notes = TextAreaField("Observations", validators=[Optional(), Length(max=3000)])

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.route_id.choices = [(r.id, f"{r.code} – {r.name}") for r in Route.query.order_by(Route.code)]

    def validate_last_inspection(self, field):
        if field.data and field.data > date.today():
            raise ValidationError("La date d'inspection ne peut pas être dans le futur.")

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators)
        # Optional() court-circuite les validateurs « validate_<champ> » : contrôle de la position ici
        la, ln = self.lat.data, self.lng.data
        err = None
        if (la is None) != (ln is None):
            err = "Placez l'ouvrage sur la carte (latitude et longitude)."
        elif la is not None:
            route = db.session.get(Route, self.route_id.data) if self.route_id.data else None
            if route:
                s, w, n, e = ISLAND_BOUNDS.get(route.island, (-90, -180, 90, 180))
                if not (s <= la <= n and w <= ln <= e):
                    err = f"La position doit se trouver sur l'île de {route.island}."
        if err:
            self.lng.errors = list(self.lng.errors) + [err]
            ok = False
        return ok


def _num(v):
    return float(v) if v is not None else None


def _apply(form, o):
    o.route_id = form.route_id.data
    o.kind = form.kind.data
    o.ref = (form.ref.data or "").strip() or o.ref
    o.pk_km = _num(form.pk_km.data)
    o.side = form.side.data or None
    o.lat, o.lng = form.lat.data, form.lng.data
    o.length_m, o.width_m = _num(form.length_m.data), _num(form.width_m.data)
    o.quantity = form.quantity.data or 1
    o.material = form.material.data or None
    o.condition = form.condition.data
    o.defects = json.dumps([d for d in form.defects.data if d in STRUCTURE_DEFECTS])
    o.built_year = form.built_year.data
    o.last_inspection = form.last_inspection.data
    o.notes = (form.notes.data or "").strip() or None
    if not o.ref:               # référence automatique, une fois l'identifiant connu
        db.session.flush()
        o.ref = f"OUV-{o.id:04d}"


def _context_others():
    """Autres ouvrages (points gris de repère sur la carte du formulaire)."""
    out = {}
    for o in Ouvrage.query.filter(Ouvrage.lat.isnot(None)).all():
        out.setdefault(o.route_id, []).append({"id": o.id, "lat": o.lat, "lng": o.lng, "ref": o.ref,
                                                "kind": STRUCTURE_KINDS.get(o.kind, o.kind)})
    return out


@bp.route("/")
@login_required
def index():
    kind = request.args.get("kind", "")
    cond = request.args.get("condition", "")
    island = request.args.get("island", "")
    route_id = request.args.get("route", type=int)
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)

    query = Ouvrage.query.join(Route)
    if kind in STRUCTURE_KINDS:
        query = query.filter(Ouvrage.kind == kind)
    if cond in CONDITIONS:
        query = query.filter(Ouvrage.condition == cond)
    if island in ISLANDS:
        query = query.filter(Route.island == island)
    if route_id:
        query = query.filter(Ouvrage.route_id == route_id)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Ouvrage.ref.ilike(like), Route.code.ilike(like), Route.name.ilike(like),
                                    Ouvrage.notes.ilike(like)))
    pagination = query.order_by(Route.code, Ouvrage.pk_km.is_(None), Ouvrage.pk_km, Ouvrage.id).paginate(
        page=page, per_page=PER_PAGE, error_out=False)

    by_cond = {k: 0 for k in CONDITIONS}
    for k, n in db.session.query(Ouvrage.condition, func.count()).group_by(Ouvrage.condition):
        by_cond[k] = n
    by_kind = {k: 0 for k in STRUCTURE_KINDS}
    for k, n in db.session.query(Ouvrage.kind, func.count()).group_by(Ouvrage.kind):
        by_kind[k] = n
    total = sum(by_cond.values())
    stale_limit = date.today() - timedelta(days=STALE_DAYS)
    stale = Ouvrage.query.filter(db.or_(Ouvrage.last_inspection.is_(None), Ouvrage.last_inspection < stale_limit)).count()
    args = {k: v for k, v in {"q": q, "kind": kind, "condition": cond, "island": island,
                               "route": route_id or ""}.items() if v}
    routes = Route.query.order_by(Route.code).all()
    return render_template("ouvrages_list.html", pagination=pagination, args=args, q=q, kind=kind, cond=cond,
                           island=island, route_id=route_id, total=total, by_cond=by_cond, by_kind=by_kind,
                           stale=stale, kinds=STRUCTURE_KINDS, materials=STRUCTURE_MATERIALS, conditions=CONDITIONS,
                           defects=STRUCTURE_DEFECTS, islands=ISLANDS, routes=routes)


@bp.route("/nouveau", methods=["GET", "POST"])
@login_required
def create():
    form = OuvrageForm()
    if request.method == "GET":
        rid = request.args.get("route_id", type=int)
        if rid and db.session.get(Route, rid):
            form.route_id.data = rid
    if form.validate_on_submit():
        o = Ouvrage(created_by_id=current_user.id)
        db.session.add(o)
        _apply(form, o)
        db.session.commit()
        flash(f"Ouvrage {o.ref} enregistré.", "success")
        return redirect(url_for("ouvrages.index"))
    return render_template("ouvrage_form.html", form=form, item=None, route_geo=route_geo(with_geom=True),
                           others=_context_others(), bounds=ISLAND_BOUNDS)


@bp.route("/<int:item_id>", methods=["GET", "POST"])
@login_required
def edit(item_id):
    o = db.get_or_404(Ouvrage, item_id)
    form = OuvrageForm(obj=o)
    if request.method == "GET":
        form.defects.data = o.defect_list
        form.side.data = o.side or ""
        form.material.data = o.material or ""
    if form.validate_on_submit():
        _apply(form, o)
        db.session.commit()
        flash(f"Ouvrage {o.ref} mis à jour.", "success")
        return redirect(url_for("ouvrages.index"))
    return render_template("ouvrage_form.html", form=form, item=o, route_geo=route_geo(with_geom=True),
                           others=_context_others(), bounds=ISLAND_BOUNDS)


@bp.route("/<int:item_id>/supprimer", methods=["POST"])
@admin_required
def delete(item_id):
    o = db.get_or_404(Ouvrage, item_id)
    ref = o.ref
    db.session.delete(o)
    db.session.commit()
    flash(f"Ouvrage {ref} supprimé.", "info")
    return redirect(url_for("ouvrages.index"))
