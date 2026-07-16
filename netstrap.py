import os
import subprocess
import sys
import json
import platform
import glob
import shutil
import urllib.request
import urllib.error
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog, font, simpledialog

# Try to import PIL for Image processing (Required for Cursor Resize and Logo)
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ── constants ────────────────────────────────────────────────────────────────
FASTFLAGS_FILE  = "fastFlags.json"
CUSTOM_ROOTS_FILE = "customRoots.json"
BOOTSTRAPPER_URL  = "https://setup.pekora.zip/PekoraPlayerLauncher.exe"
BOOTSTRAPPER_FILE = "PekoraPlayerLauncher.exe"

# ── Pekora Target Constants ──────────────────────────────────────────────────
PEKORA_VERSION_HASH = "version-cde8fee1a1e747d4"
PEKORA_2020L_FOLDER  = "2020L"
PEKORA_2021M_FOLDER  = "2021M"
PEKORA_FONTS_SUBPATH = os.path.join("content", "fonts")
PEKORA_TEXT_SUBPATH  = os.path.join("content", "textures")

# Files to manage as bundled resources
LOGO_FILENAME = "486334643-c0477fe6-8ed3-48dc-9404-ff9463d542ca.jpg"
ICON_FILENAME = "icon.ico" # The new icon file

# ── palette (DARK NEUTRAL THEME) ─────────────────────────────────────────────
BG      = "#121212"
SURFACE = "#1a1a1a"
CARD    = "#1f1f1f"
BORDER  = "#2a2a2a"
ACCENT  = "#f5c518"
ACCENT2 = "#d4af0f"
TEXT    = "#eaeaea"
MUTED   = "#8a8a8a"
GREEN   = "#3ddc84"
RED     = "#ff5c5c"
YELLOW  = "#ffd633"

# ── Helper to find bundled resources ─────────────────────────────────────────
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# ── platform helpers ─────────────────────────────────────────────────────────
def get_system_info():
    s = platform.system().lower()
    return {"is_windows": s=="windows", "is_linux": s=="linux", "system_name": s}

