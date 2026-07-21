# Tab Library — Repo Spec (`CLAUDE.md`)

A single-user system to acquire guitar tabs, normalize them, and view + search the
collection from phone and computer. One Flask app, hosted on PythonAnywhere's free
tier. Not a public site — **the app and the library are private; only the code is public.**

---

## 0. Where we are (read this before anything else)

**`docs/ROADMAP.md` holds the current state of the build** — which phase, which PR is
next, and the decisions behind choices that aren't visible in a diff. Read it first;
sessions don't carry over, but that file does.

**Update it in the last commit of every PR.** That is part of the PR, not a follow-up.

---

**How to use this file:** This is the source of truth. Scaffold incrementally by the
phases in §9 — do not build everything at once. Prefer small, reviewable commits.
Ask before adding heavy dependencies not listed in §8.

**Scope for now:** two format lanes only — `chordpro` and `guitarpro`. PDF/sheet-music
is explicitly out of scope for v1 (revisit later). This keeps everything text-sized:
plain git, no LFS, and 512 MiB of free disk holds thousands of pieces.

---

## 1. Where things live (read this first)

**Two repos, cloned side by side.** This is the most important structural fact in the
project — code and library are separate, with different visibility:

```
library_of_tabel/          PUBLIC   — this repo. Code, MIT licensed.
library_of_tabel_data/     PRIVATE  — the library. Never public.
```

- **The code repo is public.** App, `tl` CLI, adapters, skills, sample content. It
  contains no tabs and no credentials.
- **The data repo is private, and is the source of truth for the library.** The pipeline
  runs on my laptop and commits `library/`, `captures/`, and `index/library.db` there.
  Private because the tabs are third-party content — this split is what keeps them
  unpublished while the code stays open.
- **Nothing links the two in git.** No submodule, no URL in the public repo. The app finds
  the library through the `TL_DATA_DIR` config value, defaulting to the sibling path
  above. The public repo does not advertise that the private one exists.
- **PythonAnywhere holds a disposable serving copy** — both repos cloned on PA's disk. If
  the app lapses or the account is lost, nothing important is gone: re-clone and reload.
- **Never let PA hold the only copy.** Everything on PA is reproducible from the two repos.

This split is what makes the free tier's monthly keep-alive click a non-issue: forgetting
it disables the *site* (temporary), not the *data*.

**Corollary — never write library data into the code repo.** `library/`, `captures/`, and
`index/` are gitignored here and `tests/repo_hygiene_test.py` fails if they appear, because
a tool that ignores `TL_DATA_DIR` would otherwise put third-party tabs one `git add -A`
away from a public commit. Anything committed to the public repo must be my own work.

---

## 2. Design spine

Two format lanes share one metadata index + one SQLite database. Keep the original
artifact per piece; the index/DB is what powers search and the app, regardless of format.

| Lane        | Canonical artifact              | Cleaning          | Rendered by (in browser) |
|-------------|---------------------------------|-------------------|--------------------------|
| `chordpro`  | `tab.chordpro`                  | **central** (LLM) | ChordSheetJS             |
| `guitarpro` | `score.gp*` / `score.musicxml`  | metadata-only     | alphaTab                 |

The LLM clean step exists only for the `chordpro` lane — GP/MusicXML arrive already
structured, so "clean" there means extract metadata and move the blob into place.

---

## 3. Repo layout

**Code repo — `library_of_tabel/` (public):**

```
library_of_tabel/
  adapters/              # one module per source: fetch(url) -> RawArtifact
  skills/
    clean-tab/           # Claude Code skill for the chordpro lane (see §6)
  app/                   # the Flask app served on PythonAnywhere (see §7)
    __init__.py          # create_app() factory
    config.py            # TL_* resolution; refuses to boot without credentials
    config_test.py       # unit tests sit beside the module (see below)
    auth.py
    views.py
    library.py           # the only module that reads the library from disk
    templates/
    static/
      vendor/            # ChordSheetJS + alphaTab, vendored with their licenses
  samples/
    library/             # my own original sample entries — runs v0 with no data repo
  scripts/               # tl CLI (see §5), vendoring + sample generators
  tests/
    integration/         # anything needing the app assembled
    repo_hygiene_test.py # repo-level guards, tied to no one module
  docs/ROADMAP.md        # build state (see §0)
  pyproject.toml  uv.lock  .python-version  Makefile
  config.example.py      # documents every config key; real values never committed
  wsgi.py                # PythonAnywhere entry point -> app
  LICENSE                # MIT (vendored assets keep their own — see §8)
  CLAUDE.md              # this file
```

**Data repo — `library_of_tabel_data/` (private):**

