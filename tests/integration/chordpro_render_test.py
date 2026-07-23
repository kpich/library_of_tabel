"""The chordpro detail page carries the hooks ChordSheetJS renders from.

The formatting and transpose happen in the browser (js/chordpro.js), so the server
side can only assert the page is wired correctly: the vendored library and our
wiring script are referenced, both same-origin; the transpose control is present;
and the raw ChordPro is still inlined as the no-JavaScript fallback. That the
vendored bundle is fetchable is asserted here too, so a broken path fails the
suite rather than only the browser.
"""

from flask.testing import FlaskClient

CHORDPRO_SLUG = "the-repeat-signs--kitchen-light"
VENDOR_SRC = "/static/vendor/chordsheetjs/chordsheetjs.min.js"
WIRING_SRC = "/static/js/chordpro.js"


def _text(response) -> str:
    return response.get_data(as_text=True)


def test_page_references_the_vendored_library_and_wiring(
    logged_in: FlaskClient,
) -> None:
    body = _text(logged_in.get(f"/tab/{CHORDPRO_SLUG}"))

    assert VENDOR_SRC in body
    assert WIRING_SRC in body


def test_page_carries_the_transpose_control(logged_in: FlaskClient) -> None:
    body = _text(logged_in.get(f"/tab/{CHORDPRO_SLUG}"))

    assert 'class="transpose"' in body
    assert 'data-transpose="1"' in body
    assert 'data-transpose="-1"' in body


def test_page_still_inlines_the_source_as_a_fallback(logged_in: FlaskClient) -> None:
    """With JavaScript off the readable ChordPro must remain on the page."""
    body = _text(logged_in.get(f"/tab/{CHORDPRO_SLUG}"))

    assert '<pre class="chordpro source">' in body
    assert "{start_of_chorus}" in body


def test_every_script_is_same_origin(logged_in: FlaskClient) -> None:
    """The v0 exit criterion is zero external requests; no script may point off-site."""
    body = _text(logged_in.get(f"/tab/{CHORDPRO_SLUG}"))

    assert 'src="http' not in body
    assert 'src="//' not in body


def test_vendored_bundle_is_served(logged_in: FlaskClient) -> None:
    # `with`, because the static route hands back a response holding an open file;
    # the leak would otherwise surface as a ResourceWarning, which the suite errors on.
    with logged_in.get(VENDOR_SRC) as response:
        assert response.status_code == 200
        assert "ChordSheetJS" in _text(response)


def test_static_assets_are_public_by_design(client: FlaskClient) -> None:
    """/static is gate-exempt (CLAUDE.md 7): vendored code and our own assets only,
    never library content -- so serving them unauthenticated is intended."""
    for path in (VENDOR_SRC, WIRING_SRC):
        with client.get(path) as response:
            assert response.status_code == 200, path
