# ProPresenter 7 `.pro` format reference

Practical reference for generating ProPresenter 7 (and later) presentation files.
Derived from read-only analysis of SongEditor's `*_pb2.py` descriptors plus 118 real
`.pro` files (SongEditor outputs and ProPresenter-created files).

For the complete machine-generated field catalog, see
[`_re/pro_format_report.md`](../_re/pro_format_report.md) (regenerate with
[`_re/extract_schema.py`](../_re/extract_schema.py)).

---

## 1. File format

- A `.pro` file is **raw protobuf binary** of the top-level message
  `rv.data.Presentation`. There is **no magic number, header, or compression**.
- Parse / serialize with the `presentation_pb2` module:

```python
import presentation_pb2

with open("song.pro", "rb") as f:
    pres = presentation_pb2.Presentation()
    pres.ParseFromString(f.read())

# modify pres, then:
data = pres.SerializeToString()
```

- All messages live under the `rv.data.*` namespace and are split across the
  `*_pb2.py` modules (one file per `.proto`). The relevant ones for song generation:
  `presentation_pb2`, `presentationSlide_pb2`, `slide_pb2`, `graphicsData_pb2`,
  `cue_pb2`, `action_pb2`, `background_pb2`, `basicTypes_pb2`, `groups_pb2`,
  `templateIdentification_pb2`.

---

## 2. Top-level `Presentation` fields actually used

From the 118-file sample, these fields are present in (nearly) every file:

| Field | Number | Type | Notes |
|---|---|---|---|
| `application_info` | 1 | `ApplicationInfo` | always set (see §5) |
| `uuid` | 2 | `UUID` | presentation identity |
| `name` | 3 | `string` | song/file name |
| `last_modified_date` | 5 | `Timestamp` | `seconds` set |
| `background` | 8 | `Background` | `color.alpha` set |
| `ccli` | 14 | `Presentation.CCLI` | present, usually empty |
| `selected_arrangement` | 10 | `UUID` | references an arrangement |
| `arrangements` | 11 | `repeated Arrangement` | 1 in almost all files |
| `cue_groups` | 12 | `repeated CueGroup` | one per group/section |
| `cues` | 13 | `repeated Cue` | one per slide |
| `timeline` | 17 | `Presentation.Timeline` | `duration` set |

Fields that exist in the schema but are rarely/never used in song files:
`last_date_used`, `category`, `notes`, `chord_chart` (26/118), `bible_reference`,
`social_media`, `transition`, `content_destination`, `multi_tracks_licensing`,
`music_key`, `music`, `slide_show_duration`.

---

## 3. Message hierarchy for a slide

```
Presentation
└── cues[]                              (rv.data.Cue)
    ├── uuid                            (rv.data.UUID)          # cue identity
    ├── isEnabled                       (bool)
    ├── completion_target_uuid          (rv.data.UUID)
    ├── completion_action_uuid          (rv.data.UUID)
    ├── completion_action_type          (CompletionActionType)
    ├── trigger_time                    (Cue.TimecodeTime)
    └── actions[]                       (rv.data.Action)
        └── actions[0]                  # the slide action
            ├── uuid
            ├── isEnabled
            ├── type                    (Action.ActionType)    # ACTION_TYPE_PRESENTATION_SLIDE
            └── slide                   (Action.SlideType)
                └── presentation        (rv.data.PresentationSlide)
                    ├── base_slide      (rv.data.Slide)        # the visible slide
                    │   ├── uuid
                    │   ├── size        (Graphics.Size)        # width/height
                    │   ├── background_color (Color)           # alpha set
                    │   ├── elements[]  (Slide.Element)
                    │   │   ├── element  (Graphics.Element)
                    │   │   │   ├── uuid
                    │   │   │   ├── name            # <-- text block name (e.g. "Romana")
                    │   │   │   ├── bounds          (Graphics.Rect)
                    │   │   │   ├── fill / path / shadow / stroke / feather
                    │   │   │   ├── opacity
                    │   │   │   └── text    (Graphics.Text)
                    │   │   │       ├── rtf_data     (bytes)  # <-- the lyric text
                    │   │   │       ├── attributes   (Graphics.Text.Attributes)
                    │   │   │       ├── vertical_alignment
                    │   │   │       ├── scale_behavior
                    │   │   │       └── margins
                    │   │   ├── info        (uint32)
                    │   │   └── text_scroller (Slide.Element.TextScroller)
                    │   └── element_build_order[] (UUID)
                    ├── notes           (PresentationSlide.Notes)
                    │   ├── rtf_data    (bytes)
                    │   └── attributes  (Graphics.Text.Attributes)
                    └── chord_chart     (rv.data.URL)
```

---

## 4. Text / RTF contract

- Lyric text lives in `...base_slide.elements[].element.text.rtf_data` as **bytes**.
- The **text block name** is `...element.name` (e.g. `Romana`, `Engleza`). SongEditor
  matches blocks by this name, so order does not matter, but names must match the
  template.
