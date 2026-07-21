# Roadmap & build state

**This file is the memory of the project.** Sessions don't carry over; this does.
Read it before starting work, and update it in the last commit of every PR.

---

## Current state

**Updated:** 2026-07-21
**Phase:** v0 — app skeleton
**Next action:** PR 2 — auth (`v0/auth`)

To resume: `make setup`, then create `instance/config.py` from `config.example.py` (see
README), then `make test` to confirm a green baseline before starting the next PR.

---

## v0 — app skeleton

Goal: prove the gated viewer end to end, locally. Both lanes render behind auth, from
vendored assets, with no network. Deploy is **not** part of v0 (it's v3, per CLAUDE.md §9).

| PR | Branch | Scope | Status |
|----|--------|-------|--------|
| 1 | `v0/scaffold` | uv + Makefile + config + app factory + `wsgi.py` + LICENSE + pre-commit/ruff + this file + CLAUDE.md rewrite | **done** |
| 2 | `v0/auth` | Flask-Login, `/login`, `/logout`, blanket `before_request` gate, tests | next |
| 3 | `v0/library-io` | `meta.yaml` loader, `samples/` + generator, `/`, `/tab/<slug>`, `/file/…` | |
| 4 | `v0/chordpro-render` | vendor script + manifest, ChordSheetJS, transpose control | |
| 5 | `v0/guitarpro-render` | alphaTab + Bravura + soundfont, playback | |

**v0 exit criterion:** logged out in a fresh private window, each of `/`, `/tab/<slug>`,
and `/file/<slug>/<file>` lands on `/login`; both lanes render with **zero external network
requests** in DevTools.

### Later phases

Per CLAUDE.md §9 — v1 chordpro pipeline (`tl` CLI, clean-tab skill, FTS5 search),
v2 guitarpro lane, v3 PythonAnywhere deploy + PWA + polish.

---

## Decisions

Choices whose *reasons* aren't visible in a diff.

**Two repos: public code, private data.** The tabs are third-party content; the code isn't.
Linked only by `TL_DATA_DIR` config — no submodule, so the public repo never advertises
that the private one exists. `library/`, `captures/`, `index/` are gitignored here and
`tests/test_repo_hygiene.py` fails if they appear, because a `tl` bug that ignores
`TL_DATA_DIR` would otherwise put tabs one `git add -A` from a public commit.

**MIT for our code; vendored libraries keep their own licenses.** ChordSheetJS is
GPL-2.0-only, which only became relevant once the code repo was public — vendoring is
redistribution. GPL-2 §3 permits verbatim redistribution with the license and a source
pointer, which is what `SOURCE.md` in each vendor directory is for. The combined-work
question is left unresolved; it's not a practical concern for a personal project.

**uv over pip.** Both hold direct deps in `pyproject.toml` identically. The difference that
mattered: `uv.lock` is written automatically by `uv sync`, whereas pinning with pip needs a
manual `pip freeze` after every change — a forgettable step, and forgotten steps are the
environment drift we're trying to prevent.

**Python 3.13, floor at 3.11.** `.python-version` is 3.13; `requires-python = ">=3.11"` is a
compatibility floor, not a pin. PA offers 3.11/3.12/3.13, so there's no reason to target the
oldest. uv is free to fetch its own interpreter locally — that's the point of uv.
`UV_PYTHON_DOWNLOADS=never` applies **only on PA**, where uv-installed interpreters can't
back a web app; it's in the deploy notes, not the Makefile.

**Blanket `before_request` auth gate, not per-route `@login_required`.** CLAUDE.md §7
requires the file-serving routes to be gated. One forgotten decorator is one leaked tab, so
the gate is structural and exempts only `/login` and `/static/`. Consequence: `/static/`
must hold vendored assets only, never library content.

**App refuses to boot without `SECRET_KEY`/`PASSWORD_HASH`.** No development fallback — a
silent dev secret reaching a deployment is the exact failure this prevents. The error names
`make hash` so the fix is obvious.

**alphaTab will load scores as bytes, not URLs** (PR 5). `fetch()` → `arrayBuffer` →
`api.load(Uint8Array)`. Using `data-file`/`api.load(url)` would bypass the session-cookie
fetch and defeat the auth gate.

**Deploy stays at v3** as CLAUDE.md §9 specs it, rather than being pulled forward.

**mypy is a standalone `make mypy`, not part of `make check` or pre-commit** — matching the
convention in `~/dev/cycl`. `check_untyped_defs = true` (cycl passes it as a flag; here it
lives in `pyproject.toml` so editors pick it up too), because without it mypy skips the body
of every unannotated function, which is most of a young repo. `flask_login` has no `py.typed`
and no stub package, so it carries an `ignore_missing_imports` override — needed from PR 2 on.
Wiring it into `check` is a one-line change if the standalone target starts getting skipped.

**Pre-commit hooks exclude `app/static/vendor/` entirely.** Modelled on `~/dev/cycl`, with
two deliberate departures. Vendored bundles get verified against npm-published hashes
(PR 4), so `trailing-whitespace`/`end-of-file-fixer` rewriting one would silently break
that check; and alphaTab's JS (1.1 MB) plus the soundfont (977 KB) would trip
`check-added-large-files`. A single top-level `exclude:` covers both, and keeps the
large-file guard active everywhere else — which is where it earns its keep.

---

## Cleanup owed

- [ ] Delete the placeholder `/` route in `app/__init__.py` once PR 3 registers real views.
- [ ] Delete `samples/` demo entries once v1 produces real captures — or keep them as test
      fixtures if the tests come to depend on them. Decide at v1, don't let them linger.
- [ ] Extend `make check` with vendored-asset hash verification when PR 4 adds it (the
      target currently just aliases `make test`).
