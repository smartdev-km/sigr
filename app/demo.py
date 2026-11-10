"""Jeu de données de DÉMONSTRATION (fictif) : routes, ouvrages, diagnostics, travaux, entretien, marchés.

Les lieux et les routes sont réels (coordonnées OpenStreetMap) ; les noms d'entreprises, montants, dates,
inspecteurs et états sont inventés pour illustrer l'application. Lancer :  flask --app run seed-demo
"""
import json
import math
import urllib.request
from datetime import date, timedelta

from . import db
from .models import (Avenant, Diagnostic, Entreprise, Maintenance, Marche, Ouvrage, Paiement, Route, Work)

T = date.today()
DEMO_NOTE = "Donnée de démonstration."


def d(days):
    """Date relative à aujourd'hui (négatif = passé)."""
    return T + timedelta(days=days)


# --------------------------------------------------------------------------------------
# Routes : (code, nom, type, île, départ, arrivée, [étapes], état)   — coordonnées (lat, lng)
# --------------------------------------------------------------------------------------
P = {
    "Moroni": (-11.70403, 43.25191), "Mitsamiouli": (-11.38885, 43.29301), "Foumbouni": (-11.86545, 43.49516),
    "Hahaya": (-11.56445, 43.27132), "Itsandra": (-11.6828, 43.27482), "Mbeni": (-11.506, 43.38681),
    "Salimani": (-11.81085, 43.26899), "M'djoiezi Hambou": (-11.83627, 43.31316),
    "Mutsamudu": (-12.16885, 44.39428), "Domoni": (-12.25865, 44.52885), "Sima": (-12.19812, 44.27327),
    "Ouani": (-12.13399, 44.42727), "Pomoni": (-12.28362, 44.41012), "Moya": (-12.3099, 44.43716),
    "Fomboni": (-12.28405, 43.74273), "Nioumachoua": (-12.36445, 43.7179),
    "Wanani": (-12.34552, 43.80044), "Miringoni": (-12.30229, 43.63661),
}

ROUTES = [
    ("RN1", "Moroni – Mitsamiouli", "RN", "Grande Comore", "Moroni", "Mitsamiouli", ["Hahaya"], "moyen"),
    ("RN2", "Moroni – Foumbouni", "RN", "Grande Comore", "Moroni", "Foumbouni", ["M'djoiezi Hambou"], "mauvais"),
    ("RN3", "Mutsamudu – Domoni", "RN", "Anjouan", "Mutsamudu", "Domoni", [], "moyen"),
    ("RN4", "Fomboni – Nioumachoua", "RN", "Mohéli", "Fomboni", "Nioumachoua", [], "mauvais"),
    ("RR1", "Itsandra – Hahaya", "RR", "Grande Comore", "Itsandra", "Hahaya", [], "bon"),
    ("RR2", "Sima – Ouani", "RR", "Anjouan", "Sima", "Ouani", [], "mauvais"),
    ("RR3", "Wanani – Miringoni", "RR", "Mohéli", "Wanani", "Miringoni", [], "moyen"),
    ("RR4", "Mbeni – Mitsamiouli", "RR", "Grande Comore", "Mbeni", "Mitsamiouli", [], "bon"),
    ("SR1", "Salimani – M'djoiezi Hambou", "SR", "Grande Comore", "Salimani", "M'djoiezi Hambou", [], "mauvais"),
    ("SR2", "Pomoni – Moya", "SR", "Anjouan", "Pomoni", "Moya", [], "critique"),
]

