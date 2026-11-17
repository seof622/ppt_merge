"""밝은 블루 계열의 명도 차이로 작업 영역과 상태를 구분한다."""

from PySide6.QtGui import QColor, QPalette


CANVAS = "#F3F7FF"
SURFACE = "#FFFFFF"
SIDEBAR = "#EFF5FF"
TEXT = "#24334A"
MUTED = "#65758D"
ACCENT = "#3563E9"
ACCENT_HOVER = "#244FC7"
SELECTION = "#E8F0FF"
SELECTION_TEXT = "#244FC7"
DISABLED_TEXT = "#9AA9BE"
BORDER = "#DDE6F2"
BADGE_SURFACE = "#E5EEFF"
BADGE_TEXT = "#345CB0"


def application_palette() -> QPalette:
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: CANVAS,
        QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: SURFACE,
        QPalette.ColorRole.AlternateBase: "#EEF4FD",
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
        QPalette.ColorRole.Midlight: "#EEF4FD",
        QPalette.ColorRole.Mid: BORDER,
        QPalette.ColorRole.Dark: "#B4C5DE",
        QPalette.ColorRole.Shadow: "#65758D",
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(DISABLED_TEXT))
    return palette


APP_STYLESHEET = """
QMainWindow, QWidget { color: #24334A; font-family: 'Segoe UI', '맑은 고딕'; font-size: 13px; }
QMainWindow, QWidget#appShell { background: #F3F7FF; }
QSplitter#workspaceShell, QWidget#workspace { background: #F3F7FF; border: none; }
QWidget#slidePanel { background: #FFFFFF; border-top-left-radius: 10px; }
QWidget#outputPanel { background: #EDF3FF; border-left: 1px solid #D7E3F6; border-top-right-radius: 10px; }
QFrame#sourcePanel, QFrame#originalsPanel { background: #EFF5FF; border: none; }
QWidget#outputFooter { background: #F3F7FF; }
QToolBar { background: #F3F7FF; border: none; padding: 10px 20px; spacing: 6px; }
QToolBar::separator { background: #DDE6F4; width: 1px; margin: 6px 12px; }
QLabel#appBrand { color: #2854C7; font-size: 18px; font-weight: 700; padding: 0 8px 0 0; }
QToolButton { padding: 7px; border: 1px solid transparent; border-radius: 6px; background: transparent; }
QToolButton:hover { background: #E6EEFC; }
QToolButton:pressed { background: #D7E4FA; }
QToolButton:focus { border-color: #3563E9; }
QToolButton#searchToggle:checked { background: #E8F0FF; color: #244FC7; }
QToolButton:disabled { color: #9AA9BE; background: transparent; border-color: transparent; }
QToolButton::menu-indicator { image: none; width: 0; height: 0; }
QLabel#sectionTitle { color: #24334A; font-size: 18px; font-weight: 600; }
QLabel#subsectionTitle { color: #4C607C; font-size: 13px; font-weight: 500; }
QLabel#mutedText, QLabel#rootPath, QLabel#statusText { color: #65758D; font-size: 12px; }
QLabel#emptyState { color: #65758D; padding: 24px; font-size: 13px; }
QLabel#notice { background: #FFF4DB; color: #795A21; padding: 12px 16px; border-radius: 6px; }
QListWidget#sourceList { border: none; background: #EFF5FF; outline: none; }
QListWidget#sourceList::item { padding: 12px 10px; border: 1px solid transparent; border-radius: 6px; }
QListWidget#sourceList::item:hover { background: #E8F0FF; }
QListWidget#sourceList::item:selected { background: #E2ECFF; color: #244FC7; }
QListWidget#sourceList:focus::item:selected { border-color: #B8C8F0; }
QListView#slideView { border: none; background: #FFFFFF; outline: none; }
QListView#outputView { border: none; background: #EDF3FF; outline: none; }
QWidget#outputPanel QLabel#sectionTitle { color: #3D5D95; }
QWidget#outputPanel QPushButton#quietButton { background: #DFE9FC; color: #46618F; }
QWidget#outputPanel QPushButton#quietButton:hover { background: #D4E1FA; }
QWidget#outputPanel QPushButton#quietButton:disabled { background: #E8EFFC; color: #8D9FBD; }
QWidget#outputPanel QToolButton:hover { background: #DCE7FC; }
QWidget#outputPanel QComboBox#viewModeCombo { background: #DFE9FC; color: #46618F; }
QWidget#outputPanel QComboBox#viewModeCombo:hover { background: #D4E1FA; }
QWidget#outputPanel QSlider::groove:horizontal { background: #D5E2F8; }
QWidget#outputPanel QSlider::sub-page:horizontal { background: #7C9FE0; }
QWidget#outputPanel QSlider::handle:horizontal { border-color: #A0B7E0; }
QStatusBar { background: #F3F7FF; border: none; padding: 2px 16px; }
QStatusBar::item { border: none; }
QProgressBar { background: #E3ECFB; color: #24334A; border: none; border-radius: 4px; height: 16px; text-align: center; }
QProgressBar::chunk { background: #3563E9; border-radius: 4px; }
QPushButton { background: #FFFFFF; border: 1px solid #D9E3F1; border-radius: 6px; padding: 7px 12px; }
QPushButton:hover { background: #F1F6FE; border-color: #B9CDEA; }
QPushButton:pressed { background: #E1EBFC; }
QPushButton:focus { border-color: #3563E9; }
QPushButton:disabled { background: #F1F6FE; color: #9AA9BE; border-color: #E7EEF9; }
QPushButton#primaryButton { background: #3563E9; color: #FFFFFF; border: 1px solid #3563E9; font-weight: 600; padding: 7px 18px; }
QPushButton#primaryButton:hover { background: #254FCC; border-color: #254FCC; }
QPushButton#primaryButton:pressed { background: #1F43B0; border-color: #1F43B0; }
QPushButton#primaryButton:focus { border-color: #3563E9; }
QPushButton#primaryButton:disabled { background: #E2ECFF; color: #9AA9BE; border-color: #E2ECFF; }
QPushButton#addSlidesButton { background: #E8F0FF; color: #244FC7; border-color: transparent; font-weight: 500; }
QPushButton#addSlidesButton:hover { background: #DAE7FF; }
QPushButton#addSlidesButton:pressed { background: #CCDDFE; }
QPushButton#addSlidesButton:focus { border-color: #3563E9; }
QPushButton#addSlidesButton:disabled { background: #EDF3FD; color: #9AA9BE; border-color: transparent; }
QPushButton#resultAction { color: #365B92; background: #FFFFFF; font-weight: 500; }
QPushButton#resultAction:hover { background: #E5EEFC; }
QPushButton#resultAction:focus { border-color: #3563E9; }
QPushButton#quietButton { background: #F3F7FF; border-color: transparent; color: #4C607C; }
QPushButton#quietButton:hover { background: #E4EDFC; color: #24334A; }
QPushButton#quietButton:focus { border-color: #3563E9; }
QPushButton#quietButton:disabled { color: #9AA9BE; background: #F5F8FE; border-color: transparent; }
QLineEdit, QComboBox { background: #FFFFFF; border: 1px solid #D9E3F1; border-radius: 6px; padding: 7px 10px; selection-background-color: #E8F0FF; selection-color: #244FC7; }
QLineEdit:hover, QComboBox:hover { border-color: #B9CDEA; }
QLineEdit:focus, QComboBox:focus { border-color: #3563E9; background: #FFFFFF; }
QLineEdit#slideSearch { background: #F1F6FE; border-color: transparent; padding: 0 8px; }
QLineEdit#slideSearch:hover { background: #E9F1FE; }
QLineEdit#slideSearch:focus { background: #FFFFFF; border-color: #3563E9; }
QLineEdit:disabled { color: #9AA9BE; background: #F3F7FF; }
QComboBox { padding-right: 26px; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow { image: none; }
QComboBox#viewModeCombo { background: #F3F7FF; border-color: transparent; }
QComboBox#viewModeCombo:hover { background: #E4EDFC; }
QComboBox#viewModeCombo:focus { border-color: #3563E9; }
QTreeView, QListWidget#fileSearchResults { background: #EFF5FF; border: none; outline: none; }
QTreeView::item, QListWidget#fileSearchResults::item { padding: 6px; border-radius: 5px; }
QTreeView::item:hover, QListWidget#fileSearchResults::item:hover { background: #E8F0FF; }
QTreeView::item:selected, QListWidget#fileSearchResults::item:selected { background: #E2ECFF; color: #24334A; }
QSplitter::handle { background: transparent; border: none; }
QSplitter::handle:hover { background: #A7C2EE; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #C2D2EA; border-radius: 3px; min-height: 28px; margin: 1px 2px; }
QScrollBar::handle:horizontal { background: #C2D2EA; border-radius: 3px; min-width: 28px; margin: 2px 1px; }
QScrollBar::handle:hover { background: #9AB7DE; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QMenu { background: #FFFFFF; border: 1px solid #DDE6F2; padding: 5px; }
QMenu::item { padding: 8px 18px; border-radius: 5px; }
QMenu::item:selected { background: #E9F1FF; color: #24334A; }
QMenu::item:disabled { color: #9AA9BE; }
QMenu::separator { height: 1px; background: #DDE6F2; margin: 4px 8px; }
QToolTip { color: #FFFFFF; background: #3563E9; border: none; padding: 6px 8px; }
QDialog, QMessageBox { background: #F3F7FF; }
QTabWidget::pane { border: none; background: transparent; }
QTabBar::tab { color: #65758D; background: transparent; padding: 9px 8px; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #24334A; font-weight: 500; border-bottom: 2px solid #3563E9; }
QTabBar::tab:hover { color: #24334A; }
QWidget#modeSwitch { background: #E4EDFC; border: 1px solid #D8E4F6; border-radius: 8px; }
QPushButton#viewModeButton { background: transparent; border: 1px solid transparent; border-radius: 5px; color: #65758D; padding: 5px 12px; }
QPushButton#viewModeButton:hover { color: #24334A; background: #D6E4FC; }
QPushButton#viewModeButton:checked { background: #FFFFFF; color: #244FC7; border-color: #C8D9F5; font-weight: 500; }
QPushButton#viewModeButton:focus { border-color: #3563E9; }
QSlider::groove:horizontal { height: 3px; background: #D8E4F6; border-radius: 1px; }
QSlider::sub-page:horizontal { background: #7EA4EE; border-radius: 1px; }
QSlider::handle:horizontal { width: 10px; margin: -4px 0; border: 1px solid #92B0E6; border-radius: 5px; background: #FFFFFF; }
QSlider::handle:horizontal:hover { border-color: #3563E9; }
QSlider:focus { border: 1px solid #3563E9; border-radius: 3px; }
"""
