#!/usr/bin/python

import ttkbootstrap as tb
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import filedialog
from tkinter.font import nametofont, families
import os
import sys
import json
import logging
import threading
import re
from SongEditorPro7Generic import save_song, get_text_block_names, split_slides
from single_export import save_single
from melodii import saved_song_names, save_json_to_melodii, load_json_from_melodii, find_saved_song
from autocorrect import find_typos, get_spellchecker
from tkinterdnd2 import DND_FILES, TkinterDnD
import pymupdf as fitz

# --- Modern label font ---
LABEL_FONT_FAMILY = "Segoe UI Semibold"
LABEL_FONT_SIZE = 10

# --- Theme colors ---
DARK_THEME = "bootstrap-dark"
LIGHT_THEME = "bootstrap-light"
DARK_BG = "#0f1b2d"        # dark blue tint (app background)
DARK_SURFACE = "#16273d"   # text areas
DARK_FG = "#dbe6f5"        # primary text
LIGHT_BG = "#e3f1dd"       # light greenish background
LIGHT_SURFACE = "#f5fbf2"  # text areas
LIGHT_FG = "#0a2410"       # dark green, high contrast text

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
        self.app_config = load_config()
        self.current_font_size = self.app_config.get("font_size", 11)
        default_theme = self.app_config.get("theme", DARK_THEME)
        if default_theme in ("darkly",):
            default_theme = DARK_THEME
        elif default_theme in ("litera",):
            default_theme = LIGHT_THEME
        super().__init__()
        self.label_font = (
            (LABEL_FONT_FAMILY, LABEL_FONT_SIZE)
            if LABEL_FONT_FAMILY in families()
            else ("Segoe UI", LABEL_FONT_SIZE, "bold")
        )
        self.style = tb.Style(theme=default_theme)
        self.title("ProPresenter7 Song Editor — Modern UI")
        self.geometry("1300x850")

        self.text_block_names = text_block_names
        self.output_dir = output_dir
        self.text_widgets = {}
        self._syncing_single = False
        self._preview_refresh_job = None
        self.template_path = self.app_config.get("template_path", None)

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
        self._syncing_single = True
        self._set_text(self.single_text, ro_text)
        self._syncing_single = False
        self.song_title.delete(0, tk.END)
        self.song_title.insert(0, os.path.basename(path).replace(".pdf", ""))
        line_count = len(ro_text.splitlines())
        self.number_widget.delete("1.0", tk.END)
        self.number_widget.insert("1.0", "\n".join(str(i+1) for i in range(line_count)))
        self.single_number_widget.delete("1.0", tk.END)
        self.single_number_widget.insert("1.0", "\n".join(str(i+1) for i in range(line_count)))
        self.show_message(f"Loaded: {os.path.basename(path)}")
        self._schedule_preview_refresh()

    def bind_unicode_fix(self, widget):
        widget.bind("<KeyPress>", on_key_press)

    def make_label(self, parent, text, **kwargs):
        return tb.Label(parent, text=text, font=self.label_font, **kwargs)

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
        self.single_number_widget.config(font=("Segoe UI", size))
        self.app_config["font_size"] = size
        save_config(self.app_config)

    def apply_theme_colors(self, light):
        if light:
            bg, fg, surface = LIGHT_BG, LIGHT_FG, LIGHT_SURFACE
        else:
            bg, fg, surface = DARK_BG, DARK_FG, DARK_SURFACE

        self.configure(bg=bg)
        for style_name in ("TFrame", "TLabel", "TLabelframe", "TLabelframe.Label", "TNotebook"):
            try:
                self.style.configure(style_name, background=bg, foreground=fg)
            except Exception:
                pass
        try:
            self.style.configure("TNotebook.Tab", foreground=fg)
        except Exception:
            pass

        for w in list(self.text_widgets.values()) + [self.single_text, self.groupnames_text]:
            w.config(bg=surface, fg=fg)
        self.number_widget.config(bg=bg, fg=fg)
        self.single_number_widget.config(bg=bg, fg=fg)
        self.message_area.config(bg=bg, fg=fg)
        if hasattr(self, "preview_canvas"):
            self.preview_canvas.config(bg=bg)

    def toggle_theme(self):
        if self.style.theme.name == DARK_THEME:
            self.style.theme_use(LIGHT_THEME)
            self.theme_btn.config(text="Dark Mode")
            self.app_config["theme"] = LIGHT_THEME
            self.apply_theme_colors(light=True)
        else:
            self.style.theme_use(DARK_THEME)
            self.theme_btn.config(text="Light Mode")
            self.app_config["theme"] = DARK_THEME
            self.apply_theme_colors(light=False)
        save_config(self.app_config)

    # ---------------------------------------------------------
    def edit_arrangement(self):
        win = tb.Toplevel(self)
        win.title("Edit Arrangement")
        win.geometry("420x420")
        win.transient(self)

        groups = []
        for g in self.text_block_names:
            pass
        # collect unique group names from GroupNames.txt
        try:
            with open(resource_path("GroupNames.txt"), "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and line not in groups:
                        groups.append(line)
        except Exception:
            groups = ["Verse 1", "Chorus", "Bridge"]

        # parse current arrangement
        current = [x.strip() for x in self.arrangement_order.get().split(",") if x.strip()]

        tb.Label(win, text="Available groups:").pack(pady=(10, 2))
        avail_lb = tk.Listbox(win, height=6)
        avail_lb.pack(fill=tk.X, padx=10)
        for g in groups:
            avail_lb.insert(tk.END, g)

        tb.Label(win, text="Arrangement (top to bottom):").pack(pady=(10, 2))
        arr_lb = tk.Listbox(win, height=8)
        arr_lb.pack(fill=tk.BOTH, expand=True, padx=10)
        for g in current:
            arr_lb.insert(tk.END, g)

        def add_sel():
            sel = avail_lb.curselection()
            if sel:
                arr_lb.insert(tk.END, avail_lb.get(sel[0]))

        def remove_sel():
            sel = arr_lb.curselection()
            if sel:
                arr_lb.delete(sel[0])

        def move_up():
            sel = arr_lb.curselection()
            if sel and sel[0] > 0:
                i = sel[0]
                val = arr_lb.get(i)
                arr_lb.delete(i)
                arr_lb.insert(i - 1, val)
                arr_lb.selection_set(i - 1)

        def move_down():
            sel = arr_lb.curselection()
            if sel and sel[0] < arr_lb.size() - 1:
                i = sel[0]
                val = arr_lb.get(i)
                arr_lb.delete(i)
                arr_lb.insert(i + 1, val)
                arr_lb.selection_set(i + 1)

        btn_frame = tb.Frame(win)
        btn_frame.pack(pady=5)
        tb.Button(btn_frame, text="Add", command=add_sel).pack(side=tk.LEFT, padx=3)
        tb.Button(btn_frame, text="Remove", command=remove_sel).pack(side=tk.LEFT, padx=3)
        tb.Button(btn_frame, text="Up", command=move_up).pack(side=tk.LEFT, padx=3)
        tb.Button(btn_frame, text="Down", command=move_down).pack(side=tk.LEFT, padx=3)

        def apply():
            items = [arr_lb.get(i) for i in range(arr_lb.size())]
            self.arrangement_order.delete(0, tk.END)
            self.arrangement_order.insert(0, ", ".join(items))
            win.destroy()

        tb.Button(win, text="Apply", bootstyle="success", command=apply).pack(pady=10)

    def import_chordpro(self):
        path = filedialog.askopenfilename(
            initialdir=self.output_dir,
            filetypes=[("ChordPro", "*.cho *.chordpro *.txt"), ("All", "*.*")],
            title="Import ChordPro")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except Exception as e:
            self.show_message("Error reading file: " + str(e))
            return
        from chordpro import parse_chordpro
        sections = parse_chordpro(text)
        # Build a combined text for the primary block with group labels
        lines = []
        for label, lyrics in sections.items():
            lines.append(label)
            lines.extend(lyrics)
        if self.text_block_names:
            primary = self.text_block_names[0]
            widget = self.text_widgets.get(primary)
            if widget:
                widget.delete("1.0", tk.END)
                widget.insert("1.0", "\n".join(lines))
        title = os.path.splitext(os.path.basename(path))[0]
        self.song_title.set(title)
        self.show_message("Imported ChordPro: " + os.path.basename(path)
                          + " (" + str(len(sections)) + " sections)")

    def load_template(self):
        path = filedialog.askopenfilename(
            initialdir=self.output_dir,
            filetypes=[("ProPresenter", "*.pro")],
            title="Select Template.pro")
        if not path:
            return
        try:
            new_names = get_text_block_names(path)
        except Exception as e:
            self.show_message("Invalid template: " + str(e))
            log_error("Failed to load template")
            return
        if not new_names:
            self.show_message("Template has no text blocks.")
            return
        self.template_path = path
        self.app_config["template_path"] = path
        save_config(self.app_config)
        self.text_block_names = new_names
        self.text_widgets = {}
        for child in self.compare_tab.winfo_children():
            child.destroy()
        for child in self.single_tab.winfo_children():
            child.destroy()
        self.build_compare_tab()
        self.build_single_tab()
        self.show_message("Loaded template: " + os.path.basename(path)
                          + " - " + ", ".join(new_names))

    # UI BUILD
    # ---------------------------------------------------------
    def init_ui(self):

        # Header (modern card)
        header = tb.Frame(self, padding=10)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        header.grid_columnconfigure(4, weight=1)

        self.make_label(header, "Song Name:").grid(row=0, column=0, sticky="w")
        self.song_title = tb.Combobox(header, width=34, bootstyle="info")
        self.song_title.grid(row=0, column=1, padx=5)
        self.song_title.configure(postcommand=self.refresh_song_autocomplete)
        self.bind_unicode_fix(self.song_title)
        self.refresh_song_autocomplete()

        tb.Button(header, text="Import", bootstyle="info-outline", command=self.import_from_melodii_action).grid(row=0, column=2, padx=5)
        tb.Button(header, text="Load Template", bootstyle="secondary-outline", command=self.load_template).grid(row=0, column=3, padx=5)

        self.make_label(header, "Lines per Slide:").grid(row=0, column=5, sticky="e")
        self.line_count = tb.Entry(header, width=5, bootstyle="info")
        self.line_count.insert(0, "2")
        self.line_count.grid(row=0, column=6, padx=5)
        self.bind_unicode_fix(self.line_count)
        self.line_count.bind("<KeyRelease>", self._schedule_preview_refresh)
        self.line_count.bind("<FocusOut>", self._schedule_preview_refresh)

        tb.Button(header, text="Open", bootstyle="primary-outline", command=self.open_file).grid(row=0, column=7, padx=5)
        tb.Button(header, text="Import ChordPro", bootstyle="secondary-outline", command=self.import_chordpro).grid(row=0, column=8, padx=5)
        tb.Button(header, text="Save", bootstyle="success-outline", command=self.save_song_action).grid(row=0, column=9, padx=5)
        tb.Button(header, text="Check Typos", bootstyle="danger-outline", command=self.check_typos_action).grid(row=0, column=10, padx=5)

        self.make_label(header, "Arrangement:").grid(row=1, column=0, sticky="w", pady=(5,0))
        self.arrangement_order = tb.Entry(header, width=80, bootstyle="info")
        self.arrangement_order.insert(0, "Verse 1, Chorus, Verse 2, Chorus, Bridge, Chorus")
        self.arrangement_order.grid(row=1, column=1, columnspan=4, padx=5, pady=(5,0), sticky="ew")
        self.bind_unicode_fix(self.arrangement_order)
        tb.Button(header, text="Edit Arrangement", bootstyle="secondary-outline", command=self.edit_arrangement).grid(row=1, column=5, columnspan=2, padx=5, pady=(5,0))

        self.theme_btn = tb.Button(header, text="Light Mode", bootstyle="secondary-outline", command=self.toggle_theme)
        self.theme_btn.grid(row=1, column=10, padx=5, pady=(5,0), sticky="e")

        self.make_label(header, "Font Size:").grid(row=2, column=0, sticky="w", pady=(5,0))
        self.font_slider = tb.Scale(header, from_=10, to=24, value=self.current_font_size, command=self.on_font_slider_change, bootstyle="info")
        self.font_slider.grid(row=2, column=1, columnspan=9, padx=5, pady=(5,0), sticky="ew")

        # Notebook
        self.notebook = tb.Notebook(self, bootstyle="primary")
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        self.compare_tab = tb.Frame(self.notebook)
        self.single_tab = tb.Frame(self.notebook)
        self.groupnames_tab = tb.Frame(self.notebook)
        self.preview_tab = tb.Frame(self.notebook)

        self.notebook.add(self.compare_tab, text="Translate View")
        self.notebook.add(self.single_tab, text="Single View")
        self.notebook.add(self.preview_tab, text="Slide Preview")
        self.notebook.add(self.groupnames_tab, text="Edit Group Names")

        self.build_compare_tab()
        self.build_single_tab()
        self.build_preview_tab()
        self.build_groupnames_tab()

        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Group Names Preview
        self.label_hint = tb.Label(self, justify=tk.LEFT, wraplength=1000, bootstyle="secondary")
        self.label_hint.grid(row=2, column=0, padx=10, pady=5, sticky="ew")
        self.update_group_label_preview()

        # Status message
        self.message_area = tk.Text(self, height=2, bg=DARK_BG, fg=DARK_FG)
        self.message_area.grid(row=3, column=0, padx=10, pady=5, sticky="ew")
        self.bind_unicode_fix(self.message_area)

        self.apply_theme_colors(light=(self.style.theme.name == LIGHT_THEME))

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
        number_frame = tb.Frame(self.compare_tab)
        number_frame.grid(row=0, column=0, sticky="nsew", padx=5)

        self.make_label(number_frame, "#").pack()
        self.number_widget = tk.Text(number_frame, wrap=tk.NONE, width=4,
                                     bg=DARK_BG, fg=DARK_FG, yscrollcommand=self.scrollbar.set)
        self.number_widget.pack(expand=True, fill=tk.BOTH)
        self.number_widget.bind("<Motion>", self.on_hover)

        # Text columns
        for col, name in enumerate(self.text_block_names):
            frame = tb.Frame(self.compare_tab)
            frame.grid(row=0, column=col+1, sticky="nsew", padx=5)

            self.make_label(frame, name).pack()

            text_widget = tk.Text(frame, wrap=tk.WORD, bg=DARK_SURFACE, fg=DARK_FG,
                                  yscrollcommand=self.scrollbar.set)
            text_widget.pack(expand=True, fill=tk.BOTH)

            self.bind_unicode_fix(text_widget)
            self.text_widgets[name] = text_widget
            text_widget.bind("<Motion>", self.on_hover)
            text_widget.bind("<KeyRelease>", self.update_number_widget)
            text_widget.bind("<KeyRelease>", self._schedule_preview_refresh, add="+")

        self.number_widget.bind("<MouseWheel>", self._sync_all_scroll)
        for wname, widget in self.text_widgets.items():
            widget.bind("<MouseWheel>", self._sync_all_scroll)
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
        self.single_tab.grid_columnconfigure(1, weight=1)

        # Scrollbar
        self.single_scrollbar = tb.Scrollbar(self.single_tab, orient="vertical", bootstyle="info")
        self.single_scrollbar.grid(row=0, column=2, sticky="ns")

        def sync_scroll(*args):
            self.single_number_widget.yview(*args)
            self.single_text.yview(*args)

        self.single_scrollbar.config(command=sync_scroll)

        # Number column
        single_number_frame = tb.Frame(self.single_tab)
        single_number_frame.grid(row=0, column=0, sticky="nsew", padx=5)
        self.make_label(single_number_frame, "#").pack()
        self.single_number_widget = tk.Text(
            single_number_frame, wrap=tk.NONE, width=4,
            bg=DARK_BG, fg=DARK_FG, yscrollcommand=self.single_scrollbar.set)
        self.single_number_widget.pack(expand=True, fill=tk.BOTH)

        # Text column
        single_text_frame = tb.Frame(self.single_tab)
        single_text_frame.grid(row=0, column=1, sticky="nsew", padx=5)
        self.make_label(single_text_frame, self.text_block_names[0]).pack()
        self.single_text = tk.Text(single_text_frame, wrap=tk.WORD,
                                   bg=DARK_SURFACE, fg=DARK_FG,
                                   yscrollcommand=self.single_scrollbar.set)
        self.single_text.pack(expand=True, fill=tk.BOTH)
        self.bind_unicode_fix(self.single_text)

        # Download button
        tb.Button(self.single_tab, text="Download as Single",
                  bootstyle="primary", command=self.download_single_action).grid(
            row=1, column=1, pady=10)

        # Behavior wired like the compare columns
        self.single_text.bind("<Motion>", self.on_single_hover)
        self.single_number_widget.bind("<Motion>", self.on_single_hover)
        self.single_text.bind("<KeyRelease>", self._mirror_single_to_compare)
        self.single_text.bind("<KeyRelease>", self._schedule_preview_refresh, add="+")
        self.single_text.bind("<MouseWheel>", self._sync_single_scroll)
        self.single_number_widget.bind("<MouseWheel>", self._sync_single_scroll)
        self.single_text.drop_target_register(DND_FILES)
        self.single_text.dnd_bind('<<Drop>>', lambda e: self.handle_pdf_drop(e, self.text_block_names[0]))

        # Mirror the first/primary block (Romana) both ways
        self.text_widgets[self.text_block_names[0]].bind(
            "<KeyRelease>", self._mirror_compare_to_single, add="+")

    def on_single_hover(self, event):
        index = event.widget.index(f"@0,{event.y}")
        line = index.split(".")[0]
        self.single_text.tag_remove("hover", "1.0", tk.END)
        self.single_number_widget.tag_remove("hover", "1.0", tk.END)
        self.single_text.tag_add("hover", f"{line}.0", f"{line}.end")
        self.single_text.tag_config("hover", background="#004d40")
        self.single_number_widget.tag_add("hover", f"{line}.0", f"{line}.end")
        self.single_number_widget.tag_config("hover", background="#004d40")

    def update_single_number_widget(self, event=None):
        text = self.single_text.get("1.0", tk.END)
        line_count = len(text.splitlines())
        self.single_number_widget.delete("1.0", tk.END)
        self.single_number_widget.insert("1.0", "\n".join(str(i+1) for i in range(line_count)))

    def _sync_single_scroll(self, event):
        self.single_number_widget.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.single_text.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _set_text(self, widget, content):
        widget.delete("1.0", tk.END)
        widget.insert("1.0", content)
        widget.edit_modified(False)

    def _mirror_single_to_compare(self, event=None):
        if self._syncing_single:
            return
        first = self.text_block_names[0]
        self._syncing_single = True
        self._set_text(self.text_widgets[first], self.single_text.get("1.0", "end-1c"))
        self._syncing_single = False
        self.update_single_number_widget()
        self.update_number_widget()

    def _mirror_compare_to_single(self, event=None):
        if self._syncing_single:
            return
        first = self.text_block_names[0]
        self._syncing_single = True
        self._set_text(self.single_text, self.text_widgets[first].get("1.0", "end-1c"))
        self._syncing_single = False
        self.update_single_number_widget()
        self.update_number_widget()


    # ---------------------------------------------------------
    # SLIDE PREVIEW TAB
    # ---------------------------------------------------------
    def build_preview_tab(self):
        self.preview_tab.grid_rowconfigure(1, weight=1)
        self.preview_tab.grid_columnconfigure(0, weight=1)

        toolbar = tb.Frame(self.preview_tab)
        toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        tb.Button(toolbar, text="Refresh Preview", bootstyle="info-outline",
                  command=self.refresh_preview).pack(side=tk.LEFT)
        self.preview_primary_only = tk.BooleanVar(value=False)
        tb.Checkbutton(toolbar, text="Primary language only",
                       variable=self.preview_primary_only,
                       bootstyle="info-round-toggle",
                       command=self.refresh_preview).pack(side=tk.LEFT, padx=10)
        self.preview_count_label = tb.Label(toolbar, text="", bootstyle="secondary")
        self.preview_count_label.pack(side=tk.LEFT, padx=10)

        body = tb.Frame(self.preview_tab)
        body.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        self.preview_canvas = tk.Canvas(body, highlightthickness=0, bg=DARK_BG)
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")
        preview_scrollbar = tb.Scrollbar(body, orient="vertical", bootstyle="info",
                                         command=self.preview_canvas.yview)
        preview_scrollbar.grid(row=0, column=1, sticky="ns")
        self.preview_canvas.configure(yscrollcommand=preview_scrollbar.set)

        self.preview_inner = tb.Frame(self.preview_canvas)
        self._preview_window = self.preview_canvas.create_window(
            (0, 0), window=self.preview_inner, anchor="nw")

        self.preview_inner.bind("<Configure>", self._on_preview_inner_configure)
        self.preview_canvas.bind("<Configure>", self._on_preview_canvas_configure)
        self.preview_canvas.bind("<MouseWheel>", self._on_preview_mousewheel)
        self.preview_inner.bind("<MouseWheel>", self._on_preview_mousewheel)

    def _on_preview_inner_configure(self, event=None):
        self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

    def _on_preview_canvas_configure(self, event):
        self.preview_canvas.itemconfigure(self._preview_window, width=event.width)

    def _on_preview_mousewheel(self, event):
        self.preview_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _on_tab_changed(self, event=None):
        try:
            if self.notebook.select() == str(self.preview_tab):
                self.refresh_preview()
        except Exception:
            pass

    def _schedule_preview_refresh(self, event=None):
        if self._preview_refresh_job is not None:
            try:
                self.after_cancel(self._preview_refresh_job)
            except Exception:
                pass
        self._preview_refresh_job = self.after(400, self.refresh_preview)

    def refresh_preview(self, event=None):
        self._preview_refresh_job = None
        if not hasattr(self, "preview_inner"):
            return

        for child in self.preview_inner.winfo_children():
            child.destroy()

        song_texts = self.collect_song_texts()
        max_lines = self.parse_max_lines()
        primary_only = self.preview_primary_only.get()
        names = [self.text_block_names[0]] if primary_only else list(self.text_block_names)

        try:
            slides = split_slides(self.text_block_names, song_texts, max_lines)
        except Exception as e:
            self.preview_count_label.config(text="Preview unavailable: " + str(e))
            return

        total = len(slides)
        self.preview_count_label.config(text=f"{total} slide(s)")

        if total == 0:
            tb.Label(self.preview_inner, text="No slides yet - add some lyrics.",
                     bootstyle="secondary").pack(anchor="w", padx=5, pady=5)
            return

        for idx, slide in enumerate(slides, start=1):
            label = slide.get("label", "")
            card = tb.Labelframe(
                self.preview_inner, text=f"#{idx} / {total}  -  {label}",
                bootstyle="info", padding=8)
            card.pack(fill=tk.X, padx=5, pady=4)
            for col, name in enumerate(names):
                col_frame = tb.Frame(card)
                col_frame.grid(row=0, column=col, sticky="nw", padx=(0, 24))
                tb.Label(col_frame, text=name, font=self.label_font,
                         bootstyle="info").pack(anchor="w")
                lines = slide.get(name, [])
                tb.Label(col_frame, text="\n".join(lines) if lines else " ",
                         justify=tk.LEFT, bootstyle="secondary",
                         wraplength=320).pack(anchor="w")

        self.preview_inner.update_idletasks()
        self.preview_canvas.configure(scrollregion=self.preview_canvas.bbox("all"))

    # ---------------------------------------------------------
    # GROUP NAMES TAB
    # ---------------------------------------------------------
    def build_groupnames_tab(self):
        self.groupnames_tab.grid_rowconfigure(1, weight=1)
        self.groupnames_tab.grid_columnconfigure(0, weight=1)

        self.make_label(self.groupnames_tab, "Edit GroupNames.txt:").grid(row=0, column=0, sticky="w", padx=5, pady=5)

        self.groupnames_text = tk.Text(self.groupnames_tab, wrap=tk.WORD, bg=DARK_SURFACE, fg=DARK_FG)
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
            except Exception:
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
        except Exception as e:
            self.show_message("Error opening file: " + str(e))
            log_error("Failed to open file")
            return

        self.song_title.set(os.path.basename(path).replace(".json", ""))
        self.load_json_data(data, f"Opened: {path}")

    def load_json_data(self, data, label=""):
        for name in self.text_block_names:
            self.text_widgets[name].delete("1.0", tk.END)
            self.text_widgets[name].insert("1.0", "\n".join(data.get(name, [])))

        max_len = max(len(data.get(name, [])) for name in self.text_block_names)
        self.number_widget.delete("1.0", tk.END)
        self.number_widget.insert("1.0", "\n".join(str(i+1) for i in range(max_len)))

        self._syncing_single = True
        self._set_text(self.single_text, self.text_widgets[self.text_block_names[0]].get("1.0", tk.END))
        self._syncing_single = False
        self.update_single_number_widget()

        if label:
            self.show_message(label)
        self._schedule_preview_refresh()

    def refresh_song_autocomplete(self):
        self.song_title["values"] = saved_song_names()

    def import_from_melodii_action(self):
        title = self.song_title.get().strip()
        if not title:
            self.show_message("Type a song name to import.")
            return

        found = find_saved_song(title)
        if not found:
            self.show_message(f"No saved song named '{title}' in Melodii.")
            return

        try:
            data = load_json_from_melodii(found)
        except (OSError, ValueError) as e:
            self.show_message("Import failed: " + str(e))
            log_error("Failed to import from Melodii")
            return

        self.song_title.set(found)
        self.load_json_data(data, f"Imported: {found}")

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

    def collect_song_texts(self):
        return {name: self.text_widgets[name].get("1.0", tk.END).splitlines()
                for name in self.text_block_names}

    def parse_max_lines(self):
        try:
            return int(self.line_count.get())
        except (ValueError, TypeError):
            self.line_count.delete(0, tk.END)
            self.line_count.insert(0, "2")
            return 2

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

        song_texts = self.collect_song_texts()

        unknown = self.validate_group_labels(song_texts)
        if unknown:
            msg = "Unknown group labels found:\n\n" + "\n".join(unknown) + "\n\nSave anyway?"
            if not tb.dialogs.Messagebox.yesno(msg, "Unknown Labels"):
                return

        max_lines = self.parse_max_lines()

        max_len = max(len(song_texts[name]) for name in self.text_block_names)
        self.number_widget.delete("1.0", tk.END)
        self.number_widget.insert("1.0", "\n".join(str(i+1) for i in range(max_len)))

        output_file = os.path.join(self.output_dir, title)

        try:
            save_song(self.text_block_names, song_texts, max_lines, output_file, arrangement_order=self.arrangement_order.get().strip(), template_path=self.template_path)
            save_json_to_melodii(title, song_texts)
            self.refresh_song_autocomplete()
            self.show_message(f"Saved! Import in ProPresenter: File → Import → {output_file}.pro")
        except Exception as e:
            self.show_message("Save failed: " + str(e))
            log_error("Failed to save song")

    # ---------------------------------------------------------
    # DOWNLOAD AS SINGLE — .pro with only the primary block
    # ---------------------------------------------------------
    def download_single_action(self):
        title = self.song_title.get().strip()
        if not title:
            self.show_message("Please enter a song title.")
            return

        for char in r":\\|/?*&^%$#@!~`'\";,.<>":
            title = title.replace(char, " ")

        block_name = self.text_block_names[0]
        lines = self.single_text.get("1.0", tk.END).splitlines()

        unknown = self.validate_group_labels({block_name: lines})
        if unknown:
            msg = "Unknown group labels found:\n\n" + "\n".join(unknown) + "\n\nDownload anyway?"
            if not tb.dialogs.Messagebox.yesno(msg, "Unknown Labels"):
                return

        max_lines = self.parse_max_lines()

        output_file = os.path.join(self.output_dir, title + " (Single)")

        try:
            save_single(block_name, {block_name: lines}, max_lines, output_file,
                        arrangement_order=self.arrangement_order.get().strip(),
                        template_path=self.template_path)
            self.show_message(f"Saved single! Import in ProPresenter: File → Import → {output_file}.pro")
        except Exception as e:
            self.show_message("Single download failed: " + str(e))
            log_error("Failed to download single")

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
        template_path = load_config().get("template_path", None)
        text_block_names = get_text_block_names(template_path)
        logging.info(f"Text block names: {text_block_names} (template: {template_path})")
        output_dir = get_download_path()
        logging.info(f"Output directory: {output_dir}")
        app = SongEditorApp(text_block_names, output_dir)

        default_font = nametofont("TkDefaultFont")
        default_font.configure(family="Segoe UI", size=app.current_font_size)

        logging.info("Entering main loop")
        app.mainloop()
    except Exception as e:
        logging.critical(f"Fatal error: {e}", exc_info=True)
        raise