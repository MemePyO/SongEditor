import re


def parse_chordpro(text):
    """Parse ChordPro text into {label: [lines]} dict like SongEditor expects.

    - Section headers like [Verse 1], [Chorus] become group labels.
    - Chord lines (lines where every token is a chord) are stripped.
    - {start_of_*}/{end_of_*} directives are ignored.
    - {title:...}/{artist:...} directives are ignored.
    - All other non-empty lines become lyric lines.
    """
    sections = {}
    current = None
    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("{") and stripped.endswith("}"):
            continue
        m = re.match(r"^\[(.+)\]$", stripped)
        if m:
            current = m.group(1).strip()
            sections.setdefault(current, [])
            continue
        # detect chord-only lines: tokens are all chords
        tokens = stripped.split()
        if tokens and all(_is_chord(t) for t in tokens):
            continue
        if current is None:
            current = "Verse 1"
            sections.setdefault(current, [])
        sections[current].append(stripped)
    if not sections:
        sections = {"Verse 1": []}
    return sections


_CHORD_RE = re.compile(r"^[A-G][#b]?(m|maj|min|dim|aug|sus|add)?\d*(/[A-G][#b]?)?$")


def _is_chord(token):
    return bool(_CHORD_RE.match(token))


if __name__ == "__main__":
    sample = """[Verse 1]
C       G
Hello world
Am      F
again here
[Chorus]
C     G
la la la
"""
    print(parse_chordpro(sample))
