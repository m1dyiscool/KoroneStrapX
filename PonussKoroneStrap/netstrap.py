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

# ── palette (PURPLE THEME) ───────────────────────────────────────────────────
BG      = "#0a0014" 
SURFACE = "#16002b" 
BORDER  = "#2d0052" 
ACCENT  = "#b366ff" 
ACCENT2 = "#8a2be2" 
TEXT    = "#f2e6ff" 
MUTED   = "#7d6a96" 
GREEN   = "#a64dff" 
RED     = "#ff4d4d" 
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

def get_version_roots():
    si = get_system_info()
    roots = []
    if si["is_windows"]:
        roots += [os.path.expandvars(r"%localappdata%\ProjectX\Versions"),
                  os.path.expandvars(r"%localappdata%\Pekora\Versions")]
    return list(set([p for p in roots if os.path.isdir(p)]))

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
    ok = False
    for cd, sp, folder in get_clientsettings_targets():
        try:
            os.makedirs(cd, exist_ok=True)
            with open(sp, "w") as f: json.dump(ff, f, indent=2)
            ok = True
        except: pass
    return ok

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
#  MAIN APPLICATION
# ═════════════════════════════════════════════════════════════════════════════
class KoroneStrap(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("KoroneStrap")
        self.geometry("880x700")
        self.configure(bg=BG)

        self.f_main = font.Font(family="Consolas", size=10)
        self.f_sm   = font.Font(family="Consolas", size=9)
        self.f_lg   = font.Font(family="Consolas", size=13, weight="bold")
        self.f_xl   = font.Font(family="Consolas", size=15, weight="bold")

        self._load_logo()
        self._apply_app_icon() # New call to apply the icon
        self._build_ui()

    def _load_logo(self):
        # Find the full path to the bundled logo image
        img_name = resource_path(LOGO_FILENAME)
        
        self.logo_img = None
        if os.path.exists(img_name) and HAS_PIL:
            try:
                img = Image.open(img_name)
                img = img.resize((120, 120), Image.Resampling.LANCZOS)
                self.logo_img = ImageTk.PhotoImage(img)
            except: pass

    def _apply_app_icon(self):
        # Set the icon for the application window
        # For Windows, we use a .ico file
        si = get_system_info()
        if si["is_windows"]:
            try:
                icon_path = resource_path(ICON_FILENAME)
                if os.path.exists(icon_path):
                    self.iconbitmap(icon_path)
            except Exception: pass

    def _build_ui(self):
        sidebar = tk.Frame(self, bg=SURFACE, width=200)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        logo_f = tk.Frame(sidebar, bg=SURFACE)
        logo_f.pack(fill=tk.X, pady=20)
        if self.logo_img:
            tk.Label(logo_f, image=self.logo_img, bg=SURFACE).pack()
        else:
            tk.Label(logo_f, text="KORONE", font=self.f_xl, fg=ACCENT, bg=SURFACE).pack()

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.pages = {}
        self._nav_btns = {}
        nav_items = [
            ("launch", "▶  Launch"),
            ("fastflags", "⚙  FastFlags"),
            ("bootstrap", "⬇  Bootstrapper"),
            ("editfont", "✎  Edit Font"),
            ("editcursor", "🖱  Edit Cursor"),
            ("debug", "🔍  Debug")
        ]

        for key, label in nav_items:
            btn = tk.Button(sidebar, text=label, font=self.f_main, anchor="w", padx=20,
                            bg=SURFACE, fg=MUTED, bd=0, relief=tk.FLAT, cursor="hand2",
                            activebackground=BORDER, activeforeground=TEXT,
                            command=lambda k=key: self.show(k))
            btn.pack(fill=tk.X, pady=2)
            self._nav_btns[key] = btn

        for name, cls in [("launch", LaunchPage), ("fastflags", FastFlagsPage), 
                          ("bootstrap", BootstrapPage), ("editfont", EditFontPage), 
                          ("editcursor", EditCursorPage), ("debug", DebugPage)]:
            p = cls(self.content, self)
            p.place(relwidth=1, relheight=1)
            self.pages[name] = p

        self.show("launch")

    def show(self, key):
        for k, b in self._nav_btns.items():
            b.configure(bg=BORDER if k==key else SURFACE, fg=ACCENT if k==key else MUTED)
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

    def _btn(self, parent, text, cmd, color=ACCENT, fg=BG, **kw):
        return tk.Button(parent, text=text, font=self.app.f_main, bg=color, fg=fg, 
                         relief=tk.FLAT, bd=0, padx=15, pady=6, cursor="hand2", command=cmd, **kw)

# ── LAUNCH PAGE ─────────────────────────────────────────────────────────────
class LaunchPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._build()
    def _build(self):
        self._title("Launch", "Choose your version")
        container = tk.Frame(self, bg=BG)
        container.pack(fill=tk.X, padx=24)
        for yr, folder in [("2020", PEKORA_2020L_FOLDER), ("2021", PEKORA_2021M_FOLDER)]:
            card = tk.Frame(container, bg=SURFACE, padx=20, pady=20)
            card.pack(side=tk.LEFT, padx=10, expand=True, fill=tk.X)
            tk.Label(card, text=f"Client {yr}", font=self.app.f_lg, fg=TEXT, bg=SURFACE).pack(anchor="w")
            self._btn(card, f"▶ Launch {yr}", lambda f=folder: self._launch(f)).pack(fill=tk.X, pady=(15,0))
    
    def _launch(self, folder):
        paths = get_executable_paths(folder)
        exe = next((p for p in paths if os.path.isfile(p)), None)
        if exe:
            apply_fastflags(load_fastflags())
            subprocess.Popen([exe, "--app"])
        else:
            messagebox.showerror("Error", f"Could not find executable for {folder}")

# ── EDIT FONT PAGE (2020 & 2021 SUPPORT) ────────────────────────────────────
class EditFontPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._target_ver = tk.StringVar(value=PEKORA_2021M_FOLDER)
        self._build()

    def _build(self):
        self._title("Edit Font", "Mirror replacement for .ttf and .otf")
        
        card = tk.Frame(self, bg=SURFACE, padx=20, pady=20)
        card.pack(fill=tk.X, padx=24)
        
        tk.Label(card, text="1. Select Version", font=self.app.f_lg, fg=ACCENT, bg=SURFACE).pack(anchor="w")
        
        # Version Toggle
        toggle_f = tk.Frame(card, bg=SURFACE)
        toggle_f.pack(anchor="w", pady=10)
        
        for text, val in [("2021 Client", PEKORA_2021M_FOLDER), ("2020 Client", PEKORA_2020L_FOLDER)]:
            tk.Radiobutton(toggle_f, text=text, variable=self._target_ver, value=val,
                           bg=SURFACE, fg=TEXT, selectcolor=BG, activebackground=SURFACE,
                           font=self.app.f_main, cursor="hand2").pack(side=tk.LEFT, padx=10)

        tk.Label(card, text="2. Mirror Overwrite", font=self.app.f_lg, fg=ACCENT, bg=SURFACE).pack(anchor="w", pady=(15, 0))
        tk.Label(card, text="This replaces every font inside the selected client's folder with your chosen font.", 
                 font=self.app.f_sm, fg=TEXT, bg=SURFACE, wraplength=550, justify="left").pack(anchor="w", pady=10)
        
        self._btn(card, "✎ Select Font & Overwrite", self._do_font_mirror).pack(pady=10)

    def _do_font_mirror(self):
        ft = filedialog.askopenfilename(title="Select Font", filetypes=[("Font Files", "*.ttf *.otf")])
        if not ft: return

        # Dynamic path based on selection
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
        card = tk.Frame(self, bg=SURFACE, padx=20, pady=20)
        card.pack(fill=tk.X, padx=24)
        tk.Label(card, text="Pekora Cursor Changer", font=self.app.f_lg, fg=ACCENT, bg=SURFACE).pack(anchor="w")
        tk.Label(card, text="Replaces ArrowCursor.png and ArrowFarCursor.png. Automatically resizes to 64x64.", 
                 font=self.app.f_sm, fg=TEXT, bg=SURFACE, wraplength=550, justify="left").pack(anchor="w", pady=10)
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
        style.configure("Treeview", background=SURFACE, foreground=TEXT, fieldbackground=SURFACE, borderwidth=0)
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
        if apply_fastflags(load_fastflags()): messagebox.showinfo("Success", "FastFlags applied.")

# ── BOOTSTRAP PAGE ──────────────────────────────────────────────────────────
class BootstrapPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._build()
    def _build(self):
        self._title("Bootstrapper", "Installer management")
        card = tk.Frame(self, bg=SURFACE, padx=20, pady=20)
        card.pack(fill=tk.X, padx=24)
        tk.Label(card, text="PekoraPlayerLauncher.exe", font=self.app.f_lg, fg=TEXT, bg=SURFACE).pack(anchor="w")
        btn_f = tk.Frame(card, bg=SURFACE); btn_f.pack(anchor="w", pady=10)
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
        f = tk.Frame(self, bg=SURFACE); f.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 20))
        self.txt = scrolledtext.ScrolledText(f, bg="#000", fg=GREEN, font=self.app.f_sm, bd=0)
        self.txt.pack(fill=tk.BOTH, expand=True)

    def on_show(self):
        self.txt.configure(state=tk.NORMAL); self.txt.delete("1.0", tk.END)
        info = [f"OS: {platform.platform()}", f"Python: {sys.version}", "\nRoots:"]
        for r in get_version_roots(): info.append(f" - {r}")
        self.txt.insert(tk.END, "\n".join(info))
        self.txt.configure(state=tk.DISABLED)

if __name__ == "__main__":
    app = KoroneStrap()
    app.mainloop()
