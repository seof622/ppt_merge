"""따뜻한 종이·오트밀·브라운 색상을 앱 전체에 일관되게 적용한다."""

from PySide6.QtGui import QColor, QPalette


CANVAS = "#faf7f1"
SURFACE = "#fffdf8"
SIDEBAR = "#e6dac7"
TEXT = "#3d352e"
MUTED = "#7c6e5e"
ACCENT = "#78583e"
ACCENT_HOVER = "#624630"
SELECTION = "#e9dcc8"
SELECTION_TEXT = "#543d29"
DISABLED_TEXT = "#a09686"
BORDER = "#dfd5c5"


def application_palette() -> QPalette:
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: CANVAS,
        QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: SURFACE,
        QPalette.ColorRole.AlternateBase: "#f7f2e9",
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
        QPalette.ColorRole.Midlight: "#f7f2e9",
        QPalette.ColorRole.Mid: BORDER,
        QPalette.ColorRole.Dark: "#b2a28e",
        QPalette.ColorRole.Shadow: "#6e5c49",
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(DISABLED_TEXT))
    return palette


APP_STYLESHEET = """
QMainWindow, QWidget { color: #3d352e; font-family: '맑은 고딕'; font-size: 14px; }
QMainWindow, QWidget#appShell { background: #e7ddce; }
QSplitter#workspaceShell { background: #f0e7db; border: none; border-radius: 14px; }
QWidget#workspace { background: #faf7f1; border-top-right-radius: 14px; border-bottom-right-radius: 14px; }
QWidget#slidePanel { background: #faf7f1; border-top-right-radius: 14px; }
QToolBar { background: #e7ddce; border: none; padding: 12px 16px; spacing: 8px; }
QToolBar::separator { background: transparent; width: 1px; margin: 8px; }
QLabel#appBrand { color: #543d29; font-size: 16px; font-weight: 700; padding: 0 8px 0 2px; }
QToolButton { padding: 7px; border: 1px solid transparent; border-radius: 8px; background: transparent; }
QToolButton:hover { background: #e9dfd0; }
QToolButton:pressed { background: #ddcdb7; }
QToolButton:focus { border-color: #a17d55; }
QToolButton#searchToggle:checked { background: #e0d0b9; border-color: #c4aa86; }
QToolButton:disabled { color: #a09686; background: transparent; border-color: transparent; }
QFrame#sourcePanel { background: #e6dac7; border-top-left-radius: 14px; border-bottom-left-radius: 14px; }
QFrame#originalsPanel { background: #f0e7db; }
QWidget#outputPanel { background: #faf7f1; border: none; }
QWidget#outputFooter { background: #faf7f1; border-bottom-right-radius: 14px; }
QToolButton#outputMore::menu-indicator { image: none; width: 0; height: 0; }
QLabel#sectionTitle { color: #3d352e; font-size: 16px; font-weight: 600; }
QLabel#mutedText, QLabel#rootPath, QLabel#statusText { color: #7c6e5e; font-size: 12px; }
QLabel#emptyState { color: #7c6e5e; padding: 32px; font-size: 14px; }
QLabel#notice { background: #f4e5ce; color: #754a25; padding: 12px 16px; }
QListWidget#sourceList { border: none; background: #f0e7db; outline: none; }
QListWidget#sourceList::item { padding: 10px 8px; border: 1px solid transparent; border-radius: 8px; }
QListWidget#sourceList::item:hover { background: #eee6d9; }
QListWidget#sourceList::item:selected { background: #e9dcc8; border-color: #cfb996; color: #543d29; }
QListView#slideView { border: none; background: #faf7f1; outline: none; }
QListView#slideView::item { background: #fffdf8; border: 1px solid #dfd5c5; border-radius: 10px; padding: 8px; }
QListView#slideView::item:hover { border-color: #b89b77; }
QListView#slideView::item:selected { background: #e9dcc8; border-color: #a17d55; color: #543d29; }
QListView#outputView { border: 1px solid transparent; border-radius: 10px; background: #eee6d9; outline: none; }
QListView#outputView:focus { border-color: #d4c6b2; }
QListView#outputView::item { background: #fffdf8; border: 1px solid #dfd5c5; border-radius: 8px; padding: 6px; }
QListView#outputView::item:hover { border-color: #b89b77; }
QListView#outputView::item:selected { background: #e9dcc8; border-color: #a17d55; color: #543d29; }
QStatusBar { background: #e7ddce; border: none; padding: 4px 16px; }
QStatusBar::item { border: none; }
QProgressBar { background: #e7dfd3; color: #3d352e; border: none; border-radius: 4px; height: 18px; text-align: center; }
QProgressBar::chunk { background: #b39976; border-radius: 4px; }
QPushButton { background: #fffdf8; border: 1px solid #d4c6b2; border-radius: 8px; padding: 7px 14px; }
QPushButton:hover { background: #eee6d9; border-color: #b89b77; }
QPushButton:pressed { background: #ddcdb7; }
QPushButton:focus { border-color: #a17d55; }
QPushButton:disabled { background: #f5f0e8; color: #a09686; border-color: #e7dfd3; }
QPushButton#primaryButton { background: #78583e; color: #fffdf8; border: 1px solid #78583e; font-weight: 600; padding: 7px 18px; }
QPushButton#primaryButton:hover { background: #624630; border-color: #624630; }
QPushButton#primaryButton:pressed { background: #4e3726; border-color: #4e3726; }
QPushButton#primaryButton:focus { border-color: #35271d; }
QPushButton#primaryButton:disabled { background: #e7dfd3; color: #a09686; border-color: #e7dfd3; }
QPushButton#resultAction { background: #f2e8d9; color: #624630; border: 1px solid #d4bd9d; font-weight: 600; }
QPushButton#resultAction:hover { background: #e9dcc8; border-color: #a17d55; }
QPushButton#resultAction:pressed { background: #ddcdb7; }
QPushButton#resultAction:focus { border-color: #78583e; }
QLineEdit, QComboBox { background: #fffdf8; border: 1px solid #d4c6b2; border-radius: 8px; padding: 6px 8px; selection-background-color: #e9dcc8; selection-color: #543d29; }
QLineEdit:hover, QComboBox:hover { border-color: #b89b77; }
QLineEdit:focus, QComboBox:focus { border-color: #a17d55; }
QTreeView, QListWidget#fileSearchResults { background: #e6dac7; border: none; outline: none; }
QTreeView::item, QListWidget#fileSearchResults::item { padding: 6px; border-radius: 6px; }
QTreeView::item:hover, QListWidget#fileSearchResults::item:hover { background: #e5d9c7; }
QTreeView::item:selected, QListWidget#fileSearchResults::item:selected { background: #ddcdb7; color: #543d29; }
QSplitter::handle { background: transparent; border: none; }
QSplitter::handle:hover { background: #cbb99f; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #c8baa5; border-radius: 4px; min-height: 28px; margin: 1px 2px; }
QScrollBar::handle:horizontal { background: #c8baa5; border-radius: 4px; min-width: 28px; margin: 2px 1px; }
QScrollBar::handle:hover { background: #a58f71; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QMenu { background: #fffdf8; border: 1px solid #dfd5c5; padding: 6px; }
QMenu::item { padding: 8px 20px; border-radius: 6px; }
QMenu::item:selected { background: #e9dcc8; color: #543d29; }
QMenu::item:disabled { color: #a09686; }
QMenu::separator { height: 1px; background: #dfd5c5; margin: 4px 8px; }
QToolTip { color: #fffdf8; background: #3d352e; border: none; padding: 6px 8px; }
QDialog, QMessageBox { background: #faf6ef; }
"""
