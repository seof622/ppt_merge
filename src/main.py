"""PPT Merge 데스크톱 앱 진입점: python -m src.main [PPT 경로 ...]."""

import argparse
import logging
from pathlib import Path
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.utils.logger import configure_logging
from src.utils.app_paths import app_data_root

ROOT = app_data_root()

APP_STYLESHEET = """
QMainWindow, QWidget { color: #243247; font-family: '맑은 고딕'; font-size: 14px; }
QMainWindow, QWidget#slidePanel { background: #f5f7fb; }
QToolBar { background: #ffffff; border: none; border-bottom: 1px solid #edf0f5; padding: 12px 16px; spacing: 8px; }
QToolBar::separator { background: #e7ecf3; width: 1px; margin: 8px; }
QToolButton { padding: 7px; border: 1px solid transparent; border-radius: 8px; background: transparent; }
QToolButton:hover { background: #edf3fc; }
QToolButton:pressed { background: #dce8fa; }
QToolButton:focus { border-color: #adc4eb; }
QToolButton#searchToggle:checked { background: #e7effc; }
QToolButton:disabled { color: #a4afbf; background: transparent; border-color: transparent; }
QFrame#sourcePanel, QFrame#originalsPanel { background: #ffffff; }
QWidget#outputPanel { background: #ffffff; border-top: 1px solid #edf0f5; }
QLabel#sectionTitle { color: #243247; font-size: 16px; font-weight: 600; }
QLabel#mutedText, QLabel#rootPath, QLabel#statusText { color: #738198; font-size: 12px; }
QLabel#emptyState { color: #738198; padding: 32px; font-size: 14px; }
QLabel#notice { background: #fff7ed; color: #9a3412; padding: 12px 16px; }
QListWidget#sourceList { border: none; background: #ffffff; outline: none; }
QListWidget#sourceList::item { padding: 10px 8px; border-radius: 8px; }
QListWidget#sourceList::item:hover { background: #f2f5fa; }
QListWidget#sourceList::item:selected { background: #e7effc; color: #244d8c; }
QListView#slideView { border: none; background: #f5f7fb; outline: none; }
QListView#slideView::item { background: #ffffff; border: 1px solid #e7ecf3; border-radius: 10px; padding: 8px; }
QListView#slideView::item:hover { border-color: #bccde7; }
QListView#slideView::item:selected { background: #edf3ff; border-color: #709be6; color: #244d8c; }
QListView#outputView { border: 1px solid #edf0f5; border-radius: 10px; background: #f5f7fb; outline: none; }
QListView#outputView:focus { border-color: #adc4eb; }
QListView#outputView::item { background: #ffffff; border: 1px solid #e7ecf3; border-radius: 8px; padding: 6px; }
QListView#outputView::item:hover { border-color: #bccde7; }
QListView#outputView::item:selected { background: #edf3ff; border-color: #709be6; color: #244d8c; }
QStatusBar { background: #ffffff; border-top: 1px solid #edf0f5; padding: 4px 16px; }
QStatusBar::item { border: none; }
QProgressBar { background: #edf1f7; border: none; border-radius: 4px; height: 18px; text-align: center; }
QProgressBar::chunk { background: #3773df; border-radius: 4px; }
QPushButton { background: #ffffff; border: 1px solid #dce3ed; border-radius: 8px; padding: 7px 14px; }
QPushButton:hover { background: #edf3fc; }
QPushButton:pressed { background: #dce8fa; }
QPushButton:focus { border-color: #adc4eb; }
QPushButton:disabled { color: #a4afbf; border-color: #edf0f5; }
QPushButton#primaryButton { background: #2864d7; color: #ffffff; border: 1px solid #2864d7; font-weight: 600; padding: 7px 18px; }
QPushButton#primaryButton:hover { background: #2158c1; border-color: #2158c1; }
QPushButton#primaryButton:pressed { background: #1c4ca8; border-color: #1c4ca8; }
QPushButton#primaryButton:focus { border-color: #173c86; }
QPushButton#primaryButton:disabled { background: #edf1f7; color: #94a3b8; border-color: #edf1f7; }
QPushButton#resultAction { background: #edf3ff; color: #2454a1; border: 1px solid #c8d9f5; font-weight: 600; }
QPushButton#resultAction:hover { background: #dce8fa; border-color: #709be6; }
QPushButton#resultAction:pressed { background: #c8d9f5; }
QPushButton#resultAction:focus { border-color: #2864d7; }
QLineEdit, QComboBox { background: #ffffff; border: 1px solid #dce3ed; border-radius: 8px; padding: 6px 8px; selection-background-color: #dce8fa; selection-color: #244d8c; }
QLineEdit:focus, QComboBox:focus { border-color: #709be6; }
QTreeView, QListWidget#fileSearchResults { background: #ffffff; border: none; outline: none; }
QTreeView::item, QListWidget#fileSearchResults::item { padding: 6px; border-radius: 6px; }
QTreeView::item:hover, QListWidget#fileSearchResults::item:hover { background: #f2f5fa; }
QTreeView::item:selected, QListWidget#fileSearchResults::item:selected { background: #e7effc; color: #244d8c; }
QSplitter::handle { background: #edf0f5; }
QSplitter::handle:hover { background: #c4d6f2; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #cbd4e1; border-radius: 4px; min-height: 28px; margin: 1px 2px; }
QScrollBar::handle:horizontal { background: #cbd4e1; border-radius: 4px; min-width: 28px; margin: 2px 1px; }
QScrollBar::handle:hover { background: #a6b6cc; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QMenu { background: #ffffff; border: 1px solid #e7ecf3; padding: 6px; }
QMenu::item { padding: 8px 20px; border-radius: 6px; }
QMenu::item:selected { background: #edf3fc; }
QToolTip { color: #ffffff; background: #243247; border: none; padding: 6px 8px; }
"""


def configure_application(app: QApplication) -> None:
    app.setApplicationName("PPT Merge")
    app.setStyle("Fusion")
    # 화면 없는 Qt 검증에서도 Windows의 한글 글꼴로 실제 UI를 렌더한다.
    font_path = Path("C:/Windows/Fonts/malgun.ttf")
    if font_path.is_file():
        QFontDatabase.addApplicationFont(str(font_path))
    app.setFont(QFont("맑은 고딕", 10))
    app.setStyleSheet(APP_STYLESHEET)


def main() -> int:
    parser = argparse.ArgumentParser(description="PPT 슬라이드를 미리 보고 출력 순서를 편집합니다.")
    parser.add_argument("sources", nargs="*", type=Path)
    parser.add_argument("--package-check", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    configure_logging(ROOT / "logs")
    app = QApplication(sys.argv[:1])
    configure_application(app)
    window = MainWindow(ROOT / "cache")
    window.show()
    if args.package_check:
        from src.utils.package_check import start_package_check
        start_package_check(app, window, args.package_check, args.sources, ROOT)
    elif args.sources:
        QTimer.singleShot(0, lambda: window.add_sources(args.sources))
    logger = logging.getLogger("ppt_merge.app")
    logger.info("앱 시작 frozen=%s 데이터=%s", getattr(sys, "frozen", False), ROOT)
    try:
        return app.exec()
    finally:
        logger.info("앱 종료")


if __name__ == "__main__":
    raise SystemExit(main())
