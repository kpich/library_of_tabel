"""The library, assembled and driven through a test client.

These run against the committed ``samples/`` -- the same shelf a clean clone
gets -- so they cover the path a first run actually takes. The tmp_path cases
below are the ones samples cannot express: an empty library, and a record that
is wrong.
"""

from collections.abc import Callable
from pathlib import Path

from flask.testing import FlaskClient
import pytest
import yaml

CHORDPRO_SLUG = "the-repeat-signs--kitchen-light"
GUITARPRO_SLUG = "the-repeat-signs--practice-loop"


def _text(response) -> str:
    return response.get_data(as_text=True)


def test_index_lists_every_sample(logged_in: FlaskClient) -> None:
    body = _text(logged_in.get("/"))

    assert "Kitchen Light" in body
    assert "Practice Loop" in body
    assert f"/tab/{CHORDPRO_SLUG}" in body


def test_index_survives_an_empty_library(
    logged_in_against: Callable[[Path], FlaskClient], tmp_path: Path
) -> None:
    """A clean clone with no data repo beside it must still render a page."""
    response = logged_in_against(tmp_path).get("/")

    assert response.status_code == 200
    assert "Nothing here yet" in _text(response)


def test_index_skips_a_broken_record_and_shows_the_rest(
    logged_in_against: Callable[[Path], FlaskClient], tmp_path: Path
) -> None:
    good = tmp_path / "library" / "good--entry"
    good.mkdir(parents=True)
    (good / "meta.yaml").write_text(
        yaml.safe_dump(
            {
                "title": "Good",
                "artist": "A",
                "format": "chordpro",
                "files": ["tab.chordpro"],
            }
        ),
        encoding="utf-8",
    )
    (good / "tab.chordpro").write_text("[G]fine", encoding="utf-8")
    broken = tmp_path / "library" / "broken--entry"
    broken.mkdir(parents=True)
    (broken / "meta.yaml").write_text("title: [unclosed", encoding="utf-8")

    response = logged_in_against(tmp_path).get("/")

    assert response.status_code == 200
    assert "Good" in _text(response)


def test_detail_page_shows_the_record_and_the_chordpro(logged_in: FlaskClient) -> None:
    body = _text(logged_in.get(f"/tab/{CHORDPRO_SLUG}"))

    assert "Kitchen Light" in body
    assert "EADGBE" in body
    assert "92 bpm" in body
    # The document itself is inlined for PR 4's parser to pick up in place.
    assert "{start_of_chorus}" in body


def test_detail_page_carries_the_hooks_the_renderers_need(
    logged_in: FlaskClient,
) -> None:
    """PRs 4-5 attach to these; alphaTab in particular fetches data-file itself."""
    body = _text(logged_in.get(f"/tab/{GUITARPRO_SLUG}"))

    assert f'data-file="/file/{GUITARPRO_SLUG}/score.musicxml"' in body
    assert 'data-format="guitarpro"' in body


@pytest.mark.parametrize("slug", ["nobody--home", "not a slug", "..", "%2e%2e"])
def test_unknown_slug_is_a_404(logged_in: FlaskClient, slug: str) -> None:
    assert logged_in.get(f"/tab/{slug}").status_code == 404


def test_file_serves_the_chordpro_as_text(logged_in: FlaskClient) -> None:
    # `with`, here and below, because send_file hands back a response holding an
    # open file. A real WSGI server closes it; the test client only does so on
    # response.close(), and the leak surfaces as a ResourceWarning, which this
    # suite treats as an error.
    with logged_in.get(f"/file/{CHORDPRO_SLUG}/tab.chordpro") as response:
        assert response.status_code == 200
        # The whole header, not response.mimetype: mimetype drops parameters,
        # so it reads "text/plain" just as happily off the malformed
        # "text/plain; charset=utf-8; charset=utf-8" that a mimetype carrying
        # its own charset produces, Flask having appended a second one.
        assert response.headers["Content-Type"] == "text/plain; charset=utf-8"
        assert "{title: Kitchen Light}" in _text(response)


def test_file_serves_the_score_as_xml(logged_in: FlaskClient) -> None:
    """alphaTab gets bytes with a type it will accept, not octet-stream."""
    with logged_in.get(f"/file/{GUITARPRO_SLUG}/score.musicxml") as response:
        assert response.status_code == 200
        assert response.mimetype == "application/xml"
        assert _text(response).startswith("<?xml")


def test_file_declares_that_its_type_is_not_to_be_guessed(
    logged_in: FlaskClient,
) -> None:
    with logged_in.get(f"/file/{CHORDPRO_SLUG}/tab.chordpro") as response:
        assert response.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize(
    "path",
    [
        # Not listed in files:, though it sits in the same directory.
        f"/file/{CHORDPRO_SLUG}/meta.yaml",
        f"/file/{CHORDPRO_SLUG}/does-not-exist.txt",
        # Wrong entry's file.
        f"/file/{CHORDPRO_SLUG}/score.musicxml",
        "/file/nobody--home/tab.chordpro",
        # Traversal, in the shapes that survive URL normalisation.
        f"/file/{CHORDPRO_SLUG}/..%2f..%2fCLAUDE.md",
        f"/file/{CHORDPRO_SLUG}/%2e%2e%2fmeta.yaml",
        "/file/../CLAUDE.md",
    ],
)
def test_file_refuses_anything_the_record_does_not_own(
    logged_in: FlaskClient, path: str
) -> None:
    response = logged_in.get(path)

    assert response.status_code in (301, 308, 404), path
    if response.status_code == 200:  # pragma: no cover - guarded by the assert
        raise AssertionError(f"{path} served content")


@pytest.mark.parametrize(
    "path",
    [
        "/",
        f"/tab/{CHORDPRO_SLUG}",
        f"/file/{CHORDPRO_SLUG}/tab.chordpro",
        f"/file/{GUITARPRO_SLUG}/score.musicxml",
    ],
)
def test_every_real_route_is_still_gated(client: FlaskClient, path: str) -> None:
    """auth_test.py asserted this against routes that did not exist yet. Now they do."""
    response = client.get(path)

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/login")
