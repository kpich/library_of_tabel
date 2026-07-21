"""Authentication: one user, one gate.

The gate is a single ``before_request`` on the app, not a ``@login_required``
per route. CLAUDE.md 7 calls for that explicitly, and the reason is worth
restating: the routes this app will grow -- ``/tab/<slug>``,
``/file/<slug>/<filename>`` -- serve third-party tab content, and one forgotten
decorator is one leaked tab. A default-deny gate cannot be forgotten, because
adding a route is not what turns protection on.

There is one user. No registry, no signup, no database: the single valid
identity is whatever ``USERNAME`` is configured to, and the password is checked
against the ``PASSWORD_HASH`` that ``make hash`` produced.
"""

import secrets
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    Flask,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask.typing import ResponseReturnValue
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash

#: Endpoints reachable without a session. Everything else is gated -- including
#: URLs that match no route at all.
#:
#: These are *endpoints*, not path prefixes, on purpose. ``startswith("/static")``
#: is the kind of test a future route can accidentally satisfy; an endpoint name
#: is exact. ``static`` is exempt because it serves only our own assets and
#: vendored open-source libraries -- never library content (CLAUDE.md 7).
EXEMPT_ENDPOINTS = frozenset({"auth.login", "static"})

#: Where a login with no valid destination lands. A path rather than
#: ``url_for("index")`` so that renaming the index endpoint -- PR 3 moves it
#: into a blueprint -- cannot silently break the redirect.
DEFAULT_NEXT = "/"

#: One message for every kind of failure. Which field was wrong is not the
#: visitor's business; distinguishing them hands out a username oracle.
BAD_CREDENTIALS = "Wrong username or password."

bp = Blueprint("auth", __name__)


class User(UserMixin):
    """The single user. ``id`` is the username -- there is nothing else to store."""

    def __init__(self, username: str) -> None:
        self.id = username


def init_auth(app: Flask) -> None:
    """Attach the login manager and the blanket gate to ``app``."""
    login_manager = LoginManager()
    # Only consulted by flask_login's own ``unauthorized`` path; the gate below
    # builds its redirect itself. Set anyway so the two never disagree.
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        # Fails closed: a signed cookie naming anyone other than the configured
        # user -- one left over from a previous USERNAME, say -- is not a login.
        if user_id == app.config["USERNAME"]:
            return User(user_id)
        return None

    @app.before_request
    def require_login() -> ResponseReturnValue | None:
        """Deny by default. Registered once; covers every route, forever."""
        if request.endpoint in EXEMPT_ENDPOINTS:
            return None
        if current_user.is_authenticated:
            return None
        # request.endpoint is None for a URL matching no route, and Flask runs
        # before_request handlers before dispatch raises the 404 -- so unknown
        # URLs land here too, which is how routes get protected before they are
        # written.
        return redirect(url_for("auth.login", next=_requested_path()))


@bp.route("/login", methods=["GET", "POST"])
def login() -> ResponseReturnValue:
    destination = safe_next(request.values.get("next"))

    if current_user.is_authenticated:
        return redirect(destination)

    if request.method == "POST":
        username = request.form.get("username", "")
        if _credentials_ok(username, request.form.get("password", "")):
            # remember=True: the phone is a first-class client (CLAUDE.md 7),
            # and re-typing a password on a touchscreen every time the browser
            # restarts is the kind of friction that gets auth disabled.
            login_user(User(username), remember=True)
            return redirect(destination)
        flash(BAD_CREDENTIALS)

    # The destination is re-emitted already validated, so nothing attacker-shaped
    # round-trips through the form.
    return render_template("login.html", next=destination)


@bp.get("/logout")
def logout() -> ResponseReturnValue:
    # GET rather than POST: forging it costs the victim a re-login and nothing
    # more, which does not justify a form on every page.
    logout_user()
    return redirect(url_for("auth.login"))


def _requested_path() -> str:
    """The path to come back to after logging in, query string included."""
    if request.query_string:
        return request.full_path
    # full_path always appends "?", which is noise on a path with no query.
    return request.path


def _credentials_ok(username: str, password: str) -> bool:
    config = current_app.config
    # Both halves always run -- no early return on a bad username -- so a wrong
    # username costs the same time as a wrong password. compare_digest works on
    # bytes so a non-ASCII submission is a mismatch, not a TypeError.
    username_ok = secrets.compare_digest(
        username.encode("utf-8"), str(config["USERNAME"]).encode("utf-8")
    )
    password_ok = check_password_hash(config["PASSWORD_HASH"], password)
    return username_ok and password_ok


def safe_next(target: str | None) -> str:
    """Return ``target`` only if it points back at this site.

    The gate hands out ``?next=`` itself, so the parameter is attacker-supplyable:
    a mailed ``/login?next=https://evil.example/`` would otherwise turn the login
    page into an open redirect that borrows this site's name. flask_login 0.6.3
    does not validate it for us.
    """
    if not target:
        return DEFAULT_NEXT
    # Browsers normalise backslashes to forward slashes, so "/\evil.example"
    # would leave as a path and arrive as the host "//evil.example".
    if "\\" in target or not target.startswith("/"):
        return DEFAULT_NEXT
    parts = urlsplit(target)
    if parts.scheme or parts.netloc:
        return DEFAULT_NEXT
    return target
