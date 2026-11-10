from datetime import date, timedelta

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import func

from . import db
from .models import (CONDITIONS, ISLANDS, MAINT_KINDS, ROUTE_TYPES, WORK_OPEN_STATUS, Diagnostic, Maintenance, Marche,
                     Ouvrage, Route, Work)

bp = Blueprint("dashboard", __name__)
STALE_DAYS = 365


def compute_stats():
    """Statistiques « routes » (utilisées par /api/stats)."""
    total_count, total_km = db.session.query(
        func.count(Route.id), func.coalesce(func.sum(Route.length_km), 0)
    ).one()
    by_type = {t: {"count": 0, "km": 0.0} for t in ROUTE_TYPES}
    for t, c, km in db.session.query(Route.type, func.count(), func.sum(Route.length_km)).group_by(Route.type):
        by_type[t] = {"count": c, "km": round(km or 0, 1)}
    by_condition = {k: 0 for k in CONDITIONS}
    for k, c in db.session.query(Route.condition, func.count()).group_by(Route.condition):
        by_condition[k] = c
    by_island = {i: {"count": 0, "km": 0.0} for i in ISLANDS}
    for i, c, km in db.session.query(Route.island, func.count(), func.sum(Route.length_km)).group_by(Route.island):
        by_island[i] = {"count": c, "km": round(km or 0, 1)}
    return {"total_count": total_count, "total_km": round(total_km, 1),
            "to_maintain": by_condition["mauvais"] + by_condition["critique"],
            "by_type": by_type, "by_condition": by_condition, "by_island": by_island}


