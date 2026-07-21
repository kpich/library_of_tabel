# Tab Library — Repo Spec (`CLAUDE.md`)

A private, single-user system to acquire guitar tabs, normalize them, and view +
search the collection from phone and computer. One Flask app, hosted on
PythonAnywhere's free tier. Not a public site.

**How to use this file:** This is the source of truth. Scaffold incrementally by the
phases in §9 — do not build everything at once. Prefer small, reviewable commits.
Ask before adding heavy dependencies not listed in §8.

**Scope for now:** two format lanes only — `chordpro` and `guitarpro`. PDF/sheet-music
is explicitly out of scope for v1 (revisit later). This keeps everything text-sized:
plain git, no LFS, and 512 MiB of free disk holds thousands of pieces.

---

## 1. Where things live (read this first)

- **Source of truth = a private git repo + my laptop.** The pipeline runs locally and
  produces the library and a search index, which get committed to a **private** GitHub
  (or GitLab) repo. Private = personal storage, not publishing.
- **PythonAnywhere holds a disposable serving copy.** The Flask app + the library files
  live on the PA account's disk, pulled from the repo. If the app ever lapses or the
  account is lost, nothing important is gone — re-pull and reload.
- **Never let PA hold the only copy.** Everything on PA is reproducible from the repo.

This split is what makes the free tier's monthly keep-alive click a non-issue: forgetting
it disables the *site* (temporary), not the *data*.

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

```
tab-library/
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
  adapters/              # one module per source: fetch(url) -> RawArtifact
  skills/
    clean-tab/           # Claude Code skill for the chordpro lane (see §6)
  app/                   # the Flask app served on PythonAnywhere (see §7)
    __init__.py
    auth.py
    views.py
    templates/
    static/              # ChordSheetJS + alphaTab assets
  scripts/               # tl CLI (see §5)
  wsgi.py                # PythonAnywhere entry point -> app
  CLAUDE.md              # this file
```

`slug` = `normalize(artist)--normalize(title)[--variant]`, ascii, lowercased,
hyphen-separated. Collisions get a `--v2` suffix.

GP/MusicXML files are small (KB–low MB), so plain git handles them — **no Git LFS.**

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
- `tl deploy` — `git add/commit/push` to the private repo. (Actual publish to PA is a
  `git pull` + reload on PA — see §7.)

`clean` and `index` must be idempotent. Re-running `clean` on an already-clean capture
produces no diff. Acquisition never runs on PA (free tier has an outbound allowlist and
tiny CPU budget); it runs on the laptop.

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
- Single user. A `@login_required` decorator (Flask-Login, or a minimal session check)
  gates **every** route — including the file-serving routes, so tabs/GP files can't be
  fetched by guessing URLs.
- The password hash is read from a PythonAnywhere **env var / a config file that is NOT
  committed** to the repo. The repo never contains the credential.
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

**Deploy loop (one place):**
1. Locally: `tl clean ...` → `tl index` → `tl deploy` (push to private repo).
2. On PA: open a Bash console → `git pull` → click **Reload** on the Web tab. Done.

**Free-tier reality:** the web app must be renewed ~monthly via one button on the Web tab,
or it goes offline (files are preserved — see §1). If that click will be forgotten and
downtime is unacceptable, the paid tier ($10/mo) removes expiry entirely; that's the only
part of this that would ever cost money.

---

## 8. Tech choices

- Pipeline/CLI: **Python** + Typer. GP header parse: **PyGuitarPro** (.gp3–5); for
  .gp7/.gpx, unzip and parse `score.gpif` XML.
- App: **Flask** + **Flask-Login** + **SQLite/FTS5** (stdlib `sqlite3`). Templates serve
  **ChordSheetJS** + **@coderline/alphatab** (vendored into `app/static`).
- Store/transport: **git**, private repo (GitHub/GitLab). No LFS (no PDFs → files stay small).
- Host: **PythonAnywhere** free tier (512 MiB disk, 1 web app). Deploy via console `git pull`.

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

Personal, single-user library. Keep the repo **private**.
