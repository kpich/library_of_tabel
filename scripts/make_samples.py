"""Generate the sample library under ``samples/``.

    python scripts/make_samples.py [target-dir]

``samples/`` is what a clean clone runs against -- the Makefile points
``TL_DATA_DIR`` at it, so the app has a shelf to show before the private data
repo exists (CLAUDE.md 1). Its output is committed; this script is how it stays
reproducible, the same arrangement the vendored browser libraries use.

**Everything here is original work.** CLAUDE.md 10 keeps third-party tabs and
lyrics out of the public repo entirely -- including as fixtures -- so the words,
the chord changes and the little four-bar score below are mine, written for this
purpose. The pieces and the band are invented.

Determinism is the point: rerunning must reproduce the committed bytes exactly,
which is what ``scripts/make_samples_test.py`` asserts. Nothing here may read
the clock -- ``fetched_at`` is a literal.
"""

from pathlib import Path
import sys
from typing import Any

import yaml

from app.library import entry_id

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_TARGET = REPO_ROOT / "samples"

#: A literal, not today: a generated timestamp would make every regeneration a
#: diff and this script's own test unfalsifiable.
AUTHORED_ON = "2026-07-22"

ARTIST = "The Repeat Signs"


CHORDPRO_SLUG = "the-repeat-signs--kitchen-light"

# Original words and chords. A plain descending progression in G, verse/chorus,
# written to exercise the ChordPro directives the clean skill emits (CLAUDE.md 6)
# rather than to be a good song.
KITCHEN_LIGHT = """\
{title: Kitchen Light}
{artist: The Repeat Signs}
{key: G}
{capo: 0}
{tempo: 92}
{comment: Sample entry - original words and music, written for this repo.}

{start_of_verse}
[G]Coffee going cold be[D]side the sink
[Em]Nobody awake to [C]tell me what to think
[G]Half a dozen dishes [D]waiting for the day
[Em]Kitchen light is [C]on and I let it [G]stay
{end_of_verse}

{start_of_chorus}
[C]Hum of the [G]fridge, [D]hum of the street
[C]Everything is [G]quiet and [D]nothing is complete
[C]Leave it burning [G]low, [D]leave it burning [Em]bright
[C]Nobody goes [D]hungry by the kitchen [G]light
{end_of_chorus}

{start_of_verse}
[G]Rain against the window [D]sounds like applause
[Em]Every empty chair is [C]empty for a cause
[G]Morning is a rumour [D]somebody let slip
[Em]I'll believe it [C]when I see the [G]drip
{end_of_verse}

{start_of_chorus}
[C]Hum of the [G]fridge, [D]hum of the street
[C]Everything is [G]quiet and [D]nothing is complete
[C]Leave it burning [G]low, [D]leave it burning [Em]bright
[C]Nobody goes [D]hungry by the kitchen [G]light
{end_of_chorus}
"""


GUITARPRO_SLUG = "the-repeat-signs--practice-loop"

PRACTICE_LOOP_TITLE = "Practice Loop"

#: Four bars, 4/4, quarter notes, resolving to a held chord. ``divisions`` is 2,
#: so a quarter note is 2 and a whole note is 8.
#:
#: MusicXML rather than a real .gp5 for the guitarpro lane at v0: it is text, so
#: no binary blob and no PyGuitarPro dependency yet, and alphaTab reads it
#: natively (CLAUDE.md 2 lists both as canonical artifacts for the lane).
PRACTICE_LOOP_MEASURES: list[list[list[tuple[str, int]]]] = [
    [[("A", 2)], [("E", 3)], [("C", 3)], [("E", 3)]],
    [[("G", 2)], [("D", 3)], [("B", 2)], [("D", 3)]],
    [[("F", 2)], [("C", 3)], [("A", 2)], [("C", 3)]],
    [[("E", 2), ("B", 2), ("E", 3)]],
]

PRACTICE_LOOP_TEMPO = 84


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 else DEFAULT_TARGET
    for slug, meta, files in (_chordpro_sample(), _guitarpro_sample()):
        directory = target / "library" / slug
        directory.mkdir(parents=True, exist_ok=True)
        _write(directory / "meta.yaml", _dump_meta(meta))
        for name, content in files.items():
            _write(directory / name, content)
        print(f"wrote {directory}")
    return 0


def _chordpro_sample() -> tuple[str, dict[str, Any], dict[str, str]]:
    return (
        CHORDPRO_SLUG,
        _meta(
            slug=CHORDPRO_SLUG,
            title="Kitchen Light",
            fmt="chordpro",
            files=["tab.chordpro"],
            key="G",
            tempo=92,
            tags=["sample", "acoustic"],
        ),
        {"tab.chordpro": KITCHEN_LIGHT},
    )


