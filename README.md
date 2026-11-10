# ProPresenter 7 Song Editor

A Windows desktop app (plus optional web editors) that turns multilingual song
lyrics into a ProPresenter 7 presentation. Paste each language's lyrics side by
side, mark the sections (`Verse`, `Chorus`, `Bridge`, ...) and the app generates
a `.pro` file that imports straight into ProPresenter 7 — with section groups,
slide splits and template styling already built.

It supports multiple languages/translations (the bundled template defines
`Romana` and `Engleza`), single-language export, Romanian spell checking, PDF
import, Melodii song import, and opening saved presentations back into the
editor for round-trip editing.

---

## What it does

ProPresenter 7 has no simple way to build a song with several language
translations. This tool reads a **template** presentation (which defines how
many text boxes exist and their names/order), takes your lyrics, and produces a
new `.pro` presentation where:

- each **section label** (`Verse 1`, `Chorus`, ...) becomes a ProPresenter
  **group / arrangement**
- lyrics are split into **slides** of N lines (configurable)
- each language is placed in its own text box, matching the template layout
- the text keeps the template's RTF styling (font, colour, alignment)

It can also go the other way: a `.pro` presentation produced by this app (or any
ProPresenter export) can be **opened in the editor** — the RTF text is decoded
(including `\u` unicode escapes, hex escapes and surrogate pairs) and re-injected
back into the template, so diacritics such as `Ă`, `Â`, `Î`, `ș`, `ț` survive the
round trip.

A `.pro` file is raw protobuf (`rv.data.Presentation`). See
[`docs/pro_format.md`](docs/pro_format.md) for a practical reference to the
parts of the format this app relies on.

---

## Features

