import csv
import io
from datetime import date, datetime, timedelta

from flask import Blueprint, Response, render_template, request
from flask_login import login_required

from .models import (CONDITIONS, ISLANDS, MAINT_KINDS, MAINT_STATUS, RECOMMENDATIONS, ROUTE_TYPES, WORK_KINDS,
                     WORK_OPEN_STATUS, WORK_STATUS, STRUCTURE_KINDS, MARCHE_STATUS, Diagnostic, Maintenance, Marche, Ouvrage, Paiement,
                     Route, Work)

bp = Blueprint("reports", __name__, url_prefix="/rapport")
SEVERITY = {k: i for i, k in enumerate(["critique", "mauvais", "moyen", "bon"])}  # tri : pire d'abord


def _date(name, default):
    try:
        return date.fromisoformat(request.args.get(name, ""))
    except ValueError:
        return default


def _filters():
    today = date.today()
    d_from = _date("from", date(today.year, 1, 1))
    d_to = _date("to", today)
    if d_from > d_to:
        d_from, d_to = d_to, d_from
    island = request.args.get("island", "")
    rtype = request.args.get("type", "")
    return {
        "from": d_from, "to": d_to,
        "island": island if island in ISLANDS else "",
        "type": rtype if rtype in ROUTE_TYPES else "",
    }


def build_report(flt):
    q = Route.query
    if flt["island"]:
        q = q.filter(Route.island == flt["island"])
    if flt["type"]:
        q = q.filter(Route.type == flt["type"])
    routes = q.order_by(Route.code).all()
    ids = {r.id for r in routes}
    d_from, d_to = flt["from"], flt["to"]

    maint = [m for m in Maintenance.query.all()
             if m.route_id in ids and d_from <= m.planned_date <= d_to]
    diags = [d for d in Diagnostic.query.all()
             if d.route_id in ids and d_from <= d.inspected_on <= d_to]
    works = [w for w in Work.query.all()
             if w.route_id in ids and w.status != "annule"
             and ((w.start_date and d_from <= w.start_date <= d_to) or (w.start_date is None and w.status in WORK_OPEN_STATUS))]

    # --- réseau ---
    def group(attr, keys):
        out = {k: {"count": 0, "km": 0.0, "bad": 0} for k in keys}
        for r in routes:
            g = out.setdefault(getattr(r, attr), {"count": 0, "km": 0.0, "bad": 0})
            g["count"] += 1
            g["km"] += r.length_km or 0
            g["bad"] += r.condition in ("mauvais", "critique")
        return out

    network = {
        "count": len(routes), "km": round(sum(r.length_km or 0 for r in routes), 1),
        "by_type": group("type", ROUTE_TYPES), "by_island": group("island", ISLANDS),
        "by_condition": {k: sum(1 for r in routes if r.condition == k) for k in CONDITIONS},
        "km_bad": round(sum(r.length_km or 0 for r in routes if r.condition in ("mauvais", "critique")), 1),
    }
    for g in list(network["by_type"].values()) + list(network["by_island"].values()):
        g["km"] = round(g["km"], 1)

    # --- diagnostics ---
    last_diag = {}
    for d in Diagnostic.query.order_by(Diagnostic.inspected_on, Diagnostic.id):
        if d.route_id in ids and d.inspected_on <= d_to:
            last_diag[d.route_id] = d
    diag = {
        "count": len(diags), "routes": len({d.route_id for d in diags}),
        "never": sum(1 for r in routes if r.id not in last_diag),
        "by_condition": {k: sum(1 for d in diags if d.condition == k) for k in CONDITIONS},
        "by_reco": {k: sum(1 for d in diags if d.recommendation == k) for k in RECOMMENDATIONS},
    }

    # --- entretien ---
    done = [m for m in maint if m.status == "termine"]
    maintenance = {
        "count": len(maint),
        "by_status": {k: sum(1 for m in maint if m.status == k) for k in MAINT_STATUS},
        "by_kind": {k: {"count": sum(1 for m in maint if m.kind == k),
                        "cost": sum(m.cost_kmf or 0 for m in done if m.kind == k)} for k in MAINT_KINDS},
        "cost": sum(m.cost_kmf or 0 for m in done),
        "late": sum(1 for m in maint if m.is_late),
    }

    # --- travaux ---
    wk = {
        "count": len(works),
        "by_status": {k: sum(1 for w in works if w.status == k) for k in WORK_STATUS if k != "annule"},
        "by_kind": {k: sum(1 for w in works if w.kind == k) for k in WORK_KINDS},
        "budget": sum(w.budget_kmf or 0 for w in works), "spent": sum(w.spent_kmf or 0 for w in works),
        "late": sum(1 for w in works if w.is_late), "over": sum(1 for w in works if w.over_budget),
        "avg": round(sum(w.progress for w in works if w.status == "en_cours") /
                     max(1, sum(1 for w in works if w.status == "en_cours"))),
    }

    # --- ouvrages (inventaire actuel des routes filtrées) ---
    ouv = [o for o in Ouvrage.query.all() if o.route_id in ids]
    stale_limit = date.today() - timedelta(days=365)
    ouvrages = {
        "count": len(ouv),
        "bad": sum(1 for o in ouv if o.condition in ("mauvais", "critique")),
        "stale": sum(1 for o in ouv if o.last_inspection is None or o.last_inspection < stale_limit),
        "by_kind": {k: {"count": sum(1 for o in ouv if o.kind == k),
                        "bad": sum(1 for o in ouv if o.kind == k and o.condition in ("mauvais", "critique"))}
                    for k in STRUCTURE_KINDS},
        "by_condition": {k: sum(1 for o in ouv if o.condition == k) for k in CONDITIONS},
    }
    o_by = {}
    for o in ouv:
        o_by.setdefault(o.route_id, []).append(o)

    # --- marchés et dépenses (indépendants du filtre île / type de route) ---
    all_m = [m for m in Marche.query.all()
             if (m.signed_on and d_from <= m.signed_on <= d_to) or (m.signed_on is None and m.status in ("preparation", "en_cours", "suspendu"))]
    spent_period = sum(p.amount_kmf for p in Paiement.query.filter(Paiement.status == "paye").all()
                       if d_from <= p.paid_on <= d_to)
    by_ent = {}
    for m in all_m:
        g = by_ent.setdefault(m.entreprise.name, {"count": 0, "amount": 0, "paid": 0})
        g["count"] += 1
        g["amount"] += m.current_amount
        g["paid"] += m.paid
    marches = {
        "count": len(all_m),
        "by_status": {k: sum(1 for m in all_m if m.status == k) for k in MARCHE_STATUS},
        "amount": sum(m.current_amount for m in all_m if m.status != "resilie"),
        "paid": sum(m.paid for m in all_m),
        "remaining": sum(m.remaining for m in all_m if m.status != "resilie"),
        "late": sum(1 for m in all_m if m.is_late),
        "over": sum(1 for m in all_m if m.over_budget),
        "spent_period": spent_period,
        "top": sorted(by_ent.items(), key=lambda kv: kv[1]["amount"], reverse=True)[:5],
    }

    # --- détail par route ---
    m_by, w_by = {}, {}
    for m in maint:
        m_by.setdefault(m.route_id, []).append(m)
    for w in works:
        w_by.setdefault(w.route_id, []).append(w)
    rows = []
    for r in routes:
        ms, ws, ld = m_by.get(r.id, []), w_by.get(r.id, []), last_diag.get(r.id)
        open_m = [m for m in Maintenance.query.filter_by(route_id=r.id) if m.status in ("planifie", "en_cours")]
        open_w = [w for w in Work.query.filter_by(route_id=r.id) if w.status in WORK_OPEN_STATUS]
        rows.append({
            "route": r, "last_diag": ld,
            "maint_n": len(ms), "maint_cost": sum(m.cost_kmf or 0 for m in ms if m.status == "termine"),
            "works_n": len(ws), "works_spent": sum(w.spent_kmf or 0 for w in ws),
            "ouv_n": len(o_by.get(r.id, [])),
            "ouv_bad": sum(1 for o in o_by.get(r.id, []) if o.condition in ("mauvais", "critique")),
            "pending": bool(open_m or open_w),
        })
    rows.sort(key=lambda x: (SEVERITY.get(x["route"].condition, 9), x["route"].code))
    priority = [x for x in rows if x["route"].condition in ("mauvais", "critique")]
    return {"routes": routes, "network": network, "diag": diag, "maint": maintenance, "works": wk, "ouvrages": ouvrages, "marches": marches,
            "rows": rows, "priority": priority}


