# Roadmap & build state

**This file is the memory of the project.** Sessions don't carry over; this does.
Read it before starting work, and update it in the last commit of every PR.

---

## Current state

**Updated:** 2026-07-22
**Phase:** v0 — app skeleton
**Next action:** PR 4 — chordpro rendering (`v0/chordpro-render`)

To resume: `make setup`, then create `instance/config.py` from `config.example.py` (see
README), then `make test` to confirm a green baseline before starting the next PR.

`make run` now serves a real library: `TL_DATA_DIR` defaults to `samples/`, which holds one
entry per lane. Both render as plain text — PR 4 replaces the chordpro `<pre>` with
ChordSheetJS, PR 5 fills the guitarpro `<div>` with alphaTab. Both attach to the `data-slug`
/ `data-format` / `data-file` attributes already on those elements in `templates/tab.html`.

---

## v0 — app skeleton

Goal: prove the gated viewer end to end, locally. Both lanes render behind auth, from
vendored assets, with no network. Deploy is **not** part of v0 (it's v3, per CLAUDE.md §9).

| PR | Branch | Scope | Status |
|----|--------|-------|--------|
| 1 | `v0/scaffold` | uv + Makefile + config + app factory + `wsgi.py` + LICENSE + pre-commit/ruff + this file + CLAUDE.md rewrite | **done** |
| 2 | `v0/auth` | Flask-Login, `/login`, `/logout`, blanket `before_request` gate, tests | **done** |
| 3 | `v0/library-io` | `meta.yaml` loader, `samples/` + generator, `/`, `/tab/<slug>`, `/file/…` | **done** |
| 4 | `v0/chordpro-render` | vendor script + manifest, ChordSheetJS, transpose control | next |
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
`tests/repo_hygiene_test.py` fails if they appear, because a `tl` bug that ignores
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

**`/file` serves a whitelist read out of `meta.yaml`, not a sanitized path** (PR 3). The route
takes two attacker-controlled segments, so neither is turned into a path directly: the slug
must match a grammar (`[a-z0-9]+(?:-+[a-z0-9]+)*`) that cannot express `.`, `/`, `\` or `%`,
and the filename must appear in that entry's own `files:` list. A slug that cannot spell a
path cannot escape one, and there is nothing to strip and therefore nothing to strip wrongly.
Two useful consequences fall out for free: `meta.yaml` itself is never servable, because no
record lists it, and neither is anything else that happens to be sitting in the directory.
The `resolve()`-is-inside-the-entry-dir check behind that is not redundant — the whitelist's
*contents* come off disk, so a `meta.yaml` listing `../../secret` or a symlink out of the
library is still a path this app must refuse. All three are tested as tables.

**A broken record is skipped with a warning; the page still renders** (PR 3). From v1 the
writer is `tl clean` running unattended, and the failure mode to design against is one
malformed `meta.yaml` emptying the whole shelf. `/tab/<bad-slug>` 404s — absent, malformed
and not-a-slug are deliberately indistinguishable to the view, since "no such tab" versus
"broken tab" is not a distinction a visitor can act on. A missing `library/` is likewise
normal (a clone with no data repo beside it), not an error.

**The guitarpro sample is MusicXML, not `.gp5`** (PR 3). CLAUDE.md §2 makes both canonical
for the lane, and MusicXML is text: no binary blob in the public repo, no PyGuitarPro
dependency at v0 (it's a v1 CLI concern), and alphaTab reads it natively. Its DOCTYPE is
omitted deliberately — the MusicXML DTD lives at musicxml.org, and v0's exit criterion is
zero external requests. Browsers not fetching external DTDs is not a thing to lean on when
leaving it out is valid.

**`samples/` is generated *and* committed** (PR 3), like the vendored assets: `scripts/
make_samples.py` writes it, `scripts/make_samples_test.py` regenerates into `tmp_path` and
compares bytes. Same failure mode either arrangement guards against — an edit to one side
that never reaches the other leaves a "reproducible" artifact that doesn't reproduce. It
also pins `entry_id` by consequence, which is what "stable hash" in §4 has to mean. Nothing
in the generator may read the clock; `fetched_at` is a literal, or every run is a diff.
The content is original work written for this repo, per CLAUDE.md §10 — including the
fixtures, since "no third-party tabs in the public repo" has no fixture exemption.

**Tests pass `DATA_DIR` explicitly** (PR 3). `load_config` reads `TL_DATA_DIR` from the
environment and the Makefile exports it, so before this a bare `pytest` ran the suite
against whatever that variable held — on a working laptop, the real private data repo. The
fixture names it, and defaults to `samples/`, so the view tests cover the path a clean clone
actually takes and the suite depends on nothing outside the checkout.

**`send_file` responses are closed in tests** (PR 3). The response holds an open file that a
real WSGI server closes and the test client does not; with `filterwarnings = ["error"]` the
leak fails the suite as a `ResourceWarning`, so those tests use `with client.get(...)`.
Related trap, found by a live `curl` and not by a test: a mimetype carrying its own
`charset` arrives as `text/plain; charset=utf-8; charset=utf-8`, because Flask appends one
to every `text/*`. `response.mimetype` drops parameters and reads clean either way — assert
on the whole `Content-Type` header.

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

**Unit tests live beside their module; integration tests live under `tests/`.** `app/config.py`
is covered by `app/config_test.py`; anything that assembles the app and drives it through a
test client moved to `tests/integration/`. One `*_test.py` suffix for both, so the *location*
is what distinguishes them and no file has to be renamed when it changes character. The
payoff is the negative space: a module with no neighbouring `_test.py` is visible in a
directory listing, where an untested module under a central `tests/` tree is an absence
nobody notices. Cost: `testpaths` now spans `app`, `scripts`, `tests`, and the hatch wheel
build excludes `*_test.py` so tests don't ship inside the package. `tests/__init__.py` and
`tests/integration/__init__.py` both stay — without them mypy resolves `conftest.py` under
two module names and refuses to check anything.

**Pytest runs with `filterwarnings = ["error"]`.** A warning nobody is failing on is a bug
nobody has read. The single exemption is flask_login 0.6.3's `datetime.utcnow()` call, and
it is pinned by message *and* module rather than by blanket `DeprecationWarning`, so a
different deprecation out of the same file still breaks the build. Note the escaping
difference that costs a debugging round if you hit it: pytest treats the `-W` command-line
message as a literal (`warnings._setoption` escapes it) but the ini `filterwarnings` message
as a regex — the parens in `utcnow\(\)` need backslashes in `pyproject.toml` and not on the
command line.

---

## Cleanup owed

- [ ] Decide `samples/`'s fate at v1. The tests now *do* depend on it — it is the default
      `DATA_DIR` for the integration suite — so the "delete it once real captures exist"
      half of this is no longer free. Keeping it is the likely answer; make it deliberately.
- [ ] Give `/` a real search box when v1 lands FTS5. It has none today on purpose: a
      client-side filter would be thrown away, and would quietly stop being the truth once
      the shelf outgrows one page.
- [ ] Extend `make check` with vendored-asset hash verification when PR 4 adds it.
- [ ] Set `TL_SESSION_COOKIE_SECURE=1` on PythonAnywhere at v3. It is off by default for
      local http; leaving it off on an HTTPS deployment sends the session cookie in clear
      on any downgraded request.
- [ ] Drop the `flask_login` `datetime.utcnow()` entry from pytest's `filterwarnings` once
      upstream releases a fix. It is the only exemption to `error`; check it still fails
      without the line before deleting it, so a genuinely fixed upstream is what removes it.
