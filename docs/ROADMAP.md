# Roadmap & build state

**This file is the memory of the project.** Sessions don't carry over; this does.
Read it before starting work, and update it in the last commit of every PR.

---

## Current state

**Updated:** 2026-07-21
**Phase:** v0 — app skeleton
**Next action:** PR 3 — library I/O (`v0/library-io`)

To resume: `make setup`, then create `instance/config.py` from `config.example.py` (see
README), then `make test` to confirm a green baseline before starting the next PR.

---

## v0 — app skeleton

Goal: prove the gated viewer end to end, locally. Both lanes render behind auth, from
vendored assets, with no network. Deploy is **not** part of v0 (it's v3, per CLAUDE.md §9).

| PR | Branch | Scope | Status |
|----|--------|-------|--------|
| 1 | `v0/scaffold` | uv + Makefile + config + app factory + `wsgi.py` + LICENSE + pre-commit/ruff + this file + CLAUDE.md rewrite | **done** |
| 2 | `v0/auth` | Flask-Login, `/login`, `/logout`, blanket `before_request` gate, tests | **done** |
| 3 | `v0/library-io` | `meta.yaml` loader, `samples/` + generator, `/`, `/tab/<slug>`, `/file/…` | next |
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

**The gate exempts *endpoints*, not path prefixes** (PR 2). `EXEMPT_ENDPOINTS = {"auth.login",
"static"}`, matched against `request.endpoint`. A path test like `startswith("/static")` is
something a future route can accidentally satisfy; an endpoint name is exact. The useful
consequence: `request.endpoint` is `None` for a URL matching no route, and Flask runs
`before_request` *before* dispatch raises the 404 — so unknown URLs are gated too, and PR 3's
`/tab/<slug>` and `/file/…` were already covered by tests before they existed.

**`?next=` is validated in-app** (PR 2). The gate hands the parameter out itself, so it is
attacker-supplyable, and flask-login 0.6.3 does not check it — without `safe_next` a mailed
`/login?next=https://evil.example/` would make our login page an open redirect wearing this
site's name. Rejects a scheme, a netloc, anything not starting with `/`, and any backslash
(browsers fold `\` into `/`, so `/\evil.example` leaves as a path and arrives as a host).

**No Flask-WTF; `SameSite=Lax` instead** (PR 2). CSRF protection for a single-user app whose
only form is the login form isn't worth a dependency (CLAUDE.md §8 says flag additions). Lax
cookies can't ride a cross-site POST, which covers the login-CSRF case that actually applies.
Revisit if a state-changing form ever ships.

**Remember-me, 30 days** (PR 2). A deliberate trade of strictness for usability: the phone is
a first-class client, and a password retyped on a touchscreen at every browser restart is the
friction that ends with auth turned off. `HttpOnly` + `SameSite=Lax`; `/logout` ends it.

**`SESSION_COOKIE_SECURE` defaults to *off*** (PR 2). On, over plain http, browsers silently
drop the cookie and login just appears not to work — and plain http is the whole of the
README's getting-started path. `TL_SESSION_COOKIE_SECURE=1` turns it on for HTTPS
deployments. Cookie policy is applied *before* every other config source so all of it stays
overridable; it can't use `setdefault`, because Flask pre-populates its own `SESSION_COOKIE_*`
keys and `setdefault` would therefore never fire.

**App refuses to boot without `SECRET_KEY`/`PASSWORD_HASH`.** No development fallback — a
silent dev secret reaching a deployment is the exact failure this prevents. The error names
`make hash` so the fix is obvious.

**alphaTab will load scores as bytes, not URLs** (PR 5). `fetch()` → `arrayBuffer` →
`api.load(Uint8Array)`. Using `data-file`/`api.load(url)` would bypass the session-cookie
fetch and defeat the auth gate.

**Deploy stays at v3** as CLAUDE.md §9 specs it, rather than being pulled forward.

**mypy runs in `make check`.** It started standalone, matching the convention in `~/dev/cycl`,
on the theory that `make mypy` would get run on its own. It didn't — the standalone target was
being skipped, which is the exact trigger that entry pre-authorized the reversal for. Wired in
now, while the typed baseline is four files and trivially green; a type checker outside the
gate decays into a backlog nobody pays down. It runs before `test` so type errors surface
ahead of the slower step. Still deliberately **not** a pre-commit hook: pre-commit passes the
changed files, and mypy wants the whole tree — whole-tree checks belong in `make check`.
`check_untyped_defs = true` (cycl passes it as a flag; here it lives in `pyproject.toml` so
editors pick it up too), because without it mypy skips the body of every unannotated function,
which is most of a young repo. `flask_login` has no `py.typed` and no stub package, so it
carries an `ignore_missing_imports` override.

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
- [ ] Extend `make check` with vendored-asset hash verification when PR 4 adds it.
- [ ] Set `TL_SESSION_COOKIE_SECURE=1` on PythonAnywhere at v3. It is off by default for
      local http; leaving it off on an HTTPS deployment sends the session cookie in clear
      on any downgraded request.
- [ ] `flask_login` 0.6.3 calls the deprecated `datetime.utcnow()`, so the remember-me tests
      emit `DeprecationWarning`s. Upstream's problem, not ours — but it blocks turning on
      `filterwarnings = ["error"]` in pytest until they release a fix.
