"""Qt 리소스와 앱을 명시적으로 정리하고 실제 프로세스 종료 결과를 반환한다."""

import ctypes
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if sys.platform == "win32":
        # 오류는 종료 코드·로그로 보고하며 자동 검사 중 OS 오류창은 띄우지 않는다.
        ctypes.windll.kernel32.SetErrorMode(0x0001 | 0x0002)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tests/unit"))
    from PySide6.QtWidgets import QApplication
    from src.utils.qt_lifecycle import shutdown_application

    loader = unittest.defaultTestLoader
    suite = (loader.loadTestsFromNames(sys.argv[1:]) if sys.argv[1:]
             else loader.discover(str(ROOT / "tests/unit")))
    try:
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        return 0 if result.wasSuccessful() else 1
    finally:
        app = QApplication.instance()
        if app is not None:
            shutdown_application(app)


if __name__ == "__main__":
    raise SystemExit(main())
