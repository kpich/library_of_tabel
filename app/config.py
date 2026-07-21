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

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: The library lives in a separate private repo, cloned alongside this one.
#: Overridden by TL_DATA_DIR -- the Makefile points it at ``samples/`` so the
#: app runs from a clean clone with no data repo present.
DEFAULT_DATA_DIR = REPO_ROOT.parent / "library_of_tabel_data"

#: Read from the environment as TL_<KEY>, stored in app.config as <KEY>.
_ENV_KEYS = ("SECRET_KEY", "PASSWORD_HASH", "USERNAME", "DATA_DIR")

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
    app.config.from_pyfile("config.py", silent=True)

    for key in _ENV_KEYS:
        value = os.environ.get(f"TL_{key}")
        if value:
            app.config[key] = value

    if overrides:
        app.config.update(overrides)

    app.config.setdefault("USERNAME", "me")
    app.config.setdefault("DATA_DIR", DEFAULT_DATA_DIR)
    app.config["DATA_DIR"] = Path(app.config["DATA_DIR"]).expanduser().resolve()

    missing = [key for key in _REQUIRED_KEYS if not app.config.get(key)]
    if missing:
        raise ConfigError(_MISSING_CONFIG_HELP.format(missing=", ".join(missing)))
