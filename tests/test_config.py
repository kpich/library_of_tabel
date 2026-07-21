"""Config resolution, including the refusal to boot without credentials."""

from __future__ import annotations

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
