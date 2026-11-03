import sys
import time
import atexit
import ctypes
import ctypes.util
import subprocess
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication,
    QSystemTrayIcon,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QFrame,
    QLabel,
    QMessageBox,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint, QRect, QObject, QEvent, QTimer
from PyQt6.QtGui import QClipboard, QColor, QCursor

from core.config import load_config
from core.youtube import extract_video_id
from core.reader import is_youtube_url, is_valid_url
from core.pipeline import run_pipeline
from ui.assets import get_brain_icon, get_processing_icon
from ui.settings_dialog import SettingsDialog


def get_mac_menu_bar_autohide() -> bool:
    """Checks if macOS automatically hides the menu bar."""
    try:
        res = subprocess.run(
            ["osascript", "-e", 'tell application "System Events" to get autohide menu bar of dock preferences'],
            capture_output=True,
            text=True,
            check=False,
            timeout=1,
        )
        return res.stdout.strip().lower() == "true"
    except Exception:
        return False


def set_mac_menu_bar_autohide(enabled: bool):
    """Sets whether macOS automatically hides the menu bar."""
    val_str = "true" if enabled else "false"
    try:
        subprocess.run(
            ["osascript", "-e", f'tell application "System Events" to set autohide menu bar of dock preferences to {val_str}'],
            check=False,
            timeout=1,
        )
    except Exception:
        pass


# Keep reference to C callbacks to prevent garbage collection
_c_callbacks = []


def make_nswindow_status_popover(widget: QWidget):
    """
    Elevates the QWidget's underlying NSWindow to NSPopUpMenuWindowLevel (101),
    swizzles canBecomeKeyWindow and canBecomeMainWindow so macOS treats it as an
    active, key panel window, disables hide-on-deactivate, and activates the
    application so the auto-hiding macOS menu bar stays locked open.
    """
    try:
        win_id = int(widget.winId())
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.restype = ctypes.c_void_p

        msgSend_ptr = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
        objc_msgSend = msgSend_ptr(ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value)

        sel_window = objc.sel_registerName(b"window")
        nswindow = objc_msgSend(win_id, sel_window)
        if not nswindow:
            return

        # 1. Swizzle canBecomeKeyWindow and canBecomeMainWindow -> YES
        objc.object_getClass.restype = ctypes.c_void_p
        objc.object_getClass.argtypes = [ctypes.c_void_p]
        cls = objc.object_getClass(nswindow)

        BOOL_IMP = ctypes.CFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        c_yes = BOOL_IMP(lambda s, sel: True)
        _c_callbacks.append(c_yes)

        objc.class_replaceMethod.restype = ctypes.c_void_p
        objc.class_replaceMethod.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p]

        sel_canBecomeKey = objc.sel_registerName(b"canBecomeKeyWindow")
        objc.class_replaceMethod(cls, sel_canBecomeKey, ctypes.cast(c_yes, ctypes.c_void_p), b"c@:")

        sel_canBecomeMain = objc.sel_registerName(b"canBecomeMainWindow")
        objc.class_replaceMethod(cls, sel_canBecomeMain, ctypes.cast(c_yes, ctypes.c_void_p), b"c@:")

        # 2. NSPopUpMenuWindowLevel = 101 (menu bar level)
        sel_setLevel = objc.sel_registerName(b"setLevel:")
        msgSend_int = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_long)
        objc_msgSend_int = msgSend_int(ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value)
        objc_msgSend_int(nswindow, sel_setLevel, 101)

        # 3. Collection behavior: MoveToActiveSpace (2) | Transient (8)
        sel_setBehavior = objc.sel_registerName(b"setCollectionBehavior:")
        msgSend_ulong = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)
        objc_msgSend_ulong = msgSend_ulong(ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value)
        objc_msgSend_ulong(nswindow, sel_setBehavior, 2 | 8)

        # 4. setHidesOnDeactivate: NO
        msgSend_bool_arg = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool)
        objc_msgSend_setHides = msgSend_bool_arg(ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value)
        sel_setHides = objc.sel_registerName(b"setHidesOnDeactivate:")
        objc_msgSend_setHides(nswindow, sel_setHides, False)

        # 5. Activate app and make window key front
        NSApp = objc.objc_getClass(b"NSApplication")
        sel_shared = objc.sel_registerName(b"sharedApplication")
        app_ptr = objc_msgSend(NSApp, sel_shared)

        sel_activate = objc.sel_registerName(b"activateIgnoringOtherApps:")
        objc_msgSend_activate = msgSend_bool_arg(ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value)
        objc_msgSend_activate(app_ptr, sel_activate, True)

        sel_makeKey = objc.sel_registerName(b"makeKeyAndOrderFront:")
        msgSend_id = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
        objc_msgSend_id = msgSend_id(ctypes.cast(objc.objc_msgSend, ctypes.c_void_p).value)
        objc_msgSend_id(nswindow, sel_makeKey, None)
    except Exception:
        pass


