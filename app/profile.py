from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, TextAreaField
from wtforms.validators import DataRequired, EqualTo, Length, Optional, ValidationError

from . import db
from .models import ISLANDS

bp = Blueprint("profile", __name__, url_prefix="/profil")


class ProfileForm(FlaskForm):
    full_name = StringField("Nom complet", validators=[DataRequired(), Length(max=120)])
    email = StringField("E-mail", validators=[Optional(), Length(max=120)])
    phone = StringField("Téléphone", validators=[Optional(), Length(max=30)])
    job_title = StringField("Fonction", validators=[Optional(), Length(max=120)])
    organization = StringField("Organisation / Service", validators=[Optional(), Length(max=120)])
    island = SelectField("Île", choices=[("", "—")] + [(i, i) for i in ISLANDS], validators=[Optional()])
    bio = TextAreaField("À propos", validators=[Optional(), Length(max=1000)])

    def validate_email(self, field):
        v = (field.data or "").strip()
        if v and ("@" not in v or "." not in v.split("@")[-1] or " " in v):
            raise ValidationError("Adresse e-mail invalide.")


class PasswordForm(FlaskForm):
    current_password = PasswordField("Mot de passe actuel", validators=[DataRequired()])
    new_password = PasswordField("Nouveau mot de passe", validators=[DataRequired(), Length(min=8, max=128, message="8 caractères minimum.")])
    confirm = PasswordField("Confirmer le nouveau mot de passe", validators=[DataRequired(), EqualTo("new_password", message="Les mots de passe ne correspondent pas.")])

    def validate_current_password(self, field):
        if not current_user.check_password(field.data):
            raise ValidationError("Mot de passe actuel incorrect.")

    def validate_new_password(self, field):
        if field.data == self.current_password.data:
            raise ValidationError("Le nouveau mot de passe doit être différent de l'ancien.")


@bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    pform = ProfileForm(obj=current_user, prefix="p")
    wform = PasswordForm(prefix="w")
    return render_template("profile.html", pform=pform, wform=wform)


@bp.route("/infos", methods=["POST"])
@login_required
def update_info():
    pform = ProfileForm(prefix="p")
    wform = PasswordForm(prefix="w")
    if pform.validate_on_submit():
        for f in ("full_name", "email", "phone", "job_title", "organization", "island", "bio"):
            val = (getattr(pform, f).data or "").strip()
            setattr(current_user, f, val or None if f != "full_name" else val)
        db.session.commit()
        flash("Profil mis à jour.", "success")
        return redirect(url_for("profile.index"))
    return render_template("profile.html", pform=pform, wform=wform)


@bp.route("/mot-de-passe", methods=["POST"])
@login_required
def change_password():
    pform = ProfileForm(obj=current_user, prefix="p")
    wform = PasswordForm(prefix="w")
    if wform.validate_on_submit():
        current_user.set_password(wform.new_password.data)
        current_user.must_change_password = False
        db.session.commit()
        flash("Mot de passe modifié.", "success")
        return redirect(url_for("profile.index"))
    return render_template("profile.html", pform=pform, wform=wform)
