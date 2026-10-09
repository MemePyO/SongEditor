#!/usr/bin/python

import ttkbootstrap as tb
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import filedialog
from tkinter.font import nametofont
import os
import sys
import json
import logging
import traceback
from datetime import datetime
from SongEditorPro7Generic import save_song, get_text_block_names
from autocorrect import autocorrect_text, load_word_list, find_typos, get_spellchecker

# --- Error Logging ---
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "app.log")

def setup_logging():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )

def log_error(msg, exc_info=True):
    logging.error(msg, exc_info=exc_info)

# --- Romanian Ș / ș / Ț / ț input fix ---
REMEDIED_CHARS_STD = {ord(c): c for c in 'ȘșȚț'}

def on_key_press(event):
    char = REMEDIED_CHARS_STD.get(event.keysym_num)
    if char:
        event.widget.insert('insert', char)
        return "break"


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


def get_download_path():
    if os.name == 'nt':
        import winreg
        sub_key = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders'
        downloads_guid = '{374DE290-123F-4565-9164-39C4925E467B}'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub_key) as key:
            location = winreg.QueryValueEx(key, downloads_guid)[0]
        return location
    else:
        return os.path.join(os.path.expanduser('~'), 'Downloads')


class SongEditorApp(tb.Window):
    def __init__(self, text_block_names, output_dir):
        super().__init__(themename="darkly")  # Soft dark mode
        self.title("ProPresenter7 Song Editor — Modern UI")
        self.geometry("1300x850")

        self.text_block_names = text_block_names
        self.output_dir = output_dir
        self.text_widgets = {}

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.init_ui()

    def bind_unicode_fix(self, widget):
        widget.bind("<KeyPress>", on_key_press)

    def toggle_theme(self):
        current = self.style.theme.name
        if current == "darkly":
            self.style.theme_use("litera")
            self.theme_btn.config(text="Dark Mode")
            self.message_area.config(bg="#f8f9fa", fg="#333333")
            for w in list(self.text_widgets.values()) + [self.single_text, self.groupnames_text]:
                w.config(bg="#ffffff", fg="#333333")
            self.number_widget.config(bg="#e9ecef", fg="#333333")
        else:
            self.style.theme_use("darkly")
            self.theme_btn.config(text="Light Mode")
            self.message_area.config(bg="#1e1e1e", fg="#d4d4d4")
            for w in list(self.text_widgets.values()) + [self.single_text, self.groupnames_text]:
                w.config(bg="#2d2d2d", fg="#d4d4d4")
            self.number_widget.config(bg="#1e1e1e", fg="#d4d4d4")

    # ---------------------------------------------------------
    # UI BUILD
    # ---------------------------------------------------------
    def init_ui(self):

        # Header (modern card)
        header = tb.Frame(self, padding=10, bootstyle="secondary")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        header.grid_columnconfigure(2, weight=1)

        tb.Label(header, text="Song Name:", bootstyle="light").grid(row=0, column=0, sticky="w")
        self.song_title = tb.Entry(header, width=40, bootstyle="info")
        self.song_title.grid(row=0, column=1, padx=5)
        self.bind_unicode_fix(self.song_title)

        tb.Label(header, text="Lines per Slide:", bootstyle="light").grid(row=0, column=2, sticky="e")
        self.line_count = tb.Entry(header, width=5, bootstyle="info")
        self.line_count.insert(0, "2")
        self.line_count.grid(row=0, column=3, padx=5)
        self.bind_unicode_fix(self.line_count)

        tb.Label(header, text="Arrangement:", bootstyle="light").grid(row=1, column=0, sticky="w", pady=(5,0))
        self.arrangement_order = tb.Entry(header, width=80, bootstyle="info")
        self.arrangement_order.insert(0, "Verse 1, Chorus, Verse 2, Chorus, Bridge, Chorus")
        self.arrangement_order.grid(row=1, column=1, columnspan=6, padx=5, pady=(5,0), sticky="ew")
        self.bind_unicode_fix(self.arrangement_order)

        tb.Button(header, text="Open", bootstyle="primary-outline", command=self.open_file).grid(row=0, column=4, padx=10)
        tb.Button(header, text="Save", bootstyle="success-outline", command=self.save_song_action).grid(row=0, column=5)
        tb.Button(header, text="Autocorrect", bootstyle="warning-outline", command=self.autocorrect_action).grid(row=0, column=6, padx=10)
        tb.Button(header, text="Check Typos", bootstyle="danger-outline", command=self.check_typos_action).grid(row=0, column=7, padx=10)
        self.theme_btn = tb.Button(header, text="Light Mode", bootstyle="secondary-outline", command=self.toggle_theme)
        self.theme_btn.grid(row=1, column=7, padx=10, pady=(5,0), sticky="e")

        # Notebook
        self.notebook = tb.Notebook(self, bootstyle="primary")
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        self.compare_tab = tb.Frame(self.notebook)
        self.single_tab = tb.Frame(self.notebook)
        self.groupnames_tab = tb.Frame(self.notebook)

        self.notebook.add(self.compare_tab, text="Translate View")
        self.notebook.add(self.single_tab, text="Single View")
        self.notebook.add(self.groupnames_tab, text="Edit Group Names")

        self.build_compare_tab()
        self.build_single_tab()
        self.build_groupnames_tab()

        # Group Names Preview
        self.label_hint = tb.Label(self, justify=tk.LEFT, wraplength=1000, bootstyle="secondary")
        self.label_hint.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        self.update_group_label_preview()

        # Status message
        self.message_area = tk.Text(self, height=2, bg="#1e1e1e", fg="#d4d4d4")
        self.message_area.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        self.bind_unicode_fix(self.message_area)

    # ---------------------------------------------------------
    # TRANSLATE VIEW — Modern UI + Highlight + Zebra
    # ---------------------------------------------------------
    def build_compare_tab(self):

        self.compare_tab.grid_rowconfigure(0, weight=1)
        self.compare_tab.grid_columnconfigure(0, weight=0)

        for i in range(len(self.text_block_names)):
            self.compare_tab.grid_columnconfigure(i+1, weight=1)

        # Scrollbar
        self.scrollbar = tb.Scrollbar(self.compare_tab, orient="vertical", bootstyle="info")
        self.scrollbar.grid(row=0, column=len(self.text_block_names)+1, sticky="ns")

        def sync_scroll(*args):
            self.number_widget.yview(*args)
            for widget in self.text_widgets.values():
                widget.yview(*args)

        self.scrollbar.config(command=sync_scroll)

        # Number column
        number_frame = tb.Frame(self.compare_tab, bootstyle="secondary")
        number_frame.grid(row=0, column=0, sticky="nsew", padx=5)

        tb.Label(number_frame, text="#", bootstyle="light").pack()
        self.number_widget = tk.Text(number_frame, wrap=tk.NONE, width=4,
                                     bg="#1e1e1e", fg="#d4d4d4", yscrollcommand=self.scrollbar.set)
        self.number_widget.pack(expand=True, fill=tk.BOTH)
        self.number_widget.bind("<Motion>", self.on_hover)

        # Text columns
        for col, name in enumerate(self.text_block_names):
            frame = tb.Frame(self.compare_tab, bootstyle="secondary")
            frame.grid(row=0, column=col+1, sticky="nsew", padx=5)

            tb.Label(frame, text=name, bootstyle="light").pack()

            text_widget = tk.Text(frame, wrap=tk.WORD, bg="#2d2d2d", fg="#d4d4d4",
                                  yscrollcommand=self.scrollbar.set)
            text_widget.pack(expand=True, fill=tk.BOTH)

            self.bind_unicode_fix(text_widget)
            self.text_widgets[name] = text_widget
            text_widget.bind("<Motion>", self.on_hover)

    # ---------------------------------------------------------
    # HOVER HIGHLIGHT
    # ---------------------------------------------------------
    def on_hover(self, event):
        index = event.widget.index(f"@0,{event.y}")
        line = index.split(".")[0]

        # Clear old highlight
        for name in self.text_block_names:
            self.text_widgets[name].tag_remove("hover", "1.0", tk.END)
        self.number_widget.tag_remove("hover", "1.0", tk.END)

        # Apply highlight
        for name in self.text_block_names:
            w = self.text_widgets[name]
            w.tag_add("hover", f"{line}.0", f"{line}.end")
            w.tag_config("hover", background="#004d40")  # teal highlight

        self.number_widget.tag_add("hover", f"{line}.0", f"{line}.end")
        self.number_widget.tag_config("hover", background="#004d40")

    # ---------------------------------------------------------
    # SINGLE VIEW
    # ---------------------------------------------------------
    def build_single_tab(self):
        self.single_tab.grid_rowconfigure(0, weight=1)
        self.single_tab.grid_columnconfigure(0, weight=1)

        self.single_text = tk.Text(self.single_tab, wrap=tk.WORD, bg="#2d2d2d", fg="#d4d4d4")
        self.single_text.grid(row=0, column=0, sticky="nsew")
        self.bind_unicode_fix(self.single_text)

    # ---------------------------------------------------------
    # GROUP NAMES TAB
    # ---------------------------------------------------------
    def build_groupnames_tab(self):
        self.groupnames_tab.grid_rowconfigure(1, weight=1)
        self.groupnames_tab.grid_columnconfigure(0, weight=1)

        tb.Label(self.groupnames_tab, text="Edit GroupNames.txt:", bootstyle="light").grid(row=0, column=0, sticky="w", padx=5, pady=5)

        self.groupnames_text = tk.Text(self.groupnames_tab, wrap=tk.WORD, bg="#2d2d2d", fg="#d4d4d4")
        self.groupnames_text.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.bind_unicode_fix(self.groupnames_text)

        tb.Button(self.groupnames_tab, text="Save Changes", bootstyle="success-outline", command=self.save_groupnames).grid(row=2, column=0, pady=10)

        self.load_groupnames()

    def load_groupnames(self):
        try:
            path = resource_path("GroupNames.txt")
            with open(path, "r", encoding="utf-8") as f:
                self.groupnames_text.delete("1.0", tk.END)
                self.groupnames_text.insert("1.0", f.read())
        except Exception as e:
            self.groupnames_text.delete("1.0", tk.END)
            self.groupnames_text.insert("1.0", "Could not load GroupNames.txt")
            log_error("Failed to load GroupNames.txt", exc_info=False)

    def save_groupnames(self):
        content = self.groupnames_text.get("1.0", tk.END).strip()
        try:
            path = resource_path("GroupNames.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.show_message("GroupNames.txt saved.")
            self.update_group_label_preview(content)
        except Exception as e:
            self.show_message("Error saving GroupNames.txt: " + str(e))
            log_error("Failed to save GroupNames.txt")

    def update_group_label_preview(self, content=None):
        if content is None:
            try:
                path = resource_path("GroupNames.txt")
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
            except:
                content = ""
        preview = "Group Names Preview:\n" + "  ".join(content.splitlines())
        self.label_hint.config(text=preview)

    # ---------------------------------------------------------
    # OPEN FILE
    # ---------------------------------------------------------
    def open_file(self):
        path = filedialog.askopenfilename(initialdir=self.output_dir, filetypes=[("JSON files", "*.json")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for name in self.text_block_names:
                self.text_widgets[name].delete("1.0", tk.END)
                self.text_widgets[name].insert("1.0", "\n".join(data.get(name, [])))

            max_len = max(len(data.get(name, [])) for name in self.text_block_names)
            self.number_widget.delete("1.0", tk.END)
            self.number_widget.insert("1.0", "\n".join(str(i+1) for i in range(max_len)))

            self.song_title.delete(0, tk.END)
            self.song_title.insert(0, os.path.basename(path).replace(".json", ""))

            self.single_text.delete("1.0", tk.END)
            self.single_text.insert("1.0", self.text_widgets[self.text_block_names[0]].get("1.0", tk.END))

            self.show_message(f"Opened: {path}")
        except Exception as e:
            self.show_message("Error opening file: " + str(e))
            log_error("Failed to open file")

    # ---------------------------------------------------------
    # SAVE SONG
    # ---------------------------------------------------------
    def save_song_action(self):
        title = self.song_title.get().strip()
        if not title:
            self.show_message("Please enter a song title.")
            return

        for char in r":\\|/?*&^%$#@!~`'\";,.<>":
            title = title.replace(char, " ")

        song_texts = {name: self.text_widgets[name].get("1.0", tk.END).splitlines()
                      for name in self.text_block_names}

        try:
            max_lines = int(self.line_count.get())
        except:
            max_lines = 2
            self.line_count.delete(0, tk.END)
            self.line_count.insert(0, "2")

        max_len = max(len(song_texts[name]) for name in self.text_block_names)
        self.number_widget.delete("1.0", tk.END)
        self.number_widget.insert("1.0", "\n".join(str(i+1) for i in range(max_len)))

        output_file = os.path.join(self.output_dir, title)

        try:
            save_song(self.text_block_names, song_texts, max_lines, output_file, arrangement_order=self.arrangement_order.get().strip())
            self.show_message(f"Saved! Import in ProPresenter: File → Import → {output_file}.pro")
        except Exception as e:
            self.show_message("Save failed: " + str(e))
            log_error("Failed to save song")

    # ---------------------------------------------------------
    # AUTOCORRECT
    # ---------------------------------------------------------
    def autocorrect_action(self):
        try:
            word_list = load_word_list()
            for name in self.text_block_names:
                w = self.text_widgets[name]
                text = w.get("1.0", tk.END)
                w.delete("1.0", tk.END)
                w.insert("1.0", autocorrect_text(text, word_list))

            first = self.text_block_names[0]
            self.single_text.delete("1.0", tk.END)
            self.single_text.insert("1.0", self.text_widgets[first].get("1.0", tk.END))

            self.show_message("Autocorrect applied to all text boxes.")
        except Exception as e:
            self.show_message("Autocorrect failed: " + str(e))
            log_error("Autocorrect failed")

    # ---------------------------------------------------------
    # CHECK TYPOS (highlight only)
    # ---------------------------------------------------------
    def check_typos_action(self):
        try:
            spell = get_spellchecker()
            total = 0
            for name in self.text_block_names:
                w = self.text_widgets[name]
                w.tag_remove("typo", "1.0", tk.END)
                text = w.get("1.0", tk.END)
                for start, end, word in find_typos(text, spell):
                    start_idx = f"1.0+{start}c"
                    end_idx = f"1.0+{end}c"
                    w.tag_add("typo", start_idx, end_idx)
                    total += 1
                w.tag_config("typo", background="#5c1a1a", foreground="#ff6b6b")
            self.show_message(f"Found {total} possible typo(s). Highlighted in red.")
        except Exception as e:
            self.show_message("Check typos failed: " + str(e))
            log_error("Check typos failed")

    # ---------------------------------------------------------
    # STATUS MESSAGE
    # ---------------------------------------------------------
    def show_message(self, msg):
        self.message_area.delete("1.0", tk.END)
        self.message_area.insert(tk.END, msg)


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------
if __name__ == "__main__":
    setup_logging()
    logging.info("=" * 60)
    logging.info("Application started")

    try:
        text_block_names = get_text_block_names()
        logging.info(f"Text block names: {text_block_names}")
        output_dir = get_download_path()
        logging.info(f"Output directory: {output_dir}")
        app = SongEditorApp(text_block_names, output_dir)

        default_font = nametofont("TkDefaultFont")
        default_font.configure(family="Segoe UI", size=11)

        logging.info("Entering main loop")
        app.mainloop()
    except Exception as e:
        logging.critical(f"Fatal error: {e}", exc_info=True)
        raise