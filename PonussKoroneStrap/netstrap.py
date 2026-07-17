import os
import sys
import json
import time
import platform
import glob
import shutil
import subprocess
import threading
import urllib.request
import urllib.error

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QFont, QIcon, QPixmap, QImage
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFrame, QProgressBar, QStackedWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QRadioButton, QButtonGroup, QPlainTextEdit, QFileDialog,
    QMessageBox, QInputDialog, QAbstractItemView,
)

# ── constants ────────────────────────────────────────────────────────────────
FASTFLAGS_FILE = "fastFlags.json"
CUSTOM_ROOTS_FILE = "customRoots.json"
BOOTSTRAPPER_URL = "https://setup.pekora.zip/PekoraPlayerLauncher.exe"
BOOTSTRAPPER_FILE = "PekoraPlayerLauncher.exe"

# ── Pekora Target Constants ──────────────────────────────────────────────────
PEKORA_VERSION_HASH = "version-cde8fee1a1e747d4"
PEKORA_2020L_FOLDER = "2020L"
PEKORA_2021M_FOLDER = "2021M"
PEKORA_FONTS_SUBPATH = os.path.join("content", "fonts")
PEKORA_TEXT_SUBPATH = os.path.join("content", "textures")

# Files to manage as bundled resources
LOGO_FILENAME = "../486334643-c0477fe6-8ed3-48dc-9404-ff9463d542ca.jpg"
ICON_FILENAME = "../icon.ico"

# ── palette (DARK NEUTRAL THEME) ─────────────────────────────────────────────
BG = "#121212"
SURFACE = "#1a1a1a"
CARD = "#1f1f1f"
BORDER = "#2a2a2a"
ACCENT = "#f5c518"
ACCENT2 = "#d4af0f"
TEXT = "#eaeaea"
MUTED = "#8a8a8a"
GREEN = "#3ddc84"
RED = "#ff5c5c"
YELLOW = "#ffd633"


# ── Helper to find bundled resources ─────────────────────────────────────────
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


# ── platform helpers ─────────────────────────────────────────────────────────
def get_system_info():
    s = platform.system().lower()
    return {"is_windows": s == "windows", "is_linux": s == "linux", "system_name": s}


