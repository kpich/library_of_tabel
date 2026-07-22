"""The committed samples must be exactly what the generator produces.

``samples/`` is committed *and* generated, the same arrangement the vendored
browser libraries use, and the same failure mode applies: an edit to one side
that never reaches the other leaves a "reproducible" artifact that does not
reproduce. Comparing bytes is what makes the claim checkable.

It also pins ``entry_id`` by consequence -- change the hash rule and every
committed ``id`` stops matching, which is the point of calling it stable.
"""

from pathlib import Path

from make_samples import DEFAULT_TARGET, main

from app.library import all_entries

SAMPLE_SLUGS = ["the-repeat-signs--kitchen-light", "the-repeat-signs--practice-loop"]


def _tree(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_regenerating_reproduces_the_committed_samples(tmp_path: Path) -> None:
    main(["make_samples.py", str(tmp_path)])

    assert _tree(tmp_path) == _tree(DEFAULT_TARGET)


def test_the_committed_samples_load(tmp_path: Path) -> None:
    """A sample the loader rejects would make a clean clone look like an empty app."""
    entries = all_entries(DEFAULT_TARGET)

    assert sorted(entry.slug for entry in entries) == SAMPLE_SLUGS
    assert sorted(entry.format for entry in entries) == ["chordpro", "guitarpro"]
    for entry in entries:
        assert (DEFAULT_TARGET / "library" / entry.slug / entry.artifact).is_file()


def test_generation_is_idempotent(tmp_path: Path) -> None:
    """`tl clean` and `tl index` carry the same requirement (CLAUDE.md 5)."""
    main(["make_samples.py", str(tmp_path)])
    first = _tree(tmp_path)
    main(["make_samples.py", str(tmp_path)])

    assert _tree(tmp_path) == first
