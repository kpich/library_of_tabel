# library of tabel

A single-user guitar tab library: acquire tabs, normalize them, and read them from a phone
or laptop. One Flask app, two format lanes (`chordpro` via ChordSheetJS, `guitarpro` via
alphaTab), SQLite/FTS5 for search.

**Status:** early. See [`docs/ROADMAP.md`](docs/ROADMAP.md) for what's built and what's next.
[`CLAUDE.md`](CLAUDE.md) is the full spec.

## Two repos

This repo is **public and holds only code**. The library itself lives in a **separate
private repo**, because the tabs are third-party content:

```
library_of_tabel/          this repo — public, MIT
library_of_tabel_data/     the library — private
  library/  captures/  index/
```

Nothing in git links them. The app finds the library through `TL_DATA_DIR`, which defaults
to the sibling path above. Out of the box it points at `samples/` instead, so a fresh clone
runs with no data repo present.

## Getting started

Requires [uv](https://docs.astral.sh/uv/). Everything else is a `make` target.

```sh
make setup                      # create .venv, install from uv.lock, install git hooks

mkdir -p instance
cp config.example.py instance/config.py
make hash                       # prints a PASSWORD_HASH line to paste into it
                                # also set SECRET_KEY — see config.example.py

make run                        # http://127.0.0.1:5000
```

`instance/` is gitignored; the password hash and secret key never enter the repo. The app
refuses to start without them rather than falling back to a development default.

Everything is behind a login — sign in with `USERNAME` and the password you hashed. The gate
is a single `before_request` covering every route, including the ones that serve tab files,
so nothing is reachable by guessing a URL. Logins are remembered for 30 days; `/logout` ends
one. Cookies are not marked `Secure` by default, because local development is plain http —
set `TL_SESSION_COOKIE_SECURE=1` wherever the app is served over HTTPS.

To run against the real library instead of the samples:

```sh
make run TL_DATA_DIR=../library_of_tabel_data
```

## Samples

`samples/` holds one entry per lane, so a fresh clone has something on the shelf before the
data repo exists. **The content is my own** — words, chords and a four-bar score written for
this repo. No third-party tabs or lyrics live in this repo, not even as fixtures.

It is generated and committed, like the vendored browser libraries:

```sh
python scripts/make_samples.py     # must reproduce the committed bytes exactly
```

`scripts/make_samples_test.py` asserts exactly that, so an edit to the generator that never
reaches the output — or the reverse — fails the suite.

## How the library is read

`app/library.py` is the only module that touches library content. `/file/<slug>/<filename>`
takes two URL segments, so neither becomes a path directly: the slug must match a grammar
that cannot express `.`, `/`, `\` or `%`, and the filename must be listed in that entry's own
`meta.yaml`. Anything a record doesn't claim — `meta.yaml` included — is not servable. A
malformed record is skipped with a warning rather than taken as an outage, so one bad file
can't empty the shelf.

## Make targets

| | |
|---|---|
| `make setup` | create `.venv`, install from `uv.lock`, install git hooks |
| `make run`   | serve locally with reload |
| `make test`  | run the test suite |
| `make lint`  | ruff check + format check, writing nothing |
| `make format`| apply ruff fixes and formatting |
| `make mypy`  | static type check over `app scripts tests wsgi.py` |
| `make check` | everything verifiable offline (`lint` + `mypy` + `test`) |
| `make hash`  | prompt for a password, print its hash |
| `make install_precommit_hooks` | install the git pre-commit hooks (part of `setup`) |
| `make clean` | remove `.venv` and caches |

Commits are gated by [pre-commit](https://pre-commit.com): ruff lint + format, plus
whitespace/YAML/TOML/large-file/private-key checks. Vendored assets under
`app/static/vendor/` are excluded from every hook — their bytes are verified against
npm-published hashes, so a formatter rewriting one would break that verification.

## Licensing

This repo's code is MIT ([`LICENSE`](LICENSE)). Vendored browser libraries under
`app/static/vendor/` keep their own licenses — ChordSheetJS is GPL-2.0-only, alphaTab is
MPL-2.0 — each shipped with its upstream license and a `SOURCE.md` pointing at upstream.