def load_custom_roots():
    if not os.path.exists(CUSTOM_ROOTS_FILE): return []
    try:
        with open(CUSTOM_ROOTS_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

def save_custom_roots(roots):
    try:
        with open(CUSTOM_ROOTS_FILE, "w") as f:
            json.dump(roots, f, indent=2)
        return True
    except Exception:
        return False

def get_version_roots(include_missing=False):
    """Returns install roots. If include_missing=True, also returns paths that
    were checked but don't exist (useful for debugging)."""
    si = get_system_info()
    candidates = []
    if si["is_windows"]:
        # Standard install locations
        candidates += [
            os.path.expandvars(r"%localappdata%\ProjectX\Versions"),
            os.path.expandvars(r"%localappdata%\Pekora\Versions"),
            os.path.expandvars(r"%appdata%\ProjectX\Versions"),
            os.path.expandvars(r"%appdata%\Pekora\Versions"),
            os.path.expandvars(r"%ProgramFiles%\Pekora\Versions"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Pekora\Versions"),
        ]
    # User-added custom paths (for portable installs, other drives, etc.)
    candidates += load_custom_roots()

    candidates = list(dict.fromkeys(candidates))  # de-dupe, keep order
    existing = [p for p in candidates if p and os.path.isdir(p)]
    if include_missing:
        return existing, candidates
    return existing

def iter_version_dirs():
    for root in get_version_roots():
        for d in sorted(glob.glob(os.path.join(root,"*"))):
            if os.path.isdir(d): yield d

def get_clientsettings_targets():
    targets = []
    for ver in iter_version_dirs():
        for folder in [PEKORA_2020L_FOLDER, PEKORA_2021M_FOLDER]:
            fp = os.path.join(ver, folder)
            if os.path.isdir(fp):
                cd = os.path.join(fp, "ClientSettings")
                targets.append((cd, os.path.join(cd, "ClientAppSettings.json"), folder))
    return targets

def get_executable_paths(folder):
    return [os.path.join(ver, folder, "ProjectXPlayerBeta.exe") for ver in iter_version_dirs()]

def load_fastflags():
    if not os.path.exists(FASTFLAGS_FILE): return {}
    try:
        with open(FASTFLAGS_FILE,"r") as f: return json.load(f)
    except: return {}

def save_fastflags(ff):
    with open(FASTFLAGS_FILE,"w") as f: json.dump(ff, f, indent=2)

def apply_fastflags(ff):
    """Returns (ok, errors). ok is True if at least one target was written
    successfully. errors is a list of human-readable messages for any target
    that failed (or if no targets were found at all)."""
    ok = False
    errors = []
    targets = get_clientsettings_targets()
    if not targets:
        errors.append("Не найдено ни одной установки Pekora/ProjectX. "
                       "Проверь вкладку Debug — список Roots пуст. "
                       "Добавь путь вручную через 'Add Custom Root'.")
        return ok, errors

    for cd, sp, folder in targets:
        try:
            os.makedirs(cd, exist_ok=True)
            with open(sp, "w") as f: json.dump(ff, f, indent=2)
            ok = True
        except Exception as e:
            errors.append(f"{folder}: {e}")
    return ok, errors

def auto_detect_value_type(s):
    s = s.strip()
    if s.lower() in ("true", "false"): return s.lower() == "true"
    try:
        if "." not in s: return int(s)
    except: pass
    try: return float(s)
    except: pass
    return s

# ═════════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION (minimalist "bootstrapper" style — logo / status / progress)
# ═════════════════════════════════════════════════════════════════════════════
class KoroneStrap(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KoroneStrap")
        self.geometry("420x480")
        self.resizable(False, False)
        self.configure(bg=BG)

        self.f_main = font.Font(family="Segoe UI", size=10)
        self.f_sm   = font.Font(family="Segoe UI", size=9)
        self.f_lg   = font.Font(family="Segoe UI", size=13, weight="bold")
        self.f_xl   = font.Font(family="Segoe UI", size=17, weight="bold")

        self.selected_version = tk.StringVar(value=PEKORA_2021M_FOLDER)
        self.settings_window = None

        self._load_logo()
        self._apply_app_icon()
        self._build_ui()

    def _load_logo(self):
        img_name = resource_path(LOGO_FILENAME)
        self.logo_img = None
        if os.path.exists(img_name) and HAS_PIL:
            try:
                img = Image.open(img_name)
                img = img.resize((88, 88), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(img)
            except Exception:
                pass

    def _apply_app_icon(self):
        si = get_system_info()
        if si["is_windows"]:
            try:
                icon_path = resource_path(ICON_FILENAME)
                if os.path.exists(icon_path):
                    self.iconbitmap(icon_path)
            except Exception:
                pass

    def _build_ui(self):
        # ── top settings icon ────────────────────────────────────────────────
        top = tk.Frame(self, bg=BG)
        top.pack(fill=tk.X, padx=16, pady=(12, 0))
        gear = tk.Button(top, text="⚙", font=("Segoe UI", 13), bg=BG, fg=MUTED, bd=0,
                          relief=tk.FLAT, cursor="hand2", activebackground=BG,
                          activeforeground=ACCENT, command=self.open_settings)
        gear.pack(side=tk.RIGHT)

        # ── centered logo + title ────────────────────────────────────────────
        center = tk.Frame(self, bg=BG)
        center.pack(expand=True, fill=tk.BOTH)

        logo_f = tk.Frame(center, bg=BG)
        logo_f.pack(pady=(30, 10))
        if self.logo_img:
            tk.Label(logo_f, image=self.logo_img, bg=BG).pack()
        else:
            tk.Label(logo_f, text="◆", font=("Segoe UI", 40), fg=ACCENT, bg=BG).pack()

        tk.Label(center, text="KoroneStrap", font=self.f_xl, fg=TEXT, bg=BG).pack()
        tk.Label(center, text="Pekora Bootstrapper", font=self.f_sm, fg=MUTED, bg=BG).pack(pady=(2, 25))

        # ── version toggle (segmented control) ───────────────────────────────
        seg = tk.Frame(center, bg=BORDER, bd=0)
        seg.pack(pady=(0, 20))
        self._seg_btns = {}
        for label, val in [("2021", PEKORA_2021M_FOLDER), ("2020", PEKORA_2020L_FOLDER)]:
            b = tk.Button(seg, text=label, font=self.f_main, bd=0, relief=tk.FLAT, padx=28, pady=6,
                          cursor="hand2", command=lambda v=val: self._select_version(v))
            b.pack(side=tk.LEFT, padx=1, pady=1)
            self._seg_btns[val] = b
        self._select_version(self.selected_version.get())

        # ── status + progress ────────────────────────────────────────────────
        self.status_lbl = tk.Label(center, text="Готово к запуску", font=self.f_sm, fg=MUTED, bg=BG)
        self.status_lbl.pack(pady=(0, 8))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Accent.Horizontal.TProgressbar", troughcolor=SURFACE,
                         background=ACCENT, bordercolor=SURFACE, lightcolor=ACCENT, darkcolor=ACCENT)
        self.progress = ttk.Progressbar(center, style="Accent.Horizontal.TProgressbar",
                                         orient="horizontal", mode="determinate", length=280)
        self.progress.pack(pady=(0, 20))

        # ── play button ───────────────────────────────────────────────────────
        self.play_btn = tk.Button(center, text="▶  ИГРАТЬ", font=self.f_lg, bg=ACCENT, fg="#000000",
                                   bd=0, relief=tk.FLAT, padx=20, pady=10, cursor="hand2",
                                   activebackground=ACCENT2, activeforeground="#000000",
                                   command=self._launch)
        self.play_btn.pack(pady=(0, 10))

        tk.Label(self, text="v1.0", font=("Segoe UI", 8), fg=BORDER, bg=BG).pack(side=tk.BOTTOM, pady=8)

    def _select_version(self, val):
        self.selected_version.set(val)
        for v, b in self._seg_btns.items():
            active = (v == val)
            b.configure(bg=ACCENT if active else BG, fg="#000000" if active else ACCENT)

    def _set_status(self, text):
        self.status_lbl.configure(text=text)
        self.update_idletasks()

    def _launch(self):
        folder = self.selected_version.get()
        paths = get_executable_paths(folder)
        exe = next((p for p in paths if os.path.isfile(p)), None)
        if not exe:
            messagebox.showerror("Error", f"Не найден исполняемый файл для {folder}.\n"
                                           "Проверь путь установки во вкладке Debug (⚙ → Debug).")
            return

        self.play_btn.configure(state=tk.DISABLED)
        self.progress["value"] = 0
        self._set_status("Применение FastFlags...")
        for i in range(0, 60, 15):
            self.progress["value"] = i
            self.update_idletasks()
            self.after(20)

        ok, errors = apply_fastflags(load_fastflags())
        if not ok and errors:
            messagebox.showwarning("FastFlags не применились", "\n".join(errors))

        self._set_status("Запуск клиента...")
        for i in range(60, 101, 10):
            self.progress["value"] = i
            self.update_idletasks()
            self.after(15)

        try:
            subprocess.Popen([exe, "--app"])
            self._set_status("Готово")
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self._set_status("Ошибка запуска")

        self.play_btn.configure(state=tk.NORMAL)
        self.after(1500, lambda: (self._set_status("Готово к запуску"), self.progress.configure(value=0)))

    def open_settings(self):
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            self.settings_window.focus_force()
            return
        self.settings_window = SettingsWindow(self)


# ── SETTINGS WINDOW (sidebar with the advanced pages) ────────────────────────
class SettingsWindow(tk.Toplevel):
    def __init__(self, root_app):
        super().__init__(root_app)
        self.root_app = root_app
        self.f_main = root_app.f_main
        self.f_sm   = root_app.f_sm
        self.f_lg   = root_app.f_lg
        self.f_xl   = root_app.f_xl

        self.title("KoroneStrap — Settings")
        self.geometry("760x560")
        self.configure(bg=BG)
        self.minsize(640, 480)

        self._build_ui()

    def _build_ui(self):
        sidebar = tk.Frame(self, bg=SURFACE, width=180)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        tk.Label(sidebar, text="НАСТРОЙКИ", font=self.f_sm, fg=MUTED, bg=SURFACE).pack(anchor="w", padx=20, pady=(20, 10))

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.pages = {}
        self._nav_btns = {}
        nav_items = [
            ("fastflags", "⚙  FastFlags"),
            ("bootstrap", "⬇  Bootstrapper"),
            ("editfont", "✎  Edit Font"),
            ("editcursor", "🖱  Edit Cursor"),
            ("debug", "🔍  Debug"),
        ]

        for key, label in nav_items:
            btn = tk.Button(sidebar, text=label, font=self.f_main, anchor="w", padx=20,
                            bg=BG, fg=ACCENT, bd=0, relief=tk.FLAT, cursor="hand2",
                            activebackground=BORDER, activeforeground=TEXT,
                            command=lambda k=key: self.show(k))
            btn.pack(fill=tk.X, pady=2)
            self._nav_btns[key] = btn

        for name, cls in [("fastflags", FastFlagsPage), ("bootstrap", BootstrapPage),
                          ("editfont", EditFontPage), ("editcursor", EditCursorPage),
                          ("debug", DebugPage)]:
            p = cls(self.content, self)
            p.place(relwidth=1, relheight=1)
            self.pages[name] = p

        self.show("fastflags")

    def show(self, key):
        for k, b in self._nav_btns.items():
            b.configure(bg=ACCENT if k == key else BG, fg="#000000" if k == key else ACCENT)
        self.pages[key].tkraise()
        self.pages[key].on_show()


# ── BASE PAGE ───────────────────────────────────────────────────────────────
class BasePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
    def on_show(self): pass
    def _title(self, txt, sub=""):
        f = tk.Frame(self, bg=BG)
        f.pack(fill=tk.X, padx=24, pady=(20, 0))
        tk.Label(f, text=txt, font=self.app.f_xl, fg=TEXT, bg=BG).pack(anchor="w")
        if sub: tk.Label(f, text=sub, font=self.app.f_sm, fg=MUTED, bg=BG).pack(anchor="w")
        tk.Frame(self, bg=BORDER, height=1).pack(fill=tk.X, padx=24, pady=(8, 20))

    def _btn(self, parent, text, cmd, color=ACCENT, fg="#000000", **kw):
        return tk.Button(parent, text=text, font=self.app.f_main, bg=color, fg=fg,
                         relief=tk.FLAT, bd=0, padx=15, pady=6, cursor="hand2", command=cmd, **kw)

# ── EDIT FONT PAGE (2020 & 2021 SUPPORT) ────────────────────────────────────
class EditFontPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._target_ver = tk.StringVar(value=PEKORA_2021M_FOLDER)
        self._build()

    def _build(self):
        self._title("Edit Font", "Mirror replacement for .ttf and .otf")

        card = tk.Frame(self, bg=CARD, padx=20, pady=20)
        card.pack(fill=tk.X, padx=24)

        tk.Label(card, text="1. Select Version", font=self.app.f_lg, fg=ACCENT, bg=CARD).pack(anchor="w")

        toggle_f = tk.Frame(card, bg=CARD)
        toggle_f.pack(anchor="w", pady=10)

        for text, val in [("2021 Client", PEKORA_2021M_FOLDER), ("2020 Client", PEKORA_2020L_FOLDER)]:
            tk.Radiobutton(toggle_f, text=text, variable=self._target_ver, value=val,
                           bg=CARD, fg=TEXT, selectcolor=BG, activebackground=CARD,
                           font=self.app.f_main, cursor="hand2").pack(side=tk.LEFT, padx=10)

        tk.Label(card, text="2. Mirror Overwrite", font=self.app.f_lg, fg=ACCENT, bg=CARD).pack(anchor="w", pady=(15, 0))
        tk.Label(card, text="This replaces every font inside the selected client's folder with your chosen font.",
                 font=self.app.f_sm, fg=TEXT, bg=CARD, wraplength=550, justify="left").pack(anchor="w", pady=10)

        self._btn(card, "✎ Select Font & Overwrite", self._do_font_mirror).pack(pady=10)

    def _do_font_mirror(self):
        ft = filedialog.askopenfilename(title="Select Font", filetypes=[("Font Files", "*.ttf *.otf")])
        if not ft: return

        dest_dir = os.path.join(os.path.expandvars(r"%localappdata%\Pekora\Versions"),
                                PEKORA_VERSION_HASH, self._target_ver.get(), PEKORA_FONTS_SUBPATH)

        if not os.path.exists(dest_dir):
            messagebox.showerror("Error", f"Folder not found: {self._target_ver.get()}\nPlease run that client once first.")
            return

        if not messagebox.askyesno("Confirm Mirror", f"Replace all fonts in {self._target_ver.get()}?"): return

        try:
            count = 0
            for filename in os.listdir(dest_dir):
                if filename.lower().endswith((".ttf", ".otf")):
                    shutil.copy2(ft, os.path.join(dest_dir, filename))
                    count += 1
            messagebox.showinfo("Success", f"Done! Replaced {count} font files in {self._target_ver.get()}.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed: {e}")

# ── EDIT CURSOR PAGE (64x64 REPLACEMENT) ────────────────────────────────────
class EditCursorPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._build()

    def _build(self):
        self._title("Edit Cursor", "Replace game cursors")
        card = tk.Frame(self, bg=CARD, padx=20, pady=20)
        card.pack(fill=tk.X, padx=24)
        tk.Label(card, text="Pekora Cursor Changer", font=self.app.f_lg, fg=ACCENT, bg=CARD).pack(anchor="w")
        tk.Label(card, text="Replaces ArrowCursor.png and ArrowFarCursor.png. Automatically resizes to 64x64.",
                 font=self.app.f_sm, fg=TEXT, bg=CARD, wraplength=550, justify="left").pack(anchor="w", pady=10)
        self._btn(card, "🖱 Select & Apply Cursor", self._do_cursor_replace).pack(pady=10)

    def _do_cursor_replace(self):
        if not HAS_PIL:
            messagebox.showerror("Error", "Pillow (PIL) is required. Run 'pip install Pillow'.")
            return
        img_path = filedialog.askopenfilename(title="Select Cursor Image", filetypes=[("Images", "*.png *.jpg *.jpeg")])
        if not img_path: return
        dest_dir = os.path.join(os.path.expandvars(r"%localappdata%\Pekora\Versions"), PEKORA_VERSION_HASH, PEKORA_2021M_FOLDER, PEKORA_TEXT_SUBPATH)
        if not os.path.exists(dest_dir):
            messagebox.showerror("Error", "Texture directory not found.")
            return
        try:
            img = Image.open(img_path)
            img_resized = img.resize((64, 64), Image.Resampling.LANCZOS)
            img_resized.save(os.path.join(dest_dir, "ArrowCursor.png"), "PNG")
            img_resized.save(os.path.join(dest_dir, "ArrowFarCursor.png"), "PNG")
            messagebox.showinfo("Success", "Cursors replaced and resized.")
        except Exception as e: messagebox.showerror("Error", str(e))

# ── FASTFLAGS PAGE ──────────────────────────────────────────────────────────
class FastFlagsPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._build()
    def _build(self):
        self._title("FastFlags", "Manage Client Settings")
        bar = tk.Frame(self, bg=BG); bar.pack(fill=tk.X, padx=24, pady=(0, 10))
        self._btn(bar, "+ Add", self._add, GREEN).pack(side=tk.LEFT, padx=2)
        self._btn(bar, "− Remove", self._remove, RED).pack(side=tk.LEFT, padx=2)
        self._btn(bar, "▶ Apply", self._apply, ACCENT).pack(side=tk.RIGHT)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=CARD, foreground=TEXT, fieldbackground=CARD, borderwidth=0)
        style.map("Treeview", background=[('selected', BORDER)])

        self.tree = ttk.Treeview(self, columns=("K", "V"), show="headings", height=15)
        self.tree.heading("K", text="Flag Key"); self.tree.heading("V", text="Value")
        self.tree.column("K", width=400); self.tree.column("V", width=200)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 20))
        self._refresh()

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        ff = load_fastflags()
        for k,v in ff.items(): self.tree.insert("", "end", values=(k, v))

    def _add(self):
        k = simpledialog.askstring("Add", "Flag Name:")
        v = simpledialog.askstring("Add", "Value:")
        if k and v:
            ff = load_fastflags(); ff[k] = auto_detect_value_type(v)
            save_fastflags(ff); self._refresh()

    def _remove(self):
        sel = self.tree.selection()
        if sel:
            k = self.tree.item(sel[0])["values"][0]
            ff = load_fastflags(); ff.pop(k, None)
            save_fastflags(ff); self._refresh()

    def _apply(self):
        ok, errors = apply_fastflags(load_fastflags())
        if ok:
            messagebox.showinfo("Success", "FastFlags applied.")
        else:
            messagebox.showerror("Не применилось", "\n".join(errors) if errors else "Неизвестная ошибка.")