# --------------------------------------------------------------------------------------
# Ouvrages : (route, position 0..1 le long de la route, type, côté, long. m, larg. m, nb, matériau, état,
#             [désordres], année, dernière inspection (jours passés ou None), observations)
# --------------------------------------------------------------------------------------
OUVRAGES = [
    ("RN1", .12, "dalot", "axe", 8, 2.0, 2, "beton", "bon", [], 2012, 60, "Dalot double sous la chaussée."),
    ("RN1", .35, "buse", "gauche", 7, .8, 1, "beton", "moyen", ["obstruction"], 2005, 200, "Ensablement partiel de l'entrée."),
    ("RN1", .58, "pont", "axe", 22, 7.5, 1, "beton", "moyen", ["fissures"], 1998, 120, "Pont sur ravine : fissures sur le tablier."),
    ("RN1", .80, "caniveau", "droite", 180, .5, 1, "beton", "mauvais", ["obstruction", "effondrement"], 2008, 300, "Caniveau bouché sur plusieurs tronçons."),
    ("RN2", .20, "radier", "axe", 30, 6.0, 1, "beton", "mauvais", ["erosion", "fissures"], 2001, 90, "Radier affouillé en aval."),
    ("RN2", .45, "buse", "droite", 8, 1.0, 2, "metal", "critique", ["corrosion", "effondrement"], 1995, 400, "Buses métalliques corrodées : risque d'effondrement."),
    ("RN2", .70, "dalot", "axe", 9, 2.5, 3, "beton", "moyen", ["vegetation"], 2010, 45, "Triple dalot, végétation dans le lit."),
    ("RN3", .30, "ponceau", "axe", 6, 1.5, 1, "maconnerie", "moyen", ["fissures"], 1990, 250, "Ponceau en maçonnerie ancienne."),
    ("RN3", .65, "fosse", "gauche", 250, 1.2, 1, "terre", "mauvais", ["obstruction", "debordement"], None, None, "Fossé non curé : débordement à chaque pluie."),
    ("RN4", .40, "dalot", "axe", 8, 2.0, 2, "beton", "bon", [], 2025, 20, "Ouvrage neuf, réceptionné récemment."),
    ("RN4", .75, "buse", "gauche", 7, .8, 1, "beton", "mauvais", ["obstruction", "erosion"], 2003, 380, "Sortie affouillée."),
    ("RR2", .50, "pont", "axe", 15, 6.0, 1, "maconnerie", "mauvais", ["erosion", "effondrement"], 1985, 150, "Culée endommagée par la crue."),
    ("RR3", .55, "ponceau", "axe", 5, 1.2, 1, "beton", "moyen", ["vegetation"], 2014, 100, None),
    ("SR1", .50, "mur", "gauche", 40, 2.5, 1, "pierre", "mauvais", ["fissures", "effondrement"], 1992, 220, "Mur de soutènement fissuré côté mer."),
    ("SR2", .50, "buse", "axe", 6, .6, 1, "pvc", "critique", ["effondrement", "obstruction"], None, 30, "Buse écrasée : passage submersible."),
]

# --------------------------------------------------------------------------------------
# Diagnostics : (route, jours passés, inspecteur, état, revêtement, [désordres], action, observations)
# --------------------------------------------------------------------------------------
DIAGNOSTICS = [
    ("RN1", 400, "A. Said", "moyen", "bitume", ["fissures", "accotements"], "preventif", "Début de faïençage sur 3 km."),
    ("RN1", 45, "A. Said", "moyen", "bitume", ["fissures", "nids_de_poule", "drainage"], "rehabilitation", "Dégradation progressive : réhabilitation lancée."),
    ("RN2", 80, "M. Ahmed Ali", "mauvais", "bitume", ["nids_de_poule", "affaissement", "erosion", "accotements"], "rehabilitation", "Nombreux nids-de-poule et affaissements."),
    ("RN2", 10, "M. Ahmed Ali", "mauvais", "bitume", ["nids_de_poule", "affaissement", "erosion", "ouvrage"], "urgence", "Ouvrage endommagé au PK 9 : intervention d'urgence."),
    ("RN3", 150, "F. Houmadi", "moyen", "bitume", ["fissures", "drainage"], "curatif", "Drainage insuffisant."),
    ("RN4", 60, "F. Houmadi", "mauvais", "bitume", ["nids_de_poule", "erosion", "eboulement"], "rehabilitation", "Éboulements ponctuels en bord de falaise."),
    ("RR1", 30, "A. Said", "bon", "bitume", [], "aucune", "Route en bon état."),
    ("RR2", 20, "M. Ahmed Ali", "mauvais", "empierre", ["nids_de_poule", "erosion", "drainage", "eboulement"], "rehabilitation", "Chaussée très dégradée après les dernières pluies."),
    ("RR3", 500, "F. Houmadi", "moyen", "empierre", ["erosion", "vegetation"], "preventif", "Inspection ancienne : à refaire."),
    ("RR4", 110, "A. Said", "bon", "bitume", ["signalisation"], "preventif", "Signalisation à compléter."),
    ("SR1", 95, "M. Ahmed Ali", "mauvais", "terre", ["erosion", "drainage", "accotements"], "curatif", "Piste ravinée."),
    ("SR2", 15, "F. Houmadi", "critique", "terre", ["erosion", "eboulement", "drainage"], "urgence", "Passage submersible : route par endroits impraticable."),
]

