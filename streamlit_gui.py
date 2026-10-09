import streamlit as st
import json
from SongEditorPro7Generic import get_text_block_names

st.set_page_config(page_title="Song JSON Editor", layout="wide")

TEXT_BLOCK_NAMES = get_text_block_names()

st.title("Song JSON Editor")
st.caption("Enter lyrics below, then download the .json file for the desktop app.")

if "text_blocks" not in st.session_state:
    st.session_state.text_blocks = {name: "" for name in TEXT_BLOCK_NAMES}

cols = st.columns(len(TEXT_BLOCK_NAMES))
for i, name in enumerate(TEXT_BLOCK_NAMES):
    with cols[i]:
        st.session_state.text_blocks[name] = st.text_area(
            name,
            value=st.session_state.text_blocks[name],
            height=500,
            key=f"ta_{name}",
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
