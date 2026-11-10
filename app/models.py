from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from . import db, login_manager

ROUTE_TYPES = {
    "RN": "Route nationale",
    "RR": "Route régionale",
    "SR": "Route secondaire",
}

ISLANDS = ["Grande Comore", "Anjouan", "Mohéli"]

# (sud, ouest, nord, est) approximatifs de chaque île
ISLAND_BOUNDS = {
    "Grande Comore": (-12.03, 43.13, -11.30, 43.62),
    "Anjouan": (-12.46, 44.12, -12.04, 44.68),
    "Mohéli": (-12.50, 43.52, -12.20, 43.90),
}

# Ordre = du meilleur au pire état
CONDITIONS = {
    "bon": "Bon",
    "moyen": "Moyen",
    "mauvais": "Mauvais",
    "critique": "Critique",
}


# Types d'interventions (catalogue DGRTR)
CATALOG_KINDS = {
    "reprofilage": "Reprofilage de chaussée",
    "rechargement": "Rechargement en matériaux",
    "roulement": "Réfection de la couche de roulement",
    "nids_de_poule": "Traitement des nids-de-poule",
    "caniveaux": "Curage des caniveaux",
    "assainissement": "Réparation des ouvrages d'assainissement",
    "accotements": "Entretien des accotements",
    "signalisation": "Signalisation et sécurité routière",
}
# Natures générales (déjà existantes)
GENERAL_KINDS = {
    "preventif": "Préventif",
    "curatif": "Curatif",
    "rehabilitation": "Réhabilitation",
    "urgence": "Urgence",
}
MAINT_KINDS = {**CATALOG_KINDS, **GENERAL_KINDS}

MAINT_STATUS = {
    "planifie": "Planifié",
    "en_cours": "En cours",
    "termine": "Terminé",
    "annule": "Annulé",
}


SURFACES = {
    "bitume": "Bitume / enrobé",
    "beton": "Béton",
    "pave": "Pavé",
    "empierre": "Empierrée / latérite",
    "terre": "Terre / piste",
}

DEFECTS = {
    "nids_de_poule": "Nids-de-poule",
    "fissures": "Fissures / faïençage",
    "affaissement": "Affaissement",
    "erosion": "Érosion / ravinement",
    "drainage": "Drainage défaillant",
    "accotements": "Accotements dégradés",
    "signalisation": "Signalisation manquante",
    "vegetation": "Végétation envahissante",
    "eboulement": "Éboulement / obstruction",
    "ouvrage": "Ouvrage d'art endommagé",
}

ISSUE_SEVERITY = {"mineur": "Mineur", "important": "Important", "critique": "Critique"}

RECOMMENDATIONS = {
    "aucune": "Aucune action",
    "preventif": "Entretien préventif",
    "curatif": "Entretien curatif",
    "rehabilitation": "Réhabilitation",
    "urgence": "Intervention d'urgence",
}


WORK_KINDS = {
    "construction": "Construction neuve",
    "rehabilitation": "Réhabilitation",
    "renforcement": "Renforcement / revêtement",
    "elargissement": "Élargissement",
    "ouvrage": "Ouvrage d'art (pont, dalot)",
    "drainage": "Drainage / assainissement",
    "securite": "Signalisation / sécurité",
}

WORK_STATUS = {
    "etude": "Étude",
    "appel_offres": "Appel d'offres",
    "en_cours": "En cours",
    "suspendu": "Suspendu",
    "receptionne": "Réceptionné",
    "annule": "Annulé",
}
WORK_OPEN_STATUS = ("etude", "appel_offres", "en_cours", "suspendu")  # non terminés


MODULES = {
    "routes": "Routes",
    "ouvrages": "Ouvrages",
    "carte": "Carte",
    "diagnostic": "Diagnostic",
    "travaux": "Travaux",
    "entretien": "Entretien",
    "marches": "Marchés",
    "rapport": "Rapport",
}
LEVELS = {"none": "Aucun accès", "read": "Lecture seule", "write": "Lecture et écriture"}
_RANK = {"none": 0, "read": 1, "write": 2}


