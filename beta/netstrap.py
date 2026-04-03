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

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ── constants ─────────────────────────────────────────────────────────────────
FASTFLAGS_FILE    = "fastFlags.json"
BOOTSTRAPPER_URL  = "https://setup.pekora.zip/PekoraPlayerLauncher.exe"
BOOTSTRAPPER_FILE = "PekoraPlayerLauncher.exe"
SETTINGS_FILE     = "koronestrap_settings.json"

PEKORA_VERSION_HASH  = "version-cde8fee1a1e747d4"
PEKORA_2020L_FOLDER  = "2020L"
PEKORA_2021M_FOLDER  = "2021M"
PEKORA_FONTS_SUBPATH = os.path.join("content", "fonts")
PEKORA_TEXT_SUBPATH  = os.path.join("content", "textures")

LOGO_FILENAME = "486334643-c0477fe6-8ed3-48dc-9404-ff9463d542ca.jpg"
ICON_FILENAME = "icon.ico"

# ── THEMES ────────────────────────────────────────────────────────────────────
THEMES = {
    "Void Black": {
        "BG":      "#000000",
        "SURFACE": "#0c0c0c",
        "BORDER":  "#1c1c1c",
        "ACCENT":  "#00d4ff",
        "ACCENT2": "#0090b8",
        "TEXT":    "#e8e8e8",
        "MUTED":   "#555555",
        "GREEN":   "#00e676",
        "RED":     "#ff1744",
        "YELLOW":  "#ffd740",
    },
    "Purple Haze": {
        "BG":      "#0a0014",
        "SURFACE": "#16002b",
        "BORDER":  "#2d0052",
        "ACCENT":  "#c084fc",
        "ACCENT2": "#8b5cf6",
        "TEXT":    "#f2e6ff",
        "MUTED":   "#7c6a96",
        "GREEN":   "#a78bfa",
        "RED":     "#f87171",
        "YELLOW":  "#fde68a",
    },
    "Blood Red": {
        "BG":      "#0d0000",
        "SURFACE": "#1a0000",
        "BORDER":  "#3a0000",
        "ACCENT":  "#ff4444",
        "ACCENT2": "#cc0000",
        "TEXT":    "#ffe8e8",
        "MUTED":   "#885555",
        "GREEN":   "#ff6b6b",
        "RED":     "#ff0000",
        "YELLOW":  "#ffaa00",
    },
    "Matrix Green": {
        "BG":      "#000d00",
        "SURFACE": "#001a00",
        "BORDER":  "#003300",
        "ACCENT":  "#00ff41",
        "ACCENT2": "#00cc33",
        "TEXT":    "#ccffcc",
        "MUTED":   "#447744",
        "GREEN":   "#00ff41",
        "RED":     "#ff4444",
        "YELLOW":  "#aaff00",
    },
    "Ocean Blue": {
        "BG":      "#000814",
        "SURFACE": "#001233",
        "BORDER":  "#023e8a",
        "ACCENT":  "#48cae4",
        "ACCENT2": "#0096c7",
        "TEXT":    "#caf0f8",
        "MUTED":   "#4a7fa0",
        "GREEN":   "#90e0ef",
        "RED":     "#ef476f",
        "YELLOW":  "#ffd166",
    },
    "Amber Retro": {
        "BG":      "#0d0800",
        "SURFACE": "#1a1000",
        "BORDER":  "#3d2600",
        "ACCENT":  "#ffb300",
        "ACCENT2": "#e65100",
        "TEXT":    "#fff8e1",
        "MUTED":   "#886633",
        "GREEN":   "#ffcc02",
        "RED":     "#ff6d00",
        "YELLOW":  "#ffe57f",
    },
}

DEFAULT_THEME = "Purple Haze"

# ── settings ──────────────────────────────────────────────────────────────────
def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {"theme": DEFAULT_THEME}
    try:
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    except:
        return {"theme": DEFAULT_THEME}

def save_settings(s):
    with open(SETTINGS_FILE, "w") as f:
        json.dump(s, f, indent=2)

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ── platform helpers ──────────────────────────────────────────────────────────
def get_system_info():
    s = platform.system().lower()
    return {"is_windows": s == "windows", "is_linux": s == "linux",
            "is_macos": s == "darwin", "system_name": s}

def get_version_roots():
    si = get_system_info()
    roots = []
    if si["is_windows"]:
        roots += [os.path.expandvars(r"%localappdata%\ProjectX\Versions"),
                  os.path.expandvars(r"%localappdata%\Pekora\Versions")]
    elif si["is_linux"]:
        u = os.getenv("USER", "user")
        roots += [
            os.path.expanduser(f"~/.wine/drive_c/users/{u}/AppData/Local/ProjectX/Versions"),
            os.path.expanduser(f"~/.wine/drive_c/users/{u}/AppData/Local/Pekora/Versions"),
            os.path.expanduser(f"~/.local/share/wineprefixes/pekora/drive_c/users/{u}/AppData/Local/Pekora/Versions"),
        ]
    return [p for p in roots if os.path.isdir(p)]

def iter_version_dirs():
    for root in get_version_roots():
        for d in sorted(glob.glob(os.path.join(root, "*"))):
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
        with open(FASTFLAGS_FILE) as f: return json.load(f)
    except: return {}

def save_fastflags(ff):
    with open(FASTFLAGS_FILE, "w") as f: json.dump(ff, f, indent=2)

def apply_fastflags(ff):
    ok = False
    for cd, sp, _ in get_clientsettings_targets():
        try:
            os.makedirs(cd, exist_ok=True)
            if os.path.exists(sp):
                try: os.replace(sp, sp + ".bak")
                except: pass
            with open(sp, "w") as f: json.dump(ff, f, indent=2)
            ok = True
        except: pass
    return ok

def auto_detect_value_type(s):
    s = s.strip()
    if s.lower() in ("true", "false"): return s.lower() == "true"
    try:
        if "." not in s and "e" not in s.lower(): return int(s)
    except: pass
    try: return float(s)
    except: pass
    return s

