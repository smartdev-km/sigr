# Déploiement sur Render

L'application est prête pour Render : `render.yaml` décrit le service web (Gunicorn) et la base PostgreSQL.

## 1. Mettre le code sur GitHub

Le dossier `SIGR` doit être **son propre dépôt Git** (à la racine du dépôt, pas dans un dossier parent) :

```bash
cd ~/Desktop/SIGR
git init
git add .
git commit -m "SIGR-COMORES"
git branch -M main
git remote add origin https://github.com/<vous>/sigr-comores.git
git push -u origin main
```

`.gitignore` exclut déjà `.venv/`, `instance/` (base SQLite locale) et `.env`.

## 2. Créer les services

1. Render → **New + → Blueprint** → choisir le dépôt.
2. Render lit `render.yaml` et crée **sigr-comores** (web) et **sigr-db** (PostgreSQL).
3. Renseigner `ADMIN_PASSWORD` quand c'est demandé (8 caractères minimum).
4. **Apply** : le premier déploiement installe les dépendances, crée les tables, crée l'administrateur puis démarre.

`SECRET_KEY` est généré automatiquement et `DATABASE_URL` est relié à la base.

## 3. Première connexion

- Identifiant : `ADMIN_USERNAME` (par défaut `admin`), mot de passe : `ADMIN_PASSWORD`.
- L'administrateur n'est pas obligé de changer son mot de passe (il peut le faire quand il veut dans **Mon profil**).
- L'administrateur n'est créé que si aucun administrateur n'existe : modifier `ADMIN_PASSWORD` plus tard ne change pas un compte existant.
- Les autres comptes se créent ensuite dans **Utilisateurs**.

## Variables d'environnement

| Variable | Rôle |
|---|---|
| `APP_ENV=production` | cookies sécurisés (HTTPS), refuse une clé secrète par défaut |
| `SECRET_KEY` | clé de session (générée par Render) |
| `DATABASE_URL` | connexion PostgreSQL (fournie par la base Render) |
| `ADMIN_USERNAME` / `ADMIN_NAME` / `ADMIN_PASSWORD` | premier administrateur |
| `SEED_DEMO` | `1` = ajoute les données de démonstration au démarrage (sans doublon) ; `0` par défaut |
| `PYTHON_VERSION` | version de Python (3.12.8) |

## Données de démonstration (facultatif)

La base Render démarre vide. Pour y mettre les données fictives de démonstration : dans le service, **Environment**,
passer `SEED_DEMO` à `1`, enregistrer (redéploiement), puis remettre `SEED_DEMO` à `0`. La commande est idempotente
(aucun doublon). Le service gratuit n'a pas de terminal (« Shell »), d'où cette variable.

## Points d'attention

- **Base gratuite** : la base PostgreSQL gratuite de Render est supprimée après 30 jours. Pour un usage réel, choisir un plan payant (`plan:` dans `render.yaml`) avant le premier déploiement ou depuis le tableau de bord.
- **Service gratuit** : il se met en veille après 15 minutes sans visite (premier chargement lent ensuite).
- **Mises à jour** : chaque `git push` redéploie. Les nouvelles colonnes sont ajoutées automatiquement au démarrage (`init-db`).
- **Sauvegardes** : activer les sauvegardes de la base (plans payants) pour ne pas perdre les données.
- **Cartes** : les fonds de carte, le calcul d'itinéraire et la recherche de lieux utilisent des services publics (OpenStreetMap, OSRM, Nominatim), sans clé mais avec des limites d'usage. Pour un trafic important, prévoir des services dédiés.

## Test local en mode production (facultatif)

```bash
APP_ENV=production SECRET_KEY=test DATABASE_URL=postgresql://user:pass@localhost/sigr \
  flask --app run init-db && gunicorn run:app
```
