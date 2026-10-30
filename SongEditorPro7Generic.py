import presentation_pb2
from uuid import uuid1
import json
import os
import sys

TEMPLATE = 0


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def make_uuid():
    return uuid1().urn.split("uuid:")[1]


def add_que_group(presentation_obj, slide_label, slide_uuid):
    presentation_obj.cue_groups.add()
    cue_group_id = len(presentation_obj.cue_groups) - 1
    presentation_obj.cue_groups[cue_group_id].CopyFrom(presentation_obj.cue_groups[TEMPLATE])
    presentation_obj.cue_groups[cue_group_id].group.uuid.string = make_uuid()
    presentation_obj.cue_groups[cue_group_id].group.name = slide_label
    presentation_obj.cue_groups[cue_group_id].group.application_group_identifier.string = make_uuid()
    presentation_obj.cue_groups[cue_group_id].group.application_group_name = slide_label
    presentation_obj.cue_groups[cue_group_id].cue_identifiers[-1].string = slide_uuid


# ---------------------------------------------------------
#  GROUP LABELS
# ---------------------------------------------------------
_labels_cache = {}


def expand_group_labels(raw_lines):
    """Expand ``Name 1..N`` ranges from GroupNames.txt into individual labels."""
    labels = []
    for raw in raw_lines:
        lbl = (raw or "").strip()
        if not lbl:
            continue
        if ".." in lbl:
            name, _, rng = lbl.rpartition(" ")
            try:
                start, end = (int(part) for part in rng.split(".."))
            except (TypeError, ValueError):
                labels.append(lbl)
                continue
            if not name:
                labels.append(lbl)
                continue
            labels.extend(f"{name} {i}" for i in range(start, end + 1))
        else:
            labels.append(lbl)
    return labels