STRUCTURE_KINDS = {
    "buse": "Buse",
    "dalot": "Dalot",
    "ponceau": "Ponceau",
    "caniveau": "Caniveau",
    "fosse": "Fossé",
    "radier": "Radier",
    "regard": "Regard / avaloir",
    "pont": "Pont / ouvrage d'art",
    "mur": "Mur de soutènement",
}
STRUCTURE_MATERIALS = {
    "beton": "Béton",
    "maconnerie": "Maçonnerie",
    "metal": "Métal",
    "pvc": "PVC / plastique",
    "pierre": "Pierre sèche",
    "terre": "Terre / enherbé",
}
STRUCTURE_DEFECTS = {
    "obstruction": "Obstruction / ensablement",
    "erosion": "Affouillement / érosion",
    "fissures": "Fissures",
    "effondrement": "Effondrement partiel",
    "corrosion": "Corrosion",
    "vegetation": "Végétation envahissante",
    "debordement": "Débordement fréquent",
}


MARCHE_STATUS = {
    "preparation": "En préparation",
    "en_cours": "En cours d'exécution",
    "suspendu": "Suspendu",
    "reception_provisoire": "Réception provisoire",
    "reception_definitive": "Réception définitive",
    "resilie": "Résilié",
}
MARCHE_OPEN_STATUS = ("preparation", "en_cours", "suspendu")
MARCHE_MODES = {
    "ao_ouvert": "Appel d'offres ouvert",
    "ao_restreint": "Appel d'offres restreint",
    "consultation": "Consultation / demande de prix",
    "gre_a_gre": "Gré à gré (entente directe)",
    "regie": "Régie",
}
PAIEMENT_KINDS = {
    "avance": "Avance de démarrage",
    "decompte": "Décompte",
    "retenue": "Libération de la retenue de garantie",
    "solde": "Solde / décompte final",
}
PAIEMENT_STATUS = {"emis": "Émis (en attente de paiement)", "paye": "Payé"}


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="agent")  # admin | agent
    email = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    job_title = db.Column(db.String(120))
    organization = db.Column(db.String(120))
    island = db.Column(db.String(40))
    bio = db.Column(db.Text)
    is_active_account = db.Column(db.Boolean, nullable=False, default=True)
    permissions = db.Column(db.Text)                  # JSON {module: none|read|write}
    can_delete = db.Column(db.Boolean, default=False)  # droit de suppression (les admins l'ont toujours)
    must_change_password = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # --- permissions par module (JSON {module: none|read|write}) ---
    def perm_dict(self):
        import json
        try:
            raw = json.loads(self.permissions) if self.permissions else None
        except ValueError:
            raw = None
        if not isinstance(raw, dict):   # comptes antérieurs aux permissions : accès complet (sans suppression)
            raw = {m: "write" for m in MODULES}
        return {m: (raw.get(m) if raw.get(m) in LEVELS else "none") for m in MODULES}

    def level(self, module):
        if self.is_admin:
            return "write"
        lvl = self.perm_dict().get(module, "none")
        return "read" if (module == "routes" and lvl == "none") else lvl  # tout le monde consulte les routes

    def can(self, module, need="read"):
        return _RANK[self.level(module)] >= _RANK[need]

    @property
    def may_delete(self):
        return self.is_admin or bool(self.can_delete)

    @property
    def role_label(self):
        return "Administrateur" if self.is_admin else "Utilisateur"

    @property
    def is_active(self):  # utilisé par Flask-Login
        return self.is_active_account

    @property
    def is_admin(self):
        return self.role == "admin"


