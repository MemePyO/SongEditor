# ProPresenter 7 Song Editor

A Windows desktop app (and optional web variants) that turns multilingual song
lyrics into a ProPresenter 7 presentation. You paste the lyrics for each
language side by side, mark the sections (Verse, Chorus, Bridge, ...), and the
app generates a `.pro` file you can import straight into ProPresenter 7 — with
the section groups and slide splits already built.

It supports multiple languages/translations (the shipped template has
`Romana` and `Engleza`), a "single language" export, Romanian spell checking,
and PDF import.

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

---

## Desktop app (`Main.py`)

Run the app, then use the three tabs:

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

### Edit Group Names
- Edit `GroupNames.txt` directly in the app and save. Supports ranges such as
  `Verse 1..30`, which expand to `Verse 1`, `Verse 2`, ... where used.

### Toolbar
- **Song Name** – output file name (sanitised automatically).
- **Lines per Slide** – how many lyric lines go on each slide.
- **Arrangement** – comma-separated group order (e.g. `Verse 1, Chorus, Verse 2, Chorus`).
- **Font Size** – editor font size (persisted).
- **Open** – load a saved `.json` back into the editor.
- **Save** – write `<title>.pro` + `<title>.json`.
- **Check Typos** – Romanian spell check; unknown words are highlighted.
- **Light/Dark Mode** – theme toggle (dark blue-tinted / light green-tinted),
  remembered in `config.json`.

Unknown group labels found in the first block are reported before saving or
exporting, so typos in section names don't silently become groups.

---

## Output files

The app writes two files (in your **Downloads** folder, or the folder chosen by
the app):

| Action | Files |
| --- | --- |
| **Save** | `<title>.pro` (all languages) and `<title>.json` (editable backup) |
| **Download as Single** | `<title> (Single).pro` and `<title> (Single).json` (Romanian block only) |

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
single_export.py         "Download as Single" export (Romanian-only .pro)
autocorrect.py           Romanian spell checker
streamlit_gui.py         Streamlit JSON editor
flask_gui.py             Flask web app
test_backend.py          Pytest backend tests
build.spec               PyInstaller spec
Template.pro             Source template presentation
GroupNames.txt           Recognised section labels
autocorrect_words.txt    Custom spell-check word replacements
dictionaries/            Romanian Hunspell dictionary (ro_RO.aff/.dic)
assets/app.ico           Application icon
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
