"""The Flask app.

One app serves the UI, the library files, and (from v1) the search. Everything
attaches to the factory below; ``wsgi.py`` is the PythonAnywhere entry point.
"""

from flask import Flask

from . import auth
from .config import load_config


def create_app(config: dict | None = None) -> Flask:
    """Build the app. ``config`` overrides everything, for tests."""
    app = Flask(__name__, instance_relative_config=True)
    load_config(app, config)

    # Before any blueprint, so that everything registered after this point is
    # gated by default rather than by remembering to gate it.
    auth.init_auth(app)
    app.register_blueprint(auth.bp)

    # Placeholder until PR 3 registers the real views blueprint. It exists so
    # that `make run` proves the app boots and config resolved.
    @app.get("/")
    def index() -> str:
        return f"library of tabel -- reading library from {app.config['DATA_DIR']}\n"

    return app