# ── BOOTSTRAP PAGE ──────────────────────────────────────────────────────────
class BootstrapPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._build()
    def _build(self):
        self._title("Bootstrapper", "Installer management")
        card = tk.Frame(self, bg=CARD, padx=20, pady=20)
        card.pack(fill=tk.X, padx=24)
        tk.Label(card, text="PekoraPlayerLauncher.exe", font=self.app.f_lg, fg=TEXT, bg=CARD).pack(anchor="w")
        btn_f = tk.Frame(card, bg=CARD); btn_f.pack(anchor="w", pady=10)
        self._btn(btn_f, "⬇ Download", self._dl).pack(side=tk.LEFT, padx=5)
        self._btn(btn_f, "▶ Run", self._run, color=GREEN).pack(side=tk.LEFT)

    def _dl(self):
        def task():
            try:
                urllib.request.urlretrieve(BOOTSTRAPPER_URL, BOOTSTRAPPER_FILE)
                messagebox.showinfo("Success", "Bootstrapper downloaded.")
            except Exception as e: messagebox.showerror("Error", str(e))
        threading.Thread(target=task, daemon=True).start()

    def _run(self):
        if os.path.exists(BOOTSTRAPPER_FILE): subprocess.Popen([BOOTSTRAPPER_FILE])
        else: messagebox.showerror("Error", "Bootstrapper not found.")