def _guitarpro_sample() -> tuple[str, dict[str, Any], dict[str, str]]:
    meta = _meta(
        slug=GUITARPRO_SLUG,
        title=PRACTICE_LOOP_TITLE,
        fmt="guitarpro",
        files=["score.musicxml"],
        key="Am",
        tempo=PRACTICE_LOOP_TEMPO,
        tags=["sample", "exercise"],
    )
    # Four bars of 4/4 at 84bpm. duration_sec is guitarpro-only (CLAUDE.md 4).
    meta["duration_sec"] = round(4 * 4 * 60 / PRACTICE_LOOP_TEMPO)
    return GUITARPRO_SLUG, meta, {"score.musicxml": _musicxml()}


def _meta(
    *,
    slug: str,
    title: str,
    fmt: str,
    files: list[str],
    key: str,
    tempo: int,
    tags: list[str],
) -> dict[str, Any]:
    """One CLAUDE.md 4 record, in schema order.

    ``source.url`` is null because these came from nowhere -- they were written
    here. ``provenance`` names this script instead of a capture id for the same
    reason: there is no capture behind them.
    """
    return {
        "id": entry_id(None, slug),
        "title": title,
        "artist": ARTIST,
        "format": fmt,
        "files": files,
        "tuning": "EADGBE",
        "capo": 0,
        "key": key,
        "tempo": tempo,
        "duration_sec": None,
        "tags": tags,
        "source": {"url": None, "site": "samples", "fetched_at": AUTHORED_ON},
        "provenance": "scripts/make_samples.py",
        "confidence": "high",
    }


def _dump_meta(meta: dict[str, Any]) -> str:
    # sort_keys=False keeps the schema's own order, which is the order CLAUDE.md
    # 4 documents and the order a human editing the file expects to find.
    return yaml.dump(
        meta, sort_keys=False, allow_unicode=True, default_flow_style=False
    )


def _musicxml() -> str:
    """A minimal, self-contained score-partwise document.

    No DOCTYPE: the MusicXML DTD lives at musicxml.org, and a reference to it is
    a reference to the network. v0's exit criterion is that both lanes render
    with zero external requests, and browsers not fetching external DTDs is not
    something to lean on when simply omitting it is valid.
    """
    measures = "\n".join(
        _measure(number, chords)
        for number, chords in enumerate(PRACTICE_LOOP_MEASURES, 1)
    )
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <work>
    <work-title>{PRACTICE_LOOP_TITLE}</work-title>
  </work>
  <identification>
    <creator type="composer">{ARTIST}</creator>
    <rights>Original sample content for library of tabel. MIT, with the repo.</rights>
    <encoding>
      <software>scripts/make_samples.py</software>
      <encoding-date>{AUTHORED_ON}</encoding-date>
    </encoding>
  </identification>
  <part-list>
    <score-part id="P1">
      <part-name>Guitar</part-name>
      <score-instrument id="P1-I1">
        <instrument-name>Acoustic Guitar</instrument-name>
      </score-instrument>
      <midi-instrument id="P1-I1">
        <midi-channel>1</midi-channel>
        <midi-program>26</midi-program>
      </midi-instrument>
    </score-part>
  </part-list>
  <part id="P1">
{measures}
  </part>
</score-partwise>
"""


def _measure(number: int, chords: list[list[tuple[str, int]]]) -> str:
    lines = [f'    <measure number="{number}">']
    if number == 1:
        lines.append(_first_measure_attributes())
    for chord in chords:
        # A whole-note chord where a bar holds one event, quarters otherwise.
        duration, note_type = (8, "whole") if len(chords) == 1 else (2, "quarter")
        for position, (step, octave) in enumerate(chord):
            lines.append(
                _note(step, octave, duration, note_type, in_chord=position > 0)
            )
    lines.append("    </measure>")
    return "\n".join(lines)


def _first_measure_attributes() -> str:
    # clef-octave-change -1 is the guitar's treble clef: it sounds an octave
    # below where it is written, and the pitches above are sounding pitches.
    return f"""\
      <attributes>
        <divisions>2</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <clef><sign>G</sign><line>2</line><clef-octave-change>-1</clef-octave-change></clef>
      </attributes>
      <direction placement="above">
        <direction-type>
          <metronome><beat-unit>quarter</beat-unit><per-minute>{PRACTICE_LOOP_TEMPO}</per-minute></metronome>
        </direction-type>
        <sound tempo="{PRACTICE_LOOP_TEMPO}"/>
      </direction>"""


def _note(
    step: str, octave: int, duration: int, note_type: str, *, in_chord: bool
) -> str:
    chord_tag = "<chord/>" if in_chord else ""
    return (
        f"      <note>{chord_tag}"
        f"<pitch><step>{step}</step><octave>{octave}</octave></pitch>"
        f"<duration>{duration}</duration><voice>1</voice><type>{note_type}</type></note>"
    )


def _write(path: Path, content: str) -> None:
    # newline="\n" so a checkout on any platform regenerates the committed bytes.
    path.write_text(content, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
