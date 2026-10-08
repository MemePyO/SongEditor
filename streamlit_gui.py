import streamlit as st
import json
from SongEditorPro7Generic import get_text_block_names

st.set_page_config(page_title="Song JSON Editor", layout="wide")

TEXT_BLOCK_NAMES = get_text_block_names()

st.title("Song JSON Editor")
st.caption("Enter lyrics below, then download the .json file for the desktop app.")

if "text_blocks" not in st.session_state:
    st.session_state.text_blocks = {name: "" for name in TEXT_BLOCK_NAMES}


def numbered_text(text):
    lines = text.split("\n")
    numbered = "\n".join(f"{i+1:>3}| {line}" for i, line in enumerate(lines))
    return numbered


for name in TEXT_BLOCK_NAMES:
    st.session_state.text_blocks[name] = st.session_state.text_blocks[name]

for name in TEXT_BLOCK_NAMES:
    text = st.session_state.text_blocks[name]
    line_count = len(text.split("\n")) if text else 1
    num_lines = "\n".join(f"{i+1:>3}|" for i in range(line_count))

    col_nums, col_text = st.columns([1, 20])
    with col_nums:
        st.markdown(f"```\n{num_lines}\n```")
    with col_text:
        st.session_state.text_blocks[name] = st.text_area(
            name,
            value=text,
            height=500,
            key=f"ta_{name}",
            label_visibility="collapsed",
        )

st.divider()

song_name = st.text_input("Song Name", value=st.session_state.get("song_name", ""))
st.session_state.song_name = song_name

json_data = json.dumps(
    {name: st.session_state.text_blocks[name].splitlines() for name in TEXT_BLOCK_NAMES},
    ensure_ascii=False,
    indent=2,
)

title = "".join(c if c.isalnum() or c in "-_ " else " " for c in song_name).strip() or "song"

st.download_button(
    "Download .json",
    data=json_data,
    file_name=f"{title}.json",
    mime="application/json",
    use_container_width=True,
)