# --------------------------------------------------------------------------------------
# Entreprises : (nom, sigle, RCCM, contact, téléphone, île, spécialités)
# --------------------------------------------------------------------------------------
ENTREPRISES = [
    ("Société Comorienne de Travaux Routiers", "SCTR", "KM-MRN-2009-B-0001", "Direction technique", "+269 000 00 01", "Grande Comore", "terrassement, enrobés, rechargement"),
    ("Hambou Bâtiment et Travaux Publics", "HBTP", "KM-MRN-2013-B-0002", "Chef de projet", "+269 000 00 02", "Grande Comore", "ouvrages d'art, dalots, béton armé"),
    ("Anjouan Génie Civil", "AGC", "KM-MUT-2011-B-0003", "Conducteur de travaux", "+269 000 00 03", "Anjouan", "entretien courant, assainissement"),
    ("Mohéli Routes et Ouvrages", "MRO", "KM-FOM-2016-B-0004", "Gérant", "+269 000 00 04", "Mohéli", "pistes, curage, signalisation"),
    ("Entreprise Générale des Comores", "EGC", "KM-MRN-2007-B-0005", "Direction générale", "+269 000 00 05", "Grande Comore", "routes, ponts, génie civil"),
]

# --------------------------------------------------------------------------------------
# Marchés : n°, objet, entreprise(sigle), bailleur, mode, statut, montant, signé (j), OS (j), délai (j),
#           avenants [(n°, j, objet, montant, jours)], paiements [(nature, n°, j, montant, statut, réf.)]
# --------------------------------------------------------------------------------------
MARCHES = [
    ("M-2026-001", "Réhabilitation de la RN1 Moroni – Mitsamiouli", "SCTR", "Financement extérieur", "ao_ouvert", "en_cours",
     480_000_000, -240, -215, 300,
     [(1, -90, "Travaux de drainage supplémentaires", 35_000_000, 30)],
     [("avance", "", -210, 72_000_000, "paye", "MAN-0101"), ("decompte", "1", -150, 95_000_000, "paye", "MAN-0145"),
      ("decompte", "2", -75, 80_000_000, "paye", "MAN-0188"), ("decompte", "3", -5, 60_000_000, "emis", "")]),
    ("M-2026-002", "Renforcement et reprise de la chaussée de la RN2", "EGC", "Budget de l'État", "ao_ouvert", "en_cours",
     620_000_000, -330, -300, 240, [],
     [("avance", "", -295, 93_000_000, "paye", "MAN-0077"), ("decompte", "1", -200, 120_000_000, "paye", "MAN-0120"),
      ("decompte", "2", -110, 110_000_000, "paye", "MAN-0171")]),
    ("M-2026-003", "Entretien courant du réseau de l'île d'Anjouan", "AGC", "Fonds d'entretien routier", "consultation", "en_cours",
     85_000_000, -120, -100, 365, [],
     [("avance", "", -95, 12_750_000, "paye", "MAN-0210"), ("decompte", "1", -30, 20_000_000, "paye", "MAN-0233")]),
    ("M-2025-014", "Construction de dalots sur la RN4 (Mohéli)", "MRO", "Budget de l'État", "ao_restreint", "reception_provisoire",
     140_000_000, -420, -400, 180,
     [(1, -250, "Ouvrage supplémentaire au PK 6", 8_000_000, 15)],
     [("avance", "", -395, 21_000_000, "paye", "MAN-0021"), ("decompte", "1", -300, 60_000_000, "paye", "MAN-0049"),
      ("decompte", "2", -200, 50_000_000, "paye", "MAN-0092"), ("solde", "3", -60, 9_800_000, "paye", "MAN-0198")]),
    ("M-2026-004", "Réfection de la RR2 Sima – Ouani", "AGC", "Financement extérieur", "ao_ouvert", "preparation",
     95_000_000, -20, None, 150, [], []),
]