def notify_mac(title: str, message: str):
    """Native macOS notification via AppleScript."""
    clean_title = title.replace('"', '\\"')
    clean_msg = message.replace('"', '\\"')
    script = f'display notification "{clean_msg}" with title "{clean_title}"'
    try:
        subprocess.run(["osascript", "-e", script], check=False)
    except Exception:
        pass


class PipelineWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    status_updated = pyqtSignal(str)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        try:
            result = run_pipeline(self.url, status_callback=self.status_updated.emit)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


def get_mac_accent_colors() -> tuple[str, str]:
    """Returns (regular_hex, hover_hex) for the user's macOS accent color."""
    color_map = {
        "-1": ("#8e8e93", "#98989d"),  # Graphite
        "0":  ("#e62e2d", "#ff453a"),  # Red
        "1":  ("#f27e18", "#ff922b"),  # Orange
        "2":  ("#e6ac00", "#ffd60a"),  # Yellow
        "3":  ("#28cd41", "#30d158"),  # Green
        "4":  ("#5856d6", "#7c7af2"),  # Purple
        "5":  ("#d62281", "#e84393"),  # Pink
        "6":  ("#007aff", "#0a84ff"),  # Blue / Multicolor
    }
    try:
        res = subprocess.run(
            ["defaults", "read", "-g", "AppleAccentColor"],
            capture_output=True,
            text=True,
            check=False,
        )
        val = res.stdout.strip()
    except Exception:
        val = "6"
    return color_map.get(val, ("#007aff", "#0a84ff"))


def is_mac_dark_mode() -> bool:
    """Returns True if macOS is in Dark Mode, False for Light Mode."""
    try:
        res = subprocess.run(
            ["defaults", "read", "-g", "AppleInterfaceStyle"],
            capture_output=True,
            text=True,
            check=False,
        )
        return res.stdout.strip().lower() == "dark"
    except Exception:
        return False