class Route(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    type = db.Column(db.String(2), nullable=False, index=True)  # RN | RR | SR
    island = db.Column(db.String(40), nullable=False, index=True)
    length_km = db.Column(db.Float, nullable=False, default=0)
    condition = db.Column(db.String(20), nullable=False, default="moyen")
    start_point = db.Column(db.String(120))
    end_point = db.Column(db.String(120))
    start_lat = db.Column(db.Float)
    start_lng = db.Column(db.Float)
    end_lat = db.Column(db.Float)
    end_lng = db.Column(db.Float)
    geometry = db.Column(db.Text)   # tracé routier mis en cache : GeoJSON LineString
    waypoints = db.Column(db.Text)  # JSON : [{"lat":…, "lng":…, "name":…}, …] points intermédiaires
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    @property
    def has_points(self):
        return self.start_lat is not None and self.end_lat is not None

    @property
    def waypoint_list(self):
        import json
        try:
            return json.loads(self.waypoints) if self.waypoints else []
        except ValueError:
            return []


class Maintenance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey("route.id"), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False, default="curatif")
    status = db.Column(db.String(20), nullable=False, default="planifie", index=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    planned_date = db.Column(db.Date, nullable=False)
    done_date = db.Column(db.Date)
    pk_start = db.Column(db.Float)      # localisation sur la route (km depuis le début), facultative
    pk_end = db.Column(db.Float)
    cost_kmf = db.Column(db.BigInteger)
    contractor = db.Column(db.String(160))                         # nom de l'intervenant (copie du nom de l'entreprise)
    entreprise_id = db.Column(db.Integer, db.ForeignKey("entreprise.id"), index=True)
    work_id = db.Column(db.Integer, db.ForeignKey("work.id"), index=True)   # chantier auquel l'intervention se rattache (facultatif)
    condition_after = db.Column(db.String(20))  # état de la route après travaux
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    entreprise = db.relationship("Entreprise", backref="maintenances")
    work = db.relationship("Work", backref=db.backref("maintenances", order_by="Maintenance.planned_date.desc()"))
    route = db.relationship("Route", backref=db.backref("maintenances", cascade="all, delete-orphan",
                                                         order_by="Maintenance.planned_date.desc()"))

    @property
    def is_late(self):
        from datetime import date
        return self.status == "planifie" and self.planned_date < date.today()


class Diagnostic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey("route.id"), nullable=False, index=True)
    inspected_on = db.Column(db.Date, nullable=False, index=True)
    inspector = db.Column(db.String(120))
    condition = db.Column(db.String(20), nullable=False)
    surface = db.Column(db.String(20))
    defects = db.Column(db.Text)  # JSON : liste de clés de DEFECTS
    recommendation = db.Column(db.String(20), nullable=False, default="aucune")
    notes = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    route = db.relationship("Route", backref=db.backref("diagnostics", cascade="all, delete-orphan",
                                                         order_by="Diagnostic.inspected_on.desc(), Diagnostic.id.desc()"))

    @property
    def defect_list(self):
        import json
        try:
            return [d for d in json.loads(self.defects or "[]") if d in DEFECTS]
        except ValueError:
            return []


