"""회색 바탕과 채도를 낮춘 슬레이트 블루로 작업 영역과 상태를 구분한다."""

import os
import re

from PySide6.QtGui import QColor, QPalette


CANVAS = "#F3F5F7"
SURFACE = "#FAFBFC"
SIDEBAR = "#EEF1F4"
TEXT = "#293440"
MUTED = "#5C6978"
ACCENT = "#526F93"
ACCENT_HOVER = "#435F80"
SELECTION = "#E5EBF1"
SELECTION_TEXT = "#435F80"
DISABLED_TEXT = "#929DAA"
BORDER = "#D8DFE6"
BADGE_SURFACE = "#E3EAF0"
BADGE_TEXT = "#48627F"
OUTPUT_SURFACE = "#EDF1F5"
CARD_SURFACE = "#F0F3F6"
HOVER_BORDER = "#A3B3C3"
DROP_SURFACE = "#E2E9F0"
DROP_BORDER = "#A7B7C8"
ON_ACCENT = "#FFFFFF"
TOOLTIP_SURFACE = TEXT
TOOLTIP_TEXT = SURFACE
BASE_FONT_SIZE = 13
CARD_TITLE_SIZE = 13
CARD_DETAIL_SIZE = 11
CARD_LABEL_SIZE = 12
CARD_BADGE_SIZE = 11
FONT_FAMILIES = ("Segoe UI", "Malgun Gothic")
TEXT_WEIGHT = 400
EMPHASIS_WEIGHT = 500


def application_palette() -> QPalette:
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: CANVAS,
        QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: SURFACE,
        QPalette.ColorRole.AlternateBase: OUTPUT_SURFACE,
        QPalette.ColorRole.Text: TEXT,
        QPalette.ColorRole.Button: SURFACE,
        QPalette.ColorRole.ButtonText: TEXT,
        QPalette.ColorRole.Highlight: SELECTION,
        QPalette.ColorRole.HighlightedText: SELECTION_TEXT,
        QPalette.ColorRole.ToolTipBase: TOOLTIP_SURFACE,
        QPalette.ColorRole.ToolTipText: TOOLTIP_TEXT,
        QPalette.ColorRole.Link: ACCENT,
        QPalette.ColorRole.LinkVisited: ACCENT_HOVER,
        QPalette.ColorRole.PlaceholderText: MUTED,
        QPalette.ColorRole.Light: SURFACE,
        QPalette.ColorRole.Midlight: OUTPUT_SURFACE,
        QPalette.ColorRole.Mid: BORDER,
        QPalette.ColorRole.Dark: DISABLED_TEXT,
        QPalette.ColorRole.Shadow: MUTED,
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(DISABLED_TEXT))
    return palette