class CompactPopover(QWidget):
    """
    Native macOS style popover anchored beneath the menu bar icon.
    Supports Light & Dark modes, macOS system accent color, thin border,
    rounded corners, and exterior drop shadow.
    """
    generate_requested = pyqtSignal(str)
    settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()

    SHADOW_MARGIN = 14

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(340 + (self.SHADOW_MARGIN * 2))
        self.init_ui()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(self.SHADOW_MARGIN, self.SHADOW_MARGIN, self.SHADOW_MARGIN, self.SHADOW_MARGIN)
        root_layout.setSpacing(0)

        # Container card with rounded corners and border
        self.container = QFrame(self)
        self.container.setObjectName("containerCard")

        # Exterior drop shadow
        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 48))
        shadow.setOffset(0, 4)
        self.container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(14, 14, 14, 12)
        layout.setSpacing(8)

        # Row 1: URL input + Paste and Go button
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste URL")
        self.url_input.returnPressed.connect(self.on_generate_clicked)

        self.paste_btn = QPushButton("Paste and Go")
        self.paste_btn.setObjectName("secondaryBtn")
        self.paste_btn.setToolTip("Paste clipboard & automatically run if valid")
        self.paste_btn.clicked.connect(self.on_paste_and_go_clicked)

        row1.addWidget(self.url_input, stretch=1)
        row1.addWidget(self.paste_btn)
        layout.addLayout(row1)

        # Row 2: Action Button
        self.generate_btn = QPushButton("Generate Cards & Note")
        self.generate_btn.setObjectName("primaryBtn")
        self.generate_btn.clicked.connect(self.on_generate_clicked)
        layout.addWidget(self.generate_btn)

        # Divider
        divider = QFrame()
        divider.setObjectName("divider")
        divider.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(divider)

        # Row 3: Settings option
        self.settings_btn = QPushButton("Settings...")
        self.settings_btn.setObjectName("menuRowBtn")
        self.settings_btn.clicked.connect(self.on_settings_clicked)
        layout.addWidget(self.settings_btn)

        # Row 4: Quit option
        self.quit_btn = QPushButton("Quit Retainer")
        self.quit_btn.setObjectName("menuRowBtn")
        self.quit_btn.clicked.connect(self.quit_requested.emit)
        layout.addWidget(self.quit_btn)

        root_layout.addWidget(self.container)
        self.apply_theme()

    def apply_theme(self):
        dark = is_mac_dark_mode()
        accent, accent_hover = get_mac_accent_colors()

        if dark:
            # macOS dark control center palette
            bg_color = "rgba(42, 42, 46, 0.95)"
            border_color = "rgba(255, 255, 255, 0.12)"
            text_color = "#f2f2f7"
            input_bg = "rgba(25, 25, 28, 0.85)"
            input_border = "rgba(255, 255, 255, 0.16)"
            input_text = "#ffffff"
            sec_btn_bg = "rgba(255, 255, 255, 0.10)"
            sec_btn_border = "rgba(255, 255, 255, 0.14)"
            sec_btn_hover = "rgba(255, 255, 255, 0.16)"
            sec_btn_text = "#ffffff"
            divider_color = "rgba(255, 255, 255, 0.10)"
            row_text = "#e5e5ea"
            row_hover_bg = accent
            row_hover_text = "#ffffff"
        else:
            # macOS light control center palette
            bg_color = "rgba(252, 250, 247, 0.96)"
            border_color = "rgba(0, 0, 0, 0.11)"
            text_color = "#1c1c1e"
            input_bg = "#ffffff"
            input_border = "rgba(0, 0, 0, 0.14)"
            input_text = "#1c1c1e"
            sec_btn_bg = "rgba(0, 0, 0, 0.05)"
            sec_btn_border = "rgba(0, 0, 0, 0.10)"
            sec_btn_hover = "rgba(0, 0, 0, 0.09)"
            sec_btn_text = "#1c1c1e"
            divider_color = "rgba(0, 0, 0, 0.08)"
            row_text = "#2c2c2e"
            row_hover_bg = accent
            row_hover_text = "#ffffff"

        style = f"""
        QFrame#containerCard {{
            background-color: {bg_color};
            border: 1px solid {border_color};
            border-radius: 12px;
        }}
        QWidget {{
            color: {text_color};
            font-family: -apple-system, BlinkMacSystemFont, ".AppleSystemUIFont", "SF Pro Text", "SF Pro", "Helvetica Neue", sans-serif;
            font-size: 13px;
        }}
        QLineEdit {{
            background-color: {input_bg};
            border: 1px solid {input_border};
            border-radius: 6px;
            padding: 5px 8px;
            color: {input_text};
            selection-background-color: {accent};
        }}
        QLineEdit:focus {{
            border: 1.5px solid {accent};
        }}
        QPushButton {{
            font-family: -apple-system, BlinkMacSystemFont, ".AppleSystemUIFont", "SF Pro Text", "SF Pro", "Helvetica Neue", sans-serif;
        }}
        QPushButton#secondaryBtn {{
            background-color: {sec_btn_bg};
            border: 1px solid {sec_btn_border};
            border-radius: 6px;
            padding: 5px 11px;
            color: {sec_btn_text};
            font-weight: 500;
            font-size: 12px;
        }}
        QPushButton#secondaryBtn:hover {{
            background-color: {sec_btn_hover};
        }}
        QPushButton#primaryBtn {{
            background-color: {accent};
            border: none;
            border-radius: 7px;
            padding: 7px 14px;
            color: #ffffff;
            font-weight: 600;
            font-size: 13px;
        }}
        QPushButton#primaryBtn:hover {{
            background-color: {accent_hover};
        }}
        QPushButton#primaryBtn:pressed {{
            background-color: {accent};
        }}
        QPushButton#menuRowBtn {{
            background-color: transparent;
            border: none;
            text-align: left;
            padding: 5px 8px;
            border-radius: 5px;
            color: {row_text};
            font-size: 13px;
            font-weight: 400;
        }}
        QPushButton#menuRowBtn:hover {{
            background-color: {row_hover_bg};
            color: {row_hover_text};
        }}
        QFrame#divider {{
            background-color: {divider_color};
            max-height: 1px;
            border: none;
            margin: 2px 0px;
        }}
        """
        self.setStyleSheet(style)

    def prepare_open(self):
        """Called before popover is shown: auto-fills if clipboard has any text and refreshes theme."""
        self.apply_theme()
        clipboard = QApplication.clipboard().text().strip()
        if clipboard:
            self.url_input.setText(clipboard)
        self.url_input.setFocus()
        self.url_input.selectAll()

    def on_paste_and_go_clicked(self):
        """Paste & Go: reads clipboard and triggers generation immediately if not empty."""
        text = QApplication.clipboard().text().strip()
        if text:
            self.url_input.setText(text)
            self.hide()
            self.generate_requested.emit(text)
            return
        # If clipboard is empty, keep popover open and select input
        self.url_input.setFocus()

    def on_generate_clicked(self):
        url = self.url_input.text().strip()
        if not url:
            return
        self.hide()
        self.generate_requested.emit(url)

    def on_settings_clicked(self):
        self.hide()
        self.settings_requested.emit()


