"""중립색 작업 공간과 파란 강조색으로 행동·선택 상태를 구분한다."""

from PySide6.QtGui import QColor, QPalette


CANVAS = "#F5F6F8"
SURFACE = "#FFFFFF"
SIDEBAR = "#F5F6F8"
TEXT = "#20242C"
MUTED = "#616B7A"
ACCENT = "#356AE6"
ACCENT_HOVER = "#2856C2"
SELECTION = "#E8EFFF"
SELECTION_TEXT = "#234CA6"
DISABLED_TEXT = "#9299A5"
BORDER = "#E2E5EA"


def application_palette() -> QPalette:
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: CANVAS,
        QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: SURFACE,
        QPalette.ColorRole.AlternateBase: "#F1F3F7",
        QPalette.ColorRole.Text: TEXT,
        QPalette.ColorRole.Button: SURFACE,
        QPalette.ColorRole.ButtonText: TEXT,
        QPalette.ColorRole.Highlight: SELECTION,
        QPalette.ColorRole.HighlightedText: SELECTION_TEXT,
        QPalette.ColorRole.ToolTipBase: TEXT,
        QPalette.ColorRole.ToolTipText: SURFACE,
        QPalette.ColorRole.Link: ACCENT,
        QPalette.ColorRole.LinkVisited: ACCENT_HOVER,
        QPalette.ColorRole.PlaceholderText: MUTED,
        QPalette.ColorRole.Light: SURFACE,
        QPalette.ColorRole.Midlight: "#F1F3F7",
        QPalette.ColorRole.Mid: BORDER,
        QPalette.ColorRole.Dark: "#BCC4D0",
        QPalette.ColorRole.Shadow: "#687587",
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(DISABLED_TEXT))
    return palette


