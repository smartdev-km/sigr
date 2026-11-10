# SIGR-COMORES

**Système Intégré de Gestion du Réseau routier** des Comores : une application web (Flask) pour inventorier,
cartographier, diagnostiquer et suivre l'entretien et les travaux des routes nationales (RN), régionales (RR)
et secondaires (SR) des trois îles (Grande Comore, Anjouan, Mohéli).

## Modules

| Module | Contenu |
|---|---|
| **Tableau de bord** | Vue d'ensemble du réseau : routes, linéaire, états, dernières routes ajoutées |
| **Routes** | Inventaire RN / RR / SR, état, départ, arrivée et points intermédiaires placés sur une carte ; la longueur se calcule d'après l'itinéraire routier |
| **Ouvrages** | Inventaire des ouvrages d'assainissement et de franchissement (buses, dalots, ponts, caniveaux…), localisés sur la carte avec calcul du PK |
| **Diagnostic** | Inspections de l'état des routes : désordres observés, action recommandée, historique |
| **Travaux** | Chantiers : statut, avancement, calendrier, budget, dépenses, lien avec un marché |
| **Entretien** | Interventions d'entretien (types du catalogue DGRTR), planification, suivi par type, coûts |
| **Marchés** | Entreprises, marchés, avenants et paiements (suivi des dépenses), export CSV |
| **Rapport** | Synthèse du réseau sur une période, impression / PDF et export CSV |
| **Carte** | Toutes les routes sur une carte, colorées par état ou type, avec couche des ouvrages |
| **Utilisateurs** | Comptes, rôles et permissions par module (administrateur) |

## Installation (développement)

Prérequis : Python 3.10 ou plus récent.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export FLASK_APP=run.py
flask init-db        # crée la base SQLite (instance/sigr.db) et met à jour les tables
flask create-admin   # crée le premier administrateur (identifiant et mot de passe demandés)
python run.py        # http://127.0.0.1:5000
```

Données de démonstration (fictives, voir `app/demo.py`) : `flask seed-demo` (`--offline` pour ne pas interroger
Internet). Elles ne sont jamais ajoutées automatiquement.

### Configuration

Variables d'environnement, à définir dans le terminal avant de lancer l'application :

| Variable | Rôle | Défaut |
|---|---|---|
| `PORT` / `HOST` | port et adresse d'écoute de `python run.py` | `5000` / `127.0.0.1` |
| `FLASK_DEBUG` | `0` désactive le mode debug de `run.py` | `1` |
| `DATABASE_URL` | base de données (PostgreSQL en production) | SQLite locale |
| `SECRET_KEY` | clé de session (**obligatoire en production**) | valeur de développement |
| `APP_ENV=production` | cookies sécurisés, refuse une clé secrète par défaut | — |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` / `ADMIN_NAME` | premier administrateur (`flask bootstrap-admin`) | — |

Sur Mac, le port 5000 peut être pris par AirPlay : utilisez par exemple `PORT=5001 python run.py`.

## Utilisateurs et permissions

- Un **administrateur** a tous les droits et gère les comptes.
- Les autres comptes reçoivent, pour chaque module, un niveau : *Aucun accès*, *Lecture seule* ou
  *Lecture et écriture*, plus un droit de suppression distinct. La consultation des routes est toujours possible.
- Un compte peut être désactivé, et le changement de mot de passe peut être imposé à la première connexion.
- Les droits sont contrôlés côté serveur (`app/access.py`), pas seulement masqués dans l'interface.

## Déploiement

Le projet est prêt pour Render (Gunicorn + PostgreSQL) : voir **[DEPLOY.md](DEPLOY.md)** et `render.yaml`.

## Structure

```
run.py              point d'entrée (serveur de développement)
config.py           configuration (base de données, cookies, production)
render.yaml         description du déploiement Render
app/
  __init__.py       création de l'application, commandes CLI, mise à jour du schéma
  models.py         modèles de données et listes de référence
  access.py         permissions par module
  routes.py  ouvrages.py  diagnostic.py  works.py  maintenance.py
  contracts.py      marchés, entreprises, avenants, paiements
  reports.py  map_view.py  users.py  profile.py  auth.py  dashboard.py
  demo.py           données de démonstration
  templates/  static/
```

## Services externes

Les fonds de carte (OpenStreetMap), la recherche de lieux (Nominatim) et le calcul d'itinéraire (OSRM) sont des
services publics appelés depuis le navigateur : ils nécessitent Internet et ont des limites d'usage. Les données
d'OpenStreetMap étant incomplètes pour certaines routes des Comores, les distances calculées sont des
**estimations** (la longueur reste modifiable à la main).

## Limites connues

- Pas de pièces jointes ni de photos, pas d'import en masse (Excel, GPS).
- Pas encore de programmation pluriannuelle, d'estimation des coûts (bordereau de prix), ni d'export SIG
  (GeoJSON, GeoPackage).
- Pas de découpage d'une route en tronçons.
- Pas de tests automatisés.
