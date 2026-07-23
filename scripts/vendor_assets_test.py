"""The committed vendored assets must match ``vendor.lock.json``.

Same shape as ``make_samples_test.py``: the bytes are committed *and* reproducible,
so the failure mode to guard is a committed file drifting from its recorded hash --
a corrupted download, a hand-edit, a lock that was never regenerated. ``verify`` is
what ``make check`` runs, offline; these exercise it without touching the network.
"""

import json
from pathlib import Path

from vendor_assets import LOCK_PATH, REPO_ROOT, sha256_hex, verify


def test_committed_assets_match_the_lock() -> None:
    """The green baseline: every locked file is present and hashes as recorded."""
    assert verify() == []


def test_lock_covers_the_chordsheetjs_bundle() -> None:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    files = lock["chordsheetjs"]["files"]
    assert "app/static/vendor/chordsheetjs/chordsheetjs.min.js" in files
    assert (REPO_ROOT / "app/static/vendor/chordsheetjs/chordsheetjs.min.js").exists()


def test_detects_a_tampered_file(tmp_path: Path) -> None:
    (tmp_path / "asset.js").write_bytes(b"tampered")
    lock = tmp_path / "lock.json"
    lock.write_text(
        json.dumps({"pkg": {"files": {"asset.js": sha256_hex(b"original")}}}),
        encoding="utf-8",
    )

    problems = verify(root=tmp_path, lock_path=lock)

    assert len(problems) == 1
    assert "asset.js" in problems[0]
    assert "sha256" in problems[0]


def test_detects_a_missing_file(tmp_path: Path) -> None:
    lock = tmp_path / "lock.json"
    lock.write_text(
        json.dumps({"pkg": {"files": {"gone.js": sha256_hex(b"x")}}}),
        encoding="utf-8",
    )

    problems = verify(root=tmp_path, lock_path=lock)

    assert len(problems) == 1
    assert "missing" in problems[0]