def load_custom_roots():
    if not os.path.exists(CUSTOM_ROOTS_FILE):
        return []
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
        candidates += [
            os.path.expandvars(r"%localappdata%\ProjectX\Versions"),
            os.path.expandvars(r"%localappdata%\Pekora\Versions"),
            os.path.expandvars(r"%appdata%\ProjectX\Versions"),
            os.path.expandvars(r"%appdata%\Pekora\Versions"),
            os.path.expandvars(r"%ProgramFiles%\Pekora\Versions"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Pekora\Versions"),
        ]
    candidates += load_custom_roots()

    candidates = list(dict.fromkeys(candidates))
    existing = [p for p in candidates if p and os.path.isdir(p)]
    if include_missing:
        return existing, candidates
    return existing


def iter_version_dirs():
    for root in get_version_roots():
        for d in sorted(glob.glob(os.path.join(root, "*"))):
            if os.path.isdir(d):
                yield d


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
    if not os.path.exists(FASTFLAGS_FILE):
        return {}
    try:
        with open(FASTFLAGS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_fastflags(ff):
    with open(FASTFLAGS_FILE, "w") as f:
        json.dump(ff, f, indent=2)


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
            with open(sp, "w") as f:
                json.dump(ff, f, indent=2)
            ok = True
        except Exception as e:
            errors.append(f"{folder}: {e}")
    return ok, errors


def auto_detect_value_type(s):
    s = s.strip()
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    try:
        if "." not in s:
            return int(s)
    except Exception:
        pass
    try:
        return float(s)
    except Exception:
        pass
    return s


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION (minimalist "bootstrapper" style — logo / status / progress)
# ═════════════════════════════════════════════════════════════════════════════
class KoroneStrap(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KoroneStrap X")
        self.setFixedSize(420, 480)
        self.setStyleSheet(f"background-color: {BG};")

        self.f_main = QFont("Segoe UI", 10)
        self.f_sm = QFont("Segoe UI", 9)
        self.f_lg = QFont("Segoe UI", 13, QFont.Bold)
        self.f_xl = QFont("Segoe UI", 17, QFont.Bold)

        self.selected_version = PEKORA_2021M_FOLDER
        self.settings_window = None

        self._load_logo()
        self._apply_app_icon()
        self._build_ui()

    def _load_logo(self):
        img_path = resource_path(LOGO_FILENAME)
        self.logo_pix = None
        if os.path.exists(img_path):
            pix = QPixmap(img_path)
            if not pix.isNull():
                self.logo_pix = pix.scaled(88, 88, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def _apply_app_icon(self):
        si = get_system_info()
        if si["is_windows"]:
            icon_path = resource_path(ICON_FILENAME)
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 8)

        top = QHBoxLayout()
        top.addStretch()
        gear = QPushButton("⚙")
        gear.setFlat(True)
        gear.setCursor(Qt.PointingHandCursor)
        gear.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {MUTED}; border: none; font-size: 16px; }}"
            f"QPushButton:hover {{ color: {ACCENT}; }}"
        )
        gear.clicked.connect(self.open_settings)
        top.addWidget(gear)
        outer.addLayout(top)

        center = QVBoxLayout()
        center.setAlignment(Qt.AlignHCenter)
        outer.addLayout(center, 1)

        logo_lbl = QLabel()
        logo_lbl.setAlignment(Qt.AlignCenter)
        if self.logo_pix:
            logo_lbl.setPixmap(self.logo_pix)
        else:
            logo_lbl.setText("◆")
            logo_lbl.setStyleSheet(f"color: {ACCENT}; font-size: 40px;")
        center.addWidget(logo_lbl, alignment=Qt.AlignHCenter)
        center.addSpacing(10)

        title_lbl = QLabel("KoroneStrap X")
        title_lbl.setFont(self.f_xl)
        title_lbl.setStyleSheet(f"color: {TEXT};")
        title_lbl.setAlignment(Qt.AlignCenter)
        center.addWidget(title_lbl)

        subtitle_lbl = QLabel("Pekora Bootstrapper")
        subtitle_lbl.setFont(self.f_sm)
        subtitle_lbl.setStyleSheet(f"color: {MUTED};")
        subtitle_lbl.setAlignment(Qt.AlignCenter)
        center.addWidget(subtitle_lbl)
        center.addSpacing(25)

        seg = QHBoxLayout()
        seg.setSpacing(1)
        self._seg_btns = {}
        for label, val in [("2021", PEKORA_2021M_FOLDER), ("2020", PEKORA_2020L_FOLDER)]:
            b = QPushButton(label)
            b.setFont(self.f_main)
            b.setCursor(Qt.PointingHandCursor)
            b.setFlat(True)
            b.clicked.connect(lambda checked=False, v=val: self._select_version(v))
            seg.addWidget(b)
            self._seg_btns[val] = b
        center.addLayout(seg)
        center.addSpacing(20)
        self._select_version(self.selected_version)

        self.status_lbl = QLabel("Готово к запуску")
        self.status_lbl.setFont(self.f_sm)
        self.status_lbl.setStyleSheet(f"color: {MUTED};")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        center.addWidget(self.status_lbl)
        center.addSpacing(8)

        self.progress = QProgressBar()
        self.progress.setFixedWidth(280)
        self.progress.setFixedHeight(8)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setStyleSheet(
            f"QProgressBar {{ background-color: {SURFACE}; border: none; border-radius: 3px; }}"
            f"QProgressBar::chunk {{ background-color: {ACCENT}; border-radius: 3px; }}"
        )
        center.addWidget(self.progress, alignment=Qt.AlignHCenter)
        center.addSpacing(20)

        self.play_btn = QPushButton("▶  ИГРАТЬ/PLAY")
        self.play_btn.setFont(self.f_lg)
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.setStyleSheet(
            f"QPushButton {{ background-color: {ACCENT}; color: #000000; border: none;"
            f" padding: 10px 20px; border-radius: 4px; }}"
            f"QPushButton:hover {{ background-color: {ACCENT2}; }}"
            f"QPushButton:disabled {{ background-color: {BORDER}; color: {MUTED}; }}"
        )
        self.play_btn.clicked.connect(self._launch)
        center.addWidget(self.play_btn, alignment=Qt.AlignHCenter)

        version_lbl = QLabel("v1.0")
        version_lbl.setStyleSheet(f"color: {BORDER}; font-size: 8pt;")
        version_lbl.setAlignment(Qt.AlignCenter)
        outer.addWidget(version_lbl)

    def _select_version(self, val):
        self.selected_version = val
        for v, b in self._seg_btns.items():
            active = (v == val)
            bg = ACCENT if active else BG
            fg = "#000000" if active else ACCENT
            b.setStyleSheet(
                f"QPushButton {{ background-color: {bg}; color: {fg};"
                f" border: 1px solid {BORDER}; padding: 6px 28px; }}"
            )

    def _set_status(self, text):
        self.status_lbl.setText(text)
        QApplication.processEvents()

    def _launch(self):
        folder = self.selected_version
        paths = get_executable_paths(folder)
        exe = next((p for p in paths if os.path.isfile(p)), None)
        if not exe:
            QMessageBox.critical(
                self, "Error",
                f"Не найден исполняемый файл для {folder}.\n"
                "Проверь путь установки во вкладке Debug (⚙ → Debug).",
            )
            return

        self.play_btn.setEnabled(False)
        self.progress.setValue(0)
        self._set_status("Применение FastFlags...")
        for i in range(0, 60, 15):
            self.progress.setValue(i)
            QApplication.processEvents()
            time.sleep(0.02)

        ok, errors = apply_fastflags(load_fastflags())
        if not ok and errors:
            QMessageBox.warning(self, "FastFlags не применились", "\n".join(errors))

        self._set_status("Запуск клиента...")
        for i in range(60, 101, 10):
            self.progress.setValue(i)
            QApplication.processEvents()
            time.sleep(0.015)

        try:
            subprocess.Popen([exe, "--app"])
            self._set_status("Готово")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self._set_status("Ошибка запуска")

        self.play_btn.setEnabled(True)

        def _reset():
            self._set_status("Готово к запуску")
            self.progress.setValue(0)

        # Qt has no direct equivalent of tk's self.after(ms, cb) on a plain
        # QWidget without importing QTimer separately for one-shot use, so
        # this stays inline rather than adding another import for one call.
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, _reset)

    def open_settings(self):
        if self.settings_window is not None and self.settings_window.isVisible():
            self.settings_window.raise_()
            self.settings_window.activateWindow()
            return
        self.settings_window = SettingsWindow(self)
        self.settings_window.show()