- Font/color/size/style are carried in `text.attributes` (see
  `graphicsData_pb2` → `Graphics.Text.Attributes` and `.Font`). SongEditor's
  `inject_text_into_rtf` rewrites the RTF payload while preserving the template's
  attributes prefix.
- `text.attributes.font`: `name`, `size`, `italic`, `bold`, `family`, `face`.
- `text.attributes.paragraph_style`: alignment, indents, line height, text lists.
- Every generated element also carries `bounds`, `fill`, `path`, `shadow`, `stroke`,
  `feather`, `opacity`, `info`, `text_scroller` — these come from the template cue and
  are copied per slide.

---

## 5. Version stamping (`application_info`)

Always present. Values observed in the sample:

| Source | `application` | `platform` | `application_version` |
|---|---|---|---|
| ProPresenter 21 (installed) | `APPLICATION_PROPRESENTER` (1) | `PLATFORM_WINDOWS` (2) | `major=21, minor=0, patch=0, build="352321578"` |
| SongEditor's `Template.pro` | `APPLICATION_PROPRESENTER` (1) | `PLATFORM_WINDOWS` (2) | `major=18, minor=4, patch=1, build="302252289"` |

`platform_version` is consistently `{ major_version: 10, patch_version: 4294967295, build: "19045" }`.

> SongEditor inherits `application_info` from its template, so all generated files
> currently carry the **18.4.1** stamp. ProPresenter 21 rewrites it to **21.0.0** on
> import. Updating the template (or stamping in `gen_pro_data`) aligns them.

---

## 6. UUID linking rules

The presentation is a graph joined by UUIDs:

- `Presentation.uuid` — top identity.
- `Presentation.cues[].uuid` — each cue's identity.
- `Presentation.cue_groups[].group.uuid` — group identity.
- `Presentation.cue_groups[].cue_identifiers[]` — references cue UUIDs (which cues
  belong to the group).
- `Presentation.arrangements[].uuid` — arrangement identity.
- `Presentation.selected_arrangement` — references one arrangement UUID.
- `Presentation.arrangements[].group_identifiers[]` — references cue_group UUIDs
  (only present in 34/118 files; optional).
- Each slide's `base_slide.uuid` and each `element.uuid` are unique per slide/element.

When cloning a cue for a new slide, regenerate the cue UUID, the action UUID, the
base slide UUID, and every element UUID (SongEditor does this).

---

## 7. Cue groups and arrangements

**CueGroup** (`Presentation.cue_groups[]`):

| Field | Type | Notes |
|---|---|---|
| `group.uuid` | `UUID` | group identity |
| `group.name` | `string` | e.g. "Intro", "Verse 1", "Chorus" |
| `group.color` | `Color` | optional (84/118) |
| `group.hotKey` | `HotKey` | optional |
| `group.application_group_identifier` | `UUID` | optional |
| `group.application_group_name` | `string` | optional |
| `cue_identifiers[]` | `repeated UUID` | cues in this group |

**Arrangement** (`Presentation.arrangements[]`):

| Field | Type | Notes |
|---|---|---|
| `uuid` | `UUID` | identity; referenced by `selected_arrangement` |
| `name` | `string` | e.g. "Duminica" |
| `group_identifiers[]` | `repeated UUID` | optional ordering of groups |

SongEditor builds one arrangement named from `Template.pro` and one cue group per
section label, with the intro in `cue_groups[0]`.

---

## 8. Template requirements

SongEditor reads `Template.pro` (a full `Presentation`) and:

1. Extracts text block names from the **last cue's base slide**
   (`get_text_block_names`) — the block names must match the user's language columns.
2. Clones that template cue for every generated slide.
3. Replaces `rtf_data` per block while keeping the template's RTF/attributes prefix.

Implications for a valid template:

- It must contain at least one cue whose `actions[0].slide.presentation.base_slide`
  has one `Graphics.Element` per language, each with `name` and `text.rtf_data`.
- The template's `cue_groups[0]` becomes the intro group.
- Keep the template's `application_info` current (see §5).

---

## 9. Known pitfalls

- **Stale version stamp** — files stamped 18.4.1 are rewritten by ProPresenter 21 on
  import (see §5).
- **Corrupt wire format** — one sample (`Este un Nume-Eng 8.pro`) failed to parse
  with `Wire format was corrupt`; avoid hand-editing binary bytes.
- **Text block order** — SongEditor's template lists `Romana, Engleza`; a fresh
  ProPresenter template may list `Engleza, Romana`. Lookup is by name, so either
  works, but keep it consistent with the user's columns.
- **Empty required-by-convention fields** — `background`, `ccli`, `timeline`,
  `last_modified_date`, `selected_arrangement`, `arrangements` are present in all
  valid samples; omitting them risks import issues.

---

## 10. Regenerating the full field catalog

```bash
python _re/extract_schema.py
```

This rewrites `_re/pro_format_report.md` with the full message/field/enum tables and
per-file usage stats. It only reads existing `.pro` and `*_pb2.py` files.