APP_STYLESHEET = """
QMainWindow, QWidget { color: #293440; font-family: 'Segoe UI', '맑은 고딕'; font-size: 13px; }
QMainWindow, QWidget#appShell { background: #F3F5F7; }
QSplitter#workspaceShell, QWidget#workspace { background: #F3F5F7; border: none; }
QWidget#slidePanel { background: #FAFBFC; border-top-left-radius: 10px; }
QWidget#outputPanel { background: #EDF1F5; border-left: 1px solid #D8DFE6; border-top-right-radius: 10px; }
QFrame#sourcePanel, QFrame#originalsPanel { background: #EEF1F4; border: none; }
QWidget#outputFooter { background: #F3F5F7; }
QToolBar { background: #F3F5F7; border: none; padding: 10px 20px; spacing: 6px; }
QToolBar::separator { background: #D8DFE6; width: 1px; margin: 6px 12px; }
QLabel#appBrand { color: #48627F; font-size: 18px; font-weight: 700; padding: 0 8px 0 0; }
QToolButton { padding: 7px; border: 1px solid transparent; border-radius: 6px; background: transparent; }
QToolButton:hover { background: #E5EAF0; }
QToolButton:pressed { background: #DCE3EB; }
QToolButton:focus { border-color: #526F93; }
QToolButton#searchToggle:checked { background: #E5EBF1; color: #435F80; }
QToolButton:disabled { color: #929DAA; background: transparent; border-color: transparent; }
QToolButton::menu-indicator { image: none; width: 0; height: 0; }
QLabel#sectionTitle { color: #293440; font-size: 18px; font-weight: 600; }
QLabel#subsectionTitle { color: #536476; font-size: 13px; font-weight: 500; }
QLabel#mutedText, QLabel#rootPath, QLabel#statusText { color: #5C6978; font-size: 12px; }
QLabel#emptyState { color: #5C6978; padding: 24px; font-size: 13px; }
QLabel#notice { background: #FFF4DB; color: #795A21; padding: 12px 16px; border-radius: 6px; }
QListWidget#sourceList { border: none; background: #EEF1F4; outline: none; }
QListWidget#sourceList::item { padding: 12px 10px; border: 1px solid transparent; border-radius: 6px; }
QListWidget#sourceList::item:hover { background: #E5EBF1; }
QListWidget#sourceList::item:selected { background: #DFE7EF; color: #435F80; }
QListWidget#sourceList:focus::item:selected { border-color: #A7B7C8; }
QListView#slideView { border: none; background: #FAFBFC; outline: none; }
QListView#outputView { border: none; background: #EDF1F5; outline: none; }
QWidget#outputPanel QLabel#sectionTitle { color: #48627F; }
QWidget#outputPanel QPushButton#quietButton { background: #E3E9EF; color: #536A84; }
QWidget#outputPanel QPushButton#quietButton:hover { background: #D9E2EB; }
QWidget#outputPanel QPushButton#quietButton:disabled { background: #E9EDF1; color: #929DAA; }
QWidget#outputPanel QToolButton:hover { background: #DFE6ED; }
QWidget#outputPanel QComboBox#viewModeCombo { background: #E3E9EF; color: #536A84; }
QWidget#outputPanel QComboBox#viewModeCombo:hover { background: #D9E2EB; }
QWidget#outputPanel QSlider::groove:horizontal { background: #D7E0E8; }
QWidget#outputPanel QSlider::sub-page:horizontal { background: #8A9FB6; }
QWidget#outputPanel QSlider::handle:horizontal { border-color: #A3B3C3; }
QStatusBar { background: #F3F5F7; border: none; padding: 2px 16px; }
QStatusBar::item { border: none; }
QProgressBar { background: #E1E7ED; color: #293440; border: none; border-radius: 4px; height: 16px; text-align: center; }
QProgressBar::chunk { background: #526F93; border-radius: 4px; }
QPushButton { background: #FAFBFC; border: 1px solid #D4DCE4; border-radius: 6px; padding: 7px 12px; }
QPushButton:hover { background: #F0F3F6; border-color: #AFBDCB; }
QPushButton:pressed { background: #DFE6ED; }
QPushButton:focus { border-color: #526F93; }
QPushButton:disabled { background: #F0F3F6; color: #929DAA; border-color: #E3E8ED; }
QPushButton#primaryButton { background: #526F93; color: #FFFFFF; border: 1px solid #526F93; font-weight: 600; padding: 7px 18px; }
QPushButton#primaryButton:hover { background: #435F80; border-color: #435F80; }
QPushButton#primaryButton:pressed { background: #374F6D; border-color: #374F6D; }
QPushButton#primaryButton:focus { border-color: #526F93; }
QPushButton#primaryButton:disabled { background: #DFE7EF; color: #929DAA; border-color: #DFE7EF; }
QPushButton#addSlidesButton { background: #E5EBF1; color: #435F80; border-color: transparent; font-weight: 500; }
QPushButton#addSlidesButton:hover { background: #DAE3EC; }
QPushButton#addSlidesButton:pressed { background: #CFDAE5; }
QPushButton#addSlidesButton:focus { border-color: #526F93; }
QPushButton#addSlidesButton:disabled { background: #EBEFF3; color: #929DAA; border-color: transparent; }
QPushButton#resultAction { color: #48627F; background: #FAFBFC; font-weight: 500; }
QPushButton#resultAction:hover { background: #E3EAF0; }
QPushButton#resultAction:focus { border-color: #526F93; }
QPushButton#quietButton { background: #F3F5F7; border-color: transparent; color: #536476; }
QPushButton#quietButton:hover { background: #E6EBF0; color: #293440; }
QPushButton#quietButton:focus { border-color: #526F93; }
QPushButton#quietButton:disabled { color: #929DAA; background: #F3F5F7; border-color: transparent; }
QLineEdit, QComboBox { background: #FAFBFC; border: 1px solid #D4DCE4; border-radius: 6px; padding: 7px 10px; selection-background-color: #E5EBF1; selection-color: #435F80; }
QLineEdit:hover, QComboBox:hover { border-color: #AFBDCB; }
QLineEdit:focus, QComboBox:focus { border-color: #526F93; background: #FAFBFC; }
QLineEdit#slideSearch { background: #F0F3F6; border-color: transparent; padding: 0 8px; }
QLineEdit#slideSearch:hover { background: #E9EEF3; }
QLineEdit#slideSearch:focus { background: #FAFBFC; border-color: #526F93; }
QLineEdit:disabled { color: #929DAA; background: #F3F5F7; }
QComboBox { padding-right: 26px; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow { image: none; }
QComboBox#viewModeCombo { background: #F3F5F7; border-color: transparent; }
QComboBox#viewModeCombo:hover { background: #E6EBF0; }
QComboBox#viewModeCombo:focus { border-color: #526F93; }
QTreeView, QListWidget#fileSearchResults { background: #EEF1F4; border: none; outline: none; }
QTreeView::item, QListWidget#fileSearchResults::item { padding: 6px; border-radius: 5px; }
QTreeView::item:hover, QListWidget#fileSearchResults::item:hover { background: #E5EBF1; }
QTreeView::item:selected, QListWidget#fileSearchResults::item:selected { background: #DFE7EF; color: #293440; }
QSplitter::handle { background: transparent; border: none; }
QSplitter::handle:hover { background: #A3B3C3; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #C1CCD6; border-radius: 3px; min-height: 28px; margin: 1px 2px; }
QScrollBar::handle:horizontal { background: #C1CCD6; border-radius: 3px; min-width: 28px; margin: 2px 1px; }
QScrollBar::handle:hover { background: #9EAFBF; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QMenu { background: #FAFBFC; border: 1px solid #D8DFE6; padding: 5px; }
QMenu::item { padding: 8px 18px; border-radius: 5px; }
QMenu::item:selected { background: #E5EBF1; color: #293440; }
QMenu::item:disabled { color: #929DAA; }
QMenu::separator { height: 1px; background: #D8DFE6; margin: 4px 8px; }
QToolTip { color: #FFFFFF; background: #293440; border: none; padding: 6px 8px; }
QDialog, QMessageBox { background: #F3F5F7; }
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab { color: #5C6978; background: transparent; padding: 9px 8px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #293440; font-weight: 500; border-bottom: 2px solid #526F93; }
QTabBar::tab:hover { color: #293440; }
QWidget#modeSwitch { background: #E6EBF0; border: 1px solid #D7E0E8; border-radius: 8px; }
QPushButton#viewModeButton { background: transparent; border: 1px solid transparent; border-radius: 5px; color: #5C6978; padding: 5px 12px; }
QPushButton#viewModeButton:hover { color: #293440; background: #DAE3EC; }
QPushButton#viewModeButton:checked { background: #FAFBFC; color: #435F80; border-color: #BCCAD8; font-weight: 500; }
QPushButton#viewModeButton:focus { border-color: #526F93; }
QSlider::groove:horizontal { height: 3px; background: #D7E0E8; border-radius: 1px; }
QSlider::sub-page:horizontal { background: #8A9FB6; border-radius: 1px; }
QSlider::handle:horizontal { width: 10px; margin: -4px 0; border: 1px solid #A3B3C3; border-radius: 5px; background: #FAFBFC; }
QSlider::handle:horizontal:hover { border-color: #526F93; }
QSlider:focus { border: 1px solid #526F93; border-radius: 3px; }
"""