# --------------------------------------------------------------------------------------
# Travaux : route, intitulé, nature, statut, avancement %, PK début/fin, budget, dépensé, marché, début (j), fin prévue (j),
#           fin réelle (j), maître d'œuvre
# --------------------------------------------------------------------------------------
TRAVAUX = [
    ("RN1", "Réhabilitation de la RN1 (Moroni – Mitsamiouli)", "rehabilitation", "en_cours", 55, 0, 34, 515_000_000, 250_000_000,
     "M-2026-001", -215, 115, None, "Bureau de contrôle DGRTR"),
    ("RN2", "Renforcement de la chaussée de la RN2", "renforcement", "en_cours", 38, 4, 38, 620_000_000, 323_000_000,
     "M-2026-002", -300, -25, None, "Bureau de contrôle DGRTR"),
    ("RN4", "Construction de dalots sur la RN4", "ouvrage", "receptionne", 100, 3, 8, 148_000_000, 140_800_000,
     "M-2025-014", -400, -190, -60, "Mission de contrôle indépendante"),
    ("RR2", "Réfection de la RR2 Sima – Ouani", "rehabilitation", "appel_offres", 0, None, None, 95_000_000, None,
     "M-2026-004", None, 150, None, "DGRTR – Anjouan"),
    ("SR2", "Traitement du passage submersible Pomoni – Moya", "drainage", "etude", 0, 2, 3, 28_000_000, None,
     None, None, 200, None, "DGRTR – Anjouan"),
    ("RN3", "Signalisation et sécurité de la RN3", "securite", "en_cours", 70, None, None, 24_000_000, 15_500_000,
     "M-2026-003", -90, 40, None, "DGRTR – Anjouan"),
]

# --------------------------------------------------------------------------------------
# Entretien : route, type, statut, titre, description, date prévue (j), réalisée (j), coût, entreprise(sigle)
# --------------------------------------------------------------------------------------
ENTRETIENS = [
    ("RN1", "nids_de_poule", "termine", None, "Traitement des nids-de-poule entre PK 12 et PK 18.", -60, -55, 3_200_000, "SCTR"),
    ("RN1", "caniveaux", "en_cours", None, "Curage des caniveaux de la traversée de Hahaya.", -5, None, 1_800_000, "SCTR"),
    ("RN2", "reprofilage", "planifie", None, "Reprofilage des zones affaissées, PK 4 à PK 9.", -12, None, 6_500_000, None),
    ("RN3", "signalisation", "termine", None, "Pose de panneaux de signalisation et de balises.", -45, -40, 2_400_000, "AGC"),
    ("RN3", "accotements", "planifie", None, "Reprise des accotements côté mer.", 20, None, 2_800_000, "AGC"),
    ("RR2", "assainissement", "planifie", "Réparation du pont de la RR2", "Réparation de la culée du pont endommagée par la crue.", -3, None, 9_000_000, None),
    ("RR3", "rechargement", "planifie", None, "Rechargement en latérite de la piste, PK 3 à PK 11.", 35, None, 4_200_000, "MRO"),
    ("SR1", "roulement", "annule", None, "Réfection de la couche de roulement (reportée faute de budget).", -30, None, None, None),
    ("SR2", "nids_de_poule", "planifie", None, "Comblement d'urgence des zones impraticables.", 7, None, 1_500_000, "AGC"),
    ("RR1", "accotements", "termine", None, "Entretien des accotements et fauchage.", -100, -92, 900_000, "SCTR"),
]


# =====================================================================================
#  Calcul d'itinéraire (même logique que le site : voiture et vélo, on garde le plus court)
# =====================================================================================
OSRM = {"car": "https://router.project-osrm.org/route/v1/driving/",
        "bike": "https://routing.openstreetmap.de/routed-bike/route/v1/driving/"}


def _haversine(a, b):
    r, p = 6371.0, math.pi / 180
    x = math.sin((b[0] - a[0]) * p / 2) ** 2 + math.cos(a[0] * p) * math.cos(b[0] * p) * math.sin((b[1] - a[1]) * p / 2) ** 2
    return 2 * r * math.asin(math.sqrt(x))