# ── SETTINGS WINDOW (sidebar with the advanced pages) ────────────────────────
class SettingsWindow(QWidget):
    def __init__(self, root_app):
        super().__init__(None, Qt.Window)
        self.root_app = root_app
        self.f_main = root_app.f_main
        self.f_sm = root_app.f_sm
        self.f_lg = root_app.f_lg
        self.f_xl = root_app.f_xl

        self.setWindowTitle("KoroneStrap — Settings")
        self.resize(760, 560)
        self.setMinimumSize(640, 480)
        self.setStyleSheet(f"background-color: {BG};")

        self._build_ui()

    def _build_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setFixedWidth(180)
        sidebar.setStyleSheet(f"background-color: {SURFACE};")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 0)
        sidebar_layout.setSpacing(2)
        sidebar_layout.setAlignment(Qt.AlignTop)

        heading = QLabel("НАСТРОЙКИ")
        heading.setFont(self.f_sm)
        heading.setStyleSheet(f"color: {MUTED}; padding-left: 20px; padding-bottom: 10px;")
        sidebar_layout.addWidget(heading)

        self.stack = QStackedWidget()

        self.pages = {}
        self._nav_btns = {}
        nav_items = [
            ("fastflags", "⚙  FastFlags", FastFlagsPage),
            ("bootstrap", "⬇  Bootstrapper", BootstrapPage),
            ("editfont", "✎  Edit Font", EditFontPage),
            ("editcursor", "🖱  Edit Cursor", EditCursorPage),
            ("debug", "🔍  Debug", DebugPage),
        ]

        for key, label, cls in nav_items:
            btn = QPushButton(label)
            btn.setFont(self.f_main)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFlat(True)
            btn.setStyleSheet(self._nav_btn_style(active=False))
            btn.clicked.connect(lambda checked=False, k=key: self.show_page(k))
            sidebar_layout.addWidget(btn)
            self._nav_btns[key] = btn

            page = cls(self.stack, self)
            self.stack.addWidget(page)
            self.pages[key] = page

        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.stack, 1)

        self.show_page("fastflags")

    def _nav_btn_style(self, active):
        bg = ACCENT if active else BG
        fg = "#000000" if active else ACCENT
        hover_bg = ACCENT if active else BORDER
        hover_fg = "#000000" if active else TEXT
        return (
            f"QPushButton {{ background-color: {bg}; color: {fg}; text-align: left;"
            f" padding: 10px 20px; border: none; }}"
            f"QPushButton:hover {{ background-color: {hover_bg}; color: {hover_fg}; }}"
        )

    def show_page(self, key):
        for k, b in self._nav_btns.items():
            b.setStyleSheet(self._nav_btn_style(active=(k == key)))
        self.stack.setCurrentWidget(self.pages[key])
        self.pages[key].on_show()