```
library_of_tabel_data/
  captures/              # raw drops from acquisition, pre-clean; one dir per capture
    <capture-id>/
      raw.*              # raw scraped text / downloaded file
      capture.json       # source url, site, fetched_at, detected format
  library/               # canonical, committed source of truth
    <slug>/
      meta.yaml          # the record (see §4)
      tab.chordpro         # chordpro lane
      score.gp5 | score.musicxml   # guitarpro lane
  index/
    library.db           # generated SQLite w/ FTS5 (search) — committed
```

The app and CLI reach the data repo through `TL_DATA_DIR` and never assume a path
relative to the code repo.

`slug` = `normalize(artist)--normalize(title)[--variant]`, ascii, lowercased,
hyphen-separated. Collisions get a `--v2` suffix.

GP/MusicXML files are small (KB–low MB), so plain git handles them — **no Git LFS.**

**Where tests go.** Unit tests for `x.py` live at `x_test.py` next to it — imports stay
short, and a module that has no test file is visible from the directory listing rather
than from an absence somewhere else. Everything that needs the app assembled (test client,
real request cycle, disk) goes under `tests/integration/`; repo-level guards that cover no
single module stay directly in `tests/`. One `*_test.py` suffix throughout, so a file's
*location* is what says which kind it is. `make test` runs the lot in one pass —
`testpaths` spans `app`, `scripts`, and `tests`.

Pytest runs with `filterwarnings = ["error"]`. New warnings are failures; the only standing
exemption is pinned to the one flask_login deprecation and named in `pyproject.toml`.

---

## 4. Metadata schema (`library/<slug>/meta.yaml`)

```yaml
id:            # stable hash of source url + slug
title:
artist:
format:        # chordpro | guitarpro
files:         # [tab.chordpro] | [score.gp5]
tuning: EADGBE
capo: 0
key:
tempo:         # bpm, when known
duration_sec:  # guitarpro lane only
tags: []
source:
  url:
  site:
  fetched_at:
provenance:    # capture-id it came from
confidence:    # low|med|high — set low when the clean step inferred fields
```

`tl index` reads every `meta.yaml` (plus the first lines of each `tab.chordpro`) into
`index/library.db` for FTS5 search. `meta.yaml` stays the human-editable truth; the DB
is regenerated, never hand-edited.

---

## 5. Pipeline CLI (`tl`, Python + Typer) — runs on the laptop only

- `tl capture <url>` — run matching adapter, write `captures/<id>/raw.* + capture.json`.
- `tl clean <capture-id>` — branch on detected format:
  - `chordpro`: deterministic pre-clean → invoke clean-tab skill (§6) → write
    `library/<slug>/tab.chordpro` + `meta.yaml`. Validate the result parses with
    ChordSheetJS. Emit a diff; commit only on approval.
  - `guitarpro`: parse header for title/artist/tempo/tracks, move blob, write `meta.yaml`.
- `tl index` — regenerate `index/library.db` (SQLite + FTS5) from all `meta.yaml`.
- `tl deploy` — `git add/commit/push` in the **private data repo**. (Actual publish to PA
  is a `git pull` + reload on PA — see §7.)

All paths above are relative to `TL_DATA_DIR`, i.e. the private data repo — `tl` must
never write into the public code repo. `clean` and `index` must be idempotent: re-running
`clean` on an already-clean capture produces no diff. Acquisition never runs on PA (free
tier has an outbound allowlist and tiny CPU budget); it runs on the laptop.

---

## 6. Clean skill (`skills/clean-tab/`)

A Claude Code skill invoked headless by `tl clean` for the chordpro lane only.

**Input:** raw tab text + `capture.json`.
**Output:** strict JSON, no prose, no markdown fences:
```json
{ "chordpro": "<full ChordPro document>", "meta": { "title": "", "artist": "",
  "key": "", "tuning": "", "capo": 0, "tempo": null, "tags": [], "confidence": "" } }
```
**Rules:**
- Never invent chords or notes not present in the source. Preserve the original structure.
- Convert sections to ChordPro directives (`{start_of_verse}`/`{soc}` etc.); chords inline as `[Am]`.
- Infer `key`/`tuning`/`capo`/`tempo`/`tags` only from evidence; set `confidence: low` and
  leave fields null when guessing.
- Deterministic pre-clean happens in `tl` before the skill: normalize line endings, strip
  HTML entities/ads, preserve monospace alignment of ASCII-tab blocks.

The CLI writes files from the JSON; the skill never touches the filesystem.

---

## 7. The app (`app/`) — one Flask app on PythonAnywhere

Single app that serves the UI, the files, and the search. No separate static host, no
separate auth layer, no sync daemon.

