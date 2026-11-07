"""Foscount visual theme.

Light, clean "biotech" look: white surfaces, deep aubergine as the primary
colour, lavender tints, muted purple accents, Space Grotesk for headings and
Inter for body text (falls back to the system sans-serif when not installed).
Put .ttf files in ``foscount/assets/fonts`` to bundle the fonts.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QFontDatabase, QIcon, QPainter,
                           QPen, QPixmap)
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout, QWidget

# ---- palette ---------------------------------------------------------------
PRIMARY = "#2E1D3F"        # deep aubergine
PRIMARY_HOVER = "#45305C"
MUTED = "#9683A8"          # muted purple
LAVENDER = "#E6E6FA"
LAVENDER_SOFT = "#F5F5FD"  # lavender tint on white
SURFACE = "#FFFFFF"
INK = "#111827"            # headings
TEXT = "#374151"           # body
TEXT_SOFT = "#6B7280"
BORDER = "#E5E3EC"
INPUT_BORDER = "#D1D5DB"
VIVID = "#7C3AED"          # bright purple accent (counting squares)
LIVE = "#16A34A"
DEAD = "#DC2626"
WARN = "#B45309"

HEADING_FAMILIES = ["Space Grotesk", "Inter", "Segoe UI", "Helvetica Neue", "Arial"]
BODY_FAMILIES = ["Inter", "Segoe UI", "Helvetica Neue", "Arial"]


def _css_families(fams: list[str]) -> str:
    return ", ".join(f'"{f}"' for f in fams) + ", sans-serif"


HEADING_CSS = _css_families(HEADING_FAMILIES)
BODY_CSS = _css_families(BODY_FAMILIES)


def load_fonts() -> None:
    d = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts")
    if os.path.isdir(d):
        for f in os.listdir(d):
            if f.lower().endswith((".ttf", ".otf")):
                QFontDatabase.addApplicationFont(os.path.join(d, f))


def heading_font(px: int, weight: QFont.Weight = QFont.Weight.Bold) -> QFont:
    f = QFont()
    f.setFamilies(HEADING_FAMILIES)
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


def eyebrow_font() -> QFont:
    """Small uppercase, widely spaced caption ("THE PROBLEM" style)."""
    f = QFont()
    f.setFamilies(BODY_FAMILIES)
    f.setPixelSize(11)
    f.setWeight(QFont.Weight.DemiBold)
    f.setCapitalization(QFont.Capitalization.AllUppercase)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.8)
    return f


STYLESHEET = f"""
QWidget {{ color: {TEXT}; }}
QLabel#headline {{ color: {PRIMARY}; }}
QMainWindow, QDialog, QWidget#central {{ background: {SURFACE}; }}
QWidget#sidePanel, QScrollArea#sideScroll, QWidget#sideInner {{ background: {LAVENDER_SOFT}; }}
QScrollArea {{ border: none; }}

/* header */
QWidget#header {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}
QLabel#pill {{
    background: {LAVENDER}; color: {PRIMARY}; border-radius: 11px;
    padding: 3px 12px; font-weight: 500; font-size: 12px;
}}

/* cards */
QFrame#card {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 10px;
}}
QLabel#eyebrow {{ color: {PRIMARY}; }}
QLabel#hint {{ color: {TEXT_SOFT}; font-size: 12px; }}

/* buttons */
QPushButton {{
    background: {SURFACE}; color: {PRIMARY}; border: 1px solid {PRIMARY};
    border-radius: 6px; padding: 7px 14px; font-weight: 500;
}}
QPushButton:hover {{ background: {LAVENDER_SOFT}; }}
QPushButton:pressed {{ background: {LAVENDER}; }}
QPushButton:disabled {{ color: #A8A2B3; border-color: #CFCAD8; }}
QPushButton[variant="primary"] {{
    background: {PRIMARY}; color: white; border: 1px solid {PRIMARY};
}}
QPushButton[variant="primary"]:hover {{ background: {PRIMARY_HOVER}; }}
QPushButton[variant="ghost"] {{ border: none; background: transparent; }}
QPushButton[variant="ghost"]:hover {{ background: {LAVENDER}; }}

/* segmented toggle (EN / FR style) */
QFrame#segment {{ border: 1px solid {INPUT_BORDER}; border-radius: 6px; background: {SURFACE}; }}
QFrame#segment QPushButton {{
    border: none; border-radius: 5px; padding: 6px 14px; color: {PRIMARY}; background: transparent;
}}
QFrame#segment QPushButton:checked {{ background: {PRIMARY}; color: white; }}

/* inputs */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {SURFACE}; border: 1px solid {INPUT_BORDER}; border-radius: 6px;
    padding: 5px 8px; min-height: 18px; selection-background-color: {MUTED};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border: 1px solid {PRIMARY};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QAbstractSpinBox {{ padding-right: 22px; }}
QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
    subcontrol-origin: border; width: 20px; border: none; background: transparent;
}}
QAbstractSpinBox::up-button {{ subcontrol-position: top right; }}
QAbstractSpinBox::down-button {{ subcontrol-position: bottom right; }}
QAbstractSpinBox::up-arrow, QAbstractSpinBox::down-arrow {{ width: 7px; height: 7px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE}; border: 1px solid {BORDER};
    selection-background-color: {LAVENDER}; selection-color: {PRIMARY};
}}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border: 1px solid {INPUT_BORDER}; border-radius: 4px; background: white;
}}
QCheckBox::indicator:checked {{ background: {PRIMARY}; border-color: {PRIMARY}; }}

