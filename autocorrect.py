import re
from spellchecker import SpellChecker

ROMANIAN_DICT_FILE = "dictionaries/ro_RO.dic"


def load_romanian_words(path=ROMANIAN_DICT_FILE):
    words = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                if i == 0 and line.isdigit():
                    continue
                word = line.split("/")[0]
                if word:
                    words.append(word.lower())
    except FileNotFoundError:
        pass
    return words

DIACRITIC_FIXES = {
    'ş': 'ș', 'ţ': 'ț',
    'Ş': 'Ș', 'Ţ': 'Ț',
}

WORD_LIST_FILE = "autocorrect_words.txt"


def load_word_list(path=WORD_LIST_FILE):
    replacements = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                if not line.strip() or line.strip().startswith("#"):
                    continue
                if "=" in line:
                    wrong, right = line.split("=", 1)
                    replacements[wrong.strip()] = right.strip()
    except FileNotFoundError:
        pass
    return replacements


def fix_diacritics(text):
    for wrong, right in DIACRITIC_FIXES.items():
        text = text.replace(wrong, right)
    return text


def fix_spacing(text):
    text = re.sub(r'\s+([,.!?;:])', r'\1', text)
    text = re.sub(r' {2,}', ' ', text)
    text = '\n'.join(line.rstrip() for line in text.split('\n'))
    return text


def capitalize_lines(text):
    lines = text.split('\n')
    out = []
    for line in lines:
        for i, ch in enumerate(line):
            if ch.isalpha():
                line = line[:i] + ch.upper() + line[i + 1:]
                break
        out.append(line)
    return '\n'.join(out)


def apply_word_list(text, replacements):
    for wrong, right in replacements.items():
        pattern = r'\b' + re.escape(wrong) + r'\b'
        text = re.sub(pattern, right, text)
    return text


def autocorrect_text(text, word_list=None):
    if word_list is None:
        word_list = load_word_list()
    text = fix_diacritics(text)
    text = fix_spacing(text)
    text = capitalize_lines(text)
    text = apply_word_list(text, word_list)
    return text


def autocorrect_blocks(text_blocks, word_list=None):
    if word_list is None:
        word_list = load_word_list()
    return {name: autocorrect_text(text, word_list) for name, text in text_blocks.items()}


def get_spellchecker():
    spell = SpellChecker()
    spell.word_frequency.load_words(load_romanian_words())
    return spell


def find_typos(text, spell=None):
    if spell is None:
        spell = get_spellchecker()
    typos = []
    for match in re.finditer(r"[A-Za-zÀ-ȚȘȚțșăâî]+", text):
        word = match.group()
        if word.lower() not in spell:
            typos.append((match.start(), match.end(), word))
    return typos
