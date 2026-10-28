import os

import pytest
from SongEditorPro7Generic import escape_cocoa_rtf, rtf_text_start, inject_text_into_rtf, split_slides, resolve_template
from autocorrect import find_typos
import presentation_pb2
from single_export import gen_single_pro
from melodii import save_json_to_melodii, load_json_from_melodii, saved_song_names, find_saved_song


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

    def test_preview_model_realistic(self):
        names = ["Romana", "Engleza"]
        texts = {
            "Romana": ["Verse 1", "linia 1", "linia 2", "linia 3", "Chorus", "ref 1", "ref 2"],
            "Engleza": ["Verse 1", "line 1", "line 2", "line 3", "Chorus", "cho 1", "cho 2"],
        }
        slides = split_slides(names, texts, 2)
        assert [s["label"] for s in slides] == ["Verse 1", "Verse 1", "Chorus"]
        assert slides[0]["Romana"] == ["linia 1", "linia 2"]
        assert slides[1]["Romana"] == ["linia 3"]
        assert slides[2]["Engleza"] == ["cho 1", "cho 2"]
        for slide in slides:
            assert "Verse 1" not in slide["Romana"]
            assert "Chorus" not in slide["Romana"]


class TestResolveTemplate:
    def test_configured_template_used(self):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Template.pro")
        resolved, names, used_fallback = resolve_template(path)
        assert resolved == path
        assert used_fallback is False
        assert names

    def test_missing_template_falls_back_to_bundled(self):
        resolved, names, used_fallback = resolve_template("C:/definitely/not/here.pro")
        assert resolved is None
        assert used_fallback is True
        assert names


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


class TestSingleExport:
    def _element_names(self, raw):
        p = presentation_pb2.Presentation()
        p.ParseFromString(raw)
        names = set()
        for cue in p.cues:
            for action in cue.actions:
                for el in action.slide.presentation.base_slide.elements:
                    names.add(el.element.name)
        return names

    def test_only_single_block_remains(self):
        texts = {"Romana": ["Verse 1", "hello world", "again here"]}
        raw = gen_single_pro("Romana", texts, 2)
        assert self._element_names(raw) == {"Romana"}

    def test_keep_other_blocks_when_disabled(self):
        texts = {"Romana": ["hello world"]}
        raw = gen_single_pro("Romana", texts, 2, remove_other_blocks=False)
        assert self._element_names(raw) == {"Romana", "Engleza"}

    def test_text_injected(self):
        texts = {"Romana": ["hello world"]}
        raw = gen_single_pro("Romana", texts, 2)
        p = presentation_pb2.Presentation()
        p.ParseFromString(raw)
        rtfs = [el.element.text.rtf_data
                for cue in p.cues for action in cue.actions
                for el in action.slide.presentation.base_slide.elements]
        assert any(b"hello world" in rtf.lower() for rtf in rtfs)

    def test_groups_generated(self):
        texts = {"Romana": ["Verse 1", "hello world", "Chorus", "la la la"]}
        raw = gen_single_pro("Romana", texts, 2)
        p = presentation_pb2.Presentation()
        p.ParseFromString(raw)
        group_names = {cg.group.name for cg in p.cue_groups}
        assert "Verse 1" in group_names
        assert "Chorus" in group_names


class TestMelodii:
    def _seed(self, directory):
        save_json_to_melodii("Amazing Grace", {"Romana": ["Verse 1", "linie"]}, directory)
        save_json_to_melodii("How Great", {"Romana": ["line"]}, directory)
        save_json_to_melodii("Amazing Grace (Single)", {"Romana": ["single"]}, directory)

    def test_round_trip(self, tmp_path):
        texts = {"Romana": ["Verse 1", "salvata"], "Engleza": ["Verse 1", "saved"]}
        path = save_json_to_melodii("Melodie", texts, tmp_path)
        assert os.path.exists(path)
        assert load_json_from_melodii("Melodie", tmp_path) == texts

    def test_saved_song_names_excludes_single(self, tmp_path):
        self._seed(tmp_path)
        assert saved_song_names(tmp_path) == ["Amazing Grace", "How Great"]

    def test_saved_song_names_include_single(self, tmp_path):
        self._seed(tmp_path)
        assert saved_song_names(tmp_path, include_single=True) == [
            "Amazing Grace", "Amazing Grace (Single)", "How Great"]

    def test_find_saved_song_exact_and_case_insensitive(self, tmp_path):
        self._seed(tmp_path)
        assert find_saved_song("How Great", tmp_path) == "How Great"
        assert find_saved_song("how great", tmp_path) == "How Great"
        assert find_saved_song("Missing", tmp_path) is None
