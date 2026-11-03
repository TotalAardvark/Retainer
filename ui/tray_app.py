import sys
import time
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
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint, QRect, QObject, QEvent
from PyQt6.QtGui import QColor, QCursor, QKeySequence, QShortcut

from core.config import load_config
from core.youtube import extract_video_id
from core.reader import is_youtube_url, is_valid_url
from core.pipeline import run_pipeline
from ui.assets import get_brain_icon, get_processing_icon
from ui.settings_dialog import SettingsDialog


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


class QuickCapturePalette(QWidget):
    """
    Spotlight/Raycast-style quick-capture palette centered in the upper screen.
    Floating frameless card with drop shadow, accent highlights, and Escape dismissal.
    """
    generate_requested = pyqtSignal(str)
    settings_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    dismiss_requested = pyqtSignal()

    SHADOW_MARGIN = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(420 + (self.SHADOW_MARGIN * 2))
        self.init_ui()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(
            self.SHADOW_MARGIN,
            self.SHADOW_MARGIN,
            self.SHADOW_MARGIN,
            self.SHADOW_MARGIN,
        )
        root_layout.setSpacing(0)

        # Container card with rounded corners and border
        self.container = QFrame(self)
        self.container.setObjectName("containerCard")

        # Soft drop shadow
        shadow = QGraphicsDropShadowEffect(self.container)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 60))
        shadow.setOffset(0, 8)
        self.container.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(18, 16, 18, 14)
        layout.setSpacing(10)

        # Header / Title row
        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        
        title_label = QLabel("Retainer")
        title_label.setObjectName("appTitle")
        
        esc_hint = QLabel("esc to close")
        esc_hint.setObjectName("escHint")
        esc_hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        header_row.addWidget(title_label)
        header_row.addStretch(1)
        header_row.addWidget(esc_hint)
        layout.addLayout(header_row)

        # Row 1: URL input + Paste and Go button
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste YouTube or Article URL...")
        self.url_input.returnPressed.connect(self.on_generate_clicked)

        self.paste_btn = QPushButton("Paste & Go")
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

        # Bottom row: Settings and Quit
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        self.settings_btn = QPushButton("Settings...")
        self.settings_btn.setObjectName("menuRowBtn")
        self.settings_btn.clicked.connect(self.on_settings_clicked)
        bottom_row.addWidget(self.settings_btn)

        bottom_row.addStretch(1)

        self.quit_btn = QPushButton("Quit Retainer")
        self.quit_btn.setObjectName("menuRowBtn")
        self.quit_btn.clicked.connect(self.quit_requested.emit)
        bottom_row.addWidget(self.quit_btn)

        layout.addLayout(bottom_row)

        root_layout.addWidget(self.container)
        self.apply_theme()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.dismiss_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def apply_theme(self):
        dark = is_mac_dark_mode()
        accent, accent_hover = get_mac_accent_colors()

        if dark:
            bg_color = "rgba(36, 36, 40, 0.96)"
            border_color = "rgba(255, 255, 255, 0.14)"
            text_color = "#f2f2f7"
            hint_color = "rgba(255, 255, 255, 0.40)"
            input_bg = "rgba(24, 24, 27, 0.90)"
            input_border = "rgba(255, 255, 255, 0.18)"
            input_text = "#ffffff"
            sec_btn_bg = "rgba(255, 255, 255, 0.10)"
            sec_btn_border = "rgba(255, 255, 255, 0.14)"
            sec_btn_hover = "rgba(255, 255, 255, 0.16)"
            sec_btn_text = "#ffffff"
            divider_color = "rgba(255, 255, 255, 0.10)"
            row_text = "#c7c7cc"
            row_hover_bg = "rgba(255, 255, 255, 0.08)"
            row_hover_text = "#ffffff"
        else:
            bg_color = "rgba(255, 255, 255, 0.98)"
            border_color = "rgba(0, 0, 0, 0.12)"
            text_color = "#1c1c1e"
            hint_color = "rgba(0, 0, 0, 0.40)"
            input_bg = "#ffffff"
            input_border = "rgba(0, 0, 0, 0.16)"
            input_text = "#1c1c1e"
            sec_btn_bg = "rgba(0, 0, 0, 0.05)"
            sec_btn_border = "rgba(0, 0, 0, 0.10)"
            sec_btn_hover = "rgba(0, 0, 0, 0.09)"
            sec_btn_text = "#1c1c1e"
            divider_color = "rgba(0, 0, 0, 0.08)"
            row_text = "#48484a"
            row_hover_bg = "rgba(0, 0, 0, 0.06)"
            row_hover_text = "#1c1c1e"

        style = f"""
        QFrame#containerCard {{
            background-color: {bg_color};
            border: 1px solid {border_color};
            border-radius: 14px;
        }}
        QWidget {{
            color: {text_color};
            font-family: -apple-system, BlinkMacSystemFont, ".AppleSystemUIFont", "SF Pro Text", "SF Pro", "Helvetica Neue", sans-serif;
            font-size: 13px;
        }}
        QLabel#appTitle {{
            font-size: 13px;
            font-weight: 600;
            color: {text_color};
            letter-spacing: -0.2px;
        }}
        QLabel#escHint {{
            font-size: 11px;
            color: {hint_color};
            font-weight: 400;
        }}
        QLineEdit {{
            background-color: {input_bg};
            border: 1px solid {input_border};
            border-radius: 8px;
            padding: 7px 10px;
            color: {input_text};
            font-size: 13px;
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
            border-radius: 7px;
            padding: 7px 12px;
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
            border-radius: 8px;
            padding: 8px 16px;
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
            padding: 4px 8px;
            border-radius: 5px;
            color: {row_text};
            font-size: 12px;
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
        """Refreshes theme and fills clipboard URL if present."""
        self.apply_theme()
        clipboard = QApplication.clipboard().text().strip()
        if clipboard:
            self.url_input.setText(clipboard)
        self.url_input.setFocus()
        self.url_input.selectAll()

    def on_paste_and_go_clicked(self):
        text = QApplication.clipboard().text().strip()
        if text:
            self.url_input.setText(text)
            self.hide()
            self.generate_requested.emit(text)
            return
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


# Backward-compatibility alias
CompactPopover = QuickCapturePalette


class PaletteDismissFilter(QObject):
    """
    Global event filter that detects clicks outside the palette card
    or when another app takes focus, dismissing the palette immediately.
    """
    def __init__(self, app_instance):
        super().__init__()
        self.app_instance = app_instance
        self.shown_time = 0.0

    def mark_shown(self):
        self.shown_time = time.time()

    def eventFilter(self, obj, event):
        palette = self.app_instance.popover
        if not palette.isVisible():
            return super().eventFilter(obj, event)

        # 1. Direct mouse clicks inside Qt event system
        if event.type() == QEvent.Type.MouseButtonPress:
            pos = event.globalPosition().toPoint()
            card_top_left = palette.container.mapToGlobal(QPoint(0, 0))
            card_rect = QRect(card_top_left, palette.container.size())
            if not card_rect.contains(pos):
                self.app_instance.hide_popover()

        # 2. Window deactivation when clicking outside into another application
        elif event.type() == QEvent.Type.WindowDeactivate and obj == palette:
            if time.time() - self.shown_time > 0.3:
                pos = QCursor.pos()
                card_top_left = palette.container.mapToGlobal(QPoint(0, 0))
                card_rect = QRect(card_top_left, palette.container.size())
                if not card_rect.contains(pos):
                    self.app_instance.hide_popover()

        return super().eventFilter(obj, event)


class RetainerApp:
    def __init__(self):
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(get_brain_icon())
        self.tray_icon.setToolTip("Retainer - Quick Capture")

        self.popover = QuickCapturePalette()
        self.popover.generate_requested.connect(self.start_processing)
        self.popover.settings_requested.connect(self.open_settings)
        self.popover.quit_requested.connect(self.quit_app)
        self.popover.dismiss_requested.connect(self.hide_popover)

        self.tray_icon.activated.connect(self.on_tray_activated)
        self.worker: Optional[PipelineWorker] = None
        self.is_processing = False
        self.last_close_time = 0.0

        # Install click-outside dismiss monitor
        self.dismiss_filter = PaletteDismissFilter(self)
        QApplication.instance().installEventFilter(self.dismiss_filter)
        self.popover.installEventFilter(self.dismiss_filter)

    def quit_app(self):
        QApplication.instance().quit()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            now = time.time()
            if self.popover.isVisible():
                self.hide_popover()
            elif now - self.last_close_time < 0.35:
                # Caught toggle right around click outside
                pass
            else:
                self.show_popover()

    def hide_popover(self):
        if self.popover.isVisible():
            self.last_close_time = time.time()
            self.popover.hide()

    def show_popover(self):
        """Positions palette centered horizontally and in the upper quarter of the screen."""
        cursor_pos = QCursor.pos()
        screen = QApplication.screenAt(cursor_pos) or QApplication.primaryScreen()
        screen_geo = screen.availableGeometry()

        # Center horizontally
        x = screen_geo.x() + (screen_geo.width() - self.popover.width()) // 2
        # Position in top quarter (roughly 18% down from top edge)
        y = screen_geo.y() + int(screen_geo.height() * 0.18)

        self.dismiss_filter.mark_shown()
        self.popover.prepare_open()
        self.popover.move(QPoint(int(x), int(y)))
        self.popover.show()
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

        if "Transcript unavailable" in err_msg:
            notify_mac("Transcript Unavailable", "This video has no captions or transcripts enabled.")
        else:
            notify_mac("Error Processing Video", err_msg[:120])


# Backward-compatibility alias
YouTubeRetentionApp = RetainerApp