# 모듈을 읽는 시점에 선택해 아이콘과 직접 그리는 카드도 같은 팔레트를 사용한다.
ACTIVE_THEME = os.environ.get("PPT_MERGE_THEME", "slate-blue")
if ACTIVE_THEME == "gruvbox-material":
    from src.ui.gruvbox_material import COLOR_MAP, TOKENS

    globals().update(TOKENS)
    APP_STYLESHEET = re.sub(r"#[0-9A-Fa-f]{6}",
                            lambda match: COLOR_MAP[match[0].upper()], APP_STYLESHEET)
    APP_STYLESHEET += """
QMainWindow, QWidget { font-family: 'Pretendard GOV', 'Malgun Gothic', 'Segoe UI'; font-size: 14px; font-weight: 500; }
QLabel#mutedText, QLabel#rootPath, QLabel#statusText { font-size: 13px; font-weight: 500; }
QLabel#subsectionTitle { font-size: 14px; }
QLabel#emptyState { font-size: 14px; }
QLineEdit { color: #F2E5BC; placeholder-text-color: #D5C4A1; }
QListWidget#sourceList, QTreeView, QListWidget#fileSearchResults { font-weight: 500; }
QPushButton, QToolButton { font-weight: 500; }
QPushButton#addSlidesButton, QPushButton#resultAction { font-weight: 600; }
QTabBar::tab:selected, QPushButton#viewModeButton:checked { font-weight: 600; }
QToolTip { color: #F2E5BC; background: #252423; border: 1px solid #504945; }
QPushButton#primaryButton:hover { background: #B7C475; border-color: #B7C475; }
QProgressBar { color: #F2E5BC; }
QProgressBar::chunk { background: #424A3E; }
"""