def load_group_labels(path=None, use_cache=True):
    """Return the expanded section labels, cached by file mtime/size.

    Reading GroupNames.txt on every preview refresh is unnecessary; the cache
    is invalidated automatically when the file changes on disk.
    """
    path = path or resource_path("GroupNames.txt")
    try:
        stat = os.stat(path)
        key = (os.path.abspath(path), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return []
    if use_cache and key in _labels_cache:
        return list(_labels_cache[key])
    try:
        with open(path, "r", encoding="utf-8") as f:
            labels = expand_group_labels(f.read().splitlines())
    except OSError:
        return []
    _labels_cache.clear()
    _labels_cache[key] = labels
    return list(labels)


def invalidate_group_labels_cache():
    _labels_cache.clear()


# ---------------------------------------------------------
#  MERGED SPLITTER — LABELS & GROUPS LIKE OLD SCRIPT,
#  BUT RETURNS LINES PER BLOCK FOR TEMPLATE-AWARE RTF
# ---------------------------------------------------------
def split_slides(text_block_names, song_texts, max_line_count, labels=None):
    # Load group labels (cached) unless the caller already resolved them
    if labels is None:
        labels = load_group_labels()

    slides = []
    block_len = len(song_texts[text_block_names[0]])
    line_index = 0

    current_label = "Verse 1"

    while line_index < block_len:
        main_line = song_texts[text_block_names[0]][line_index].strip()

        # If label encountered -> update group label
        if main_line in labels:
            current_label = main_line
            line_index += 1
            continue

        # Start new slide
        slide = {tb: [] for tb in text_block_names}
        slide["label"] = current_label

        lines_added = 0
        while lines_added < max_line_count and line_index < block_len:
            main_line = song_texts[text_block_names[0]][line_index].strip()

            # If next line is a label -> stop slide but DO NOT consume the label
            if main_line in labels:
                break

            # Add line to each text block
            for tb in text_block_names:
                line = song_texts[tb][line_index] if line_index < len(song_texts[tb]) else ""
                slide[tb].append(line)

            lines_added += 1
            line_index += 1

        # Only add non-empty slides
        if any(any(line.strip() for line in slide[tb]) for tb in text_block_names):
            slides.append(slide)

    return slides


# ---------------------------------------------------------
#  RTF ENCODING
# ---------------------------------------------------------
def rtf_text_start(rtf):
    # Scan RTF bytes, return the index where the plain text content begins.
    # Everything before that index is the formatting prefix copied from the template.
    # Handles nested groups, control words, \'hh escapes. Stops at the closing
    # brace of the main group, so it also works on an already cleared RTF.
    i = 1
    depth = 0
    n = len(rtf)
    while i < n:
        c = rtf[i]
        if c == 0x7B:  # {
            depth += 1
            i += 1
        elif c == 0x7D:  # }
            if depth == 0:
                return i
            depth -= 1
            i += 1
        elif c == 0x5C:  # \
            i += 1
            if i >= n:
                break
            if 0x61 <= rtf[i] <= 0x7A or 0x41 <= rtf[i] <= 0x5A:
                # control word: letters, optional signed number, optional space delimiter
                while i < n and (0x61 <= rtf[i] <= 0x7A or 0x41 <= rtf[i] <= 0x5A):
                    i += 1
                if i < n and rtf[i] == 0x2D:
                    i += 1
                while i < n and 0x30 <= rtf[i] <= 0x39:
                    i += 1
                if i < n and rtf[i] == 0x20:
                    i += 1
            else:
                # control symbol, e.g. \\ \{ \} \'hh \newline
                i += 1
                if rtf[i - 1] == 0x27 and i + 1 < n:
                    i += 2
        elif depth == 0 and c not in (0x20, 0x0A, 0x0D, 0x09):
            return i
        else:
            i += 1
    return n


def escape_cocoa_rtf(text):
    text = text.replace('\\', r'\\').replace('{', r'\{').replace('}', r'\}')
    out = []
    for ch in text:
        code = ord(ch)
        if code < 128:
            out.append(ch)
        elif code <= 0xFFFF:
            # Apple RTF 16-bit signed short Unicode convention
            signed = code if code < 32768 else code - 65536
            out.append(f"\\u{signed}?")
        else:
            # Surrogate pairs for code points > 0xFFFF
            code_adj = code - 0x10000
            h = 0xD800 + (code_adj >> 10)
            l = 0xDC00 + (code_adj & 0x3FF)
            h_signed = h if h < 32768 else h - 65536
            l_signed = l if l < 32768 else l - 65536
            out.append(f"\\u{h_signed}?\\u{l_signed}?")
    return "".join(out)


def element_all_caps(element):
    attrs = element.element.text.attributes
    field = attrs.DESCRIPTOR.fields_by_name["capitalization"]
    return attrs.capitalization == field.enum_type.values_by_name["CAPITALIZATION_ALL_CAPS"].number


def inject_text_into_rtf(template_rtf_bytes, new_text_lines, font_size=None, font_color=None, font_style=None, font_family=None, all_caps=False):
    """
    Preserves ProPresenter 7's RTF structure, style, font,
    and alignment intact from Template.pro, replacing only the inner text.
    font_size/font_color/font_style/font_family are reserved for future overrides.
    When all_caps is set, \\caps is re-emitted after each \\par so character
    formatting survives ProPresenter's per-paragraph RTF reset.
    """
    if not template_rtf_bytes:
        return b""

    # Find where the formatting prefix ends and the text content begins
    if template_rtf_bytes[:1] == b"{":
        prefix_end = rtf_text_start(template_rtf_bytes)
    else:
        prefix_end = 0
    if prefix_end <= 0:
        # Fallback: keep everything up to the last closing brace
        last_brace = template_rtf_bytes.rfind(b"}")
        prefix_end = last_brace if last_brace != -1 else len(template_rtf_bytes)

    prefix = template_rtf_bytes[:prefix_end]

    # Keep RTF wrapper/formatting, strip actual content (Intro, Interlude, Ending)
    clean_lines = [escape_cocoa_rtf(line.strip().upper() if all_caps else line.strip())
                   for line in new_text_lines if line.strip()]
    if not clean_lines:
        return prefix + b"}"

    # Append lines joined by RTF paragraph breaks, then close.
    # If the prefix ends with a letter or digit (a control word such as \cb2),
    # a space delimiter is required so the first word is not parsed as part of it.
    separator = r"\caps \par " if all_caps else r"\par "
    joined_text = separator.join(clean_lines).encode("ascii")
    if prefix and (0x30 <= prefix[-1] <= 0x39 or 0x41 <= prefix[-1] <= 0x5A or 0x61 <= prefix[-1] <= 0x7A):
        prefix = prefix + b" "
    return prefix + joined_text + b"}"


# ---------------------------------------------------------
#  PRO DATA GENERATION (TEMPLATE-AWARE)
# ---------------------------------------------------------
def gen_pro_data(text_block_names, song_texts, line_count,
                 per_block_colors=None, per_block_styles=None,
                 per_block_sizes=None, per_block_families=None,
                 arrangement_order=None,
                 template_path=None,
                 notes_lines=None):

    sample_file = template_path if template_path else r"Template.pro"
    if os.path.isabs(sample_file):
        open_path = sample_file
    else:
        open_path = resource_path(sample_file)
    presentation_obj = presentation_pb2.Presentation()

    with open(open_path, "rb") as f:
        presentation_obj.ParseFromString(f.read())

    presentation_obj.uuid.string = make_uuid()

    if per_block_colors is None:
        per_block_colors = {}
    if per_block_styles is None:
        per_block_styles = {}
    if per_block_sizes is None:
        per_block_sizes = {}
    if per_block_families is None:
        per_block_families = {}

    # Clear intro slide using template elements
    for element in presentation_obj.cues[TEMPLATE].actions[0].slide.presentation.base_slide.elements:
        tb = element.element.name
        template_rtf = element.element.text.rtf_data

        size = per_block_sizes.get(tb, 72)
        color = per_block_colors.get(tb, "#000000")
        style = per_block_styles.get(tb, "Regular")
        family = per_block_families.get(tb, "Arial")

        element.element.text.rtf_data = inject_text_into_rtf(
            template_rtf, [],
            font_size=size, font_color=color,
            font_style=style, font_family=family,
            all_caps=element_all_caps(element)
        )

    # Inject notes into intro slide (if provided)
    if notes_lines:
        intro_ps = presentation_obj.cues[TEMPLATE].actions[0].slide.presentation
        intro_ps.notes.rtf_data = inject_text_into_rtf(
            intro_ps.notes.rtf_data, notes_lines,
            all_caps=intro_ps.notes.attributes.capitalization == intro_ps.notes.attributes.DESCRIPTOR.fields_by_name["capitalization"].enum_type.values_by_name["CAPITALIZATION_ALL_CAPS"].number
        )

    # Fix intro cue UUIDs
    presentation_obj.cue_groups[0].group.name = "Intro"
    presentation_obj.cue_groups[0].group.uuid.string = make_uuid()

    intro_uuid = make_uuid()
    presentation_obj.cue_groups[0].cue_identifiers[0].string = intro_uuid
    presentation_obj.cues[0].uuid.string = intro_uuid

    presentation_obj.cues[0].actions[0].uuid.string = make_uuid()
    presentation_obj.cues[0].actions[0].slide.presentation.base_slide.uuid.string = make_uuid()

    # Generate slides (using merged splitter)
    slides = split_slides(text_block_names, song_texts, line_count)
    prev_label = None

    for slide in slides:
        slide_uuid = make_uuid()
        label = slide.get("label", "")

        if label == prev_label:
            presentation_obj.cue_groups[-1].cue_identifiers.add().string = slide_uuid
        else:
            add_que_group(presentation_obj, label, slide_uuid)

        prev_label = label

        new_cue = presentation_obj.cues.add()
        new_cue.CopyFrom(presentation_obj.cues[TEMPLATE])
        new_cue.uuid.string = slide_uuid
        new_cue.actions[0].uuid.string = make_uuid()
        new_cue.actions[0].slide.presentation.base_slide.uuid.string = make_uuid()

        for element in new_cue.actions[0].slide.presentation.base_slide.elements:
            tb = element.element.name
            template_rtf = element.element.text.rtf_data

            size = per_block_sizes.get(tb, 72)
            color = per_block_colors.get(tb, "#000000")
            style = per_block_styles.get(tb, "Regular")
            family = per_block_families.get(tb, "Arial")

            lines = slide.get(tb, [])

            element.element.text.rtf_data = inject_text_into_rtf(
                template_rtf, lines,
                font_size=size, font_color=color,
                font_style=style, font_family=family,
                all_caps=element_all_caps(element)
            )

            # Inject notes into this slide (if provided)
            if notes_lines:
                slide_ps = new_cue.actions[0].slide.presentation
                slide_ps.notes.rtf_data = inject_text_into_rtf(
                    slide_ps.notes.rtf_data, notes_lines,
                    all_caps=slide_ps.notes.attributes.capitalization == slide_ps.notes.attributes.DESCRIPTOR.fields_by_name["capitalization"].enum_type.values_by_name["CAPITALIZATION_ALL_CAPS"].number
                )

    # Add Interlude & Ending once
    for extra in ["Interlude", "Ending"]:
        slide_uuid = make_uuid()
        add_que_group(presentation_obj, extra, slide_uuid)

        new_cue = presentation_obj.cues.add()
        new_cue.CopyFrom(presentation_obj.cues[TEMPLATE])
        new_cue.uuid.string = slide_uuid
        new_cue.actions[0].uuid.string = make_uuid()
        new_cue.actions[0].slide.presentation.base_slide.uuid.string = make_uuid()

        for element in new_cue.actions[0].slide.presentation.base_slide.elements:
            tb = element.element.name
            template_rtf = element.element.text.rtf_data

            size = per_block_sizes.get(tb, 72)
            color = per_block_colors.get(tb, "#000000")
            style = per_block_styles.get(tb, "Regular")
            family = per_block_families.get(tb, "Arial")

            element.element.text.rtf_data = inject_text_into_rtf(
                template_rtf, [],
                font_size=size, font_color=color,
                font_style=style, font_family=family,
                all_caps=element_all_caps(element)
            )

        if notes_lines:
            extra_ps = new_cue.actions[0].slide.presentation
            extra_ps.notes.rtf_data = inject_text_into_rtf(
                extra_ps.notes.rtf_data, notes_lines,
                all_caps=extra_ps.notes.attributes.capitalization == extra_ps.notes.attributes.DESCRIPTOR.fields_by_name["capitalization"].enum_type.values_by_name["CAPITALIZATION_ALL_CAPS"].number
            )

    if arrangement_order:
        group_uuids = {}
        for cg in presentation_obj.cue_groups:
            group_uuids[cg.group.name] = cg.group.uuid.string

        arrangement = presentation_obj.arrangements.add()
        arrangement.uuid.string = make_uuid()
        arrangement.name = "Duminica"
        for part in arrangement_order.split(","):
            name = part.strip()
            if name in group_uuids:
                arrangement.group_identifiers.add().string = group_uuids[name]

        presentation_obj.selected_arrangement.string = arrangement.uuid.string

    return presentation_obj.SerializeToString()


# ---------------------------------------------------------
#  SAVE SONG
# ---------------------------------------------------------
def save_song(text_block_names, song_texts, line_count, output_filename, font_data=None, arrangement_order=None, template_path=None, notes_lines=None):

    with open(output_filename + ".json", "w", encoding="utf-8") as f:
        json.dump(song_texts, f, ensure_ascii=False, indent=2)

    colors = {}
    styles = {}
    sizes = {}
    families = {}

    if font_data:
        for name in text_block_names:
            colors[name] = font_data[name]["color"]
            style = ""
            if font_data[name]["bold"]:
                style += "bold "
            if font_data[name]["italic"]:
                style += "italic"
            styles[name] = style.strip() or "Regular"
            sizes[name] = font_data[name]["size"]
            families[name] = font_data[name]["family"]

    with open(output_filename + ".pro", "wb") as f:
        f.write(gen_pro_data(
            text_block_names, song_texts, line_count,
            per_block_colors=colors,
            per_block_styles=styles,
            per_block_sizes=sizes,
            per_block_families=families,
            arrangement_order=arrangement_order,
            template_path=template_path,
            notes_lines=notes_lines
        ))


# ---------------------------------------------------------
#  MAIN
# ---------------------------------------------------------
def get_text_block_names(template_path=None):
    sample_file = template_path if template_path else r"Template.pro"
    if os.path.isabs(sample_file):
        open_path = sample_file
    else:
        open_path = resource_path(sample_file)
    presentation_obj = presentation_pb2.Presentation()
    with open(open_path, "rb") as f:
        presentation_obj.ParseFromString(f.read())
    return [el.element.name for el in presentation_obj.cues[-1].actions[0].slide.presentation.base_slide.elements]


def resolve_template(configured_path=None):
    """Return (template_path, text_block_names, used_fallback).

    Tries the configured template first. If it is missing/unreadable/invalid,
    falls back to the bundled ``Template.pro`` (template_path becomes None) and
    sets ``used_fallback`` so callers can surface a friendly message.
    """
    if configured_path:
        try:
            return configured_path, get_text_block_names(configured_path), False
        except Exception:
            pass
    return None, get_text_block_names(None), bool(configured_path)


# Fixed group names that wrap a song and are not user lyrics.
_FIXED_GROUPS = ("Intro", "Interlude", "Ending")


def rtf_to_plain(rtf_bytes):
    """Decode a ProPresenter RTF blob into a list of plain text lines.

    Handles ``\\par``/``\\line`` breaks, ``\\'hh`` hex escapes, ``\\uN?M?``
    unicode escapes and ignores other control words/symbols. Braces (group
    delimiters) are skipped. Empty lines are kept so callers can filter.
    """
    if not rtf_bytes:
        return []
    content = rtf_bytes[rtf_text_start(rtf_bytes):]
    lines = []
    current = []
    i = 0
    n = len(content)

    def is_letter(b):
        return (0x61 <= b <= 0x7A) or (0x41 <= b <= 0x5A)

    def is_digit(b):
        return 0x30 <= b <= 0x39

    while i < n:
        c = content[i]
        if c == 0x5C and i + 1 < n:  # backslash -> control sequence
            cmd = content[i + 1]
            if cmd == 0x75:  # \uN?M? -> unicode surrogate pair
                j = i + 2
                num_start = j
                while j < n and is_digit(content[j]):
                    j += 1
                code = int(content[num_start:j]) if j > num_start else 0
                i = j
                if i < n and content[i:i + 1] == b"?":
                    # Surrogate-pair suffix: ?M?
                    k = i + 1
                    num_start2 = k
                    while k < n and is_digit(content[k]):
                        k += 1
                    low = int(content[num_start2:k]) if k > num_start2 else 0
                    if 0xD800 <= code <= 0xDBFF and 0xDC00 <= low <= 0xDFFF:
                        code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)
                    i = k + 1
                current.append(chr(code))
            elif is_letter(cmd):
                # Control word: letters followed by an optional numeric param
                # and an optional single space delimiter.
                end = i + 2
                while end < n and is_letter(content[end]):
                    end += 1
                num_start = end
                while end < n and is_digit(content[end]):
                    end += 1
                word = content[i + 1:num_start].decode("ascii")
                if end < n and content[end] == 0x20:
                    end += 1
                i = end
                if word in ("par", "line"):
                    lines.append("".join(current))
                    current = []
                elif word == "tab":
                    current.append("\t")
                # Ignore other control words (fonts, sizes, caps, ...)
            elif cmd == 0x27:  # \'hh -> hex character
                hex_start = i + 2
                hex_str = content[hex_start:hex_start + 2].decode("ascii", "replace")
                try:
                    current.append(chr(int(hex_str, 16)))
                except ValueError:
                    pass
                i = hex_start + 2
            else:
                # Control symbol like \{ \} \\ \* — not needed for plain text.
                i = i + 2
            continue
        elif c == 0x7B or c == 0x7D:  # group delimiters are not text
            i += 1
            continue
        else:
            current.append(chr(c))
            i += 1
    lines.append("".join(current))
    return lines