class Work(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey("route.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    kind = db.Column(db.String(20), nullable=False, default="rehabilitation")
    status = db.Column(db.String(20), nullable=False, default="etude", index=True)
    progress = db.Column(db.Integer, nullable=False, default=0)  # avancement physique, %
    pk_start = db.Column(db.Float)  # point kilométrique de début (km)
    pk_end = db.Column(db.Float)
    budget_kmf = db.Column(db.BigInteger)
    spent_kmf = db.Column(db.BigInteger)
    funder = db.Column(db.String(160))      # bailleur / financement
    contractor = db.Column(db.String(160))  # entreprise
    supervisor = db.Column(db.String(160))  # maître d'œuvre / mission de contrôle
    start_date = db.Column(db.Date)
    end_planned = db.Column(db.Date)
    end_actual = db.Column(db.Date)
    description = db.Column(db.Text)
    marche_id = db.Column(db.Integer, db.ForeignKey("marche.id"), index=True)   # marché d'exécution (facultatif)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    marche = db.relationship("Marche", backref="works")
    route = db.relationship("Route", backref=db.backref("works", cascade="all, delete-orphan",
                                                         order_by="Work.start_date.desc()"))

    @property
    def is_late(self):
        from datetime import date
        return self.status in WORK_OPEN_STATUS and self.end_planned is not None and self.end_planned < date.today()

    @property
    def over_budget(self):
        return bool(self.budget_kmf and self.spent_kmf and self.spent_kmf > self.budget_kmf)


class Entreprise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False, unique=True, index=True)
    acronym = db.Column(db.String(30))
    registration = db.Column(db.String(60))     # RCCM / NIF
    contact_name = db.Column(db.String(120))
    phone = db.Column(db.String(40))
    email = db.Column(db.String(120))
    address = db.Column(db.String(200))
    island = db.Column(db.String(40))
    specialties = db.Column(db.String(200))     # ex. terrassement, ouvrages d'art
    approved = db.Column(db.Boolean, default=True)   # agréée / référencée
    active = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    @property
    def label(self):
        return f"{self.name} ({self.acronym})" if self.acronym else self.name


class Marche(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(40), nullable=False, unique=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    entreprise_id = db.Column(db.Integer, db.ForeignKey("entreprise.id"), nullable=False, index=True)
    funder = db.Column(db.String(160))
    mode = db.Column(db.String(20))
    status = db.Column(db.String(25), nullable=False, default="preparation", index=True)
    amount_kmf = db.Column(db.BigInteger, nullable=False, default=0)   # montant initial
    signed_on = db.Column(db.Date)
    start_order_on = db.Column(db.Date)                                # ordre de service de démarrage
    duration_days = db.Column(db.Integer)                              # délai d'exécution
    description = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    entreprise = db.relationship("Entreprise", backref="marches")
    amendments = db.relationship("Avenant", backref="marche", cascade="all, delete-orphan",
                                 order_by="Avenant.signed_on, Avenant.id")
    payments = db.relationship("Paiement", backref="marche", cascade="all, delete-orphan",
                               order_by="Paiement.paid_on, Paiement.id")

    @property
    def amendments_total(self):
        return sum(a.amount_kmf or 0 for a in self.amendments)

    @property
    def current_amount(self):
        return (self.amount_kmf or 0) + self.amendments_total

    @property
    def total_days(self):
        if self.duration_days is None:
            return None
        return self.duration_days + sum(a.extra_days or 0 for a in self.amendments)

    @property
    def planned_end(self):
        from datetime import timedelta
        if self.start_order_on and self.total_days is not None:
            return self.start_order_on + timedelta(days=self.total_days)
        return None

    @property
    def paid(self):
        return sum(p.amount_kmf or 0 for p in self.payments if p.status == "paye")

    @property
    def pending(self):
        return sum(p.amount_kmf or 0 for p in self.payments if p.status == "emis")

    @property
    def remaining(self):
        return self.current_amount - self.paid

    @property
    def paid_rate(self):
        return round(100 * self.paid / self.current_amount) if self.current_amount else 0

    @property
    def is_late(self):
        from datetime import date
        end = self.planned_end
        return self.status in ("en_cours", "suspendu") and end is not None and end < date.today()

    @property
    def over_budget(self):
        return self.current_amount > 0 and self.paid > self.current_amount


class Avenant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    marche_id = db.Column(db.Integer, db.ForeignKey("marche.id"), nullable=False, index=True)
    number = db.Column(db.Integer, nullable=False, default=1)
    signed_on = db.Column(db.Date)
    purpose = db.Column(db.String(200))
    amount_kmf = db.Column(db.BigInteger, default=0)       # peut être négatif (moins-value)
    extra_days = db.Column(db.Integer, default=0)          # prolongation du délai
    created_at = db.Column(db.DateTime, default=utcnow)


class Paiement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    marche_id = db.Column(db.Integer, db.ForeignKey("marche.id"), nullable=False, index=True)
    kind = db.Column(db.String(15), nullable=False, default="decompte")
    number = db.Column(db.String(20))                      # n° de décompte
    paid_on = db.Column(db.Date, nullable=False)
    amount_kmf = db.Column(db.BigInteger, nullable=False)
    status = db.Column(db.String(10), nullable=False, default="paye")
    reference = db.Column(db.String(80))                   # mandat / virement / chèque
    notes = db.Column(db.String(300))
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=utcnow)


class Ouvrage(db.Model):
    """Ouvrage d'assainissement ou de franchissement rattaché à une route."""
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey("route.id"), nullable=False, index=True)
    ref = db.Column(db.String(30), index=True)           # référence (auto : OUV-0001)
    kind = db.Column(db.String(20), nullable=False, index=True)
    pk_km = db.Column(db.Float)                          # point kilométrique depuis le début de la route
    side = db.Column(db.String(10))                      # gauche | droite | axe
    lat = db.Column(db.Float)
    lng = db.Column(db.Float)
    length_m = db.Column(db.Float)
    width_m = db.Column(db.Float)                        # largeur ou diamètre
    quantity = db.Column(db.Integer, nullable=False, default=1)  # nombre de files / de buses
    material = db.Column(db.String(20))
    condition = db.Column(db.String(20), nullable=False, default="moyen", index=True)
    defects = db.Column(db.Text)                         # JSON : clés de STRUCTURE_DEFECTS
    built_year = db.Column(db.Integer)
    last_inspection = db.Column(db.Date)
    notes = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    route = db.relationship("Route", backref=db.backref("ouvrages", cascade="all, delete-orphan",
                                                         order_by="Ouvrage.pk_km"))

    @property
    def defect_list(self):
        import json
        try:
            return [d for d in json.loads(self.defects or "[]") if d in STRUCTURE_DEFECTS]
        except ValueError:
            return []

    @property
    def has_point(self):
        return self.lat is not None and self.lng is not None


