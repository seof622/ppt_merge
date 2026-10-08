"""실제 PowerPoint를 QThread에서 실행해 화면·캐시·종료를 검증한다."""

from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.main import configure_application
from src.ppt.presentation_manager import PresentationManager
from src.ppt.thumbnail_service import ThumbnailService
from src.ui.main_window import MainWindow
from src.utils.logger import configure_logging
from src.utils.process_utils import process_pids

ROOT = Path(__file__).resolve().parents[2]


def wait_until(predicate, timeout=45):
    if predicate():
        return
    # 실제 앱과 같이 Qt 이벤트 루프가 GIL을 해제한 상태에서 COM 워커를 기다린다.
    loop = QEventLoop()
    poll = QTimer(loop)
    poll.setInterval(20)
    poll.timeout.connect(lambda: loop.quit() if predicate() else None)
    limit = QTimer(loop)
    limit.setSingleShot(True)
    limit.timeout.connect(loop.quit)
    poll.start()
    limit.start(timeout * 1000)
    loop.exec()
    if not predicate():
        raise AssertionError("실제 PowerPoint UI 작업 시간 초과")


@unittest.skipUnless(os.environ.get("PPT_MERGE_UI_COM_TESTS") == "1", "UI Office 통합 검증 활성화 필요")
class UiComTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if process_pids("POWERPNT.EXE"):
            raise unittest.SkipTest("사용자 PowerPoint를 먼저 저장하고 닫아 주세요.")
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        configure_application(cls.app)
        configure_logging(ROOT / "logs")
        cls.directory = Path(tempfile.mkdtemp(prefix="ui_validation_", dir=ROOT / "output"))
        cls.cache = cls.directory / "cache"
        cls.cleanups = []
        cls.cases = []

    @classmethod
    def tearDownClass(cls):
        report = {"directory": str(cls.directory), "cases": cls.cases,
                  "sessions": cls.cleanups, "live_powerpoint_pids": sorted(process_pids("POWERPNT.EXE"))}
        (cls.directory / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def service_factory(self):
        cleanups = self.cleanups

        class RecordingManager(PresentationManager):
            def __exit__(self, *args):
                try:
                    super().__exit__(*args)
                finally:
                    cleanups.append(dict(self.cleanup))

        return ThumbnailService(self.cache, backend_factory=RecordingManager)

    def setUp(self):
        self.window = None

    def tearDown(self):
        if self.window is not None:
            if self.window.is_loading:
                self.window.cancel_loading()
                wait_until(lambda: not self.window.is_loading)
            self.window.close()
            self.app.processEvents()

    def assert_clean(self):
        self.assertFalse(process_pids("POWERPNT.EXE"))
        self.assertTrue(all(c["owned_process_exited"] and not c["errors"] for c in self.cleanups))

    def test_01_load_real_ppt_and_cache_in_qthread(self):
        self.window = MainWindow(self.cache, self.service_factory)
        self.window.resize(1920, 1080)
        self.window.show()
        QTest.qWait(100)
        self.assertTrue(self.window.grab().save(str(self.directory / "empty.png")))
        ticks = []
        timer = QTimer()
        timer.setInterval(20)
        timer.timeout.connect(lambda: ticks.append(1))
        timer.start()
        self.window.add_sources([ROOT / "tests/fixtures/basic/A.pptx",
                                 ROOT / "tests/fixtures/advanced/advanced.pptx"])
        wait_until(lambda: not self.window.is_loading)
        timer.stop()
        self.assertGreater(len(ticks), 20)
        self.assertEqual([s.result.presentation.slide_count for s in self.window._sources.values()], [4, 9])
        self.assertTrue(all(s.status == "ready" for s in self.window._sources.values()))
        self.assertEqual(self.window.slide_grid.model.rowCount(), 4)
        advanced_key = os.path.normcase(str(ROOT / "tests/fixtures/advanced/advanced.pptx"))
        self.window.source_panel.select_source(advanced_key)
        self.assertEqual(self.window.slide_grid.model.rowCount(), 9)
        self.window.slide_grid.view.doItemsLayout()
        QTest.qWait(100)
        self.assertTrue(self.window.grab().save(str(self.directory / "loaded.png")))
        self.window.resize(1000, 640)
        QTest.qWait(100)
        self.assertTrue(self.window.grab().save(str(self.directory / "compact.png")))
        started = len(self.cleanups)
        self.window.reload_action.trigger()
        wait_until(lambda: not self.window.is_loading)
        self.assertEqual(len(self.cleanups), started)
        self.assertTrue(self.window._sources[advanced_key].result.cache_hit)
        self.assert_clean()
        self.cases.append({"case": "qthread_load_and_cache", "passed": True,
                           "ui_timer_ticks": len(ticks), "native_exported_slides": 13,
                           "sources": [asdict(state.result) for state in self.window._sources.values()]})

    def test_02_close_during_real_com_work(self):
        self.window = MainWindow(self.cache, self.service_factory)
        self.window.show()
        timer = QTimer(self.window)
        timer.setInterval(20)

        def close_after_first_thumbnail():
            if self.window.progress_bar.maximum() > 0 and self.window.progress_bar.value() > 0:
                timer.stop()
                self.window.close()

        timer.timeout.connect(close_after_first_thumbnail)
        timer.start()
        self.window.add_sources([ROOT / "tests/fixtures/basic/B.pptx"])
        wait_until(lambda: not self.window.is_loading and not self.window.isVisible())
        self.assertTrue(self.window._closing)
        self.assert_clean()
        self.cases.append({"case": "close_during_com_work", "passed": True})


if __name__ == "__main__":
    unittest.main()
