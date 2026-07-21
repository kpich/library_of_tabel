"""This repo is public. The library is not.

The layout in CLAUDE.md gives the pipeline directory names -- library/,
captures/, index/ -- that belong in the private data repo. If a tool ever
ignores TL_DATA_DIR and writes them here, third-party tab content would be one
`git add -A` away from a public commit. .gitignore covers that case; this test
covers the case where someone force-adds or the ignore rule gets edited away.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

DATA_ONLY_DIRS = ("library", "captures", "index")


@pytest.mark.parametrize("name", DATA_ONLY_DIRS)
def test_data_directories_absent_from_code_repo(name: str) -> None:
    path = REPO_ROOT / name
    assert not path.exists(), (
        f"{name}/ exists in the public code repo. The library belongs in the "
        f"private data repo -- set TL_DATA_DIR instead of writing here."
    )
