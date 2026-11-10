#!/usr/bin/env bash
# Démarrage sur Render : prépare la base, crée l'administrateur, puis lance le serveur.
set -e

flask --app run init-db            # crée / met à jour les tables
flask --app run bootstrap-admin    # crée le 1er administrateur s'il n'y en a pas

if [ "$SEED_DEMO" = "1" ]; then    # données de démonstration (facultatif, sans doublon)
  # en arrière-plan : le site démarre tout de suite, les données arrivent ~1 minute plus tard
  flask --app run seed-demo &
fi

exec gunicorn run:app --bind "0.0.0.0:${PORT:-10000}" --workers 2 --threads 4 --timeout 60 --access-logfile -
