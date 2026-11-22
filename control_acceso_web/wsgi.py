"""Punto de entrada.

Local:      python wsgi.py           (abre http://127.0.0.1:5000)
En la nube: gunicorn wsgi:app        (lo usa Render automáticamente)
"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # En local no hay https: la cookie de sesión no debe exigirlo
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("COOKIE_SEGURA", "0") == "1"
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("DEBUG") == "1")