class PopoverDismissFilter(QObject):
    """
    Global event filter that detects clicks outside the popover card,
    as well as window deactivation (focus lost to another application),
    and dismisses the popover immediately.
    """
    def __init__(self, app_instance):
        super().__init__()
        self.app_instance = app_instance
        self.shown_time = 0.0

    def mark_shown(self):
        self.shown_time = time.time()

    def eventFilter(self, obj, event):
        pop = self.app_instance.popover
        if not pop.isVisible():
            return super().eventFilter(obj, event)

        # 1. Direct mouse clicks inside Qt event system
        if event.type() == QEvent.Type.MouseButtonPress:
            pos = event.globalPosition().toPoint()
            card_top_left = pop.container.mapToGlobal(QPoint(0, 0))
            card_rect = QRect(card_top_left, pop.container.size())
            if not card_rect.contains(pos):
                self.app_instance.hide_popover()

        # 2. Window deactivation when clicking outside into another application
        elif event.type() == QEvent.Type.WindowDeactivate and obj == pop:
            if time.time() - self.shown_time > 0.4:
                pos = QCursor.pos()
                card_top_left = pop.container.mapToGlobal(QPoint(0, 0))
                card_rect = QRect(card_top_left, pop.container.size())
                if not card_rect.contains(pos):
                    self.app_instance.hide_popover()

        return super().eventFilter(obj, event)


