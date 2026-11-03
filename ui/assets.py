"""Generates clean vector SVG icons for the macOS Menu Bar."""
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import QByteArray, QSize, Qt
from PyQt6.QtSvg import QSvgRenderer

import os
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QImage
from PyQt6.QtCore import QByteArray, QRectF, Qt
from PyQt6.QtSvg import QSvgRenderer

PROCESSING_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <line x1="12" y1="2" x2="12" y2="6"/>
  <line x1="12" y1="18" x2="12" y2="22"/>
  <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/>
  <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/>
  <line x1="2" y1="12" x2="6" y2="12"/>
  <line x1="18" y1="12" x2="22" y2="12"/>
  <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"/>
  <line x1="16.24" y1="7.76" x2="19.07" y2="4.93"/>
</svg>"""


def get_brain_icon(size: int = 22) -> QIcon:
    """
    Create an optically balanced, crisp macOS menu bar template icon
    from the reference brain silhouette.
    """
    asset_path = os.path.join(os.path.dirname(__file__), "assets", "brain_template.png")
    if os.path.exists(asset_path):
        ref_img = QImage(asset_path)
    else:
        ref_img = QImage("brain_reference.png")

    # Target canvas: size x size pt (rendered at 2x Retina resolution: (size*2) x (size*2))
    canvas_size = size * 2
    canvas = QImage(canvas_size, canvas_size, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    # In standard macOS menu bar (22pt / 44px @2x):
    # Standard icon glyph height is 15-16pt (~30-32px @2x).
    # Brain aspect ratio is ~1.21:1 -> 36px wide by 30px high.
    # Vertically: center is 22px; shifting up by 2-3px aligns with macOS system icons.
    glyph_w = 36.0
    glyph_h = 30.0
    x_pos = (canvas_size - glyph_w) / 2.0
    y_pos = (canvas_size - glyph_h) / 2.0 - 2.5

    painter.drawImage(QRectF(x_pos, y_pos, glyph_w, glyph_h), ref_img)
    painter.end()

    pixmap = QPixmap.fromImage(canvas)
    pixmap.setDevicePixelRatio(2.0)

    icon = QIcon(pixmap)
    icon.setIsMask(True)  # macOS template icon (automatically adapts to light/dark menu bar)
    return icon


def get_processing_icon(color_hex: str = "#007AFF", size: int = 22) -> QIcon:
    """Create processing indicator icon."""
    svg_data = PROCESSING_SVG.replace('stroke="currentColor"', f'stroke="{color_hex}"')
    renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))

    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    pixmap.setDevicePixelRatio(2.0)

    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()

    return QIcon(pixmap)
