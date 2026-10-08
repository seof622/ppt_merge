"""PPT Merge 데스크톱 앱 진입점: python -m src.main [PPT 경로 ...]."""

import argparse
from pathlib import Path
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.utils.logger import configure_logging

ROOT = Path(__file__).resolve().parents[1]

APP_STYLESHEET = """
QMainWindow, QWidget { color: #1e293b; font-family: '맑은 고딕'; font-size: 14px; }
QMainWindow { background: #f8fafc; }
QToolBar { background: #ffffff; border: none; border-bottom: 1px solid #e2e8f0; padding: 10px 14px; spacing: 8px; }
QToolButton { padding: 8px 14px; border: 1px solid #cbd5e1; border-radius: 6px; background: #ffffff; }
QToolButton:hover { background: #eff6ff; border-color: #93c5fd; }
QToolButton:disabled { color: #94a3b8; border-color: #e2e8f0; }
QFrame#sourcePanel { background: #ffffff; border-right: 1px solid #e2e8f0; }
QLabel#sectionTitle { font-size: 18px; font-weight: 600; }
QLabel#mutedText { color: #64748b; font-size: 12px; }
QLabel#emptyState { color: #64748b; padding: 36px; font-size: 16px; }
QLabel#notice { background: #fff7ed; color: #9a3412; padding: 12px 20px; }
QListWidget#sourceList { border: none; background: #ffffff; outline: none; }
QListWidget#sourceList::item { padding: 12px 10px; border-radius: 6px; }
QListWidget#sourceList::item:selected { background: #dbeafe; color: #1e40af; }
QListView#slideView { border: none; background: #f8fafc; outline: none; }
QListView#slideView::item { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px; }
QListView#slideView::item:selected { background: #eff6ff; border: 2px solid #3b82f6; color: #1e40af; }
QListView#outputView { border: 1px solid #cbd5e1; border-radius: 6px; background: #f8fafc; outline: none; }
QListView#outputView::item { background: #ffffff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px; }
QListView#outputView::item:selected { background: #eff6ff; border: 2px solid #3b82f6; color: #1e40af; }
QStatusBar { background: #ffffff; border-top: 1px solid #e2e8f0; padding: 6px 14px; }
QStatusBar::item { border: none; }
QProgressBar { border: 1px solid #cbd5e1; border-radius: 4px; height: 18px; text-align: center; }
QProgressBar::chunk { background: #3b82f6; }
QPushButton { background: #ffffff; border: 1px solid #cbd5e1; border-radius: 5px; padding: 5px 12px; }
QPushButton:hover { background: #eff6ff; }
QPushButton:disabled { color: #94a3b8; border-color: #e2e8f0; }
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
    args = parser.parse_args()
    configure_logging(ROOT / "logs")
    app = QApplication(sys.argv[:1])
    configure_application(app)
    window = MainWindow(ROOT / "cache")
    window.show()
    if args.sources:
        QTimer.singleShot(0, lambda: window.add_sources(args.sources))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