def build_dashboard(user, island=""):
    """Tout ce que le tableau de bord affiche, limité aux modules que l'utilisateur peut lire."""
    today = date.today()
    can = user.can
    routes = Route.query.filter(Route.island == island).all() if island else Route.query.all()
    ids = {r.id for r in routes}
    km = sum(r.length_km or 0 for r in routes)
    bad = [r for r in routes if r.condition in ("mauvais", "critique")]
    km_bad = sum(r.length_km or 0 for r in bad)

    def group(attr, keys):
        out = {k: {"count": 0, "km": 0.0, "bad": 0} for k in keys}
        for r in routes:
            g = out.setdefault(getattr(r, attr), {"count": 0, "km": 0.0, "bad": 0})
            g["count"] += 1
            g["km"] += r.length_km or 0
            g["bad"] += r.condition in ("mauvais", "critique")
        for g in out.values():
            g["km"] = round(g["km"], 1)
        return out

    data = {
        "island": island,
        "routes": {
            "count": len(routes), "km": round(km, 1), "bad": len(bad), "km_bad": round(km_bad, 1),
            "bad_pct": round(100 * km_bad / km) if km else 0,
            "by_cond": {k: sum(1 for r in routes if r.condition == k) for k in CONDITIONS},
            "by_type": group("type", ROUTE_TYPES), "by_island": group("island", ISLANDS),
            "recent": (Route.query.filter(Route.island == island) if island else Route.query)
            .order_by(Route.created_at.desc(), Route.id.desc()).limit(6).all(),
        },
    }

    # ---- éléments ouverts par route (pour repérer les routes dégradées sans action prévue) ----
    open_m = {m.route_id for m in Maintenance.query.filter(Maintenance.status.in_(("planifie", "en_cours"))).all()}
    open_w = {w.route_id for w in Work.query.filter(Work.status.in_(WORK_OPEN_STATUS)).all()}
    untreated = [r for r in bad if r.id not in open_m and r.id not in open_w]

    alerts = []

    def add(level, text, count, url, module):
        if count:
            alerts.append({"level": level, "text": text, "count": count, "url": url, "module": module})

    from flask import url_for
    crit = [r for r in routes if r.condition == "critique"]
    add("critical", "Routes en état critique", len(crit), url_for("routes.index", condition="critique"), "routes")
    add("critical" if crit else "warning", "Routes dégradées sans intervention ni chantier en cours", len(untreated),
        url_for("routes.index", sort="condition", order="desc"), "routes")

    # ---- ouvrages ----
    if can("ouvrages"):
        ov = [o for o in Ouvrage.query.all() if o.route_id in ids]
        ov_bad = [o for o in ov if o.condition in ("mauvais", "critique")]
        limit = today - timedelta(days=STALE_DAYS)
        ov_stale = [o for o in ov if o.last_inspection is None or o.last_inspection < limit]
        data["ouvrages"] = {"count": len(ov), "bad": len(ov_bad),
                            "critical": sum(1 for o in ov if o.condition == "critique")}
        add("critical", "Ouvrages en état critique", data["ouvrages"]["critical"],
            url_for("ouvrages.index", condition="critique"), "ouvrages")
        add("warning", "Ouvrages en mauvais état", data["ouvrages"]["bad"] - data["ouvrages"]["critical"],
            url_for("ouvrages.index", condition="mauvais"), "ouvrages")
        add("info", "Ouvrages à inspecter (> 1 an ou jamais)", len(ov_stale), url_for("ouvrages.index"), "ouvrages")

    # ---- diagnostics ----
    if can("diagnostic"):
        last = {}
        for dg in Diagnostic.query.order_by(Diagnostic.inspected_on, Diagnostic.id):
            if dg.route_id in ids:
                last[dg.route_id] = dg
        never = [r for r in routes if r.id not in last]
        stale = [r for r in routes if r.id in last and (today - last[r.id].inspected_on).days > STALE_DAYS]
        data["diagnostics"] = {"inspected": len(last), "never": len(never), "stale": len(stale),
                               "recent": [dg for dg in Diagnostic.query.order_by(
                                   Diagnostic.inspected_on.desc(), Diagnostic.id.desc()).limit(40).all()
                                   if dg.route_id in ids][:5]}
        crit_pts = sum(1 for dg in last.values() for i in dg.issues if i.severity == "critique")
        add("critical", "Points ou secteurs critiques signalés", crit_pts, url_for("diagnostic.index"), "diagnostic")
        add("info", "Routes jamais diagnostiquées", len(never), url_for("diagnostic.index"), "diagnostic")
        add("info", "Routes à réinspecter (> 1 an)", len(stale), url_for("diagnostic.index"), "diagnostic")

    # ---- travaux ----
    if can("travaux"):
        ws = [w for w in Work.query.all() if w.route_id in ids and w.status != "annule"]
        active = sorted([w for w in ws if w.status == "en_cours"], key=lambda w: -(w.budget_kmf or 0))
        budget = sum(w.budget_kmf or 0 for w in ws)
        spent = sum(w.spent_kmf or 0 for w in ws)
        data["works"] = {
            "count": len(ws), "active": len(active), "done": sum(1 for w in ws if w.status == "receptionne"),
            "late": sum(1 for w in ws if w.is_late), "over": sum(1 for w in ws if w.over_budget),
            "budget": budget, "spent": spent, "spent_pct": round(100 * spent / budget) if budget else 0,
            "avg": round(sum(w.progress for w in active) / len(active)) if active else 0, "top": active[:5],
        }
        add("critical", "Chantiers en retard", data["works"]["late"], url_for("works.index"), "travaux")
        add("warning", "Chantiers au-dessus du budget", data["works"]["over"], url_for("works.index"), "travaux")

    # ---- entretien ----
    if can("entretien"):
        ms = [m for m in Maintenance.query.all() if m.route_id in ids]
        late = sorted([m for m in ms if m.is_late], key=lambda m: m.planned_date)
        upcoming = sorted([m for m in ms if m.status in ("planifie", "en_cours") and not m.is_late],
                          key=lambda m: m.planned_date)
        data["maintenance"] = {
            "planned": sum(1 for m in ms if m.status == "planifie"), "ongoing": sum(1 for m in ms if m.status == "en_cours"),
            "late": len(late), "done": sum(1 for m in ms if m.status == "termine"),
            "next": (late + upcoming)[:5], "kinds": MAINT_KINDS,
        }
        add("warning", "Interventions d'entretien en retard", len(late), url_for("maintenance.index"), "entretien")

    # ---- marchés ----
    if can("marches"):
        mk = Marche.query.all()
        live = [m for m in mk if m.status != "resilie"]
        amount = sum(m.current_amount for m in live)
        paid = sum(m.paid for m in mk)
        data["marches"] = {
            "count": len(mk), "active": sum(1 for m in mk if m.status == "en_cours"),
            "amount": amount, "paid": paid, "pending": sum(m.pending for m in mk),
            "remaining": amount - sum(m.paid for m in live), "paid_pct": round(100 * paid / amount) if amount else 0,
            "late": sum(1 for m in mk if m.is_late), "over": sum(1 for m in mk if m.over_budget),
        }
        add("critical", "Marchés en retard", data["marches"]["late"], url_for("marches.index"), "marches")
        add("warning", "Marchés payés au-delà du montant", data["marches"]["over"], url_for("marches.index"), "marches")

    order = {"critical": 0, "warning": 1, "info": 2}
    data["alerts"] = sorted(alerts, key=lambda a: order[a["level"]])
    return data


@bp.route("/")
@login_required
def index():
    island = request.args.get("island", "")
    island = island if island in ISLANDS else ""
    carte = None
    if current_user.can("carte"):
        from .map_view import _payload
        carte = [r for r in _payload() if r["a"] and (not island or r["island"] == island)]
    return render_template("dashboard.html", d=build_dashboard(current_user, island), islands=ISLANDS,
                           route_types=ROUTE_TYPES, conditions=CONDITIONS, carte=carte, today=date.today())


@bp.route("/api/stats")
@login_required
def api_stats():
    return jsonify(compute_stats())
