"""기존 실제 PPT 캐시로 출력 편집과 화면을 검증하며 Office를 실행하지 않는다."""

from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QItemSelectionModel, QModelIndex, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.main import configure_application
from src.ppt.thumbnail_service import ThumbnailService
from src.ui.main_window import MainWindow
from src.utils.logger import configure_logging
from test_ui_com import wait_until

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.environ.get("PPT_MERGE_OUTPUT_UI_TESTS") == "1", "출력 UI 캐시 통합 검증 활성화 필요")
class OutputCachedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        configure_application(cls.app)
        configure_logging(ROOT / "logs")
        (ROOT / "output").mkdir(exist_ok=True)
        cls.directory = Path(tempfile.mkdtemp(prefix="composer_validation_", dir=ROOT / "output"))
        cls.cases = []
        cls.backend_calls = 0

    @classmethod
    def tearDownClass(cls):
        report = {"directory": str(cls.directory), "cases": cls.cases,
                  "office_backend_calls": cls.backend_calls,
                  "manual_native_drag_validation": "pending"}
        (cls.directory / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def no_office_backend(self):
        type(self).backend_calls += 1
        raise AssertionError("이 검증은 기존 캐시가 필요하며 PowerPoint를 실행하지 않습니다.")

    def setUp(self):
        self.window = MainWindow(ROOT / "cache", lambda: ThumbnailService(
            ROOT / "cache", backend_factory=self.no_office_backend))
        self.window.resize(1920, 1080)
        self.window.show()

    def tearDown(self):
        if self.window.is_loading:
            self.window.cancel_loading()
            wait_until(lambda: not self.window.is_loading)
        self.window.close()
        self.app.processEvents()

    def test_real_cached_slides_preserve_requested_order_and_render(self):
        QTest.qWait(50)
        self.assertTrue(self.window.grab().save(str(self.directory / "empty.png")))
        a = ROOT / "tests/fixtures/basic/A.pptx"
        b = ROOT / "tests/fixtures/basic/B.pptx"
        advanced = ROOT / "tests/fixtures/advanced/advanced.pptx"
        self.window.add_sources([a, b, advanced])
        wait_until(lambda: not self.window.is_loading)
        self.assertTrue(all(state.status == "ready" and state.result.cache_hit
                            for state in self.window._sources.values()))
        self.assertEqual(self.backend_calls, 0)
        grid = self.window.slide_grid
        panel = self.window.output_panel

        def add(source, rows):
            self.window.source_panel.select_source(os.path.normcase(str(source)))
            selection = grid.view.selectionModel()
            selection.clearSelection()
            for row in rows:
                selection.select(grid.model.index(row, 0), QItemSelectionModel.SelectionFlag.Select)
            grid.add_button.click()

        add(a, [1])
        add(b, [3])
        add(a, [0])
        panel.select_rows([0])
        panel.actions["duplicate"].trigger()
        self.assertEqual(panel.selected_rows(), [1])
        mime = panel.model.mimeData([panel.model.index(1, 0)])
        self.assertTrue(panel.model.dropMimeData(mime, Qt.DropAction.MoveAction, 4, 0, QModelIndex()))
        self.assertEqual([(slide.source_file_name, slide.slide_index) for slide in panel.output_slides],
                         [("A.pptx", 2), ("B.pptx", 4), ("A.pptx", 1), ("A.pptx", 2)])
        add(advanced, [0, 2, 8])
        for slide in panel.output_slides:
            self.assertTrue(Path(slide.thumbnail_path).is_file())
            info = self.window._sources[os.path.normcase(slide.source_file)].result.presentation
            self.assertEqual(slide, info.slides[slide.slide_index - 1])
        panel.select_rows([3])
        panel.view.horizontalScrollBar().setValue(0)
        grid.view.doItemsLayout()
        panel.view.doItemsLayout()
        QTest.qWait(80)
        self.assertTrue(self.window.grab().save(str(self.directory / "loaded.png")))
        self.window.resize(1000, 640)
        QTest.qWait(80)
        first_card = grid.view.visualRect(grid.model.index(0, 0))
        self.assertLessEqual(first_card.bottom(), grid.view.viewport().rect().bottom())
        self.assertTrue(self.window.grab().save(str(self.directory / "compact.png")))
        self.assertGreater(panel.view.horizontalScrollBar().maximum(), 0)
        desired = [asdict(slide) for slide in panel.output_slides]
        self.window.clear_sources()
        self.assertEqual(panel.model.rowCount(), 7)
        self.assertTrue(a.is_file() and b.is_file() and advanced.is_file())
        self.cases.append({"case": "real_cached_output_composer", "passed": True,
                           "source_slide_counts": [4, 4, 9], "output": desired,
                           "screenshots": ["empty.png", "loaded.png", "compact.png"]})


if __name__ == "__main__":
    unittest.main()