class RetainerApp:
    def __init__(self):
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(get_brain_icon())
        self.tray_icon.setToolTip("Retainer - YouTube Spaced Repetition")

        self.popover = CompactPopover()
        self.popover.generate_requested.connect(self.start_processing)
        self.popover.settings_requested.connect(self.open_settings)
        self.popover.quit_requested.connect(self.quit_app)

        self.tray_icon.activated.connect(self.on_tray_activated)
        self.worker: Optional[PipelineWorker] = None
        self.is_processing = False
        self.last_close_time = 0.0

        # Keep menu bar open while Retainer is running
        self._user_had_autohide = get_mac_menu_bar_autohide()
        if self._user_had_autohide:
            set_mac_menu_bar_autohide(False)
        atexit.register(self.restore_menu_bar)
        QApplication.instance().aboutToQuit.connect(self.restore_menu_bar)

        # Install click-outside dismiss monitor
        self.dismiss_filter = PopoverDismissFilter(self)
        QApplication.instance().installEventFilter(self.dismiss_filter)
        self.popover.installEventFilter(self.dismiss_filter)

    def restore_menu_bar(self):
        """Restores user's autohide menu bar preference on exit."""
        if getattr(self, "_user_had_autohide", False):
            self._user_had_autohide = False
            set_mac_menu_bar_autohide(True)

    def quit_app(self):
        self.restore_menu_bar()
        QApplication.instance().quit()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            now = time.time()
            # If clicked icon while open, or just closed within 350ms by clicking the icon, toggle close
            if self.popover.isVisible():
                self.hide_popover()
            elif now - self.last_close_time < 0.35:
                # The click-outside filter just caught this click on the tray icon; keep it closed
                pass
            else:
                self.show_popover()

    def hide_popover(self):
        if self.popover.isVisible():
            self.last_close_time = time.time()
            self.popover.hide()

    def show_popover(self):
        # Position directly beneath the status bar item
        geometry = self.tray_icon.geometry()
        # Fallback to cursor position if tray geometry isn't reported by OS
        if geometry.width() <= 0 or geometry.x() <= 0:
            cursor_pos = QCursor.pos()
            x = cursor_pos.x() - (self.popover.width() // 2)
            y = 26
        else:
            x = geometry.x() + (geometry.width() // 2) - (self.popover.width() // 2)
            y = geometry.y() + geometry.height() - (CompactPopover.SHADOW_MARGIN // 2)

        # Keep on-screen
        screen = QApplication.primaryScreen().availableGeometry()
        if x + self.popover.width() > screen.right():
            x = screen.right() - self.popover.width() - 10
        if x < screen.left():
            x = screen.left() + 10

        self.dismiss_filter.mark_shown()
        self.popover.prepare_open()
        self.popover.move(QPoint(int(x), int(y)))
        self.popover.show()
        make_nswindow_status_popover(self.popover)
        self.popover.raise_()
        self.popover.activateWindow()

    def open_settings(self):
        dialog = SettingsDialog()
        dialog.exec()

    def start_processing(self, url: str):
        if self.is_processing:
            notify_mac("Processing Busy", "Another item is currently being processed.")
            return

        config = load_config()
        # Ensure minimum configuration before running
        if not config.get("gemini_api_key"):
            notify_mac("Configuration Needed", "Please configure your Gemini API Key in Settings.")
            self.open_settings()
            return

        if not config.get("obsidian_vault"):
            notify_mac("Configuration Needed", "Please select your Obsidian Vault in Settings.")
            self.open_settings()
            return

        self.is_processing = True
        self.tray_icon.setIcon(get_processing_icon())
        item_type = "video" if (is_youtube_url(url) or extract_video_id(url)) else "article"
        notify_mac("Retainer", f"Analyzing {item_type} content...")

        self.worker = PipelineWorker(url)
        self.worker.finished.connect(self.on_success)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_success(self, result: dict):
        self.is_processing = False
        self.tray_icon.setIcon(get_brain_icon())

        title = result.get("title", "Video")
        card_count = result.get("card_count", 0)
        anki_status = result.get("anki_status", "skipped")

        msg = f"Saved to Obsidian/Retainer!"
        if "pushed" in anki_status:
            msg += f" + {card_count} cards added to Anki."
        elif "unreachable" in anki_status:
            msg += " (AnkiConnect not running, cards skipped)."

        notify_mac(f"Done: {title[:35]}", msg)

    def on_error(self, err_msg: str):
        self.is_processing = False
        self.tray_icon.setIcon(get_brain_icon())

        # Clean display for missing captions
        if "Transcript unavailable" in err_msg:
            notify_mac("Transcript Unavailable", "This video has no captions or transcripts enabled.")
        else:
            notify_mac("Error Processing Video", err_msg[:120])


# Backward-compatibility alias
YouTubeRetentionApp = RetainerApp
