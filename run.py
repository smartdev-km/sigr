import os

from app import create_app

app = create_app()

# Port d'écoute : modifiez la valeur par défaut ici, ou lancez `PORT=8080 python run.py`.
PORT = int(os.environ.get("PORT", 5001))
HOST = os.environ.get("HOST", "127.0.0.1")

if __name__ == "__main__":
    # Mode debug : développement local uniquement (FLASK_DEBUG=0 pour le désactiver)
    app.run(host=HOST, port=PORT, debug=os.environ.get("FLASK_DEBUG", "1") == "1")
