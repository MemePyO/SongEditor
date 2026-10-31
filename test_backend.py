import os
import json

import pytest
from SongEditorPro7Generic import (escape_cocoa_rtf, rtf_text_start, inject_text_into_rtf,
                                  split_slides, resolve_template, expand_group_labels,
                                  load_group_labels, invalidate_group_labels_cache,
                                  save_song, gen_pro_data, rtf_to_plain, pro_to_song_texts)
from autocorrect import find_typos
import presentation_pb2
from single_export import gen_single_pro, save_single
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


class TestGroupLabels:
    def test_expand_ranges(self):
        labels = expand_group_labels(["Verse 1..3", "Chorus", "", "  Bridge  "])
        assert labels == ["Verse 1", "Verse 2", "Verse 3", "Chorus", "Bridge"]

    def test_expand_keeps_unparseable_lines(self):
        assert expand_group_labels(["Weird..thing"]) == ["Weird..thing"]
        assert expand_group_labels(["Verse 1..x"]) == ["Verse 1..x"]

    def test_load_group_labels_from_file(self, tmp_path):
        path = tmp_path / "GroupNames.txt"
        path.write_text("Verse 1..2\nChorus\n", encoding="utf-8")
        assert load_group_labels(str(path)) == ["Verse 1", "Verse 2", "Chorus"]

    def test_load_group_labels_missing_file(self, tmp_path):
        assert load_group_labels(str(tmp_path / "nope.txt")) == []

    def test_load_group_labels_cache_invalidated(self, tmp_path):
        path = tmp_path / "GroupNames.txt"
        path.write_text("Verse 1\n", encoding="utf-8")
        assert load_group_labels(str(path)) == ["Verse 1"]
        path.write_text("Chorus\n", encoding="utf-8")
        invalidate_group_labels_cache()
        assert load_group_labels(str(path)) == ["Chorus"]

    def test_split_slides_accepts_explicit_labels(self):
        names = ["Romana"]
        texts = {"Romana": ["Verse 1", "a", "b", "Chorus", "c", "d"]}
        slides = split_slides(names, texts, 2, labels=["Verse 1", "Chorus"])
        assert [s["label"] for s in slides] == ["Verse 1", "Chorus"]

    def test_split_slides_with_no_labels_treats_text_as_lyrics(self):
        names = ["Romana"]
        texts = {"Romana": ["Verse 1", "a", "b"]}
        slides = split_slides(names, texts, 3, labels=[])
        assert len(slides) == 1
        assert slides[0]["Romana"] == ["Verse 1", "a", "b"]


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


class TestRtfToPlain:
    def test_plain_text(self):
        assert rtf_to_plain(b"{\\rtf1\\ansi Hello World}") == ["Hello World"]

    def test_par_line_break(self):
        assert rtf_to_plain(b"{\\rtf1\\ansi Hello\\par World}") == ["Hello", "World"]

    def test_control_word_param_ignored(self):
        # \fs24 sets font size; its numeric param must not leak into the text.
        assert rtf_to_plain(b"{\\rtf1\\ansi Hello\\fs24") == ["Hello"]

    def test_hex_escape(self):
        assert rtf_to_plain(b"{\\rtf1\\ansi Caf\\'e9 B}") == ["Café B"]

    def test_unicode_escape(self):
        assert rtf_to_plain(b"{\\rtf1\\ansi Caf\\u233? B}") == ["Café B"]

    def test_unicode_escape_surrogate_pair(self):
        # Astral plane: encoder emits two \u escapes (high?low?) that must
        # combine into a single code point. Values are signed 16-bit shorts.
        cp = 0x1F600  # emoji, astral plane
        high = 0xD800 + ((cp - 0x10000) >> 10)
        low = 0xDC00 + ((cp - 0x10000) & 0x3FF)
        high_s = high - 65536 if high > 32767 else high
        low_s = low - 65536 if low > 32767 else low

        def esc(v):
            return "\\u" + str(v - 65536 if v > 32767 else v) + "?"

        raw = ("{\\rtf1\\ansi " + esc(high_s) + esc(low_s) + "}").encode("ascii")
        assert rtf_to_plain(raw) == [chr(cp)]

    def test_unicode_escape_negative_signed_value(self):
        # Negative signed shorts appear for astral code points (e.g. \u-10179?).
        high = -10179 + 65536  # 0xD83D, a high surrogate
        raw = ("{\\rtf1\\ansi \\u-10179?}").encode("ascii")
        assert rtf_to_plain(raw) == [chr(high)]

    def test_empty_rtf(self):
        assert rtf_to_plain(b"") == []


