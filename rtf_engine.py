"""RTF encode/decode engine for ProPresenter 7 text elements.

Extracted from SongEditorPro7Generic so the encode (``escape_cocoa_rtf`` /
``inject_text_into_rtf``) and decode (``rtf_to_plain``) paths have a single,
standalone home with no dependency on the ProPresenter protobuf layer.
"""


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



def rtf_to_plain(rtf_bytes):
    r"""Decode a ProPresenter RTF blob into a list of plain text lines.

    Handles \par/\line breaks, \'hh hex escapes, \uN? unicode escapes (including
    surrogate pairs for astral plane code points) and ignores other control words
    and symbols. Braces (group delimiters) are skipped, and only text inside the
    top-level group (depth 1) is kept. Empty lines are kept so callers can filter.
    """
    if not rtf_bytes:
        return []

    is_letter = lambda b: (0x61 <= b <= 0x7A) or (0x41 <= b <= 0x5A)
    is_digit = lambda b: 0x30 <= b <= 0x39

    lines = []
    current = []
    i = 0
    n = len(rtf_bytes)
    depth = 0
    started = False

    while i < n:
        c = rtf_bytes[i]
        if c == 0x7B:
            depth += 1
            i += 1
            continue
        if c == 0x7D:
            if depth == 0:
                break
            depth -= 1
            i += 1
            continue
        if c == 0x5C and i + 1 < n:
            cmd = rtf_bytes[i + 1]
            if cmd == 0x75 and i + 2 < n and (is_digit(rtf_bytes[i + 2]) or rtf_bytes[i + 2:i + 3] == b"-"):
                # \uN? unicode escape (N may be signed, e.g. \u-10179? for high surrogates)
                j = i + 2
                neg = rtf_bytes[j:j + 1] == b"-"
                if neg:
                    j += 1
                num_start = j
                while j < n and is_digit(rtf_bytes[j]):
                    j += 1
                val = int(rtf_bytes[num_start:j]) if j > num_start else 0
                code = -val if neg else val
                code_u = code + 65536 if code < 0 else code
                end = j
                if j < n and rtf_bytes[j:j + 1] == b"?":
                    end = j + 1
                if 0xD800 <= code_u <= 0xDBFF and end + 1 < n and rtf_bytes[end:end + 2] == b"\\u":
                    # Surrogate pair: \u{h}?\\u{l}?
                    j2 = end + 2
                    neg2 = rtf_bytes[j2:j2 + 1] == b"-"
                    if neg2:
                        j2 += 1
                    num_start2 = j2
                    while j2 < n and is_digit(rtf_bytes[j2]):
                        j2 += 1
                    val2 = int(rtf_bytes[num_start2:j2]) if j2 > num_start2 else 0
                    low = -val2 if neg2 else val2
                    low_u = low + 65536 if low < 0 else low
                    if 0xDC00 <= low_u <= 0xDFFF:
                        code = 0x10000 + ((code_u - 0xD800) << 10) + (low_u - 0xDC00)
                        end = j2 + 1
                current.append(chr(code + 65536 if code < 0 else code))
                i = end
                continue
            if is_letter(cmd):
                end = i + 2
                while end < n and is_letter(rtf_bytes[end]):
                    end += 1
                num_start = end
                while end < n and is_digit(rtf_bytes[end]):
                    end += 1
                word = rtf_bytes[i + 1:num_start].decode("ascii")
                if end < n and rtf_bytes[end:end + 1] == b" ":
                    end += 1
                i = end
                if word in ("par", "line"):
                    lines.append("".join(current))
                    current = []
                elif word == "tab":
                    current.append("\t")
                continue
            if cmd == 0x27:
                hex_start = i + 2
                hex_str = rtf_bytes[hex_start:hex_start + 2].decode("ascii", "replace")
                code = int(hex_str, 16) if len(hex_str) == 2 else 0
                current.append(chr(code))
                i = hex_start + 2
                continue
            i = i + 2
            continue
        if not started and depth == 1 and c not in (0x20, 0x0A, 0x0D, 0x09):
            started = True
        if started:
            current.append(chr(c))
        i += 1
    lines.append("".join(current))
    return lines
