"""Unit tests for the library loader.

Two things are being pinned here. One is that reading is *lenient in the right
places*: an absent library and a corrupt record are both normal states of a
system whose writer (``tl clean``, v1) runs unattended, and neither may take
down the page. The other is that path handling is not lenient at all --
``/file/<slug>/<filename>`` puts two URL segments next to a filesystem, and
every way of leaving the entry directory gets its own row below.
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

from app.library import Entry, all_entries, artifact_path, entry_id, load_entry

CHORDPRO_META: dict[str, Any] = {
    "title": "Kitchen Light",
    "artist": "The Repeat Signs",
    "format": "chordpro",
    "files": ["tab.chordpro"],
    "key": "G",
    "tempo": 92,
    "tags": ["sample"],
    "source": {"url": "https://example.invalid/kitchen", "site": "example"},
}

GUITARPRO_META: dict[str, Any] = {
    "title": "Practice Loop",
    "artist": "The Repeat Signs",
    "format": "guitarpro",
    "files": ["score.musicxml"],
    "duration_sec": 11,
}


def write_entry(
    data_dir: Path,
    slug: str,
    meta: dict[str, Any] | str | None = None,
    files: dict[str, str] | None = None,
) -> Path:
    """Create one entry on disk. ``meta`` as a string is written verbatim."""
    directory = data_dir / "library" / slug
    directory.mkdir(parents=True)
    if meta is not None:
        text = meta if isinstance(meta, str) else yaml.safe_dump(meta)
        (directory / "meta.yaml").write_text(text, encoding="utf-8")
    for name, content in (files or {}).items():
        (directory / name).write_text(content, encoding="utf-8")
    return directory


@pytest.fixture
def library(tmp_path: Path) -> Path:
    """A data dir holding one readable entry per lane."""
    write_entry(tmp_path, "a--chordpro", CHORDPRO_META, {"tab.chordpro": "[G]hello"})
    write_entry(
        tmp_path, "b--guitarpro", GUITARPRO_META, {"score.musicxml": "<score/>"}
    )
    return tmp_path


def test_reads_both_lanes(library: Path) -> None:
    entries = all_entries(library)

    assert [entry.slug for entry in entries] == ["a--chordpro", "b--guitarpro"]
    assert [entry.format for entry in entries] == ["chordpro", "guitarpro"]


def test_carries_the_schema_fields(library: Path) -> None:
    entry = load_entry(library, "a--chordpro")

    assert entry is not None
    assert (entry.title, entry.artist, entry.key, entry.tempo) == (
        "Kitchen Light",
        "The Repeat Signs",
        "G",
        92,
    )
    assert entry.tags == ["sample"]
    assert entry.source["site"] == "example"


def test_optional_fields_default_rather_than_failing(library: Path) -> None:
    """Most of CLAUDE.md 4 is genuinely optional; only the record's spine is not."""
    entry = load_entry(library, "b--guitarpro")

    assert entry is not None
    assert (entry.tuning, entry.capo) == ("EADGBE", 0)
    assert (entry.key, entry.tempo, entry.tags) == (None, None, [])
    assert entry.duration_sec == 11


def test_sorted_by_artist_then_title(tmp_path: Path) -> None:
    write_entry(tmp_path, "z--one", {**CHORDPRO_META, "artist": "Ash", "title": "Two"})
    write_entry(tmp_path, "y--two", {**CHORDPRO_META, "artist": "ash", "title": "One"})
    write_entry(
        tmp_path, "x--three", {**CHORDPRO_META, "artist": "Birch", "title": "A"}
    )

    assert [entry.title for entry in all_entries(tmp_path)] == ["One", "Two", "A"]


def test_missing_library_is_empty_not_an_error(tmp_path: Path) -> None:
    """The default DATA_DIR is a sibling repo that may simply not be cloned."""
    assert all_entries(tmp_path) == []


def test_stray_files_beside_the_entries_are_ignored(library: Path) -> None:
    (library / "library" / "README.md").write_text("not an entry", encoding="utf-8")

    assert len(all_entries(library)) == 2


@pytest.mark.parametrize(
    "name, meta",
    [
        ("no meta.yaml at all", None),
        ("unparseable", "title: [unclosed"),
        ("not a mapping", "- just\n- a list\n"),
        ("empty file", ""),
        ("no title", {k: v for k, v in CHORDPRO_META.items() if k != "title"}),
        ("no artist", {k: v for k, v in CHORDPRO_META.items() if k != "artist"}),
        ("blank title", {**CHORDPRO_META, "title": "   "}),
        ("no format", {k: v for k, v in CHORDPRO_META.items() if k != "format"}),
        ("unknown format", {**CHORDPRO_META, "format": "pdf"}),
        ("no files", {k: v for k, v in CHORDPRO_META.items() if k != "files"}),
        ("empty files", {**CHORDPRO_META, "files": []}),
        ("files not a list", {**CHORDPRO_META, "files": "tab.chordpro"}),
    ],
)
def test_a_broken_record_is_skipped_not_fatal(
    library: Path, name: str, meta: dict[str, Any] | str | None
) -> None:
    """One corrupt entry must not empty the shelf -- `tl clean` writes unattended."""
    write_entry(library, "broken--entry", meta)

    assert len(all_entries(library)) == 2, name
    assert load_entry(library, "broken--entry") is None, name