APP_STYLESHEET = """
QMainWindow, QWidget { color: #20242C; font-family: '맑은 고딕'; font-size: 14px; }
QMainWindow, QWidget#appShell { background: #F5F6F8; }
QSplitter#workspaceShell { background: #F5F6F8; border: none; border-radius: 14px; }
QWidget#workspace { background: #F5F6F8; border-top-right-radius: 14px; border-bottom-right-radius: 14px; }
QWidget#slidePanel { background: #FFFFFF; border-top-right-radius: 14px; }
QToolBar { background: #F5F6F8; border: none; padding: 12px 16px; spacing: 8px; }
QToolBar::separator { background: transparent; width: 1px; margin: 8px; }
QLabel#appBrand { color: #20242C; font-size: 20px; font-weight: 700; padding: 0 8px 0 2px; }
QToolButton { padding: 7px; border: 1px solid transparent; border-radius: 8px; background: transparent; }
QToolButton:hover { background: #E8EDF5; }
QToolButton:pressed { background: #D9E5FF; }
QToolButton:focus { border-color: #356AE6; }
QToolButton#searchToggle:checked { background: #E8EFFF; border-color: #A5BFF5; }
QToolButton:disabled { color: #9299A5; background: transparent; border-color: transparent; }
QFrame#sourcePanel { background: #F5F6F8; border-top-left-radius: 14px; border-bottom-left-radius: 14px; }
QFrame#originalsPanel { background: #F5F6F8; }
QWidget#outputPanel { background: #F8FAFD; border: none; }
QWidget#outputFooter { background: #F5F6F8; border-bottom-right-radius: 14px; }
QToolButton#outputMore::menu-indicator { image: none; width: 0; height: 0; }
QLabel#sectionTitle { color: #20242C; font-size: 16px; font-weight: 600; }
QLabel#mutedText, QLabel#rootPath, QLabel#statusText { color: #616B7A; font-size: 12px; }
QLabel#emptyState { color: #616B7A; padding: 32px; font-size: 14px; }
QLabel#notice { background: #FFF3D6; color: #77520E; padding: 12px 16px; }
QListWidget#sourceList { border: none; background: #F5F6F8; outline: none; }
QListWidget#sourceList::item { padding: 12px 8px; border: 1px solid transparent; border-radius: 8px; }
QListWidget#sourceList::item:hover { background: #F5F7FA; }
QListWidget#sourceList::item:selected { background: #E8EFFF; border-color: #356AE6; color: #234CA6; }
QListView#slideView { border: none; background: #FFFFFF; outline: none; }
QListView#slideView::item { background: #FFFFFF; border: 1px solid #E2E5EA; border-radius: 10px; padding: 8px; }
QListView#slideView::item:hover { border-color: #A5B7D5; }
QListView#slideView::item:selected { background: #E8EFFF; border-color: #356AE6; color: #234CA6; }
QListView#outputView { border: none; background: #F8FAFD; outline: none; }
QListView#outputView:focus { border-color: #D5DAE3; }
QListView#outputView::item { background: #FFFFFF; border: 1px solid #E2E5EA; border-radius: 8px; padding: 6px; }
QListView#outputView::item:hover { border-color: #A5B7D5; }
QListView#outputView::item:selected { background: #E8EFFF; border-color: #356AE6; color: #234CA6; }
QStatusBar { background: #F5F6F8; border: none; padding: 4px 16px; }
QStatusBar::item { border: none; }
QProgressBar { background: #E6EAF0; color: #20242C; border: none; border-radius: 4px; height: 18px; text-align: center; }
QProgressBar::chunk { background: #356AE6; border-radius: 4px; }
QPushButton { background: #FFFFFF; border: 1px solid #D5DAE3; border-radius: 8px; padding: 7px 14px; }
QPushButton:hover { background: #F5F7FA; border-color: #A5B7D5; }
QPushButton:pressed { background: #D9E5FF; }
QPushButton:focus { border-color: #356AE6; }
QPushButton:disabled { background: #F0F2F6; color: #9299A5; border-color: #E6EAF0; }
QPushButton#primaryButton { background: #356AE6; color: #FFFFFF; border: 1px solid #356AE6; font-weight: 600; padding: 7px 18px; }
QPushButton#primaryButton:hover { background: #2856C2; border-color: #2856C2; }
QPushButton#primaryButton:pressed { background: #2046A5; border-color: #2046A5; }
QPushButton#primaryButton:focus { border-color: #173F9D; }
QPushButton#primaryButton:disabled { background: #E6EAF0; color: #9299A5; border-color: #E6EAF0; }
QPushButton#resultAction { background: #EDF3FF; color: #2856C2; border: 1px solid #BFCFF0; font-weight: 600; }
QPushButton#resultAction:hover { background: #E8EFFF; border-color: #356AE6; }
QPushButton#resultAction:pressed { background: #D9E5FF; }
QPushButton#resultAction:focus { border-color: #356AE6; }
QLineEdit, QComboBox { background: #FFFFFF; border: 1px solid #D5DAE3; border-radius: 8px; padding: 6px 8px; selection-background-color: #E8EFFF; selection-color: #234CA6; }
QLineEdit:hover, QComboBox:hover { border-color: #A5B7D5; }
QLineEdit:focus, QComboBox:focus { border-color: #356AE6; }
QTreeView, QListWidget#fileSearchResults { background: #F5F6F8; border: none; outline: none; }
QTreeView::item, QListWidget#fileSearchResults::item { padding: 6px; border-radius: 6px; }
QTreeView::item:hover, QListWidget#fileSearchResults::item:hover { background: #E9EDF5; }
QTreeView::item:selected, QListWidget#fileSearchResults::item:selected { background: #D9E5FF; color: #234CA6; }
QSplitter::handle { background: transparent; border: none; }
QSplitter::handle:hover { background: #B8C5DA; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #C6CEDA; border-radius: 4px; min-height: 28px; margin: 1px 2px; }
QScrollBar::handle:horizontal { background: #C6CEDA; border-radius: 4px; min-width: 28px; margin: 2px 1px; }
QScrollBar::handle:hover { background: #9FAEC4; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QMenu { background: #FFFFFF; border: 1px solid #E2E5EA; padding: 6px; }
QMenu::item { padding: 8px 20px; border-radius: 6px; }
QMenu::item:selected { background: #E8EFFF; color: #234CA6; }
QMenu::item:disabled { color: #9299A5; }
QMenu::separator { height: 1px; background: #E2E5EA; margin: 4px 8px; }
QToolTip { color: #FFFFFF; background: #20242C; border: none; padding: 6px 8px; }
QDialog, QMessageBox { background: #F5F6F8; }

QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab { color: #616B7A; background: transparent; padding: 10px 8px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #234CA6; font-weight: 600; border-bottom: 2px solid #356AE6; }
QTabBar::tab:hover { color: #356AE6; }
QPushButton#viewModeButton { background: transparent; border-color: transparent; color: #616B7A; padding: 7px 12px; }
QPushButton#viewModeButton:checked { background: #E8EFFF; color: #234CA6; border-color: #C9D8F7; font-weight: 600; }
QPushButton#viewModeButton:focus { border-color: #356AE6; }
QSlider::groove:horizontal { height: 4px; background: #DCE2ED; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #356AE6; border-radius: 2px; }
QSlider::handle:horizontal { width: 12px; margin: -5px 0; border: 2px solid #356AE6; border-radius: 7px; background: white; }
QSlider:focus { border: 1px solid #356AE6; }
QToolButton::menu-indicator { image: none; }
"""