**Auth (real, because there's now a backend).**
- Single user. A blanket **`before_request` gate** on the app — not per-route
  `@login_required` — covers **every** route including the file-serving routes, so
  tabs/GP files can't be fetched by guessing URLs. Structural rather than per-route,
  because one forgotten decorator is one leaked tab. Exempts only `/login` and `/static/`.
- `/static/` stays public and therefore holds **only** our own static assets (CSS, the PWA
  manifest) and vendored open-source JS and fonts — **never library content.** Tabs are
  served solely through `/file/<slug>/<filename>`, behind the gate.
- The password hash is read from an **env var / a config file that is NOT committed**
  (`instance/config.py`; see `config.example.py`). The repo never contains the credential.
- Serve only over HTTPS (PA gives you HTTPS on the `*.pythonanywhere.com` domain).

**Routes.**
- `/login`, `/logout`.
- `/` — searchable list (query box hits FTS5), filter by tag/tuning/artist.
- `/tab/<slug>` — detail page; loads `meta.yaml` + the artifact.
- `/file/<slug>/<filename>` — auth-gated file bytes (the browser renderers fetch these).
- `/api/search?q=` — FTS5 query → JSON, for the list page.

**Rendering (client-side, in the templates).**
- `chordpro` → **ChordSheetJS** parse + render, with a transpose control.
- `guitarpro` → **alphaTab** (renders GP 3–7 / MusicXML; enable alphaSynth playback).
- The Flask routes hand over metadata + file bytes; the browser does the rendering.

**Search.** SQLite **FTS5** over title/artist/tags/tuning + first lines of content. Server
-side, so no build step — `tl index` regenerates `library.db`, the app queries it live.

**Phone.** Just a browser at `you.pythonanywhere.com`; add a PWA manifest so it installs to
the home screen. (Offline is a later nicety, not v1.)

**Deploy loop (one place):** two repos means two clones on PA and two pulls.
1. Locally: `tl clean ...` → `tl index` → `tl deploy` (push to the private data repo).
2. On PA: open a Bash console → `git pull` in **both** repos → click **Reload** on the
   Web tab. Code changes need the code repo pulled; new tabs need the data repo pulled.
3. PA's virtualenv must be built from the **system** Python — uv-installed interpreters
   cannot back a PA web app. Use `UV_PYTHON_DOWNLOADS=never` there (local dev has no such
   constraint), and set `TL_DATA_DIR` to the data repo's path on PA.

**Free-tier reality:** the web app must be renewed ~monthly via one button on the Web tab,
or it goes offline (files are preserved — see §1). If that click will be forgotten and
downtime is unacceptable, the paid tier ($10/mo) removes expiry entirely; that's the only
part of this that would ever cost money.

---

## 8. Tech choices

- Pipeline/CLI: **Python** + Typer. GP header parse: **PyGuitarPro** (.gp3–5); for
  .gp7/.gpx, unzip and parse `score.gpif` XML.
- App: **Flask** + **Flask-Login** + **SQLite/FTS5** (stdlib `sqlite3`) + **PyYAML** (the
  `meta.yaml` records of §4). Templates serve **ChordSheetJS** + **@coderline/alphatab**,
  vendored into `app/static/vendor/`.
- Packaging: **uv**, with `uv.lock` committed and `.python-version` at 3.13.
  `requires-python` stays `>=3.11` as a floor — PA offers 3.11/3.12/3.13.
- Store/transport: **git** — public code repo, private data repo (§1). No LFS (no PDFs →
  files stay small).
- Host: **PythonAnywhere** free tier (512 MiB disk, 1 web app). Deploy via console `git pull`.

**Vendored asset licensing.** The code repo is public, so vendoring is redistribution.
Each vendored library ships with its upstream `LICENSE` and a `SOURCE.md` naming the
project and exact version. ChordSheetJS is **GPL-2.0-only**; alphaTab is **MPL-2.0**;
this repo's own code is **MIT**. Vendored bytes are committed *and* reproducible via
`scripts/vendor_assets.py`, which verifies them against npm-published hashes — PA's
outbound allowlist means deploy can never depend on fetching them.

Pin versions. Flag before adding anything beyond this list.

---

## 9. Build phases

- **v0 — app skeleton.** Flask app + login gate + a hardcoded example of each lane rendered
  (ChordSheetJS + alphaTab working behind auth). Prove the gated viewer end to end, locally.
- **v1 — chordpro pipeline.** One text adapter + `tl capture` + clean-tab skill + `tl clean`
  chordpro branch + `tl index` + FTS5 search in the app. Full acquire→clean→commit→view loop.
- **v2 — guitarpro lane.** Drop-in + metadata parse + alphaTab in the app.
- **v3 — deploy + polish.** Live on PythonAnywhere (git-pull deploy), PWA manifest,
  tags/setlists, dedupe on capture.

---

## 10. Privacy

Personal, single-user library.

- **The data repo stays private.** It holds third-party tab content acquired for personal
  use; it is personal storage, not publishing. Never make it public, and never mirror its
  contents into the code repo.
- **The code repo is public** and must contain only my own work plus properly-licensed
  vendored dependencies (§8). Sample and test fixtures are original material I wrote — no
  third-party tabs or lyrics, not even as fixtures.
- **Credentials live in neither repo.** `instance/config.py` is gitignored; the app refuses
  to start rather than fall back to a default secret.