def _wine_cmd():
    for c in ("wine64", "wine"):
        try:
            subprocess.check_output([c, "--version"], stderr=subprocess.DEVNULL)
            return c
        except: pass
    return "wine"

# ═════════════════════════════════════════════════════════════════════════════
#  THEME ENGINE
# ═════════════════════════════════════════════════════════════════════════════
class ThemeEngine:
    def __init__(self):
        settings = load_settings()
        self._name = settings.get("theme", DEFAULT_THEME)
        if self._name not in THEMES:
            self._name = DEFAULT_THEME
        self._palette = dict(THEMES[self._name])
        self._listeners = []

    @property
    def name(self): return self._name

    def get(self, key): return self._palette.get(key, "#ffffff")

    def __getattr__(self, key):
        if key.startswith("_"): raise AttributeError(key)
        return self._palette.get(key, "#ffffff")

    def register(self, fn):
        self._listeners.append(fn)

    def apply(self, theme_name):
        if theme_name not in THEMES: return
        self._name = theme_name
        self._palette = dict(THEMES[theme_name])
        s = load_settings()
        s["theme"] = theme_name
        save_settings(s)
        for fn in self._listeners:
            try: fn(self._palette)
            except: pass

    def p(self): return self._palette


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION
# ═════════════════════════════════════════════════════════════════════════════
class KoroneStrap(tk.Tk):
    def __init__(self):
        super().__init__()
        self.theme = ThemeEngine()
        T = self.theme

        self.title("KoroneStrap")
        self.geometry("960x680")
        self.minsize(820, 560)
        self.configure(bg=T.BG)
        self.resizable(True, True)

        # remove the OS title bar entirely
        self.overrideredirect(True)

        self.f_main  = font.Font(family="Consolas", size=10)
        self.f_sm    = font.Font(family="Consolas", size=9)
        self.f_lg    = font.Font(family="Consolas", size=13, weight="bold")
        self.f_xl    = font.Font(family="Consolas", size=15, weight="bold")
        self.f_title = font.Font(family="Consolas", size=20, weight="bold")
        self.f_micro = font.Font(family="Consolas", size=8)

        self._drag_x = 0
        self._drag_y = 0

        self._apply_icon()
        self._load_logo()
        self._build_ui()

        self.theme.register(lambda p: self.configure(bg=p["BG"]))

    def _apply_icon(self):
        si = get_system_info()
        if si["is_windows"]:
            try:
                p = resource_path(ICON_FILENAME)
                if os.path.exists(p): self.iconbitmap(p)
            except: pass

    def _load_logo(self):
        self.logo_img = None
        p = resource_path(LOGO_FILENAME)
        if os.path.exists(p) and HAS_PIL:
            try:
                img = Image.open(p).resize((80, 80), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(img)
            except: pass

    def _minimize(self):
        """Minimize via iconify — works even with overrideredirect on Windows."""
        self.overrideredirect(False)
        self.iconify()
        self.bind("<Map>", self._on_restore)

    def _on_restore(self, event):
        self.overrideredirect(True)
        self.unbind("<Map>")

    def _drag_start(self, event):
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _drag_motion(self, event):
        self.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def _build_ui(self):
        T = self.theme

        # ── custom title bar ──────────────────────────────────────────────────
        tb = tk.Frame(self, bg=T.SURFACE, height=36)
        tb.pack(fill=tk.X, side=tk.TOP)
        tb.pack_propagate(False)
        self.theme.register(lambda p, w=tb: w.configure(bg=p["SURFACE"]))

        # accent top line
        accent_line = tk.Frame(self, bg=T.ACCENT, height=2)
        accent_line.pack(fill=tk.X, side=tk.TOP)
        self.theme.register(lambda p, w=accent_line: w.configure(bg=p["ACCENT"]))

        # app title label
        tb_lbl = tk.Label(tb, text="  KoroneStrap",
                          font=self.f_micro, fg=T.MUTED, bg=T.SURFACE)
        tb_lbl.pack(side=tk.LEFT)
        self.theme.register(lambda p, w=tb_lbl: w.configure(fg=p["MUTED"], bg=p["SURFACE"]))

        btn_kw = dict(font=("Consolas", 12), bd=0, relief=tk.FLAT,
                      padx=13, pady=0, cursor="hand2", height=36)

        close_btn = tk.Button(tb, text="✕",
                              bg=T.SURFACE, fg=T.MUTED,
                              activebackground="#c0392b", activeforeground="#ffffff",
                              command=self.destroy, **btn_kw)
        close_btn.pack(side=tk.RIGHT)

        min_btn = tk.Button(tb, text="─",
                            bg=T.SURFACE, fg=T.MUTED,
                            activebackground=T.BORDER, activeforeground=T.TEXT,
                            command=self._minimize, **btn_kw)
        min_btn.pack(side=tk.RIGHT)

        self.theme.register(lambda p, c=close_btn, m=min_btn: (
            c.configure(bg=p["SURFACE"], fg=p["MUTED"]),
            m.configure(bg=p["SURFACE"], fg=p["MUTED"],
                        activebackground=p["BORDER"], activeforeground=p["TEXT"]),
        ))

        # drag — bind to bar and label (not buttons)
        for w in (tb, tb_lbl):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>",     self._drag_motion)

        # thin separator under title bar
        sep_tb = tk.Frame(self, bg=T.BORDER, height=1)
        sep_tb.pack(fill=tk.X, side=tk.TOP)
        self.theme.register(lambda p, w=sep_tb: w.configure(bg=p["BORDER"]))

        # ── body frame holds sidebar + content side by side ───────────────────
        body = tk.Frame(self, bg=T.BG)
        body.pack(fill=tk.BOTH, expand=True)
        self.theme.register(lambda p, w=body: w.configure(bg=p["BG"]))

        # ── sidebar ───────────────────────────────────────────────────────────
        self.sidebar = tk.Frame(body, bg=T.SURFACE, width=215)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)
        self.theme.register(lambda p: self.sidebar.configure(bg=p["SURFACE"]))

        # logo area
        logo_frame = tk.Frame(self.sidebar, bg=T.SURFACE, pady=22)
        logo_frame.pack(fill=tk.X)
        self.theme.register(lambda p, f=logo_frame: f.configure(bg=p["SURFACE"]))

        if self.logo_img:
            lbl = tk.Label(logo_frame, image=self.logo_img, bg=T.SURFACE)
            lbl.pack()
            self.theme.register(lambda p, w=lbl: w.configure(bg=p["SURFACE"]))
        else:
            self._logo_lbl = tk.Label(logo_frame, text="KORONE",
                font=self.f_title, fg=T.ACCENT, bg=T.SURFACE)
            self._logo_lbl.pack()
            self._sub_lbl = tk.Label(logo_frame, text="S T R A P",
                font=self.f_micro, fg=T.ACCENT2, bg=T.SURFACE)
            self._sub_lbl.pack()
            self.theme.register(lambda p: (
                self._logo_lbl.configure(fg=p["ACCENT"], bg=p["SURFACE"]),
                self._sub_lbl.configure(fg=p["ACCENT2"], bg=p["SURFACE"]),
                logo_frame.configure(bg=p["SURFACE"]),
            ))

        sep = tk.Frame(self.sidebar, bg=T.BORDER, height=1)
        sep.pack(fill=tk.X, padx=16, pady=(0, 8))
        self.theme.register(lambda p, w=sep: w.configure(bg=p["BORDER"]))

        # nav
        self._nav_btns = {}
        nav_items = [
            ("launch",     "▶   Launch"),
            ("fastflags",  "⚙   FastFlags"),
            ("bootstrap",  "⬇   Bootstrapper"),
            ("editfont",   "✎   Edit Font"),
            ("editcursor", "🖱   Edit Cursor"),
            ("themes",     "🎨   Themes"),
            ("debug",      "🔍   Debug"),
        ]
        for key, label in nav_items:
            self._make_nav_btn(key, label)

        badge = tk.Label(self.sidebar,
            text=f"v2.0  ·  {platform.system()}",
            font=self.f_micro, fg=T.MUTED, bg=T.SURFACE)
        badge.pack(side=tk.BOTTOM, pady=12)
        self.theme.register(lambda p, w=badge: w.configure(fg=p["MUTED"], bg=p["SURFACE"]))

        # ── content ───────────────────────────────────────────────────────────
        self.content = tk.Frame(body, bg=T.BG)
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.theme.register(lambda p: self.content.configure(bg=p["BG"]))

        self.pages = {}
        for name, cls in [
            ("launch",     LaunchPage),
            ("fastflags",  FastFlagsPage),
            ("bootstrap",  BootstrapPage),
            ("editfont",   EditFontPage),
            ("editcursor", EditCursorPage),
            ("themes",     ThemesPage),
            ("debug",      DebugPage),
        ]:
            pg = cls(self.content, self)
            pg.place(relwidth=1, relheight=1)
            self.pages[name] = pg

        self._current_page = "launch"
        self.show("launch")

    def _make_nav_btn(self, key, label):
        T = self.theme
        row = tk.Frame(self.sidebar, bg=T.SURFACE)
        row.pack(fill=tk.X, pady=1)

        bar = tk.Frame(row, bg=T.SURFACE, width=3)
        bar.pack(side=tk.LEFT, fill=tk.Y)

        btn = tk.Button(row, text=label, font=self.f_main,
                        anchor="w", padx=14,
                        bg=T.SURFACE, fg=T.MUTED,
                        activebackground=T.BORDER, activeforeground=T.TEXT,
                        bd=0, relief=tk.FLAT, cursor="hand2",
                        command=lambda k=key: self.show(k))
        btn.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=9)

        self._nav_btns[key] = (btn, bar, row)

        def _reg(p, b=btn, br=bar, r=row):
            b.configure(bg=p["SURFACE"], fg=p["MUTED"],
                        activebackground=p["BORDER"], activeforeground=p["TEXT"])
            br.configure(bg=p["SURFACE"])
            r.configure(bg=p["SURFACE"])
        self.theme.register(_reg)

    def show(self, key):
        T = self.theme
        self._current_page = key
        for k, (btn, bar, row) in self._nav_btns.items():
            if k == key:
                btn.configure(bg=T.BORDER, fg=T.ACCENT)
                bar.configure(bg=T.ACCENT)
                row.configure(bg=T.BORDER)
            else:
                btn.configure(bg=T.SURFACE, fg=T.MUTED)
                bar.configure(bg=T.SURFACE)
                row.configure(bg=T.SURFACE)
        self.pages[key].tkraise()
        self.pages[key].on_show()

    def refresh_nav(self):
        self.show(self._current_page)