def _route_online(points):
    """[(lat, lng), ...] → (km, [[lng, lat], ...]) ou None si les services ne répondent pas."""
    coords = ";".join(f"{lng},{lat}" for lat, lng in points)
    best = None
    for profile, base in OSRM.items():
        try:
            req = urllib.request.Request(f"{base}{coords}?overview=full&geometries=geojson&continue_straight=true",
                                         headers={"User-Agent": "sigr-demo-seed"})
            data = json.load(urllib.request.urlopen(req, timeout=10))
            if data.get("code") == "Ok" and data.get("routes"):
                r = data["routes"][0]
                if best is None or r["distance"] < best[0]:
                    best = (r["distance"], r["geometry"]["coordinates"])
        except Exception:
            continue
    return (best[0] / 1000, best[1]) if best else None


def _compact(coords, limit=500):
    step = max(1, math.ceil(len(coords) / limit))
    out = [[round(c[0], 5), round(c[1], 5)] for c in coords[::step]]
    last = [round(coords[-1][0], 5), round(coords[-1][1], 5)]
    if out[-1] != last:
        out.append(last)
    return out


def _point_at(coords, frac):
    """Point (lat, lng) situé à la fraction `frac` de la longueur d'un tracé [[lng, lat], ...]."""
    seg = [_haversine((coords[i][1], coords[i][0]), (coords[i + 1][1], coords[i + 1][0])) for i in range(len(coords) - 1)]
    target, acc = frac * sum(seg), 0.0
    for i, s in enumerate(seg):
        if acc + s >= target and s > 0:
            t = (target - acc) / s
            return (coords[i][1] + t * (coords[i + 1][1] - coords[i][1]), coords[i][0] + t * (coords[i + 1][0] - coords[i][0]))
        acc += s
    return (coords[-1][1], coords[-1][0])


