"""Reading the library from disk.

The only module that touches library content. Everything else -- views,
templates, and from v1 the search index -- goes through the three functions
below, so there is exactly one place where a path is built from a URL segment.
That matters more here than it usually would: the library holds third-party
tabs, it sits outside this repo entirely (``DATA_DIR``, CLAUDE.md 1), and
``/file/<slug>/<filename>`` hands two attacker-controlled strings straight at
the filesystem.

The record schema is CLAUDE.md 4. ``meta.yaml`` is the human-editable truth;
this module only reads it, and reads it leniently -- a missing ``tempo`` is
normal, a missing ``title`` is not.
"""

from dataclasses import dataclass
import hashlib
import logging
from pathlib import Path
import re
from typing import Any

import yaml

#: Under DATA_DIR. captures/ and index/ are the pipeline's; the app reads this.
LIBRARY_DIRNAME = "library"

META_FILENAME = "meta.yaml"

#: The lanes of CLAUDE.md 2. A record naming anything else is malformed.
FORMATS = frozenset({"chordpro", "guitarpro"})

#: The slug grammar of CLAUDE.md 3: normalize(artist)--normalize(title), ascii,
#: lowercased, hyphen-separated, "--v2" on collision. Runs of hyphens are the
#: separator, so the pattern allows them.
#:
#: This is the traversal defence, and it is a grammar rather than a sanitizer:
#: no ".", no "/", no "\", no "%", nothing to strip and therefore nothing to
#: strip wrongly. A slug that cannot express a path cannot escape one.
SLUG_PATTERN = re.compile(r"[a-z0-9]+(?:-+[a-z0-9]+)*")

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Entry:
    """One piece: the CLAUDE.md 4 record, plus the slug it was found under."""

    slug: str
    id: str
    title: str
    artist: str
    format: str
    files: list[str]
    tuning: str
    capo: int
    key: str | None
    tempo: int | None
    duration_sec: int | None
    tags: list[str]
    source: dict[str, Any]
    provenance: str | None
    confidence: str | None

    @property
    def artifact(self) -> str:
        """The file the browser renders. One per piece in both lanes so far."""
        return self.files[0]

    @property
    def is_chordpro(self) -> bool:
        return self.format == "chordpro"


def entry_id(url: str | None, slug: str) -> str:
    """The stable id of CLAUDE.md 4: a hash of source url + slug.

    Lives here rather than in the pipeline because both sides need to agree on
    it -- ``tl`` (v1) mints ids, the sample generator mints ids, and a record
    whose id does not survive a regeneration is not stable in the sense the
    schema means. Truncated to 16 hex chars: this is a collision-resistant
    label for a few thousand rows, not a security token.
    """
    return hashlib.sha256(f"{url or ''}\n{slug}".encode()).hexdigest()[:16]


def all_entries(data_dir: Path) -> list[Entry]:
    """Every readable entry under ``data_dir``, sorted by artist then title.

    Never raises. A missing ``library/`` is the normal state of a clean clone
    with no data repo beside it, and an unreadable record is skipped with a
    warning rather than taken as an outage: once ``tl clean`` writes these
    unattended, one bad file must not be able to empty the whole shelf.
    """
    library = data_dir / LIBRARY_DIRNAME
    if not library.is_dir():
        _log.warning("no library at %s", library)
        return []

    entries = []
    for directory in sorted(library.iterdir()):
        if not directory.is_dir():
            continue
        entry = _read_entry(directory)
        if entry is not None:
            entries.append(entry)

    return sorted(
        entries, key=lambda entry: (entry.artist.casefold(), entry.title.casefold())
    )


def load_entry(data_dir: Path, slug: str) -> Entry | None:
    """One entry, or ``None`` if it is absent, malformed, or not a valid slug.

    The three cases are deliberately indistinguishable to the caller: the view
    answers 404 to all of them, and telling a visitor which of "no such tab"
    and "broken tab" applies is not information the view has any use for.
    """
    directory = _entry_dir(data_dir, slug)
    if directory is None:
        return None
    return _read_entry(directory)


def artifact_path(data_dir: Path, slug: str, filename: str) -> Path | None:
    """The on-disk path of one file of one entry, or ``None``.

    ``filename`` is checked against the entry's own ``files:`` list -- a
    whitelist read out of the record, not a pattern the input has to fail.
    Anything the record does not claim to own does not exist as far as this
    function is concerned, which covers ``meta.yaml`` itself as well as
    whatever else happens to be sitting in the directory.
    """
    directory = _entry_dir(data_dir, slug)
    if directory is None:
        return None

    entry = _read_entry(directory)
    if entry is None or filename not in entry.files:
        return None

    # Belt and braces. The whitelist above already rules out a crafted URL, but
    # the names in it come from a file on disk: a meta.yaml listing "../x", or
    # a symlink out of the library, is a path this app should not serve either.
    path = (directory / filename).resolve()
    if path.parent != directory.resolve() or not path.is_file():
        return None
    return path


def _entry_dir(data_dir: Path, slug: str) -> Path | None:
    """The directory for ``slug``, or ``None`` if the slug is not one."""
    if not SLUG_PATTERN.fullmatch(slug):
        return None
    directory = data_dir / LIBRARY_DIRNAME / slug
    if not directory.is_dir():
        return None
    return directory


def _read_entry(directory: Path) -> Entry | None:
    """Parse ``<directory>/meta.yaml``. ``None`` -- with a warning -- if it is bad."""
    meta_path = directory / META_FILENAME
    try:
        with meta_path.open(encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError) as error:
        _log.warning("skipping %s: %s", directory.name, error)
        return None

    try:
        return _entry_from_meta(directory.name, raw)
    except ValueError as error:
        _log.warning("skipping %s: %s", directory.name, error)
        return None


def _entry_from_meta(slug: str, raw: Any) -> Entry:
    """Build an :class:`Entry` from parsed YAML, or raise ``ValueError``.

    Required: enough to render a row and find the artifact. Everything else in
    CLAUDE.md 4 is genuinely optional -- ``tempo`` is often unknown, and
    ``duration_sec`` is guitarpro-only by definition.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"{META_FILENAME} is not a mapping")

    title = _require_str(raw, "title")
    artist = _require_str(raw, "artist")

    fmt = _require_str(raw, "format")
    if fmt not in FORMATS:
        raise ValueError(f"unknown format {fmt!r}")

    files = raw.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("files must be a non-empty list")
    if not all(isinstance(name, str) and name for name in files):
        raise ValueError("files must be a list of names")

    source = raw.get("source") or {}
    if not isinstance(source, dict):
        raise ValueError("source must be a mapping")

    tags = raw.get("tags") or []
    if not isinstance(tags, list):
        raise ValueError("tags must be a list")

    return Entry(
        slug=slug,
        # A record with no id is readable, so mint the one it should have had
        # rather than dropping the entry over a field nothing renders.
        id=str(raw.get("id") or entry_id(source.get("url"), slug)),
        title=title,
        artist=artist,
        format=fmt,
        files=list(files),
        tuning=str(raw.get("tuning") or "EADGBE"),
        capo=int(raw.get("capo") or 0),
        key=_optional_str(raw.get("key")),
        tempo=_optional_int(raw.get("tempo")),
        duration_sec=_optional_int(raw.get("duration_sec")),
        tags=[str(tag) for tag in tags],
        source=source,
        provenance=_optional_str(raw.get("provenance")),
        confidence=_optional_str(raw.get("confidence")),
    )


def _require_str(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing {key}")
    return value.strip()


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
