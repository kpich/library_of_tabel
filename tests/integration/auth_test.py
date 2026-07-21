"""The auth gate is the security boundary of the whole app.

So these tests ask "is anything reachable?", not "is this route decorated?".
Several of the gated paths below do not exist yet -- they arrive in PRs 3-5 --
and that is exactly the point: the gate has to cover a route before the route
is written, or the first forgotten decorator leaks a tab.
"""

from urllib.parse import parse_qs, urlsplit

from flask import Flask
from flask.testing import FlaskClient
import pytest

from tests.integration.conftest import PASSWORD, USERNAME

#: Anonymous requests to all of these must land on /login.
GATED_PATHS = [
    "/",  # exists today
    "/tab/some-slug",  # PR 3
    "/file/some-slug/tab.chordpro",  # PR 3
    "/api/search?q=anything",  # PR 4
    "/matches-no-route-at-all",
]


def _location_path(response) -> str:
    return urlsplit(response.headers["Location"]).path


@pytest.mark.parametrize("path", GATED_PATHS)
def test_anonymous_request_is_sent_to_login(client: FlaskClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 302
    assert _location_path(response) == "/login"


def test_a_route_added_without_a_decorator_is_still_gated(app: Flask) -> None:
    """The whole reason the gate is structural rather than per-route."""

    @app.get("/added-later")
    def added_later() -> str:
        return "a tab"

    response = app.test_client().get("/added-later")

    assert response.status_code == 302
    assert _location_path(response) == "/login"


def test_login_page_is_reachable_anonymously(client: FlaskClient) -> None:
    assert client.get("/login").status_code == 200


def test_static_is_exempt_from_the_gate(client: FlaskClient) -> None:
    # 404, not a redirect: the exemption is live even with no such file. Were
    # /static/ gated, the vendored renderers would 302 to the login page and
    # every tab would fail to draw.
    assert client.get("/static/does-not-exist.css").status_code == 404


def test_correct_credentials_open_the_app(client: FlaskClient) -> None:
    response = client.post("/login", data={"username": USERNAME, "password": PASSWORD})

    assert response.status_code == 302
    assert client.get("/").status_code == 200


@pytest.mark.parametrize(
    "username, password",
    [
        (USERNAME, "not-the-password"),
        ("not-the-user", PASSWORD),
        ("not-the-user", "not-the-password"),
        (USERNAME, ""),
        ("", ""),
        # Non-ASCII must be a plain mismatch, not a 500 out of compare_digest.
        ("mé", PASSWORD),
    ],
)
def test_bad_credentials_are_refused(
    client: FlaskClient, username: str, password: str
) -> None:
    response = client.post("/login", data={"username": username, "password": password})

    assert response.status_code == 200
    assert client.get("/").status_code == 302


def test_failure_does_not_reveal_which_field_was_wrong(app: Flask) -> None:
    # Separate clients: flashes live in the session, and reusing one client
    # would let the first message colour the second response.
    wrong_user = app.test_client().post(
        "/login", data={"username": "not-the-user", "password": PASSWORD}
    )
    wrong_password = app.test_client().post(
        "/login", data={"username": USERNAME, "password": "not-the-password"}
    )

    assert wrong_user.get_data() == wrong_password.get_data()


def test_logout_closes_the_app_again(logged_in: FlaskClient) -> None:
    assert logged_in.get("/").status_code == 200

    logged_in.get("/logout")

    assert logged_in.get("/").status_code == 302


def test_session_naming_another_user_is_not_a_login(client: FlaskClient) -> None:
    """A cookie left over from a different USERNAME must fail closed."""
    with client.session_transaction() as session:
        session["_user_id"] = "somebody-else"

    assert client.get("/").status_code == 302


def test_gate_remembers_where_you_were_going(client: FlaskClient) -> None:
    response = client.get("/tab/a-slug")

    query = parse_qs(urlsplit(response.headers["Location"]).query)
    assert query["next"] == ["/tab/a-slug"]


def test_gate_preserves_the_query_string(client: FlaskClient) -> None:
    response = client.get("/api/search?q=hallelujah")

    query = parse_qs(urlsplit(response.headers["Location"]).query)
    assert query["next"] == ["/api/search?q=hallelujah"]


def test_login_returns_you_to_where_you_were_going(client: FlaskClient) -> None:
    response = client.post(
        "/login?next=/tab/a-slug",
        data={"username": USERNAME, "password": PASSWORD},
    )

    assert _location_path(response) == "/tab/a-slug"


@pytest.mark.parametrize(
    "target",
    [
        "https://evil.example/",
        "http://evil.example",
        "//evil.example/",
        # Browsers fold backslashes into forward slashes, so this would leave
        # as a path and arrive as a host.
        "/\\evil.example/",
        "javascript:alert(1)",
        "not-even-a-path",
    ],
)
def test_off_site_next_is_refused(client: FlaskClient, target: str) -> None:
    """The gate hands out ?next= itself, so it is attacker-supplyable."""
    response = client.post(
        "/login",
        data={"username": USERNAME, "password": PASSWORD, "next": target},
    )

    assert response.headers["Location"] == "/"


def test_already_logged_in_visitor_is_moved_along(logged_in: FlaskClient) -> None:
    response = logged_in.get("/login")

    assert response.status_code == 302
    assert response.headers["Location"] == "/"


def test_login_is_remembered_beyond_the_browser_session(client: FlaskClient) -> None:
    """remember=True is what keeps the phone from re-prompting constantly."""
    response = client.post("/login", data={"username": USERNAME, "password": PASSWORD})

    cookies = response.headers.getlist("Set-Cookie")
    assert any(cookie.startswith("remember_token=") for cookie in cookies)