# =====================================================================================
#  Insertion
# =====================================================================================
def seed_demo(online=True, log=print):
    """Ajoute le jeu de démonstration (ignore ce qui existe déjà : même code / numéro / nom)."""
    n = {k: 0 for k in ("routes", "ouvrages", "diagnostics", "entreprises", "marches", "travaux", "entretiens")}
    geoms, length = {}, {}

    # ---- routes ----
    by_code = {}
    for code, name, rtype, island, a, b, vias, state in ROUTES:
        r = Route.query.filter_by(code=code).first()
        if r:
            by_code[code] = r
            if r.geometry:
                geoms[code] = json.loads(r.geometry)["coordinates"]
            length[code] = r.length_km
            continue
        pts = [P[a]] + [P[v] for v in vias] + [P[b]]
        res = _route_online(pts) if online else None
        if res:
            km, line = res
            geoms[code] = _compact(line)
        else:
            km = sum(_haversine(pts[i], pts[i + 1]) for i in range(len(pts) - 1)) * 1.35
            geoms[code] = [[lng, lat] for lat, lng in pts]
        length[code] = round(km, 1)
        r = Route(code=code, name=name, type=rtype, island=island, length_km=length[code], condition=state,
                  start_point=a, end_point=b, start_lat=P[a][0], start_lng=P[a][1], end_lat=P[b][0], end_lng=P[b][1],
                  waypoints=json.dumps([{"lat": P[v][0], "lng": P[v][1], "name": v} for v in vias], ensure_ascii=False) if vias else None,
                  geometry=json.dumps({"type": "LineString", "coordinates": geoms[code]}, separators=(",", ":")) if res else None,
                  notes=DEMO_NOTE)
        db.session.add(r)
        by_code[code] = r
        n["routes"] += 1
        log(f"  route {code} · {name} · {length[code]} km{'' if res else ' (estimation hors-ligne)'}")
    db.session.flush()

    # ---- ouvrages ----
    if Ouvrage.query.count() == 0:
        for (code, frac, kind, side, ln, wd, qty, mat, cond, defs, year, insp, note) in OUVRAGES:
            r = by_code[code]
            lat, lng = _point_at(geoms[code], frac)
            db.session.add(Ouvrage(route_id=r.id, kind=kind, side=side, pk_km=round(frac * length[code], 3), lat=round(lat, 6),
                                   lng=round(lng, 6), length_m=ln, width_m=wd, quantity=qty, material=mat, condition=cond,
                                   defects=json.dumps(defs), built_year=year,
                                   last_inspection=d(-insp) if insp is not None else None, notes=note))
            n["ouvrages"] += 1
        db.session.flush()
        for i, o in enumerate(Ouvrage.query.order_by(Ouvrage.id), 1):
            o.ref = f"OUV-{i:04d}"

    # ---- diagnostics (l'état de la route suit le plus récent) ----
    if Diagnostic.query.count() == 0:
        for (code, ago, who, cond, surf, defs, reco, note) in DIAGNOSTICS:
            db.session.add(Diagnostic(route_id=by_code[code].id, inspected_on=d(-ago), inspector=who, condition=cond,
                                      surface=surf, defects=json.dumps(defs), recommendation=reco, notes=note))
            n["diagnostics"] += 1
        db.session.flush()
        latest = {}
        for dg in Diagnostic.query.order_by(Diagnostic.inspected_on, Diagnostic.id):
            latest[dg.route_id] = dg.condition
        for r in by_code.values():
            if r.id in latest:
                r.condition = latest[r.id]

    # ---- entreprises ----
    ent = {}
    for (name, acr, rccm, contact, phone, island, spec) in ENTREPRISES:
        e = Entreprise.query.filter_by(name=name).first()
        if not e:
            e = Entreprise(name=name, acronym=acr, registration=rccm, contact_name=contact, phone=phone, island=island,
                           specialties=spec, approved=True, active=True, notes=DEMO_NOTE)
            db.session.add(e)
            n["entreprises"] += 1
        ent[acr] = e
    db.session.flush()

    # ---- marchés, avenants, paiements ----
    mk = {}
    for (num, title, acr, funder, mode, status, amount, signed, os_, delay, avs, pays) in MARCHES:
        m = Marche.query.filter_by(number=num).first()
        if not m:
            m = Marche(number=num, title=title, entreprise_id=ent[acr].id, funder=funder, mode=mode, status=status,
                       amount_kmf=amount, signed_on=d(signed), start_order_on=d(os_) if os_ is not None else None,
                       duration_days=delay, description=DEMO_NOTE)
            db.session.add(m)
            db.session.flush()
            for (an, aday, apurpose, aamount, adays) in avs:
                db.session.add(Avenant(marche_id=m.id, number=an, signed_on=d(aday), purpose=apurpose, amount_kmf=aamount,
                                       extra_days=adays))
            for (kind, pn, pday, pamount, pstatus, ref) in pays:
                db.session.add(Paiement(marche_id=m.id, kind=kind, number=pn or None, paid_on=d(pday), amount_kmf=pamount,
                                        status=pstatus, reference=ref or None))
            n["marches"] += 1
        mk[num] = m
    db.session.flush()

    # ---- travaux ----
    if Work.query.count() == 0:
        for (code, title, kind, status, prog, pk1, pk2, budget, spent, mnum, start, end_p, end_a, sup) in TRAVAUX:
            m = mk.get(mnum) if mnum else None
            db.session.add(Work(route_id=by_code[code].id, title=title, kind=kind, status=status, progress=prog, pk_start=pk1,
                                pk_end=pk2, budget_kmf=budget, spent_kmf=spent, marche_id=m.id if m else None,
                                contractor=m.entreprise.name if m else None, funder=m.funder if m else None,
                                supervisor=sup, start_date=d(start) if start is not None else None,
                                end_planned=d(end_p) if end_p is not None else None,
                                end_actual=d(end_a) if end_a is not None else None, description=DEMO_NOTE))
            n["travaux"] += 1

    # ---- entretien ----
    if Maintenance.query.count() == 0:
        from .models import MAINT_KINDS
        for (code, kind, status, title, desc, planned, done, cost, acr) in ENTRETIENS:
            db.session.add(Maintenance(route_id=by_code[code].id, kind=kind, status=status, title=title or MAINT_KINDS[kind],
                                       description=desc, planned_date=d(planned), done_date=d(done) if done is not None else None,
                                       cost_kmf=cost, contractor=ent[acr].name if acr else None,
                                       entreprise_id=ent[acr].id if acr else None))
            n["entretiens"] += 1

    # rattache l'entretien de signalisation de la RN3 à son chantier de signalisation (exemple de lien)
    wk = Work.query.filter_by(title="Signalisation et sécurité de la RN3").first()
    mt = Maintenance.query.join(Route).filter(Route.code == "RN3", Maintenance.kind == "signalisation").first()
    if wk and mt and mt.work_id is None:
        mt.work_id = wk.id

    db.session.commit()
    return n