class TestProToSongTexts:
    def test_round_trip(self):
        texts = {
            "Romana": ["Verse 1", "linia 1", "linia 2", "Chorus", "ref 1"],
            "Engleza": ["Verse 1", "line 1", "line 2", "Chorus", "cho 1"],
        }
        raw = gen_pro_data(["Romana", "Engleza"], texts, 2)
        result = pro_to_song_texts(raw, ["Romana", "Engleza"])
        assert result["Romana"] == ["Verse 1", "LINIA 1", "LINIA 2", "Chorus", "REF 1"]
        assert result["Engleza"] == ["Verse 1", "LINE 1", "LINE 2", "Chorus", "CHO 1"]

    def test_empty_pro_yields_empty_blocks(self):
        raw = gen_pro_data(["Romana"], {"Romana": []}, 2)
        result = pro_to_song_texts(raw, ["Romana"])
        assert result["Romana"] == []

    def test_pro_with_empty_lyrics_has_no_labels(self):
        raw = gen_pro_data(["Romana", "Engleza"], {"Romana": [], "Engleza": []}, 2)
        result = pro_to_song_texts(raw, ["Romana", "Engleza"])
        assert result == {"Romana": [], "Engleza": []}


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


# ---------------------------------------------------------
#  SAVE CONTRACTS (JSON + .pro)
# ---------------------------------------------------------
SONG_TEXTS = {
    "Romana": ["Verse 1", "linia 1", "linia 2", "Chorus", "ref 1"],
    "Engleza": ["Verse 1", "line 1", "line 2", "Chorus", "cho 1"],
}


def _load_pro(source):
    presentation_obj = presentation_pb2.Presentation()
    if isinstance(source, bytes):
        presentation_obj.ParseFromString(source)
    else:
        with open(source, "rb") as f:
            presentation_obj.ParseFromString(f.read())
    return presentation_obj


def _elements(cue):
    return cue.actions[0].slide.presentation.base_slide.elements


