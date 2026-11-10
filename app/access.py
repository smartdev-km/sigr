"""Contrôle d'accès : permissions par module, compte désactivé, changement de mot de passe obligatoire."""
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, logout_user

BLUEPRINT_MODULE = {
    "routes": "routes", "map": "carte", "diagnostic": "diagnostic",
    "works": "travaux", "maintenance": "entretien", "reports": "rapport", "ouvrages": "ouvrages",
    "marches": "marches", "entreprises": "marches",
}


def init_access(app):
    @app.before_request
    def guard():
        if request.endpoint is None or request.endpoint == "static" or not current_user.is_authenticated:
            return None  # les vues protégées par @login_required gèrent l'anonyme

        if not current_user.is_active:  # compte désactivé pendant la session
            logout_user()
            flash("Ce compte a été désactivé.", "danger")
            return redirect(url_for("auth.login"))

        bp = request.blueprint
        if current_user.must_change_password and bp not in ("profile", "auth"):
            flash("Pour des raisons de sécurité, définissez votre propre mot de passe.", "warning")
            return redirect(url_for("profile.index"))

        if bp == "users" and not current_user.is_admin:
            abort(403)

        module = BLUEPRINT_MODULE.get(bp)
        if module is None:
            return None
        action = request.endpoint.rsplit(".", 1)[-1]
        if request.endpoint == "map.save_geometry":
            need = "read"          # simple mise en cache d'un tracé calculé
        elif action.startswith("delete"):
            if not current_user.may_delete:
                abort(403)
            need = "write"
        elif action == "create" or request.method not in ("GET", "HEAD"):
            need = "write"
        else:
            need = "read"
        if not current_user.can(module, need):
            abort(403)
        return None

    @app.context_processor
    def inject_access():
        def can(module, need="read"):
            return current_user.is_authenticated and current_user.can(module, need)

        read_only = False
        ep = request.endpoint or ""
        module = BLUEPRINT_MODULE.get(request.blueprint or "")
        if current_user.is_authenticated and module and ep.endswith(".edit"):
            read_only = not current_user.can(module, "write")
        return {"can": can, "read_only_page": read_only}

    @app.errorhandler(403)
    def forbidden(_e):
        return render_template("403.html"), 403