@bp.route("/")
@login_required
def index():
    flt = _filters()
    rep = build_report(flt)
    args = {"from": flt["from"].isoformat(), "to": flt["to"].isoformat(),
            "island": flt["island"], "type": flt["type"]}
    return render_template("report.html", flt=flt, rep=rep, args={k: v for k, v in args.items() if v},
                           islands=ISLANDS, route_types=ROUTE_TYPES, conditions=CONDITIONS, kinds=MAINT_KINDS,
                           m_status=MAINT_STATUS, s_kinds=STRUCTURE_KINDS, mk_status=MARCHE_STATUS, w_status=WORK_STATUS, w_kinds=WORK_KINDS, recos=RECOMMENDATIONS,
                           now=datetime.now())


@bp.route("/export.csv")
@login_required
def export_csv():
    flt = _filters()
    rep = build_report(flt)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Code", "Nom", "Type", "Île", "Longueur (km)", "État", "Dernier diagnostic", "Action recommandée",
                "Entretiens (période)", "Coût entretien terminé (KMF)", "Chantiers (période)", "Dépensé chantiers (KMF)",
                "Intervention en cours/planifiée", "Ouvrages", "Ouvrages dégradés"])
    for x in rep["rows"]:
        r, d = x["route"], x["last_diag"]
        w.writerow([r.code, r.name, ROUTE_TYPES[r.type], r.island, str(round(r.length_km or 0, 1)).replace(".", ","),
                    CONDITIONS[r.condition], d.inspected_on.strftime("%d/%m/%Y") if d else "",
                    RECOMMENDATIONS[d.recommendation] if d else "", x["maint_n"], x["maint_cost"], x["works_n"],
                    x["works_spent"], "oui" if x["pending"] else "non", x["ouv_n"], x["ouv_bad"]])
    name = f"rapport-sigr-{flt['from']}_{flt['to']}.csv"
    return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})