- Multi-language columns with synchronised scrolling and hover highlighting
- Section labels become ProPresenter groups and an arrangement
- Configurable lines per slide
- Template-driven output (RTF/attribute styling preserved)
- **PDF import** — auto-detects the Romanian and English sections
- **Melodii import** — pick a saved song from the `Melodii\` folder
- **Round-trip editing** — open a `.pro` back into the editor
- **Single-language export** — a `.pro` containing only the primary text block
- Romanian spell check (Hunspell `ro_RO` dictionary)
- Slide preview with per-group slide counts
- Autosave (debounced) and keyboard shortcuts
- Light/dark theme, persisted in `config.json`
- Standalone Windows `.exe` via PyInstaller

---

## Recent changes

- **Autosave** – the song is saved as `.json` to the output folder after a short
  debounce while you type.
- **Keyboard shortcuts** – `Ctrl+S` save, `Ctrl+O` open, `Ctrl+N` new song.
- **Undo/redo** – `Ctrl+Z` / `Ctrl+Y` in every text box; arrangement order edits
  are undoable too (custom undo stack).
- **Error dialogs** – failures are shown in a dialog and logged to `logs\app.log`.
- **CI** – backend tests run on every push/PR (GitHub Actions).
- **RTF engine** – encode/decode moved into `rtf_engine.py` and covered by tests.
- **`.pro` open/edit** – open a ProPresenter file into the editor; group labels
  and lyrics are decoded from RTF and re-saved back out.
- **Melodii import** – pick a saved Melodii song and import its sections.
- **Slide preview** – incremental card updates with a debounce, plus per-group
  slide counts in the preview summary.
- **Template fallback** – if the configured template is missing/stale, fall back
  to the bundled template.
- **Undo/select-all**, **New song**, output folder picker, arrangement labels
  from the song text.

---

## Desktop app (`Main.py`)

Run the app, then use the four tabs:

### Translate View
- One column per language text block (from `Template.pro`), with a shared
  line-number column and synchronised scrolling.
- Hover a row to highlight the same line across all languages.
- **Drag-and-drop a PDF** onto a column (or the window) to import lyrics; the
  app auto-detects the Romanian and English sections.
- Lines that match a known **group name** are treated as section headers, not
  lyrics.

### Single View
- A focused editor that **mirrors the first (Romanian) text block**, with the
  same line numbers, hover highlight and label handling.
- **Download as Single** exports a `.pro` that contains **only the Romanian
  text block** — every other language text object is removed from the
  presentation.

### Slide Preview
- Live preview of the slides that will be generated, with one card per slide
  and the section label in the card title.
- Shows a per-group slide count summary (e.g. `Verse 1: 2 · Chorus: 4`).
- **Primary language only** toggle and a manual **Refresh Preview** button;
  refreshes are debounced while you type.

### Edit Group Names
- Edit `GroupNames.txt` directly in the app and save. Supports ranges such as
  `Verse 1..30`, which expand to `Verse 1`, `Verse 2`, ... where used.

### Toolbar
- **Song Name** – output file name (sanitised automatically), with autocomplete
  from the saved Melodii songs.
- **Import** – pick a saved Melodii song and load it into the editor.
- **Load Template** – choose a different `Template.pro`; the columns rebuild
  from its text block names.
- **Lines per Slide** – how many lyric lines go on each slide.
- **Arrangement** – comma-separated group order (e.g. `Verse 1, Chorus, Verse 2, Chorus`),
  with an **Edit Arrangement** dialog (add/remove/reorder).
- **Font Size** – editor font size (persisted).
- **Open** – load a saved `.json` back into the editor, or open a ProPresenter
  `.pro` presentation into the editor (RTF decode → editor → re-export).
- **Save** – write `<title>.pro` + `<title>.json`.
- **Check Typos** – Romanian spell check; unknown words are highlighted.
- **New** – clear the editor and start a new song.
- **Light/Dark Mode** – theme toggle (dark blue-tinted / light green-tinted),
  remembered in `config.json`.
- **Output Folder** – choose where `.pro`/`.json` files are written.

Unknown group labels found in the first block are reported before saving or
exporting, so typos in section names don't silently become groups.

### Autosave & shortcuts
- Typing in any lyric editor schedules an autosave after ~2 seconds; the song
  is written to `<title>.json` in the output folder.
- `Ctrl+S` save, `Ctrl+O` open, `Ctrl+N` new song, `Ctrl+A` select all.

---

## Output files

The app writes two files (in your **Downloads** folder, or the folder chosen by
the app):

| Action | Files |
| --- | --- |
| **Save** | `<title>.pro` (all languages) and `<title>.json` (editable backup) |
| **Download as Single** | `<title> (Single).pro` and `<title> (Single).json` (Romanian block only) |
| **Autosave** | `<title>.json` (editable backup, updated while you type) |

Import the `.pro` in ProPresenter 7 via **File → Import**.

---

## Requirements / setup

Prerequisite concepts:

- **`Template.pro`** – a ProPresenter 7 presentation that defines your text
  boxes. Each text object's **name** and **order** become a language column.
  To change languages: create a new presentation in ProPresenter 7, add one
  text object per language, give each a unique name, order them, and export it
  as `Template.pro` in this folder.
- **`GroupNames.txt`** – the list of recognised section labels (supports
  `Name 1..N` ranges).
- **`dictionaries/ro_RO.aff` + `ro_RO.dic`** – Romanian spell-check dictionary.

Python packages (see `requirements.txt`):

```
ttkbootstrap
pyspellchecker
protobuf
pyinstaller
pytest
streamlit
flask
pymupdf
tkinterdnd2
```

Install:

```
pip install -r requirements.txt
```

Run the desktop app:

```
python Main.py
```

The app stores its settings in `config.json` next to the program (theme, font
size, output folder and last-used template) and writes runtime errors to
`logs\app.log`.

---

## Building a standalone .exe

A PyInstaller spec is included. It bundles `Template.pro`, `GroupNames.txt`,
`autocorrect_words.txt`, the Romanian dictionary, the tkinterdnd2 data and the
PyMuPDF native libraries, and embeds `assets/app.ico`.

```
python -m PyInstaller --noconfirm --clean build.spec
```

The result is a folder build at `dist\ProPresenter7SongEditor\` containing
`ProPresenter7SongEditor.exe` (run it from its own folder — `config.json` and
`logs\` are written next to the exe). Runtime errors are logged to
`logs\app.log`.

---

## Web variants (optional)

- **Streamlit JSON editor** – `streamlit_gui.py`: a lightweight page to enter
  lyrics and download a `.json` for the desktop app.

  ```
  python -m streamlit run streamlit_gui.py
  ```

- **Flask app** – `flask_gui.py`: a full web form with `.pro`/`.json` download,
  typo checking and JSON reload. Usable for self-hosting or PythonAnywhere.

---

## Project structure

```
Main.py                  Desktop GUI (Tkinter + ttkbootstrap)
SongEditorPro7Generic.py .pro generation, RTF injection, slide/group splitting
rtf_engine.py            RTF encode/decode (escapes, unicode, surrogate pairs)
single_export.py         "Download as Single" export (Romanian-only .pro)
autocorrect.py           Romanian spell checker
melodii.py               Saved-song store (Melodii\ folder) + import helpers
streamlit_gui.py         Streamlit JSON editor
flask_gui.py             Flask web app
test_backend.py          Pytest backend tests
build.spec               PyInstaller spec
Template.pro             Source template presentation
GroupNames.txt           Recognised section labels
autocorrect_words.txt    Custom spell-check word replacements
dictionaries/            Romanian Hunspell dictionary (ro_RO.aff/.dic)
assets/app.ico           Application icon
docs/pro_format.md       ProPresenter .pro format reference
.github/workflows/       CI: backend tests on push/PR
```

Run the tests:

```
python -m pytest test_backend.py
```

---

## Credits

Originally created as **MultiLanguage ProPresenter** by
[JacobBaartse](https://github.com/JacobBaartse/MultiLanuageProPresenter).
This repository is an extended fork with a desktop GUI, single-language export,
theming, PDF import and PyInstaller packaging.

Introduction video: https://www.youtube.com/watch?v=z6BaM3yR2-k