# ── DEBUG PAGE ──────────────────────────────────────────────────────────────
class DebugPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._build()
    def _build(self):
        self._title("Debug", "System diagnostics")
        bar = tk.Frame(self, bg=BG); bar.pack(fill=tk.X, padx=24, pady=(0, 10))
        self._btn(bar, "+ Add Custom Root", self._add_custom_root, GREEN).pack(side=tk.LEFT, padx=2)
        self._btn(bar, "↻ Refresh", self.on_show).pack(side=tk.LEFT, padx=2)
        f = tk.Frame(self, bg=CARD); f.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 20))
        self.txt = scrolledtext.ScrolledText(f, bg="#000", fg=GREEN, font=self.app.f_sm, bd=0)
        self.txt.pack(fill=tk.BOTH, expand=True)

    def _add_custom_root(self):
        path = filedialog.askdirectory(title="Выбери папку 'Versions' (например ...\\Pekora\\Versions)")
        if not path: return
        roots = load_custom_roots()
        if path not in roots:
            roots.append(path)
            if save_custom_roots(roots):
                messagebox.showinfo("Готово", f"Добавлено: {path}")
            else:
                messagebox.showerror("Ошибка", "Не удалось сохранить customRoots.json")
        self.on_show()

    def on_show(self):
        self.txt.configure(state=tk.NORMAL); self.txt.delete("1.0", tk.END)
        found, checked = get_version_roots(include_missing=True)
        info = [f"OS: {platform.platform()}", f"Python: {sys.version}", "\nChecked paths:"]
        for p in checked:
            mark = "✓" if p in found else "✗"
            info.append(f" [{mark}] {p}")
        info.append(f"\nCustom roots (customRoots.json): {load_custom_roots() or 'none'}")
        targets = get_clientsettings_targets()
        info.append(f"\nClientSettings targets found: {len(targets)}")
        for cd, sp, folder in targets:
            info.append(f" - {folder}: {sp}")
        self.txt.insert(tk.END, "\n".join(info))
        self.txt.configure(state=tk.DISABLED)

if __name__ == "__main__":
    app = KoroneStrap()
    app.mainloop()
