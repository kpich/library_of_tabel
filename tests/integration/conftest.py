"""Shared fixtures.

The password hash is *generated*, not a literal, so the login route exercises
the real Werkzeug verify path rather than comparing two fixture strings. It is
computed once at import -- scrypt is deliberately slow, and it is the same hash
for every test.

``DATA_DIR`` is always passed explicitly. It has to be: ``load_config`` reads
``TL_DATA_DIR`` from the environment, the Makefile exports it, and a bare
``pytest`` would therefore run the suite against whatever that variable happens
to hold -- on a working laptop, the real private data repo. Overrides beat the
environment (``app/config.py``), so naming it here makes the suite depend on
nothing outside the checkout. The default is the committed ``samples/``, which
means the shipped-sample path is the one the view tests cover.
"""

from collections.abc import Callable
from pathlib import Path

from flask import Flask
from flask.testing import FlaskClient
import pytest
from werkzeug.security import generate_password_hash

from app import create_app

USERNAME = "me"
PASSWORD = "correct-horse-battery-staple"

_PASSWORD_HASH = generate_password_hash(PASSWORD)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: What `make run` serves out of the box, and what a clean clone has.
SAMPLES_DIR = REPO_ROOT / "samples"


def build_app(data_dir: Path = SAMPLES_DIR) -> Flask:
    return create_app(
        {
            "SECRET_KEY": "test-key",
            "PASSWORD_HASH": _PASSWORD_HASH,
            "USERNAME": USERNAME,
            "DATA_DIR": data_dir,
            "TESTING": True,
        }
    )


def sign_in(client: FlaskClient) -> FlaskClient:
    client.post("/login", data={"username": USERNAME, "password": PASSWORD})
    return client


@pytest.fixture
def app() -> Flask:
    return build_app()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture
def logged_in(client: FlaskClient) -> FlaskClient:
    """A client that has already been through the real login form."""
    return sign_in(client)


@pytest.fixture
def logged_in_against() -> Callable[[Path], FlaskClient]:
    """A logged-in client against some other library -- an empty or broken one."""
    return lambda data_dir: sign_in(build_app(data_dir).test_client())
