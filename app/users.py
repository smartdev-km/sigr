import json
import re

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, RadioField, SelectField, StringField
from wtforms.validators import DataRequired, Length, Optional, ValidationError

from . import db
from .models import LEVELS, MODULES, User

bp = Blueprint("users", __name__, url_prefix="/utilisateurs")
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,64}$")

PRESETS = {  # profils prédéfinis (appliqués côté navigateur)
    "lecteur": {"label": "Lecteur", "perms": {m: "read" for m in MODULES}, "delete": False},
    "terrain": {"label": "Agent de terrain", "delete": False,
                "perms": {"routes": "read", "ouvrages": "write", "carte": "read", "diagnostic": "write", "travaux": "read",
                          "entretien": "write", "marches": "read", "rapport": "none"}},
    "editeur": {"label": "Éditeur", "perms": {m: "write" for m in MODULES}, "delete": False},
}


def _perm_field(module):
    choices = [(k, v) for k, v in LEVELS.items() if not (module == "routes" and k == "none")]
    return RadioField(MODULES[module], choices=choices, default="read")


class UserForm(FlaskForm):
    full_name = StringField("Nom complet", validators=[DataRequired(), Length(max=120)])
    username = StringField("Nom d'utilisateur", validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField("E-mail", validators=[Optional(), Length(max=120)])
    role = SelectField("Rôle", choices=[("agent", "Utilisateur (droits personnalisés)"),
                                         ("admin", "Administrateur (tous les droits)")])
    password = PasswordField("Mot de passe", validators=[Optional(), Length(min=8, max=128, message="8 caractères minimum.")])
    must_change_password = BooleanField("Imposer le changement du mot de passe à la prochaine connexion", default=True)
    is_active_account = BooleanField("Compte actif", default=True)
    can_delete = BooleanField("Autoriser la suppression (routes, diagnostics, chantiers, interventions)")
    perm_routes = _perm_field("routes")
    perm_ouvrages = _perm_field("ouvrages")
    perm_carte = _perm_field("carte")
    perm_diagnostic = _perm_field("diagnostic")
    perm_travaux = _perm_field("travaux")
    perm_entretien = _perm_field("entretien")
    perm_marches = _perm_field("marches")
    perm_rapport = _perm_field("rapport")

    def __init__(self, *a, user=None, **kw):
        super().__init__(*a, **kw)
        self._user = user

    def perm_fields(self):
        return [(m, getattr(self, "perm_" + m)) for m in MODULES]

    def validate_username(self, field):
        field.data = field.data.strip()
        if not USERNAME_RE.match(field.data):
            raise ValidationError("Lettres, chiffres, point, tiret ou underscore (3 caractères minimum).")
        q = User.query.filter(db.func.lower(User.username) == field.data.lower())
        if self._user is not None:
            q = q.filter(User.id != self._user.id)
        if q.first():
            raise ValidationError("Ce nom d'utilisateur existe déjà.")

    def validate_email(self, field):
        v = (field.data or "").strip()
        if v and ("@" not in v or "." not in v.split("@")[-1] or " " in v):
            raise ValidationError("Adresse e-mail invalide.")

    def validate(self, extra_validators=None):
        ok = super().validate(extra_validators)
        # Optional() court-circuite les validateurs « validate_<champ> » quand le champ est vide
        if self._user is None and not self.password.data:
            self.password.errors = list(self.password.errors) + ["Un mot de passe est requis pour un nouveau compte."]
            ok = False
        return ok


def _apply(form, u):
    u.full_name = form.full_name.data.strip()
    u.username = form.username.data
    u.email = (form.email.data or "").strip() or None
    u.role = form.role.data
    u.is_active_account = form.is_active_account.data
    u.can_delete = form.can_delete.data
    u.permissions = json.dumps({m: f.data or "read" for m, f in form.perm_fields()})
    if form.password.data:
        u.set_password(form.password.data)
        u.must_change_password = form.must_change_password.data
    elif u.id is None:
        u.must_change_password = form.must_change_password.data


def _other_active_admins(exclude_id):
    return User.query.filter(User.role == "admin", User.is_active_account.is_(True), User.id != exclude_id).count()


def _guard_admin(form, u):
    """Empêche de se retirer les droits ou de supprimer le dernier administrateur actif."""
    if u is None:
        return None
    losing = u.role == "admin" and (form.role.data != "admin" or not form.is_active_account.data)
    if losing and u.id == current_user.id:
        return "Vous ne pouvez pas retirer vos propres droits d'administrateur ni désactiver votre compte."
    if losing and not _other_active_admins(u.id):
        return "Il doit rester au moins un administrateur actif."
    return None


@bp.route("/")
@login_required
def index():
    q = request.args.get("q", "").strip()
    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(User.username.ilike(like), User.full_name.ilike(like), User.email.ilike(like)))
    users = query.order_by(User.is_active_account.desc(), User.full_name).all()
    return render_template("users_list.html", users=users, q=q, modules=MODULES, levels=LEVELS)


@bp.route("/nouveau", methods=["GET", "POST"])
@login_required
def create():
    form = UserForm()
    if form.validate_on_submit():
        u = User()
        _apply(form, u)
        db.session.add(u)
        db.session.commit()
        flash(f"Compte « {u.username} » créé.", "success")
        return redirect(url_for("users.index"))
    return render_template("user_form.html", form=form, item=None, presets=PRESETS)


@bp.route("/<int:user_id>", methods=["GET", "POST"])
@login_required
def edit(user_id):
    u = db.get_or_404(User, user_id)
    form = UserForm(obj=u, user=u)
    if request.method == "GET":
        for m, f in form.perm_fields():
            f.data = u.perm_dict()[m]
        form.can_delete.data = bool(u.can_delete)
        form.must_change_password.data = bool(u.must_change_password)
        form.password.data = ""
    if form.validate_on_submit():
        err = _guard_admin(form, u)
        if err:
            flash(err, "danger")
        else:
            _apply(form, u)
            db.session.commit()
            flash(f"Compte « {u.username} » mis à jour.", "success")
            return redirect(url_for("users.index"))
    return render_template("user_form.html", form=form, item=u, presets=PRESETS)


@bp.route("/<int:user_id>/statut", methods=["POST"])
@login_required
def toggle(user_id):
    u = db.get_or_404(User, user_id)
    if u.id == current_user.id:
        abort(400)
    if u.is_active_account and u.role == "admin" and not _other_active_admins(u.id):
        flash("Il doit rester au moins un administrateur actif.", "danger")
    else:
        u.is_active_account = not u.is_active_account
        db.session.commit()
        flash(f"Compte « {u.username} » {'réactivé' if u.is_active_account else 'désactivé'}.", "info")
    return redirect(url_for("users.index"))