# ═════════════════════════════════════════════════════════════════════════════
#  BASE PAGE
# ═════════════════════════════════════════════════════════════════════════════
class BasePage(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=app.theme.BG)
        self.app = app
        app.theme.register(lambda p: self.configure(bg=p["BG"]))

    def on_show(self): pass

    def _tw(self, widget, **mapping):
        T = self.app.theme
        def _apply(p, w=widget, m=mapping):
            try: w.configure(**{prop: p[tkey] for prop, tkey in m.items()})
            except: pass
        self.app.theme.register(_apply)
        _apply(T.p())
        return widget

    def _title(self, txt, sub=""):
        T = self.app.theme
        outer = tk.Frame(self, bg=T.BG)
        outer.pack(fill=tk.X, padx=28, pady=(24, 0))
        self._tw(outer, bg="BG")

        row = tk.Frame(outer, bg=T.BG)
        row.pack(anchor="w", fill=tk.X)
        self._tw(row, bg="BG")

        bar = tk.Frame(row, bg=T.ACCENT, width=4)
        bar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 14))
        self._tw(bar, bg="ACCENT")

        tcol = tk.Frame(row, bg=T.BG)
        tcol.pack(side=tk.LEFT)
        self._tw(tcol, bg="BG")

        tl = tk.Label(tcol, text=txt, font=self.app.f_xl, fg=T.TEXT, bg=T.BG)
        tl.pack(anchor="w")
        self._tw(tl, fg="TEXT", bg="BG")

        if sub:
            sl = tk.Label(tcol, text=sub, font=self.app.f_sm, fg=T.MUTED, bg=T.BG)
            sl.pack(anchor="w")
            self._tw(sl, fg="MUTED", bg="BG")

        sep = tk.Frame(self, bg=T.BORDER, height=1)
        sep.pack(fill=tk.X, padx=28, pady=(14, 20))
        self._tw(sep, bg="BORDER")

    def _card(self, parent=None, **kw):
        if parent is None: parent = self
        T = self.app.theme
        c = tk.Frame(parent, bg=T.SURFACE, **kw)
        self._tw(c, bg="SURFACE")
        return c

    def _btn(self, parent, text, cmd, color_key="ACCENT", fg_key="BG", **kw):
        T = self.app.theme
        b = tk.Button(parent, text=text, font=self.app.f_main,
                      bg=T.get(color_key), fg=T.get(fg_key),
                      activebackground=T.get(color_key),
                      activeforeground=T.get(fg_key),
                      relief=tk.FLAT, bd=0, padx=16, pady=7,
                      cursor="hand2", command=cmd, **kw)
        self._tw(b, bg=color_key, fg=fg_key,
                 activebackground=color_key, activeforeground=fg_key)
        return b

    def _make_log(self, parent=None, height=10):
        if parent is None: parent = self
        T = self.app.theme
        f = tk.Frame(parent, bg=T.SURFACE)
        self._tw(f, bg="SURFACE")
        sb = tk.Scrollbar(f)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        t = tk.Text(f, height=height, bg=T.BG, fg=T.TEXT,
                    font=self.app.f_sm, bd=0, relief=tk.FLAT,
                    wrap=tk.WORD, state=tk.DISABLED,
                    yscrollcommand=sb.set, insertbackground=T.ACCENT)
        t.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=6)
        sb.config(command=t.yview)
        self.app.theme.register(lambda p, w=t: w.configure(
            bg=p["BG"], fg=p["TEXT"], insertbackground=p["ACCENT"]))
        return f, t

    def _log(self, widget, msg, color_key="TEXT"):
        T = self.app.theme
        widget.configure(state=tk.NORMAL)
        tag = f"tag_{color_key}"
        widget.tag_configure(tag, foreground=T.get(color_key))
        widget.insert(tk.END, msg + "\n", tag)
        widget.see(tk.END)
        widget.configure(state=tk.DISABLED)