# ── BASE PAGE ───────────────────────────────────────────────────────────────
class BasePage(QWidget):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.setStyleSheet(f"background-color: {BG};")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 20, 24, 20)
        self._layout.setAlignment(Qt.AlignTop)

    def on_show(self):
        pass

    def _title(self, txt, sub=""):
        title_lbl = QLabel(txt)
        title_lbl.setFont(self.app.f_xl)
        title_lbl.setStyleSheet(f"color: {TEXT};")
        self._layout.addWidget(title_lbl)
        if sub:
            sub_lbl = QLabel(sub)
            sub_lbl.setFont(self.app.f_sm)
            sub_lbl.setStyleSheet(f"color: {MUTED};")
            self._layout.addWidget(sub_lbl)
        self._layout.addSpacing(8)
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {BORDER}; border: none;")
        self._layout.addWidget(line)
        self._layout.addSpacing(20)

    def _card(self):
        card = QFrame()
        card.setStyleSheet(f"background-color: {CARD};")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        self._layout.addWidget(card)
        return card, card_layout

    def _btn(self, text, cmd, color=ACCENT, fg="#000000"):
        b = QPushButton(text)
        b.setFont(self.app.f_main)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(
            f"QPushButton {{ background-color: {color}; color: {fg}; border: none;"
            f" padding: 8px 15px; border-radius: 4px; }}"
            f"QPushButton:hover {{ background-color: {color}; }}"
        )
        b.clicked.connect(cmd)
        return b


