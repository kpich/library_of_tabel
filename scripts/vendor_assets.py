"""Vendor third-party browser assets into ``app/static/vendor/``.

The code repo is public, so vendoring is redistribution (CLAUDE.md 8): each
vendored library ships with its upstream ``LICENSE`` and a generated ``SOURCE.md``
naming the project and exact version. The bytes are committed *and* reproducible
from here.

Two modes:

    python scripts/vendor_assets.py          # fetch + verify + write (needs network)
    python scripts/vendor_assets.py --check   # offline: re-hash committed files vs lock

The fetch path verifies the npm tarball against its pinned ``sha512`` integrity --
that is the provenance check, and it needs the network. Deploy never fetches
(PythonAnywhere's outbound allowlist), so the committed bytes are the source of
truth; ``--check`` re-hashes them against ``vendor.lock.json`` offline and is wired
into ``make check`` so a drifted or corrupted vendored file fails the build.
"""

import argparse
import base64
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import urllib.request

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCK_PATH = REPO_ROOT / "scripts" / "vendor.lock.json"
REGISTRY = "https://registry.npmjs.org"


@dataclass(frozen=True)
class Package:
    """One npm package we redistribute a browser build of."""

    name: str
    version: str
    #: The npm registry's published ``dist.integrity`` for this exact version.
    #: Pinned here so a fetch verifies provenance without trusting the download.
    tarball_integrity: str
    license_spdx: str
    homepage: str
    #: tarball member path -> filename written under ``dest``.
    members: dict[str, str]
    #: destination directory, relative to the repo root.
    dest: str

    @property
    def tarball_url(self) -> str:
        return f"{REGISTRY}/{self.name}/-/{self.name}-{self.version}.tgz"

    @property
    def dest_dir(self) -> Path:
        return REPO_ROOT / self.dest


VENDOR = [
    Package(
        name="chordsheetjs",
        version="15.5.2",
        tarball_integrity=(
            "sha512-ckM85eD5uRT9lWMQUfQpWFSCU5ZbwP3ROGpLvgFEzalHd08gjPhoe4wPHo2"
            "okjFeRF4rMJI29YY3tBuZGlw33A=="
        ),
        license_spdx="GPL-2.0-only",
        homepage="https://github.com/martijnversluis/ChordSheetJS",
        members={
            "package/lib/bundle.min.js": "chordsheetjs.min.js",
            "package/LICENSE": "LICENSE",
        },
        dest="app/static/vendor/chordsheetjs",
    ),
]


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha512_integrity(data: bytes) -> str:
    """The Subresource-Integrity form npm publishes: ``sha512-<base64 digest>``."""
    return "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode("ascii")


def _source_md(pkg: Package) -> str:
    files = "\n".join(
        f"- `{name}` (from `{member}`)" for member, name in pkg.members.items()
    )
    return f"""# {pkg.name}

Vendored third-party asset. Redistributed under its own license (see `LICENSE`);
this repo's own code is MIT.

- **Project:** {pkg.homepage}
- **Version:** {pkg.version}
- **License:** {pkg.license_spdx}
- **Source:** `{pkg.tarball_url}`
- **Integrity:** `{pkg.tarball_integrity}`

Files, all extracted verbatim from the npm tarball:

{files}

Do not edit these by hand. Regenerate with `python scripts/vendor_assets.py`, which
verifies the tarball against the integrity above. `scripts/vendor.lock.json` pins a
`sha256` of every file here; `make check` re-hashes them offline against it.
"""


def fetch_and_vendor() -> dict[str, dict[str, object]]:
    """Download each package, verify integrity, write files, return the lock."""
    lock: dict[str, dict[str, object]] = {}
    for pkg in VENDOR:
        print(f"fetching {pkg.name}@{pkg.version} ...", file=sys.stderr)
        with urllib.request.urlopen(pkg.tarball_url, timeout=60) as resp:  # noqa: S310
            tarball = resp.read()

        got = sha512_integrity(tarball)
        if got != pkg.tarball_integrity:
            raise SystemExit(
                f"integrity mismatch for {pkg.name}@{pkg.version}\n"
                f"  expected {pkg.tarball_integrity}\n  got      {got}"
            )

        pkg.dest_dir.mkdir(parents=True, exist_ok=True)
        file_hashes: dict[str, str] = {}
        with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as tar:
            for member, out_name in pkg.members.items():
                extracted = tar.extractfile(member)
                if extracted is None:
                    raise SystemExit(f"{pkg.name}: tarball has no member {member}")
                data = extracted.read()
                (pkg.dest_dir / out_name).write_bytes(data)
                rel = str((pkg.dest_dir / out_name).relative_to(REPO_ROOT))
                file_hashes[rel] = sha256_hex(data)

        (pkg.dest_dir / "SOURCE.md").write_text(_source_md(pkg), encoding="utf-8")

        lock[pkg.name] = {
            "version": pkg.version,
            "tarball_integrity": pkg.tarball_integrity,
            "files": file_hashes,
        }
    return lock


def verify(root: Path = REPO_ROOT, lock_path: Path = LOCK_PATH) -> list[str]:
    """Offline: re-hash committed files against the lock. Return a list of problems."""
    problems: list[str] = []
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    for name, entry in lock.items():
        for rel, want in entry["files"].items():
            path = root / rel
            if not path.exists():
                problems.append(f"{name}: missing vendored file {rel}")
                continue
            got = sha256_hex(path.read_bytes())
            if got != want:
                problems.append(f"{name}: {rel} sha256 {got} != locked {want}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="offline: verify committed vendored files against vendor.lock.json",
    )
    args = parser.parse_args()

    if args.check:
        problems = verify()
        if problems:
            print("vendored assets FAILED verification:", file=sys.stderr)
            for p in problems:
                print(f"  {p}", file=sys.stderr)
            return 1
        print("vendored assets verified against lock.", file=sys.stderr)
        return 0

    lock = fetch_and_vendor()
    serialized = json.dumps(lock, indent=2, sort_keys=True) + "\n"
    LOCK_PATH.write_text(serialized, encoding="utf-8")
    print(f"wrote {LOCK_PATH.relative_to(REPO_ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