# ═════════════════════════════════════════════════════════════════════════════
#  LAUNCH PAGE
# ═════════════════════════════════════════════════════════════════════════════
class LaunchPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._build()

    def _build(self):
        T = self.app.theme
        self._title("Launch", "Select a version to start playing")

        versions = [
            ("2017", None,                True),
            ("2018", None,                True),
            ("2020", PEKORA_2020L_FOLDER, False),
            ("2021", PEKORA_2021M_FOLDER, False),
        ]

        grid = tk.Frame(self, bg=T.BG)
        grid.pack(fill=tk.X, padx=28)
        self._tw(grid, bg="BG")

        for i, (yr, folder, wip) in enumerate(versions):
            col = i % 2
            row = i // 2
            grid.columnconfigure(col, weight=1)

            card = self._card(grid, padx=20, pady=18)
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

            top_bar = tk.Frame(card, bg=T.MUTED if wip else T.ACCENT, height=2)
            top_bar.pack(fill=tk.X, pady=(0, 12))
            self._tw(top_bar, bg="MUTED" if wip else "ACCENT")

            yr_lbl = tk.Label(card, text=f"Client {yr}", font=self.app.f_lg,
                              fg=T.MUTED if wip else T.TEXT, bg=T.SURFACE)
            yr_lbl.pack(anchor="w")
            self._tw(yr_lbl, fg="MUTED" if wip else "TEXT", bg="SURFACE")

            st_lbl = tk.Label(card,
                text="Work In Progress" if wip else "Ready",
                font=self.app.f_sm,
                fg=T.MUTED if wip else T.GREEN, bg=T.SURFACE)
            st_lbl.pack(anchor="w", pady=(2, 14))
            self._tw(st_lbl, fg="MUTED" if wip else "GREEN", bg="SURFACE")

            if wip:
                tk.Button(card, text="Coming Soon", font=self.app.f_sm,
                          bg=T.BORDER, fg=T.MUTED, state=tk.DISABLED,
                          relief=tk.FLAT, bd=0, padx=12, pady=5).pack(anchor="w")
            else:
                self._btn(card, f"▶  Launch {yr}",
                          lambda f=folder: self._launch(f)).pack(anchor="w")

        lbl = tk.Label(self, text="  Console", font=self.app.f_sm,
                       fg=T.MUTED, bg=T.BG, anchor="w")
        lbl.pack(fill=tk.X, padx=28, pady=(20, 2))
        self._tw(lbl, fg="MUTED", bg="BG")

        lf, self.log = self._make_log(self, height=8)
        lf.pack(fill=tk.BOTH, expand=True, padx=28, pady=(0, 20))

    def _launch(self, folder):
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)

        si = get_system_info()
        ff = load_fastflags()

        if ff:
            self._log(self.log, f"[*] Applying {len(ff)} FastFlag(s)…", "MUTED")
            if apply_fastflags(ff):
                self._log(self.log, "[✓] FastFlags applied", "GREEN")
            else:
                self._log(self.log, "[!] Failed to apply FastFlags", "RED")
        else:
            self._log(self.log, "[*] No FastFlags configured", "MUTED")

        self._log(self.log, f"[*] Looking for {folder} executable…", "ACCENT")
        paths = get_executable_paths(folder)
        exe_path = next((p for p in paths if os.path.isfile(p)), None)

        if not exe_path:
            self._log(self.log, "[✗] Executable not found — EXECNFOUND", "RED")
            for p in paths:
                self._log(self.log, f"    - {p}", "MUTED")
            return

        try:
            if si["is_windows"]:
                subprocess.Popen([exe_path, "--app"])
            else:
                env = os.environ.copy()
                if si["is_linux"]:
                    env.update({"__NV_PRIME_RENDER_OFFLOAD": "1",
                                "__GLX_VENDOR_LIBRARY_NAME": "nvidia"})
                wine_cmd = "wine64"
                try:
                    subprocess.check_output([wine_cmd, "--version"], stderr=subprocess.DEVNULL)
                except Exception:
                    wine_cmd = "wine"
                subprocess.Popen([wine_cmd, exe_path, "--app"], env=env)
            self._log(self.log, "[✓] Launch successful!", "GREEN")
        except Exception as e:
            self._log(self.log, f"[✗] {e}", "RED")


