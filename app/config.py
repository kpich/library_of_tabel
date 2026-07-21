"""Configuration resolution.

Values resolve in this order, later sources overriding earlier ones:

  1. ``instance/config.py``   -- gitignored, never committed
  2. ``TL_*`` environment variables
  3. explicit overrides passed to :func:`create_app` (used by tests)

So the env var wins over the file, and tests win over both.

Nothing secret lives in this repo. ``config.example.py`` at the repo root
documents every key; real values go in ``instance/config.py`` or the
environment. The app refuses to start without a secret key and password hash
rather than falling back to a development default -- a silent dev secret
reaching a deployment is exactly the failure this guards against.
"""

from __future__ import annotations

from datetime import timedelta
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The library lives in a separate private repo, cloned alongside this one.
#: Overridden by TL_DATA_DIR -- the Makefile points it at ``samples/`` so the
#: app runs from a clean clone with no data repo present.
DEFAULT_DATA_DIR = REPO_ROOT.parent / "library_of_tabel_data"

#: Read from the environment as TL_<KEY>, stored in app.config as <KEY>.
_ENV_KEYS = ("SECRET_KEY", "PASSWORD_HASH", "USERNAME", "DATA_DIR")

#: Same, but coerced to a bool -- "TL_SESSION_COOKIE_SECURE=0" has to mean off,
#: and every environment variable is a non-empty string.
_ENV_BOOL_KEYS = ("SESSION_COOKIE_SECURE",)

_TRUTHY = frozenset({"1", "true", "yes", "on"})

#: Without these the app is either insecure or unopenable, so it will not boot.
_REQUIRED_KEYS = ("SECRET_KEY", "PASSWORD_HASH")

_MISSING_CONFIG_HELP = """\
Missing required configuration: {missing}

Set these as TL_* environment variables, or create instance/config.py:

    mkdir -p instance
    cp config.example.py instance/config.py
    make hash            # prints a PASSWORD_HASH line to paste in

instance/ is gitignored -- these values must never be committed.\
"""


class ConfigError(RuntimeError):
    """Raised at startup when required configuration is absent."""


def load_config(app, overrides: dict | None = None) -> None:
    """Populate ``app.config`` from the instance file, environment, overrides."""
    # First, so that every source below can override any of it.
    _set_cookie_policy(app)

    app.config.from_pyfile("config.py", silent=True)

    for key in _ENV_KEYS:
        value = os.environ.get(f"TL_{key}")
        if value:
            app.config[key] = value

    for key in _ENV_BOOL_KEYS:
        value = os.environ.get(f"TL_{key}")
        if value is not None:
            app.config[key] = value.strip().lower() in _TRUTHY

    if overrides:
        app.config.update(overrides)

    app.config.setdefault("USERNAME", "me")
    app.config.setdefault("DATA_DIR", DEFAULT_DATA_DIR)
    app.config["DATA_DIR"] = Path(app.config["DATA_DIR"]).expanduser().resolve()

    # Derived, so it waits until SESSION_COOKIE_SECURE has finished resolving.
    # setdefault, not assignment: an explicit REMEMBER_COOKIE_SECURE from any
    # source above stands.
    app.config.setdefault("REMEMBER_COOKIE_SECURE", app.config["SESSION_COOKIE_SECURE"])

    missing = [key for key in _REQUIRED_KEYS if not app.config.get(key)]
    if missing:
        raise ConfigError(_MISSING_CONFIG_HELP.format(missing=", ".join(missing)))


def _set_cookie_policy(app) -> None:
    """Session/remember cookie policy.

    Called before every other source, so all of it stays overridable from
    ``instance/config.py``, a TL_* variable, or a test.

    Plain assignment rather than ``setdefault``, which would be a no-op here:
    Flask pre-populates its own ``SESSION_COOKIE_*`` keys (SAMESITE=None,
    SECURE=False), so those keys are never absent to begin with.
    """
    # SameSite=Lax is the login-CSRF mitigation: a cross-site POST cannot carry
    # these cookies. It is why there is no Flask-WTF here -- a CSRF dependency
    # for a single-user app whose only form is the login form is not the trade
    # CLAUDE.md 8 asks us to flag.
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"
    app.config["REMEMBER_COOKIE_HTTPONLY"] = True

    # The login outlives the browser session: the phone is a first-class client,
    # and a password re-typed on a touchscreen at every browser restart is the
    # friction that gets auth turned off.
    app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=30)

    # Off by default. Secure cookies over plain http are silently dropped, and
    # plain http is the whole of the README's local getting-started path -- the
    # failure would look like "login does nothing". PythonAnywhere is HTTPS, so
    # deploy sets TL_SESSION_COOKIE_SECURE=1 there (v3).
    app.config["SESSION_COOKIE_SECURE"] = False
