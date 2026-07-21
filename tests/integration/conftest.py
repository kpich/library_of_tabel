"""Shared fixtures.

The password hash is *generated*, not a literal, so the login route exercises
the real Werkzeug verify path rather than comparing two fixture strings. It is
computed once at import -- scrypt is deliberately slow, and it is the same hash
for every test.
"""

from flask import Flask
from flask.testing import FlaskClient
import pytest
from werkzeug.security import generate_password_hash

from app import create_app

USERNAME = "me"
PASSWORD = "correct-horse-battery-staple"

_PASSWORD_HASH = generate_password_hash(PASSWORD)


@pytest.fixture
def app() -> Flask:
    return create_app(
        {
            "SECRET_KEY": "test-key",
            "PASSWORD_HASH": _PASSWORD_HASH,
            "USERNAME": USERNAME,
            "TESTING": True,
        }
    )


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture
def logged_in(client: FlaskClient) -> FlaskClient:
    """A client that has already been through the real login form."""
    client.post("/login", data={"username": USERNAME, "password": PASSWORD})
    return client