def test_a_record_without_an_id_gets_the_one_it_should_have_had(tmp_path: Path) -> None:
    meta = {k: v for k, v in CHORDPRO_META.items() if k != "id"}
    write_entry(tmp_path, "a--slug", meta)

    entry = load_entry(tmp_path, "a--slug")

    assert entry is not None
    assert entry.id == entry_id(CHORDPRO_META["source"]["url"], "a--slug")


def test_unknown_slug_is_none(library: Path) -> None:
    assert load_entry(library, "nobody--home") is None


#: Every one of these must be refused *as a slug*, before it reaches a path.
#: The grammar in library.SLUG_PATTERN admits none of the characters needed to
#: express any of them, which is why this is a table and not a sanitizer.
HOSTILE_SLUGS = [
    "..",
    "../../etc",
    "a--slug/../..",
    "/etc/passwd",
    "a--slug/tab.chordpro",
    "a--slug\\..\\..",
    ".hidden",
    "",
    ".",
    "UPPER--CASE",
    "sp ace",
    "a--slug%2f..",
    "~",
]


@pytest.mark.parametrize("slug", HOSTILE_SLUGS)
def test_a_slug_that_could_be_a_path_is_not_a_slug(library: Path, slug: str) -> None:
    assert load_entry(library, slug) is None
    assert artifact_path(library, slug, "tab.chordpro") is None


def test_artifact_path_finds_a_listed_file(library: Path) -> None:
    path = artifact_path(library, "a--chordpro", "tab.chordpro")

    assert path is not None
    assert path.read_text(encoding="utf-8") == "[G]hello"


def test_only_files_the_record_claims_are_served(library: Path) -> None:
    """A whitelist out of meta.yaml, so the directory's other contents don't exist."""
    (library / "library" / "a--chordpro" / "notes.txt").write_text(
        "x", encoding="utf-8"
    )

    assert artifact_path(library, "a--chordpro", "notes.txt") is None
    # meta.yaml is in the directory but never in files:, so it is not servable.
    assert artifact_path(library, "a--chordpro", "meta.yaml") is None


def test_a_listed_file_that_is_missing_is_none(tmp_path: Path) -> None:
    write_entry(tmp_path, "a--slug", CHORDPRO_META)  # meta lists tab.chordpro; no file

    assert artifact_path(tmp_path, "a--slug", "tab.chordpro") is None


@pytest.mark.parametrize(
    "filename",
    ["../../etc/passwd", "../b--guitarpro/score.musicxml", "/etc/passwd", ".."],
)
def test_traversal_via_the_filename_is_refused(library: Path, filename: str) -> None:
    assert artifact_path(library, "a--chordpro", filename) is None


def test_traversal_via_a_crafted_meta_yaml_is_refused(tmp_path: Path) -> None:
    """The whitelist's contents come off disk, so the whitelist is not the last word."""
    secret = tmp_path / "secret.txt"
    secret.write_text("not yours", encoding="utf-8")
    write_entry(tmp_path, "a--slug", {**CHORDPRO_META, "files": ["../../secret.txt"]})

    assert artifact_path(tmp_path, "a--slug", "../../secret.txt") is None


def test_a_symlink_out_of_the_library_is_refused(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("not yours", encoding="utf-8")
    directory = write_entry(tmp_path, "a--slug", CHORDPRO_META)
    (directory / "tab.chordpro").symlink_to(secret)

    assert artifact_path(tmp_path, "a--slug", "tab.chordpro") is None


def test_entry_id_is_stable_and_distinguishing() -> None:
    assert entry_id("https://example.invalid/x", "a--slug") == entry_id(
        "https://example.invalid/x", "a--slug"
    )
    assert entry_id(None, "a--slug") != entry_id(None, "b--slug")
    assert entry_id("https://example.invalid/x", "a--slug") != entry_id(None, "a--slug")


def test_artifact_is_the_first_listed_file() -> None:
    entry = Entry(
        slug="a--slug",
        id="x",
        title="T",
        artist="A",
        format="chordpro",
        files=["tab.chordpro", "notes.txt"],
        tuning="EADGBE",
        capo=0,
        key=None,
        tempo=None,
        duration_sec=None,
        tags=[],
        source={},
        provenance=None,
        confidence=None,
    )

    assert entry.artifact == "tab.chordpro"
    assert entry.is_chordpro
