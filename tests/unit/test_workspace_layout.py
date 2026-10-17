"""세로 패널 구성과 좁은 작업 영역의 편집·결과 열기 동작."""

import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.main import configure_application
from src.models.slide_model import SlideItem
from src.ppt.powerpoint_service import GenerationResult
from src.ui.main_window import MainWindow


class WorkspaceLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        configure_application(cls.app)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.window = MainWindow(self.root / "cache")
        self.window.show()
        QTest.qWait(50)

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        self.temp.cleanup()

    def bounds(self, widget):
        rect = widget.rect()
        rect.moveTopLeft(widget.mapTo(self.window, QPoint(0, 0)))
        return rect

    def test_sidebars_keep_full_height_when_preview_collapses(self):
        for width, height in ((1600, 900), (1000, 640)):
            self.window.resize(width, height)
            QTest.qWait(60)
            source = self.bounds(self.window.source_panel)
            originals = self.bounds(self.window.originals_panel)
            workspace = self.bounds(self.window.workspace)
            self.assertLess(source.right(), originals.left())
            self.assertLess(originals.right(), workspace.left())
            self.assertEqual(source.bottom(), workspace.bottom())
            self.assertEqual(originals.bottom(), workspace.bottom())
            self.window.output_toggle_button.click()
            QTest.qWait(30)
            self.assertEqual(self.bounds(self.window.source_panel), source)
            self.assertEqual(self.bounds(self.window.originals_panel), originals)
            self.window.collapsed_output_toggle_button.click()

    def test_move_commands_remain_available_in_compact_menu(self):
        panel = self.window.output_panel
        slides = [SlideItem(str(self.root / "A.pptx"), "A.pptx", i, 255 + i)
                  for i in (1, 2, 3)]
        panel.add_slides(slides)
        panel.select_rows([1])
        self.window.resize(1000, 640)
        QTest.qWait(80)
        self.assertTrue(panel.more_button.isVisible())
        self.assertFalse(panel.tool_buttons["up"].isVisible())
        self.assertIn(panel.actions["up"], panel.more_button.menu().actions())
        panel.actions["up"].trigger()
        self.assertEqual([slide.slide_index for slide in panel.output_slides], [2, 1, 3])
        self.window.resize(1600, 900)
        QTest.qWait(80)
        self.assertTrue(panel.tool_buttons["up"].isVisible())
        self.assertFalse(panel.more_button.isVisible())

    def test_result_controls_fit_small_window_expanded_and_collapsed(self):
        saved = self.root / "결과.pptx"
        saved.write_bytes(b"fixture")
        self.window._on_generated(GenerationResult(str(saved), 1))
        self.window._update_actions()
        self.window.resize(1000, 640)
        QTest.qWait(80)
        self.assertEqual(self.window.width(), 1000)
        for collapsed in (False, True):
            if collapsed:
                self.window.output_toggle_button.click()
                QTest.qWait(50)
            controls = [self.window.open_file_button, self.window.open_output_button,
                        self.window.generate_button]
            if collapsed:
                controls.insert(0, self.window.collapsed_output_toggle_button)
            footer = self.bounds(self.window.output_panel.footer_widget)
            for button in controls:
                self.assertTrue(button.isVisible())
                self.assertTrue(footer.contains(self.bounds(button)))
            for left, right in zip(controls, controls[1:]):
                self.assertLess(self.bounds(left).right(), self.bounds(right).left())


if __name__ == "__main__":
    unittest.main()
