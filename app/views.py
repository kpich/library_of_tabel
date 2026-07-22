"""The three routes that show the library.

No ``@login_required`` anywhere below, deliberately: ``auth.init_auth`` installs
a blanket ``before_request`` gate over the whole app (CLAUDE.md 7), so these are
protected by existing rather than by being decorated. ``/file`` in particular is
the route that hands out tab bytes -- it is gated because everything is.

Rendering is plain text here. ChordSheetJS arrives in PR 4 and alphaTab in PR 5;
both attach to the ``data-`` hooks in the templates, so neither needs this module
to change shape.
"""

from pathlib import Path

from flask import Blueprint, abort, current_app, render_template, send_from_directory
from flask.typing import ResponseReturnValue
from flask.wrappers import Response

from . import library

bp = Blueprint("views", __name__)

#: None of these are in the ``mimetypes`` registry, so Flask would guess
#: application/octet-stream and the browser would offer a download instead of
#: handing bytes to the renderer.
#:
#: Bare types only, no charset parameter: Flask appends its own to any text/*
#: response, and a mimetype that carries one arrives as the malformed
#: "text/plain; charset=utf-8; charset=utf-8".
MIMETYPES = {
    ".chordpro": "text/plain",
    ".musicxml": "application/xml",
    ".xml": "application/xml",
}

#: What anything else gets. The guitarpro lane's .gp3-.gp7 are binary formats
#: only alphaTab understands; there is no useful type to claim for them.
DEFAULT_MIMETYPE = "application/octet-stream"


@bp.get("/")
def index() -> ResponseReturnValue:
    entries = library.all_entries(_data_dir())
    return render_template("index.html", entries=entries)


@bp.get("/tab/<slug>")
def tab(slug: str) -> ResponseReturnValue:
    entry = library.load_entry(_data_dir(), slug)
    if entry is None:
        # Absent, malformed, or not a slug at all -- all 404 (see load_entry).
        abort(404)

    # The chordpro lane is text and small, so the document arrives with the page
    # rather than as a second request; PR 4 parses it out of the <pre> in place.
    # The guitarpro lane cannot work that way -- its artifacts are binary, and
    # alphaTab will fetch /file itself as bytes (ROADMAP, PR 5).
    content = _read_text(entry) if entry.is_chordpro else None
    return render_template("tab.html", entry=entry, content=content)


@bp.get("/file/<slug>/<filename>")
def file(slug: str, filename: str) -> ResponseReturnValue:
    """The bytes of one artifact. The renderers' source, and the download link."""
    path = library.artifact_path(_data_dir(), slug, filename)
    if path is None:
        abort(404)

    response: Response = send_from_directory(
        path.parent, path.name, mimetype=_mimetype(path)
    )
    # We declare the type; nothing downstream should re-guess it from content.
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _data_dir() -> Path:
    directory: Path = current_app.config["DATA_DIR"]
    return directory


def _read_text(entry: library.Entry) -> str | None:
    path = library.artifact_path(_data_dir(), entry.slug, entry.artifact)
    if path is None:
        # The record lists a file that is not there. The metadata still renders,
        # which is more useful than a 404 -- and it makes the gap visible.
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _mimetype(path: Path) -> str:
    return MIMETYPES.get(path.suffix.lower(), DEFAULT_MIMETYPE)
