import os
import sys
import json

MELODII_DIR_NAME = "Melodii"


def melodii_dir():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base, MELODII_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def saved_song_names(directory=None, include_single=False):
    directory = directory or melodii_dir()
    try:
        names = [f[:-5] for f in os.listdir(directory) if f.lower().endswith(".json")]
    except OSError:
        return []
    if not include_single:
        names = [n for n in names if not n.endswith(" (Single)")]
    return sorted(names)


def save_json_to_melodii(title, song_texts, directory=None):
    directory = directory or melodii_dir()
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, title + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(song_texts, f, ensure_ascii=False, indent=2)
    return path


def load_json_from_melodii(title, directory=None):
    directory = directory or melodii_dir()
    path = os.path.join(directory, title + ".json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def find_saved_song(title, directory=None):
    names = saved_song_names(directory, include_single=True)
    if title in names:
        return title
    lowered = title.lower()
    for name in names:
        if name.lower() == lowered:
            return name
    return None