class DiagnosticIssue(db.Model):
    """Point ou secteur à problème signalé dans un diagnostic (ex. « du PK 4 au PK 6 : affaissement »)."""
    id = db.Column(db.Integer, primary_key=True)
    diagnostic_id = db.Column(db.Integer, db.ForeignKey("diagnostic.id"), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False)       # clé de DEFECTS
    severity = db.Column(db.String(12), nullable=False, default="important")
    text = db.Column(db.String(300))
    pk_start = db.Column(db.Float)                       # km depuis le début de la route
    pk_end = db.Column(db.Float)                         # vide = point ; sinon secteur [pk_start, pk_end]
    start_lat = db.Column(db.Float)
    start_lng = db.Column(db.Float)
    end_lat = db.Column(db.Float)
    end_lng = db.Column(db.Float)

    diagnostic = db.relationship("Diagnostic", backref=db.backref(
        "issues", cascade="all, delete-orphan", order_by="DiagnosticIssue.pk_start, DiagnosticIssue.id"))

    @property
    def is_sector(self):
        return self.pk_end is not None and self.pk_start is not None and self.pk_end > self.pk_start

    @property
    def where(self):
        if self.pk_start is None:
            return "—"
        if self.is_sector:
            return f"PK {self.pk_start:.3f} → {self.pk_end:.3f} km ({(self.pk_end - self.pk_start) * 1000:.0f} m)"
        return f"PK {self.pk_start:.3f} km"

    def as_dict(self):
        return {"kind": self.kind, "severity": self.severity, "text": self.text or "", "pk_start": self.pk_start,
                "pk_end": self.pk_end, "start_lat": self.start_lat, "start_lng": self.start_lng,
                "end_lat": self.end_lat, "end_lng": self.end_lng}


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