# ── EDIT FONT PAGE (2020 & 2021 SUPPORT) ────────────────────────────────────
class EditFontPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._target_ver = PEKORA_2021M_FOLDER
        self._build()

    def _build(self):
        self._title("Edit Font", "Mirror replacement for .ttf and .otf")
        card, card_layout = self._card()

        step1 = QLabel("1. Select Version")
        step1.setFont(self.app.f_lg)
        step1.setStyleSheet(f"color: {ACCENT};")
        card_layout.addWidget(step1)

        toggle_row = QHBoxLayout()
        for text, val in [("2021 Client", PEKORA_2021M_FOLDER), ("2020 Client", PEKORA_2020L_FOLDER)]:
            rb = QRadioButton(text)
            rb.setFont(self.app.f_main)
            rb.setStyleSheet(f"color: {TEXT};")
            rb.setCursor(Qt.PointingHandCursor)
            if val == self._target_ver:
                rb.setChecked(True)
            rb.toggled.connect(lambda checked, v=val: self._on_version_toggled(checked, v))
            toggle_row.addWidget(rb)
        toggle_row.addStretch()
        card_layout.addLayout(toggle_row)

        step2 = QLabel("2. Mirror Overwrite")
        step2.setFont(self.app.f_lg)
        step2.setStyleSheet(f"color: {ACCENT}; margin-top: 15px;")
        card_layout.addWidget(step2)

        desc = QLabel("This replaces every font inside the selected client's folder with your chosen font.")
        desc.setFont(self.app.f_sm)
        desc.setStyleSheet(f"color: {TEXT};")
        desc.setWordWrap(True)
        card_layout.addWidget(desc)

        card_layout.addWidget(
            self._btn("✎ Select Font & Overwrite", self._do_font_mirror), 0, Qt.AlignLeft
        )

    def _on_version_toggled(self, checked, val):
        if checked:
            self._target_ver = val

    def _do_font_mirror(self):
        ft, _ = QFileDialog.getOpenFileName(self, "Select Font", "", "Font Files (*.ttf *.otf)")
        if not ft:
            return

        dest_dir = os.path.join(
            os.path.expandvars(r"%localappdata%\Pekora\Versions"),
            PEKORA_VERSION_HASH, self._target_ver, PEKORA_FONTS_SUBPATH,
        )

        if not os.path.exists(dest_dir):
            QMessageBox.critical(
                self, "Error",
                f"Folder not found: {self._target_ver}\nPlease run that client once first.",
            )
            return

        reply = QMessageBox.question(
            self, "Confirm Mirror", f"Replace all fonts in {self._target_ver}?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            count = 0
            for filename in os.listdir(dest_dir):
                if filename.lower().endswith((".ttf", ".otf")):
                    shutil.copy2(ft, os.path.join(dest_dir, filename))
                    count += 1
            QMessageBox.information(self, "Success", f"Done! Replaced {count} font files in {self._target_ver}.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed: {e}")


# ── EDIT CURSOR PAGE (64x64 REPLACEMENT) ────────────────────────────────────
class EditCursorPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._build()

    def _build(self):
        self._title("Edit Cursor", "Replace game cursors")
        card, card_layout = self._card()

        header = QLabel("Pekora Cursor Changer")
        header.setFont(self.app.f_lg)
        header.setStyleSheet(f"color: {ACCENT};")
        card_layout.addWidget(header)

        desc = QLabel("Replaces ArrowCursor.png and ArrowFarCursor.png. Automatically resizes to 64x64.")
        desc.setFont(self.app.f_sm)
        desc.setStyleSheet(f"color: {TEXT};")
        desc.setWordWrap(True)
        card_layout.addWidget(desc)

        card_layout.addWidget(
            self._btn("🖱 Select & Apply Cursor", self._do_cursor_replace), 0, Qt.AlignLeft
        )

    def _do_cursor_replace(self):
        img_path, _ = QFileDialog.getOpenFileName(
            self, "Select Cursor Image", "", "Images (*.png *.jpg *.jpeg)"
        )
        if not img_path:
            return

        dest_dir = os.path.join(
            os.path.expandvars(r"%localappdata%\Pekora\Versions"),
            PEKORA_VERSION_HASH, PEKORA_2021M_FOLDER, PEKORA_TEXT_SUBPATH,
        )
        if not os.path.exists(dest_dir):
            QMessageBox.critical(self, "Error", "Texture directory not found.")
            return

        try:
            img = QImage(img_path)
            if img.isNull():
                raise ValueError("Не удалось загрузить изображение")
            # Qt handles the resize natively — no Pillow dependency needed.
            resized = img.scaled(64, 64, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            resized.save(os.path.join(dest_dir, "ArrowCursor.png"), "PNG")
            resized.save(os.path.join(dest_dir, "ArrowFarCursor.png"), "PNG")
            QMessageBox.information(self, "Success", "Cursors replaced and resized.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


# ── FASTFLAGS PAGE ──────────────────────────────────────────────────────────
class FastFlagsPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._build()

    def _build(self):
        self._title("FastFlags", "Manage Client Settings")

        bar = QHBoxLayout()
        bar.addWidget(self._btn("+ Add", self._add, GREEN))
        bar.addWidget(self._btn("− Remove", self._remove, RED))
        bar.addStretch()
        bar.addWidget(self._btn("▶ Apply", self._apply, ACCENT))
        self._layout.addLayout(bar)
        self._layout.addSpacing(10)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Flag Key", "Value"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(
            f"QTableWidget {{ background-color: {CARD}; color: {TEXT};"
            f" gridline-color: {BORDER}; border: none; }}"
            f"QHeaderView::section {{ background-color: {SURFACE}; color: {MUTED};"
            f" border: none; padding: 4px; }}"
            f"QTableWidget::item:selected {{ background-color: {BORDER}; }}"
        )
        self._layout.addWidget(self.table)
        self._refresh()

    def _refresh(self):
        self.table.setRowCount(0)
        ff = load_fastflags()
        for k, v in ff.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(k)))
            self.table.setItem(row, 1, QTableWidgetItem(str(v)))

    def _add(self):
        k, ok1 = QInputDialog.getText(self, "Add", "Flag Name:")
        if not ok1 or not k:
            return
        v, ok2 = QInputDialog.getText(self, "Add", "Value:")
        if not ok2 or not v:
            return
        ff = load_fastflags()
        ff[k] = auto_detect_value_type(v)
        save_fastflags(ff)
        self._refresh()

    def _remove(self):
        sel = self.table.selectionModel().selectedRows()
        if sel:
            row = sel[0].row()
            k = self.table.item(row, 0).text()
            ff = load_fastflags()
            ff.pop(k, None)
            save_fastflags(ff)
            self._refresh()

    def _apply(self):
        ok, errors = apply_fastflags(load_fastflags())
        if ok:
            QMessageBox.information(self, "Success", "FastFlags applied.")
        else:
            QMessageBox.critical(self, "Не применилось", "\n".join(errors) if errors else "Неизвестная ошибка.")