def pro_to_song_texts(raw_bytes, text_block_names):
    """Convert a .pro presentation back into per-block lyric line lists.

    Returns ``{block_name: [lines...]}`` where group label lines are kept so
    that the result can be dropped straight into the editor text widgets (and
    re-used by ``split_slides``). Fixed groups (Intro/Interlude/Ending) are
    skipped; lyric groups map to the text blocks they hold.
    """
    presentation_obj = presentation_pb2.Presentation()
    presentation_obj.ParseFromString(raw_bytes)

    group_for_cue = {}
    for cg in presentation_obj.cue_groups:
        for cid in cg.cue_identifiers:
            group_for_cue[cid.string] = cg.group.name

    texts = {tb: [] for tb in text_block_names}
    last_label = {tb: None for tb in text_block_names}

    for cue in presentation_obj.cues:
        label = group_for_cue.get(cue.uuid.string, "")
        if label in _FIXED_GROUPS:
            continue
        lines_by_block = {}
        for action in cue.actions:
            for el in action.slide.presentation.base_slide.elements:
                tb = el.element.name
                if tb not in texts:
                    continue
                lines = [ln.strip() for ln in rtf_to_plain(el.element.text.rtf_data) if ln.strip()]
                if element_all_caps(el):
                    lines = [ln.upper() for ln in lines]
                if lines:
                    lines_by_block[tb] = lines
        for tb in text_block_names:
            lines = lines_by_block.get(tb, [])
            if label != last_label[tb]:
                texts[tb].append(label)
                last_label[tb] = label
            texts[tb].extend(lines)

    return texts


if __name__ == "__main__":
    print(get_text_block_names())
