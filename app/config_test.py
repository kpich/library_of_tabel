"""Config resolution, including the refusal to boot without credentials."""

import pytest

from app import create_app
from app.config import ConfigError

VALID = {"SECRET_KEY": "test-key", "PASSWORD_HASH": "test-hash"}


def test_app_builds_with_required_config() -> None:
    app = create_app(VALID)
    assert app.config["SECRET_KEY"] == "test-key"


@pytest.mark.parametrize("missing", sorted(VALID))
def test_app_refuses_to_boot_without_required_key(
    missing: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(f"TL_{missing}", raising=False)
    config = {k: v for k, v in VALID.items() if k != missing}

    with pytest.raises(ConfigError) as excinfo:
        create_app(config)

    # The error has to be actionable, not just correct.
    assert missing in str(excinfo.value)
    assert "make hash" in str(excinfo.value)


def test_env_var_beats_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TL_USERNAME", "from-env")
    assert create_app(VALID).config["USERNAME"] == "from-env"


def test_explicit_override_beats_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TL_USERNAME", "from-env")
    app = create_app(VALID | {"USERNAME": "from-override"})
    assert app.config["USERNAME"] == "from-override"


def test_data_dir_is_resolved_to_absolute_path() -> None:
    app = create_app(VALID | {"DATA_DIR": "samples"})
    assert app.config["DATA_DIR"].is_absolute()


def test_cookies_default_to_samesite_lax() -> None:
    # The login-CSRF mitigation we get in place of a CSRF dependency.
    app = create_app(VALID)
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert app.config["REMEMBER_COOKIE_SAMESITE"] == "Lax"


def test_cookie_policy_stays_overridable() -> None:
    # The policy is applied before every other source precisely so this works.
    app = create_app(VALID | {"SESSION_COOKIE_SAMESITE": "Strict"})
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Strict"


def test_secure_cookies_are_off_by_default() -> None:
    # On would silently break login over plain http, which is the whole of the
    # local getting-started path. PythonAnywhere turns it on via TL_* (v3).
    assert create_app(VALID).config["SESSION_COOKIE_SECURE"] is False


@pytest.mark.parametrize(
    "value, expected",
    [("1", True), ("true", True), ("on", True), ("0", False), ("false", False)],
)
def test_secure_cookie_env_var_is_read_as_a_bool(
    value: str, expected: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Every environment variable is a non-empty string, so "0" must not be True.
    monkeypatch.setenv("TL_SESSION_COOKIE_SECURE", value)
    app = create_app(VALID)
    assert app.config["SESSION_COOKIE_SECURE"] is expected
    assert app.config["REMEMBER_COOKIE_SECURE"] is expected