class TestSaveSongContract:
    def test_writes_json_and_pro(self, tmp_path):
        base = str(tmp_path / "song")
        save_song(["Romana", "Engleza"], SONG_TEXTS, 2, base)

        assert os.path.isfile(base + ".json")
        assert os.path.isfile(base + ".pro")
        with open(base + ".json", "r", encoding="utf-8") as f:
            assert json.load(f) == SONG_TEXTS

        pro = _load_pro(base + ".pro")
        # 1 intro + 2 lyric slides + Interlude + Ending
        assert len(pro.cues) == 5
        assert [e.element.name for e in _elements(pro.cues[0])] == ["Romana", "Engleza"]

    def test_cue_groups_include_sections_and_fixed_slides(self, tmp_path):
        base = str(tmp_path / "song")
        save_song(["Romana", "Engleza"], SONG_TEXTS, 2, base)
        pro = _load_pro(base + ".pro")
        groups = [cg.group.name for cg in pro.cue_groups]
        assert groups[0] == "Intro"
        assert groups[1:3] == ["Verse 1", "Chorus"]
        assert groups[-2:] == ["Interlude", "Ending"]

    def test_lyrics_land_in_the_right_block(self, tmp_path):
        base = str(tmp_path / "song")
        save_song(["Romana", "Engleza"], SONG_TEXTS, 2, base)
        pro = _load_pro(base + ".pro")
        by_name = {e.element.name: e.element.text.rtf_data for e in _elements(pro.cues[1])}
        # Both template blocks are all-caps, so compare case-insensitively.
        assert b"linia 1" in by_name["Romana"].lower()
        assert b"linia 2" in by_name["Romana"].lower()
        assert b"line 1" in by_name["Engleza"].lower()
        assert b"line 2" in by_name["Engleza"].lower()
        assert b"line 1" not in by_name["Romana"].lower()

    def test_notes_injected_into_every_cue(self, tmp_path):
        base = str(tmp_path / "song")
        save_song(["Romana", "Engleza"], SONG_TEXTS, 2, base,
                  notes_lines=["note one", "note two"])
        pro = _load_pro(base + ".pro")
        for cue in pro.cues:
            notes = cue.actions[0].slide.presentation.notes.rtf_data
            assert b"note one" in notes
            assert b"note two" in notes

    def test_no_notes_leaves_template_notes_untouched(self, tmp_path):
        template = _load_pro(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                          "Template.pro"))
        template_notes = template.cues[0].actions[0].slide.presentation.notes.rtf_data
        base = str(tmp_path / "song")
        save_song(["Romana", "Engleza"], SONG_TEXTS, 2, base)
        pro = _load_pro(base + ".pro")
        for cue in pro.cues:
            assert cue.actions[0].slide.presentation.notes.rtf_data == template_notes

    def test_arrangement_contract(self, tmp_path):
        base = str(tmp_path / "song")
        save_song(["Romana", "Engleza"], SONG_TEXTS, 2, base,
                  arrangement_order="Verse 1, Chorus, Missing")
        pro = _load_pro(base + ".pro")
        # The template ships with one empty "Duminica" arrangement.
        assert len(pro.arrangements) == 2
        arrangement = pro.arrangements[-1]
        assert arrangement.name == "Duminica"
        assert pro.selected_arrangement.string == arrangement.uuid.string

        group_uuids = {cg.group.uuid.string for cg in pro.cue_groups}
        assert len(arrangement.group_identifiers) == 2  # "Missing" is skipped
        assert all(gi.string in group_uuids for gi in arrangement.group_identifiers)

    def test_no_arrangement_when_not_requested(self, tmp_path):
        base = str(tmp_path / "song")
        save_song(["Romana", "Engleza"], SONG_TEXTS, 2, base)
        pro = _load_pro(base + ".pro")
        # Only the template's empty arrangement remains.
        assert len(pro.arrangements) == 1
        assert len(pro.arrangements[0].group_identifiers) == 0


class TestSaveSingleContract:
    SINGLE_TEXTS = {"Romana": ["Verse 1", "linia 1", "linia 2", "Chorus", "ref 1"]}

    def test_writes_json_and_pro(self, tmp_path):
        base = str(tmp_path / "song (Single)")
        save_single("Romana", self.SINGLE_TEXTS, 2, base)

        assert os.path.isfile(base + ".json")
        assert os.path.isfile(base + ".pro")
        with open(base + ".json", "r", encoding="utf-8") as f:
            assert json.load(f) == self.SINGLE_TEXTS

        pro = _load_pro(base + ".pro")
        assert len(pro.cues) == 5  # intro + 2 lyric slides + Interlude + Ending
        for cue in pro.cues:
            assert [e.element.name for e in _elements(cue)] == ["Romana"]

    def test_notes_injected_into_every_cue(self, tmp_path):
        base = str(tmp_path / "song (Single)")
        save_single("Romana", self.SINGLE_TEXTS, 2, base, notes_lines=["single note"])
        pro = _load_pro(base + ".pro")
        for cue in pro.cues:
            assert b"single note" in cue.actions[0].slide.presentation.notes.rtf_data

    def test_arrangement_contract(self, tmp_path):
        base = str(tmp_path / "song (Single)")
        save_single("Romana", self.SINGLE_TEXTS, 2, base,
                    arrangement_order="Verse 1, Chorus")
        pro = _load_pro(base + ".pro")
        assert len(pro.arrangements) == 2  # template's empty one + generated
        assert pro.arrangements[-1].name == "Duminica"
        assert len(pro.arrangements[-1].group_identifiers) == 2

    def test_json_matches_passed_texts(self, tmp_path):
        base = str(tmp_path / "song (Single)")
        texts = {"Romana": ["Verse 1", "only this"]}
        save_single("Romana", texts, 2, base)
        with open(base + ".json", "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data == texts
        assert list(data) == ["Romana"]
