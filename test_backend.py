import pytest
from SongEditorPro7Generic import escape_cocoa_rtf, rtf_text_start, inject_text_into_rtf, split_slides
from autocorrect import find_typos


class TestEscapeCocoaRtf:
    def test_ascii_text(self):
        assert escape_cocoa_rtf("hello world") == "hello world"

    def test_romanian_diacritics(self):
        result = escape_cocoa_rtf("șțăâî")
        assert "\\u" in result

    def test_special_chars(self):
        result = escape_cocoa_rtf("\\{test\\}")
        assert "\\\\" in result
        assert "\\{" in result
        assert "\\}" in result

    def test_empty_string(self):
        assert escape_cocoa_rtf("") == ""


class TestRtfTextStart:
    def test_simple_rtf(self):
        rtf = b"{\\rtf1\\ansi hello}"
        assert rtf_text_start(rtf) == 12

    def test_control_word_ending_in_digit(self):
        rtf = b"{\\rtf1\\cb2}"
        assert rtf_text_start(rtf) == 10

    def test_empty_rtf(self):
        rtf = b"{}"
        assert rtf_text_start(rtf) == 1

    def test_plain_text(self):
        rtf = b"hello"
        assert rtf_text_start(rtf) == 1


class TestInjectTextIntoRtf:
    def test_preserves_prefix(self):
        template = b"{\\rtf1\\ansi\\cb2}"
        result = inject_text_into_rtf(template, ["hello"])
        assert result.startswith(b"{\\rtf1\\ansi\\cb2")

    def test_escapes_text(self):
        template = b"{\\rtf1}"
        result = inject_text_into_rtf(template, ["{test}"])
        assert b"\\{test\\}" in result

    def test_empty_lines(self):
        template = b"{\\rtf1}"
        result = inject_text_into_rtf(template, [])
        assert result == b"{\\rtf1}"

    def test_space_after_cb2(self):
        template = b"{\\rtf1\\cb2}"
        result = inject_text_into_rtf(template, ["hello"])
        assert b"\\cb2 " in result


class TestSplitSlides:
    def test_basic_split(self):
        names = ["Romana", "Engleza"]
        texts = {
            "Romana": ["Verse 1", "line1", "line2", "Chorus", "c1", "c2"],
            "Engleza": ["Verse 1", "line1", "line2", "Chorus", "c1", "c2"],
        }
        slides = split_slides(names, texts, 2)
        assert len(slides) == 2
        assert slides[0]["label"] == "Verse 1"
        assert slides[1]["label"] == "Chorus"

    def test_empty_input(self):
        names = ["Romana"]
        texts = {"Romana": []}
        slides = split_slides(names, texts, 2)
        assert len(slides) == 0

    def test_single_block(self):
        names = ["Romana"]
        texts = {"Romana": ["line1", "line2", "line3"]}
        slides = split_slides(names, texts, 2)
        assert len(slides) == 2



class TestFindTypos:
    def test_english_words(self):
        from autocorrect import get_spellchecker
        spell = get_spellchecker()
        text = "hello world"
        assert len(find_typos(text, spell)) == 0

    def test_misspelled(self):
        from autocorrect import get_spellchecker
        spell = get_spellchecker()
        text = "helloo worldd"
        typos = find_typos(text, spell)
        assert len(typos) > 0

    def test_empty_string(self):
        from autocorrect import get_spellchecker
        spell = get_spellchecker()
        assert find_typos("", spell) == []
