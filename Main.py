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
import threading
import re
from SongEditorPro7Generic import save_song, get_text_block_names
from autocorrect import find_typos, get_spellchecker
from tkinterdnd2 import DND_FILES, TkinterDnD
import fitz

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


def load_config():
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(config):
    try:
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass


class SongEditorApp(TkinterDnD.Tk):
    def __init__(self, text_block_names, output_dir):
        self.config = load_config()
        self.current_font_size = self.config.get("font_size", 11)
        default_theme = self.config.get("theme", "darkly")
        super().__init__()
        self.style = tb.Style(theme=default_theme)
        self.title("ProPresenter7 Song Editor — Modern UI")
        self.geometry("1300x850")

        self.text_block_names = text_block_names
        self.output_dir = output_dir
        self.text_widgets = {}

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.handle_pdf_drop)

        self.init_ui()

    def handle_pdf_drop(self, event, target_name=None):
        path = event.data.strip("{}")
        if not path.lower().endswith(".pdf"):
            return
        self.show_message(f"Extracting: {os.path.basename(path)}...")
        threading.Thread(target=self._extract_pdf, args=(path, target_name), daemon=True).start()

    def _extract_pdf(self, path, target_name=None):
        try:
            doc = fitz.open(path)
            raw = ""
            for page in doc:
                raw += page.get_text("text")
            doc.close()

            lines = raw.splitlines()
            known = self.get_known_labels()
            start = 0
            for i, line in enumerate(lines):
                s = line.strip().rstrip(":").rstrip(".").strip()
                if s in known:
                    start = i
                    break

            all_lines = []
            for line in lines[start:]:
                s = line.strip()
                if s:
                    all_lines.append(s)

            if target_name:
                text = "\n".join(all_lines)
                self.after(0, self._populate_pdf, text, "", path, target_name)
            else:
                ro_lines = []
                en_lines = []
                current_lang = None
                ro_diacritics = set("ăâîșțĂÂÎȘȚ")

                for s in all_lines:
                    base = re.sub(r"\*\d+$", "", s).rstrip(":").rstrip(".").strip()
                    if base in known:
                        ro_section = any(c in ro_diacritics for c in base)
                        en_section = any(c.isalpha() and c not in ro_diacritics for c in base)
                        if ro_section and not en_section:
                            current_lang = "ro"
                        elif en_section and not ro_section:
                            current_lang = "en"
                        if current_lang == "ro":
                            ro_lines.append(s)
                        elif current_lang == "en":
                            en_lines.append(s)
                        continue

                    if current_lang == "ro":
                        ro_lines.append(s)
                    elif current_lang == "en":
                        en_lines.append(s)

                ro_text = "\n".join(ro_lines)
                en_text = "\n".join(en_lines)
                self.after(0, self._populate_pdf, ro_text, en_text, path, target_name)
        except Exception as e:
            self.after(0, self.show_message, f"PDF extraction failed: {e}")
            log_error("PDF extraction failed")

    def _populate_pdf(self, ro_text, en_text, path, target_name=None):
        first = self.text_block_names[0]
        second = self.text_block_names[1] if len(self.text_block_names) > 1 else None
        if target_name and target_name in self.text_widgets:
            self.text_widgets[target_name].delete("1.0", tk.END)
            self.text_widgets[target_name].insert("1.0", ro_text)
        else:
            self.text_widgets[first].delete("1.0", tk.END)
            self.text_widgets[first].insert("1.0", ro_text)
            if second and second in self.text_widgets:
                self.text_widgets[second].delete("1.0", tk.END)
                self.text_widgets[second].insert("1.0", en_text)
        self.single_text.delete("1.0", tk.END)
        self.single_text.insert("1.0", ro_text)
        self.song_title.delete(0, tk.END)
        self.song_title.insert(0, os.path.basename(path).replace(".pdf", ""))
        line_count = len(ro_text.splitlines())
        self.number_widget.delete("1.0", tk.END)
        self.number_widget.insert("1.0", "\n".join(str(i+1) for i in range(line_count)))
        self.show_message(f"Loaded: {os.path.basename(path)}")

    def bind_unicode_fix(self, widget):
        widget.bind("<KeyPress>", on_key_press)

    def on_font_slider_change(self, value):
        self.apply_font_size(int(float(value)))

    def update_number_widget(self, event=None):
        first = self.text_block_names[0]
        text = self.text_widgets[first].get("1.0", tk.END)
        line_count = len(text.splitlines())
        self.number_widget.delete("1.0", tk.END)
        self.number_widget.insert("1.0", "\n".join(str(i+1) for i in range(line_count)))

    def apply_font_size(self, size):
        self.current_font_size = size
        font = ("Segoe UI", size)
        for w in list(self.text_widgets.values()) + [self.single_text, self.groupnames_text, self.message_area]:
            w.config(font=font)
        self.number_widget.config(font=("Segoe UI", size))
        self.config["font_size"] = size
        save_config(self.config)

    def toggle_theme(self):
        current = self.style.theme.name
        if current == "darkly":
            self.style.theme_use("litera")
            self.theme_btn.config(text="Dark Mode")
            self.message_area.config(bg="#f8f9fa", fg="#333333")
            for w in list(self.text_widgets.values()) + [self.single_text, self.groupnames_text]:
                w.config(bg="#ffffff", fg="#333333")
            self.number_widget.config(bg="#e9ecef", fg="#333333")
            self.config["theme"] = "litera"
        else:
            self.style.theme_use("darkly")
            self.theme_btn.config(text="Light Mode")
            self.message_area.config(bg="#1e1e1e", fg="#d4d4d4")
            for w in list(self.text_widgets.values()) + [self.single_text, self.groupnames_text]:
                w.config(bg="#2d2d2d", fg="#d4d4d4")
            self.number_widget.config(bg="#1e1e1e", fg="#d4d4d4")
            self.config["theme"] = "darkly"
        save_config(self.config)

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
        self.arrangement_order.grid(row=1, column=1, columnspan=5, padx=5, pady=(5,0), sticky="ew")
        self.bind_unicode_fix(self.arrangement_order)

        tb.Label(header, text="Font Size:", bootstyle="light").grid(row=2, column=0, sticky="w", pady=(5,0))
        self.font_slider = tb.Scale(header, from_=10, to=24, value=self.current_font_size, command=self.on_font_slider_change, bootstyle="info")
        self.font_slider.grid(row=2, column=1, columnspan=6, padx=5, pady=(5,0), sticky="ew")

        tb.Button(header, text="Open", bootstyle="primary-outline", command=self.open_file).grid(row=0, column=4, padx=10)
        tb.Button(header, text="Save", bootstyle="success-outline", command=self.save_song_action).grid(row=0, column=5)
        tb.Button(header, text="Check Typos", bootstyle="danger-outline", command=self.check_typos_action).grid(row=0, column=6, padx=10)
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
            text_widget.bind("<KeyRelease>", self.update_number_widget)

        def on_text_scroll(event):
            self.number_widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
            for widget in self.text_widgets.values():
                widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        self.number_widget.bind("<MouseWheel>", on_text_scroll)
        for wname, widget in self.text_widgets.items():
            widget.bind("<MouseWheel>", on_text_scroll)
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind('<<Drop>>', lambda e, n=wname: self.handle_pdf_drop(e, n))

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

    def _sync_all_scroll(self, event):
        self.number_widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
        for widget in self.text_widgets.values():
            widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    # ---------------------------------------------------------
    # SINGLE VIEW
    # ---------------------------------------------------------
    def build_single_tab(self):
        self.single_tab.grid_rowconfigure(0, weight=1)
        self.single_tab.grid_columnconfigure(0, weight=1)

        self.single_text = tk.Text(self.single_tab, wrap=tk.WORD, bg="#2d2d2d", fg="#d4d4d4")
        self.single_text.grid(row=0, column=0, sticky="nsew")
        self.bind_unicode_fix(self.single_text)
        self.single_text.bind("<MouseWheel>", self._sync_all_scroll)

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
        self.groupnames_text.bind("<MouseWheel>", self._sync_all_scroll)

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
    def get_known_labels(self):
        try:
            path = resource_path("GroupNames.txt")
            with open(path, "r", encoding="utf-8") as f:
                raw_labels = f.read().splitlines()
            labels = []
            for lbl in raw_labels:
                if ".." in lbl:
                    name, rng = lbl.split(" ")
                    start, end = map(int, rng.split(".."))
                    for i in range(start, end + 1):
                        labels.append(f"{name} {i}")
                else:
                    if lbl.strip():
                        labels.append(lbl.strip())
            return labels
        except Exception:
            return []

    def validate_group_labels(self, song_texts):
        known = set(self.get_known_labels())
        unknown = set()
        first_block = self.text_block_names[0]
        for line in song_texts[first_block]:
            stripped = line.strip()
            if not stripped or stripped in known:
                continue
            if len(stripped) > 10:
                continue
            if stripped.endswith((".", ",", "!", "?", ";", ":")):
                continue
            unknown.add(stripped)
        return sorted(unknown)

    def save_song_action(self):
        title = self.song_title.get().strip()
        if not title:
            self.show_message("Please enter a song title.")
            return

        for char in r":\\|/?*&^%$#@!~`'\";,.<>":
            title = title.replace(char, " ")

        song_texts = {name: self.text_widgets[name].get("1.0", tk.END).splitlines()
                      for name in self.text_block_names}

        unknown = self.validate_group_labels(song_texts)
        if unknown:
            msg = "Unknown group labels found:\n\n" + "\n".join(unknown) + "\n\nSave anyway?"
            if not tb.dialogs.Messagebox.yesno(msg, "Unknown Labels"):
                return

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