# ═════════════════════════════════════════════════════════════════════════════
#  FASTFLAGS PAGE
# ═════════════════════════════════════════════════════════════════════════════
class FastFlagsPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._build()

    def _build(self):
        T = self.app.theme
        self._title("FastFlags", "Configure client settings flags")

        bar = tk.Frame(self, bg=T.BG)
        bar.pack(fill=tk.X, padx=28, pady=(0, 10))
        self._tw(bar, bg="BG")

        self._btn(bar, "+ Add",    self._add,    "GREEN").pack(side=tk.LEFT, padx=(0, 4))
        self._btn(bar, "− Remove", self._remove, "RED").pack(side=tk.LEFT, padx=(0, 4))
        self._btn(bar, "↑ Import", self._import, "ACCENT2").pack(side=tk.LEFT, padx=(0, 4))
        self._btn(bar, "✗ Clear",  self._clear,  "BORDER", "TEXT").pack(side=tk.LEFT)
        self._btn(bar, "▶ Apply",  self._apply,  "ACCENT").pack(side=tk.RIGHT)

        tf = tk.Frame(self, bg=T.SURFACE)
        tf.pack(fill=tk.BOTH, expand=True, padx=28, pady=(0, 8))
        self._tw(tf, bg="SURFACE")

        self._style_tree()
        cols = ("Key", "Value", "Type")
        self.tree = ttk.Treeview(tf, columns=cols, show="headings",
                                  selectmode="browse", style="KS.Treeview")
        for c, w in zip(cols, (360, 180, 80)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=w, minwidth=60)

        sb = tk.Scrollbar(tf, command=self.tree.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.status = tk.Label(self, text="", font=self.app.f_sm,
                               fg=T.MUTED, bg=T.BG, anchor="w")
        self.status.pack(fill=tk.X, padx=28, pady=(0, 14))
        self._tw(self.status, fg="MUTED", bg="BG")

        self.app.theme.register(lambda p: self._style_tree())
        self._refresh()

    def _style_tree(self):
        T = self.app.theme
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("KS.Treeview",
                        background=T.SURFACE, fieldbackground=T.SURFACE,
                        foreground=T.TEXT, font=("Consolas", 9),
                        rowheight=26, borderwidth=0)
        style.configure("KS.Treeview.Heading",
                        background=T.BORDER, foreground=T.MUTED,
                        font=("Consolas", 9), relief="flat")
        style.map("KS.Treeview",
                  background=[("selected", T.BORDER)],
                  foreground=[("selected", T.ACCENT)])

    def on_show(self): self._refresh()

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        ff = load_fastflags()
        for k, v in ff.items():
            self.tree.insert("", "end", values=(k, v, type(v).__name__))
        n = len(ff)
        T = self.app.theme
        self.status.configure(
            text=f"  {n} flag{'s' if n != 1 else ''} configured",
            fg=T.GREEN if n else T.MUTED)

    def _add(self):
        k = simpledialog.askstring("Add FastFlag", "Flag name:")
        if not k: return
        v = simpledialog.askstring("Add FastFlag", f"Value for  {k}:")
        if v is None: return
        ff = load_fastflags()
        ff[k] = auto_detect_value_type(v)
        save_fastflags(ff); self._refresh()

    def _remove(self):
        sel = self.tree.selection()
        if not sel: return
        key = str(self.tree.item(sel[0])["values"][0])
        if messagebox.askyesno("Remove", f"Remove '{key}'?"):
            ff = load_fastflags(); ff.pop(key, None)
            save_fastflags(ff); self._refresh()

    def _clear(self):
        if messagebox.askyesno("Clear All", "Clear ALL FastFlags?"):
            save_fastflags({}); self._refresh()

    def _apply(self):
        ff = load_fastflags()
        if not ff: messagebox.showinfo("Apply", "No flags to apply."); return
        if apply_fastflags(ff):
            messagebox.showinfo("Apply", f"Applied {len(ff)} flag(s).")
        else:
            messagebox.showerror("Apply", "Failed — no valid installation found.")

    def _import(self):
        txt = simpledialog.askstring("Import JSON",
            'Paste JSON:  {"FFlagName": true, "DFInt...": 144}', parent=self)
        if not txt: return
        try:
            imported = json.loads(txt)
            if not isinstance(imported, dict): raise ValueError("Not a dict")
            ff = load_fastflags(); ff.update(imported)
            save_fastflags(ff); self._refresh()
            messagebox.showinfo("Import", f"Imported {len(imported)} flag(s).")
        except Exception as e:
            messagebox.showerror("Import", f"Invalid JSON:\n{e}")


# ═════════════════════════════════════════════════════════════════════════════
#  BOOTSTRAPPER PAGE
# ═════════════════════════════════════════════════════════════════════════════
class BootstrapPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._build()

    def _build(self):
        T = self.app.theme
        self._title("Bootstrapper", "Download and run the Pekora launcher")

        card = self._card(padx=22, pady=18)
        card.pack(fill=tk.X, padx=28, pady=(0, 14))

        top = tk.Frame(card, bg=T.SURFACE)
        top.pack(fill=tk.X, pady=(0, 6))
        self._tw(top, bg="SURFACE")

        name_lbl = tk.Label(top, text="PekoraPlayerLauncher.exe",
                            font=self.app.f_lg, fg=T.TEXT, bg=T.SURFACE)
        name_lbl.pack(side=tk.LEFT)
        self._tw(name_lbl, fg="TEXT", bg="SURFACE")

        self._dot = tk.Label(top, text="", font=self.app.f_sm,
                             fg=T.MUTED, bg=T.SURFACE)
        self._dot.pack(side=tk.RIGHT)
        self._tw(self._dot, bg="SURFACE")
        self._update_dot()

        url_lbl = tk.Label(card, text=BOOTSTRAPPER_URL,
                           font=self.app.f_sm, fg=T.MUTED, bg=T.SURFACE)
        url_lbl.pack(anchor="w", pady=(0, 14))
        self._tw(url_lbl, fg="MUTED", bg="SURFACE")

        btn_row = tk.Frame(card, bg=T.SURFACE)
        btn_row.pack(anchor="w")
        self._tw(btn_row, bg="SURFACE")

        self._btn(btn_row, "⬇  Download", self._download, "ACCENT").pack(side=tk.LEFT, padx=(0, 8))
        self._btn(btn_row, "▶  Launch",   self._launch,   "GREEN").pack(side=tk.LEFT)

        pb_wrap = tk.Frame(self, bg=T.BG)
        pb_wrap.pack(fill=tk.X, padx=28, pady=(10, 4))
        self._tw(pb_wrap, bg="BG")

        self.pb_label = tk.Label(pb_wrap, text="", font=self.app.f_sm,
                                 fg=T.MUTED, bg=T.BG)
        self.pb_label.pack(anchor="w")
        self._tw(self.pb_label, fg="MUTED", bg="BG")

        style = ttk.Style()
        style.configure("KS.Horizontal.TProgressbar",
                        troughcolor=T.BORDER, background=T.ACCENT, borderwidth=0)
        self.app.theme.register(lambda p: style.configure(
            "KS.Horizontal.TProgressbar",
            troughcolor=p["BORDER"], background=p["ACCENT"]))

        self.pb = ttk.Progressbar(pb_wrap, style="KS.Horizontal.TProgressbar",
                                   mode="determinate")
        self.pb.pack(fill=tk.X, pady=(4, 0))

        lf, self.log = self._make_log(self, height=10)
        lf.pack(fill=tk.BOTH, expand=True, padx=28, pady=(6, 20))

    def _update_dot(self):
        T = self.app.theme
        exists = os.path.exists(BOOTSTRAPPER_FILE)
        self._dot.configure(
            text="● Downloaded" if exists else "● Not found",
            fg=T.GREEN if exists else T.MUTED)

    def on_show(self): self._update_dot()

    def _download(self):
        if os.path.exists(BOOTSTRAPPER_FILE):
            if not messagebox.askyesno("Overwrite", f"{BOOTSTRAPPER_FILE} exists. Overwrite?"):
                return
        self.pb["value"] = 0
        self.pb_label.configure(text="Starting…")
        self._log(self.log, "[*] Starting download…", "ACCENT")

        def task():
            try:
                def prog(bn, bs, tot):
                    if tot > 0:
                        pct = min(100, bn * bs * 100 // tot)
                        mb = bn * bs / 1048576
                        tm = tot / 1048576
                        self.after(0, lambda: self.pb.configure(value=pct))
                        self.after(0, lambda: self.pb_label.configure(
                            text=f"{pct}%  ({mb:.1f} / {tm:.1f} MB)"))
                urllib.request.urlretrieve(BOOTSTRAPPER_URL, BOOTSTRAPPER_FILE, prog)
                if os.path.exists(BOOTSTRAPPER_FILE) and os.path.getsize(BOOTSTRAPPER_FILE) > 0:
                    sz = os.path.getsize(BOOTSTRAPPER_FILE) / 1048576
                    self.after(0, lambda: self._log(self.log, f"[✓] Downloaded ({sz:.1f} MB)", "GREEN"))
                    self.after(0, lambda: self.pb_label.configure(text="Complete ✓"))
                    self.after(0, self._update_dot)
                else:
                    self.after(0, lambda: self._log(self.log, "[✗] File empty or missing", "RED"))
            except urllib.error.HTTPError as e:
                self.after(0, lambda: self._log(self.log, f"[✗] HTTP {e.code}: {e.reason}", "RED"))
            except Exception as e:
                self.after(0, lambda: self._log(self.log, f"[✗] {e}", "RED"))

        threading.Thread(target=task, daemon=True).start()

    def _launch(self):
        if not os.path.exists(BOOTSTRAPPER_FILE):
            messagebox.showerror("Launch", "Bootstrapper not found. Download it first.")
            return
        try:
            si = get_system_info()
            if si["is_windows"]:
                subprocess.Popen([BOOTSTRAPPER_FILE])
            else:
                env = os.environ.copy()
                if si["is_linux"]:
                    env.update({"__NV_PRIME_RENDER_OFFLOAD": "1",
                                "__GLX_VENDOR_LIBRARY_NAME": "nvidia"})
                subprocess.Popen([_wine_cmd(), BOOTSTRAPPER_FILE], env=env)
            self._log(self.log, "[✓] Bootstrapper launched", "GREEN")
        except Exception as e:
            self._log(self.log, f"[✗] {e}", "RED")


# ═════════════════════════════════════════════════════════════════════════════
#  EDIT FONT PAGE
# ═════════════════════════════════════════════════════════════════════════════
class EditFontPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._target_ver = tk.StringVar(value=PEKORA_2021M_FOLDER)
        self._build()

    def _build(self):
        T = self.app.theme
        self._title("Edit Font", "Mirror-replace all fonts in a client version")

        card = self._card(padx=22, pady=18)
        card.pack(fill=tk.X, padx=28)

        hdr = tk.Label(card, text="Target Version", font=self.app.f_lg,
                       fg=T.ACCENT, bg=T.SURFACE)
        hdr.pack(anchor="w", pady=(0, 10))
        self._tw(hdr, fg="ACCENT", bg="SURFACE")

        for text, val in [("2021 Client", PEKORA_2021M_FOLDER),
                          ("2020 Client", PEKORA_2020L_FOLDER)]:
            rb = tk.Radiobutton(card, text=text, variable=self._target_ver,
                                value=val, bg=T.SURFACE, fg=T.TEXT,
                                selectcolor=T.BG, activebackground=T.SURFACE,
                                font=self.app.f_main, cursor="hand2")
            rb.pack(anchor="w", pady=2)
            self.app.theme.register(lambda p, w=rb: w.configure(
                bg=p["SURFACE"], fg=p["TEXT"], selectcolor=p["BG"],
                activebackground=p["SURFACE"]))

        sep = tk.Frame(card, bg=T.BORDER, height=1)
        sep.pack(fill=tk.X, pady=14)
        self._tw(sep, bg="BORDER")

        info = tk.Label(card,
            text="Replaces every .ttf and .otf file inside the selected\n"
                 "client's font folder with your chosen font.",
            font=self.app.f_sm, fg=T.TEXT, bg=T.SURFACE, justify="left")
        info.pack(anchor="w", pady=(0, 14))
        self._tw(info, fg="TEXT", bg="SURFACE")

        self._btn(card, "✎  Select Font & Apply Mirror",
                  self._do_mirror, "ACCENT").pack(anchor="w")

    def _do_mirror(self):
        ft = filedialog.askopenfilename(title="Select Font File",
                filetypes=[("Font Files", "*.ttf *.otf")])
        if not ft: return

        dest_dir = os.path.join(
            os.path.expandvars(r"%localappdata%\Pekora\Versions"),
            PEKORA_VERSION_HASH, self._target_ver.get(), PEKORA_FONTS_SUBPATH)

        if not os.path.exists(dest_dir):
            messagebox.showerror("Error",
                f"Folder not found for {self._target_ver.get()}.\n"
                "Run that client at least once first.")
            return

        if not messagebox.askyesno("Confirm",
                f"Replace all fonts in {self._target_ver.get()}?"): return
        try:
            count = 0
            for fn in os.listdir(dest_dir):
                if fn.lower().endswith((".ttf", ".otf")):
                    shutil.copy2(ft, os.path.join(dest_dir, fn))
                    count += 1
            messagebox.showinfo("Success",
                f"Replaced {count} font file(s) in {self._target_ver.get()}.")
        except Exception as e:
            messagebox.showerror("Error", str(e))


# ═════════════════════════════════════════════════════════════════════════════
#  EDIT CURSOR PAGE
# ═════════════════════════════════════════════════════════════════════════════
class EditCursorPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._build()

    def _build(self):
        T = self.app.theme
        self._title("Edit Cursor", "Replace in-game cursor images")

        card = self._card(padx=22, pady=18)
        card.pack(fill=tk.X, padx=28)

        hdr = tk.Label(card, text="Cursor Replacer", font=self.app.f_lg,
                       fg=T.ACCENT, bg=T.SURFACE)
        hdr.pack(anchor="w", pady=(0, 8))
        self._tw(hdr, fg="ACCENT", bg="SURFACE")

        info = tk.Label(card,
            text="Replaces  ArrowCursor.png  and  ArrowFarCursor.png\n"
                 "in the 2021 client.  Image is auto-resized to 64×64.",
            font=self.app.f_sm, fg=T.TEXT, bg=T.SURFACE, justify="left")
        info.pack(anchor="w", pady=(0, 14))
        self._tw(info, fg="TEXT", bg="SURFACE")

        if not HAS_PIL:
            warn = tk.Label(card,
                text="⚠  Pillow not installed — run:  pip install Pillow",
                font=self.app.f_sm, fg=T.YELLOW, bg=T.SURFACE)
            warn.pack(anchor="w", pady=(0, 10))
            self._tw(warn, fg="YELLOW", bg="SURFACE")

        self._btn(card, "🖱  Select Image & Apply",
                  self._do_replace, "ACCENT").pack(anchor="w")

    def _do_replace(self):
        if not HAS_PIL:
            messagebox.showerror("Missing Dependency",
                "Pillow is required.\nRun: pip install Pillow")
            return
        img_path = filedialog.askopenfilename(title="Select Cursor Image",
                filetypes=[("Images", "*.png *.jpg *.jpeg")])
        if not img_path: return

        dest_dir = os.path.join(
            os.path.expandvars(r"%localappdata%\Pekora\Versions"),
            PEKORA_VERSION_HASH, PEKORA_2021M_FOLDER, PEKORA_TEXT_SUBPATH)

        if not os.path.exists(dest_dir):
            messagebox.showerror("Error", "Texture directory not found.")
            return
        try:
            img = Image.open(img_path).resize((64, 64), Image.Resampling.LANCZOS)
            img.save(os.path.join(dest_dir, "ArrowCursor.png"), "PNG")
            img.save(os.path.join(dest_dir, "ArrowFarCursor.png"), "PNG")
            messagebox.showinfo("Success", "Cursors replaced and resized to 64×64.")
        except Exception as e:
            messagebox.showerror("Error", str(e))


# ═════════════════════════════════════════════════════════════════════════════
#  THEMES PAGE
# ═════════════════════════════════════════════════════════════════════════════
class ThemesPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._build()

    def _build(self):
        T = self.app.theme
        self._title("Themes", "Choose a colour scheme — applies instantly")

        desc = tk.Label(self,
            text="  No restart needed. Your choice is saved automatically.",
            font=self.app.f_sm, fg=T.MUTED, bg=T.BG)
        desc.pack(anchor="w", padx=28, pady=(0, 14))
        self._tw(desc, fg="MUTED", bg="BG")

        self._grid = tk.Frame(self, bg=T.BG)
        self._grid.pack(fill=tk.BOTH, expand=True, padx=28, pady=(0, 20))
        self._tw(self._grid, bg="BG")

        self._draw_cards()
        # Redraw cards when theme changes so the active highlight updates
        self.app.theme.register(lambda p: self._redraw())

    def _draw_cards(self):
        T = self.app.theme
        for i, (name, pal) in enumerate(THEMES.items()):
            col = i % 3
            row = i // 3
            self._grid.columnconfigure(col, weight=1)

            active = (name == T.name)

            outer = tk.Frame(self._grid,
                             bg=T.ACCENT if active else pal["BORDER"],
                             padx=2, pady=2)
            outer.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")

            card = tk.Frame(outer, bg=pal["SURFACE"], padx=16, pady=14)
            card.pack(fill=tk.BOTH, expand=True)

            # colour swatches row
            sw = tk.Frame(card, bg=pal["SURFACE"])
            sw.pack(anchor="w", pady=(0, 10))
            for ck in ("ACCENT", "GREEN", "RED", "YELLOW"):
                swatch = tk.Frame(sw, bg=pal[ck], width=20, height=20)
                swatch.pack(side=tk.LEFT, padx=2)
                swatch.pack_propagate(False)

            name_lbl = tk.Label(card, text=name, font=self.app.f_lg,
                                fg=pal["TEXT"], bg=pal["SURFACE"])
            name_lbl.pack(anchor="w")

            tag_lbl = tk.Label(card,
                text="✓  Active" if active else "Click to apply",
                font=self.app.f_sm,
                fg=pal["ACCENT"] if active else pal["MUTED"],
                bg=pal["SURFACE"])
            tag_lbl.pack(anchor="w", pady=(4, 10))

            btn = tk.Button(card,
                text="Applied" if active else "Apply Theme",
                font=self.app.f_sm,
                bg=pal["ACCENT"] if active else pal["BORDER"],
                fg=pal["BG"] if active else pal["TEXT"],
                relief=tk.FLAT, bd=0, padx=14, pady=5, cursor="hand2",
                state=tk.DISABLED if active else tk.NORMAL,
                command=lambda n=name: self._pick(n))
            btn.pack(anchor="w")

    def _redraw(self):
        for w in self._grid.winfo_children():
            w.destroy()
        self._draw_cards()

    def _pick(self, name):
        self.app.theme.apply(name)
        self.app.refresh_nav()


# ═════════════════════════════════════════════════════════════════════════════
#  DEBUG PAGE
# ═════════════════════════════════════════════════════════════════════════════
class DebugPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._build()

    def _build(self):
        T = self.app.theme
        self._title("Debug", "System & installation diagnostics")

        brow = tk.Frame(self, bg=T.BG)
        brow.pack(fill=tk.X, padx=28, pady=(0, 10))
        self._tw(brow, bg="BG")
        self._btn(brow, "↻  Refresh", self.on_show, "ACCENT2").pack(side=tk.LEFT)

        lf, self.log = self._make_log(self, height=28)
        lf.pack(fill=tk.BOTH, expand=True, padx=28, pady=(0, 20))

    def on_show(self):
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)

        def w(msg, c="TEXT"): self._log(self.log, msg, c)
        si = get_system_info()

        w("── Version Roots ─────────────────────────────", "ACCENT")
        roots = get_version_roots()
        if roots:
            for root in roots:
                w(f"  ✓ {root}", "GREEN")
                for d in sorted(glob.glob(os.path.join(root, "*"))):
                    if os.path.isdir(d):
                        w(f"      {os.path.basename(d)}", "MUTED")
        else:
            w("  ✗ No installation roots found", "RED")

        w("\n── ClientSettings ────────────────────────────", "ACCENT")
        targets = get_clientsettings_targets()
        if targets:
            for cd, sp, folder in targets:
                w(f"  {folder}: {sp}", "MUTED")
                if os.path.exists(sp):
                    try:
                        s = json.load(open(sp))
                        w(f"    ✓ {len(s)} active flag(s)", "GREEN")
                    except:
                        w("    ✗ Could not parse", "RED")
                else:
                    w("    ✗ Not found", "RED")
        else:
            w("  ✗ No targets found", "RED")

        w("\n── Local FastFlags ────────────────────────────", "ACCENT")
        ff = load_fastflags()
        w(f"  {len(ff)} flag(s) in {FASTFLAGS_FILE}",
          "GREEN" if ff else "MUTED")

        w("\n── Bootstrapper ──────────────────────────────", "ACCENT")
        if os.path.exists(BOOTSTRAPPER_FILE):
            mb = os.path.getsize(BOOTSTRAPPER_FILE) / 1048576
            w(f"  ✓ {BOOTSTRAPPER_FILE}  ({mb:.1f} MB)", "GREEN")
        else:
            w(f"  ✗ {BOOTSTRAPPER_FILE} not found", "RED")

        w("\n── Active Theme ──────────────────────────────", "ACCENT")
        w(f"  {self.app.theme.name}", "YELLOW")

        w("\n── System ────────────────────────────────────", "ACCENT")
        w(f"  OS:      {platform.system()} {platform.release()}")
        w(f"  Arch:    {platform.machine()}")
        w(f"  Python:  {sys.version.split()[0]}")
        if si["is_linux"]:
            try:
                for line in open("/etc/os-release"):
                    if line.startswith("PRETTY_NAME="):
                        w(f"  Distro:  {line.split('=')[1].strip().strip(chr(34))}")
                        break
            except: pass


# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = KoroneStrap()
    app.mainloop()