# ── BOOTSTRAP PAGE ──────────────────────────────────────────────────────────
class _DownloadSignals(QObject):
    finished = Signal(bool, str)


class BootstrapPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        # Qt UI calls (message boxes) must happen on the GUI thread. The
        # download itself runs on a worker thread; this signal is how the
        # worker safely hands the result back to the GUI thread instead of
        # calling QMessageBox directly from a background thread.
        self._signals = _DownloadSignals()
        self._signals.finished.connect(self._on_download_done)
        self._build()

    def _build(self):
        self._title("Bootstrapper", "Installer management")
        card, card_layout = self._card()

        header = QLabel("PekoraPlayerLauncher.exe")
        header.setFont(self.app.f_lg)
        header.setStyleSheet(f"color: {TEXT};")
        card_layout.addWidget(header)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self._btn("⬇ Download", self._dl))
        btn_row.addWidget(self._btn("▶ Run", self._run, color=GREEN))
        btn_row.addStretch()
        card_layout.addLayout(btn_row)

    def _dl(self):
        def task():
            try:
                urllib.request.urlretrieve(BOOTSTRAPPER_URL, BOOTSTRAPPER_FILE)
                self._signals.finished.emit(True, "Bootstrapper downloaded.")
            except Exception as e:
                self._signals.finished.emit(False, str(e))

        threading.Thread(target=task, daemon=True).start()

    def _on_download_done(self, ok, msg):
        if ok:
            QMessageBox.information(self, "Success", msg)
        else:
            QMessageBox.critical(self, "Error", msg)

    def _run(self):
        if os.path.exists(BOOTSTRAPPER_FILE):
            subprocess.Popen([BOOTSTRAPPER_FILE])
        else:
            QMessageBox.critical(self, "Error", "Bootstrapper not found.")


# ── DEBUG PAGE ──────────────────────────────────────────────────────────────
class DebugPage(BasePage):
    def __init__(self, parent, app):
        super().__init__(parent, app)
        self._build()

    def _build(self):
        self._title("Debug", "System diagnostics")

        bar = QHBoxLayout()
        bar.addWidget(self._btn("+ Add Custom Root", self._add_custom_root, GREEN))
        bar.addWidget(self._btn("↻ Refresh", self.on_show))
        bar.addStretch()
        self._layout.addLayout(bar)
        self._layout.addSpacing(10)

        self.txt = QPlainTextEdit()
        self.txt.setReadOnly(True)
        self.txt.setFont(self.app.f_sm)
        self.txt.setStyleSheet(f"background-color: #000000; color: {GREEN}; border: none;")
        self._layout.addWidget(self.txt)

    def _add_custom_root(self):
        path = QFileDialog.getExistingDirectory(
            self, "Выбери папку 'Versions' (например ...\\Pekora\\Versions)"
        )
        if not path:
            return
        roots = load_custom_roots()
        if path not in roots:
            roots.append(path)
            if save_custom_roots(roots):
                QMessageBox.information(self, "Готово", f"Добавлено: {path}")
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось сохранить customRoots.json")
        self.on_show()

    def on_show(self):
        found, checked = get_version_roots(include_missing=True)
        info = [f"OS: {platform.platform()}", f"Python: {sys.version}", "", "Checked paths:"]
        for p in checked:
            mark = "✓" if p in found else "✗"
            info.append(f" [{mark}] {p}")
        info.append(f"\nCustom roots (customRoots.json): {load_custom_roots() or 'none'}")
        targets = get_clientsettings_targets()
        info.append(f"\nClientSettings targets found: {len(targets)}")
        for cd, sp, folder in targets:
            info.append(f" - {folder}: {sp}")
        self.txt.setPlainText("\n".join(info))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KoroneStrap()
    window.show()
    sys.exit(app.exec())