/* sliders */
QSlider::groove:horizontal {{ height: 4px; background: {LAVENDER}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {MUTED}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    background: {PRIMARY}; width: 14px; height: 14px; margin: -6px 0; border-radius: 7px;
}}
QSlider::handle:horizontal:disabled {{ background: #CFCAD8; }}

/* tabs: underline style */
QTabWidget::pane {{ border: none; border-top: 1px solid {BORDER}; }}
QTabBar::tab {{
    background: transparent; padding: 9px 16px; margin-right: 4px; color: {TEXT_SOFT};
    border-bottom: 2px solid transparent; font-weight: 500;
}}
QTabBar::tab:selected {{ color: {PRIMARY}; border-bottom: 2px solid {PRIMARY}; }}
QTabBar::tab:hover {{ color: {PRIMARY}; }}

/* lists & tables */
QListWidget, QTableWidget {{
    background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 8px;
    gridline-color: {BORDER}; outline: none;
}}
QListWidget::item {{ padding: 8px 8px; border-radius: 6px; }}
QListWidget::item:selected, QTableWidget::item:selected {{ background: {LAVENDER}; color: {PRIMARY}; }}
QHeaderView::section {{
    background: {LAVENDER_SOFT}; color: {PRIMARY}; border: none;
    border-bottom: 1px solid {BORDER}; padding: 6px; font-weight: 600;
}}

QMenuBar {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}
QMenuBar::item {{ padding: 6px 10px; background: transparent; }}
QMenuBar::item:selected {{ background: {LAVENDER}; color: {PRIMARY}; border-radius: 4px; }}
QMenu {{ background: {SURFACE}; border: 1px solid {BORDER}; padding: 4px; }}
QMenu::item {{ padding: 6px 22px; border-radius: 4px; }}
QMenu::item:selected {{ background: {LAVENDER}; color: {PRIMARY}; }}
QStatusBar {{ background: {SURFACE}; color: {TEXT_SOFT}; border-top: 1px solid {BORDER}; }}
QSplitter::handle {{ background: {BORDER}; }}
QProgressBar {{
    border: 1px solid {BORDER}; border-radius: 6px; background: {LAVENDER_SOFT};
    text-align: center; height: 16px;
}}
QProgressBar::chunk {{ background: {PRIMARY}; border-radius: 5px; }}
QToolTip {{ background: {PRIMARY}; color: white; border: none; padding: 6px; }}
QScrollBar:vertical {{ width: 10px; background: transparent; }}
QScrollBar::handle:vertical {{ background: #D6D2E0; border-radius: 5px; min-height: 30px; }}
QScrollBar:horizontal {{ height: 10px; background: transparent; }}
QScrollBar::handle:horizontal {{ background: #D6D2E0; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
"""


def apply(app: QApplication) -> None:
    load_fonts()
    app.setStyle("Fusion")
    f = QFont()
    f.setFamilies(BODY_FAMILIES)
    f.setPixelSize(13)
    app.setFont(f)
    app.setStyleSheet(STYLESHEET)
    app.setWindowIcon(app_icon())


def card(title: str) -> tuple[QFrame, QVBoxLayout]:
    """A white rounded card with an uppercase, letter-spaced caption."""
    fr = QFrame()
    fr.setObjectName("card")
    lay = QVBoxLayout(fr)
    lay.setContentsMargins(14, 12, 14, 14)
    lay.setSpacing(8)
    cap = QLabel(title)
    cap.setObjectName("eyebrow")
    cap.setFont(eyebrow_font())
    lay.addWidget(cap)
    return fr, lay


def wordmark() -> QLabel:
    lab = QLabel(f"<span style='color:{PRIMARY}'>Fos</span>"
                 f"<span style='color:{MUTED}'>count</span>")
    lab.setFont(heading_font(22))
    lab.setTextFormat(Qt.TextFormat.RichText)
    return lab


def pill(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setObjectName("pill")
    return lab


def app_icon() -> QIcon:
    """Purple cell-with-dots mark, drawn at runtime (no image files needed)."""
    pm = QPixmap(128, 128)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor(PRIMARY)))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(4, 4, 120, 120), 28, 28)
    p.setPen(QPen(QColor(LAVENDER), 7))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(64, 64), 36, 36)
    p.setPen(Qt.PenStyle.NoPen)
    for (x, y, r, c) in [(64, 64, 11, VIVID), (48, 50, 6, LAVENDER), (82, 54, 5, MUTED),
                         (56, 84, 5, LAVENDER), (82, 80, 7, VIVID)]:
        p.setBrush(QBrush(QColor(c)))
        p.drawEllipse(QPointF(x, y), r, r)
    p.end()
    return QIcon(pm)


class Header(QWidget):
    """Top bar: wordmark + pills on the left, extra widgets on the right."""

    def __init__(self, right_widgets: list[QWidget] = (), parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QHBoxLayout
        self.setObjectName("header")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 10, 16, 10)
        lay.setSpacing(10)
        lay.addWidget(wordmark())
        lay.addSpacing(8)
        lay.addWidget(pill("Bürker chamber"))
        lay.addWidget(pill("Cell counting"))
        lay.addStretch(1)
        for w in right_widgets:
            lay.addWidget(w)
