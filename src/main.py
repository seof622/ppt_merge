"""PPT Merge 데스크톱 앱 진입점: python -m src.main [PPT 경로 ...]."""

import argparse
import logging
from pathlib import Path
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow
from src.ui.theme import (ACTIVE_THEME, APP_STYLESHEET, BASE_FONT_SIZE, FONT_FAMILIES,
                          TEXT_WEIGHT, application_palette)
from src.ui.window_frame import install_window_frame_theme
from src.utils.logger import configure_logging
from src.utils.app_paths import app_data_root
from src.utils.qt_lifecycle import shutdown_application

ROOT = app_data_root()


def configure_application(app: QApplication) -> None:
    app.setApplicationName("PPT Merge")
    app.setStyle("Fusion")
    app.setPalette(application_palette())
    # 앱에 포함된 글꼴은 시스템 설치 없이 등록하며, EXE에서는 번들 안에서 읽는다.
    if ACTIVE_THEME == "gruvbox-material" and not app.property("pptmergeBundledFontsLoaded"):
        font_root = Path(__file__).resolve().parents[1] / "assets/fonts"
        for name in ("PretendardGOV-Medium.otf", "PretendardGOV-SemiBold.otf", "PretendardGOV-Bold.otf"):
            font_path = font_root / name
            if QFontDatabase.addApplicationFont(str(font_path)) < 0:
                logging.getLogger("ppt_merge.fonts").warning("앱 글꼴 등록 실패: %s", font_path)
        app.setProperty("pptmergeBundledFontsLoaded", True)
    # 화면 없는 검증에 필요한 글꼴은 QApplication마다 한 번만 등록한다.
    # 실제 Windows 화면에서는 시스템 글꼴을 그대로 사용한다.
    if app.platformName() == "offscreen" and not app.property("pptmergeFontsLoaded"):
        for name in ("segoeui.ttf", "segoeuib.ttf", "malgun.ttf", "malgunbd.ttf"):
            font_path = Path("C:/Windows/Fonts") / name
            if font_path.is_file():
                QFontDatabase.addApplicationFont(str(font_path))
        app.setProperty("pptmergeFontsLoaded", True)
    font = QFont()
    font.setFamilies(FONT_FAMILIES)
    font.setPixelSize(BASE_FONT_SIZE)
    font.setWeight(QFont.Weight(TEXT_WEIGHT))
    app.setFont(font)
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
    window_frame = install_window_frame_theme(app)
    logger = logging.getLogger("ppt_merge.app")
    try:
        window = MainWindow(ROOT / "cache")
        window.show()
        if args.package_check:
            from src.utils.package_check import start_package_check
            start_package_check(app, window, args.package_check, args.sources, ROOT,
                                all_slides=args.package_check_all_slides)
        elif args.sources:
            QTimer.singleShot(0, lambda: window.add_sources(args.sources))
        logger.info("앱 시작 frozen=%s 데이터=%s 실행파일=%s", getattr(sys, "frozen", False), ROOT, sys.executable)
        return app.exec()
    finally:
        if window_frame is not None:
            window_frame.close()
        logger.info("앱 종료")
        # Python GC에 남겨 두면 QWidget·폰트가 QApplication보다 늦게 해제될 수 있다.
        shutdown_application(app)


if __name__ == "__main__":
    raise SystemExit(main())
