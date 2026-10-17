"""PPT Merge 데스크톱 앱 진입점: python -m src.main [PPT 경로 ...]."""

import argparse
import logging
from pathlib import Path
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.ui.theme import APP_STYLESHEET, application_palette
from src.utils.logger import configure_logging
from src.utils.app_paths import app_data_root

ROOT = app_data_root()


def configure_application(app: QApplication) -> None:
    app.setApplicationName("PPT Merge")
    app.setStyle("Fusion")
    app.setPalette(application_palette())
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
    parser.add_argument("--package-check-all-slides", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    configure_logging(ROOT / "logs")
    app = QApplication(sys.argv[:1])
    configure_application(app)
    window = MainWindow(ROOT / "cache")
    window.show()
    if args.package_check:
        from src.utils.package_check import start_package_check
        start_package_check(app, window, args.package_check, args.sources, ROOT,
                            all_slides=args.package_check_all_slides)
    elif args.sources:
        QTimer.singleShot(0, lambda: window.add_sources(args.sources))
    logger = logging.getLogger("ppt_merge.app")
    logger.info("앱 시작 frozen=%s 데이터=%s 실행파일=%s", getattr(sys, "frozen", False), ROOT, sys.executable)
    try:
        return app.exec()
    finally:
        logger.info("앱 종료")


if __name__ == "__main__":
    raise SystemExit(main())
