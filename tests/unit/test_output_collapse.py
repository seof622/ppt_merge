"""하단 영역의 비율 높이와 버튼·splitter 접기/복원 동작."""

import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.main import configure_application
from src.models.slide_model import SlideItem
from src.ui.main_window import MainWindow


class OutputCollapseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        configure_application(cls.app)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.window = MainWindow(Path(self.temp.name) / "cache")
        self.window.show()
        QTest.qWait(30)

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        self.temp.cleanup()

    def assert_default_height(self):
        expected = round(self.window.height() * 0.30)
        self.assertAlmostEqual(self.window.composer.sizes()[1], expected, delta=2)

    def test_default_tracks_window_height_at_different_sizes(self):
        for height in (640, 900, 1100):
            self.window.resize(1600, height)
            QTest.qWait(30)
            self.assert_default_height()

    def test_button_collapse_survives_resize_and_restores_default_with_selection(self):
        item = SlideItem(str(Path(self.temp.name) / "A.pptx"), "A.pptx", 1, 256)
        self.window.output_panel.add_slides([item, item])
        self.window.output_panel.select_rows([1])
        self.assertEqual(self.window.output_toggle_button.objectName(), "outputToggleButton")
        self.assertEqual(self.window.output_toggle_button.parentWidget(), self.window.output_panel)
        self.assertEqual(self.window.output_toggle_button.geometry().center().y(),
                         self.window.output_panel.count.geometry().center().y())
        self.assertLess(self.window.output_toggle_button.geometry().right(),
                        self.window.output_panel.count.geometry().left())
        QTest.mouseClick(self.window.output_toggle_button, Qt.MouseButton.LeftButton)
        self.assertEqual(self.window.composer.sizes()[1], 0)
        self.assertEqual(self.window.output_toggle_action.text(), "결과물 펼치기")
        self.assertEqual(self.window.output_panel.height(), 0)
        self.assertTrue(self.window.collapsed_output_toggle_button.isVisible())
        self.assertTrue(self.window.generate_button.isVisible())
        self.assertEqual(self.window.output_panel.footer.contentsMargins().top(), 8)
        self.assertEqual(self.window.collapsed_output_toggle_button.geometry().top(), 8)
        self.assertEqual(self.window.generate_button.geometry().right(),
                         self.window.output_panel.footer_widget.width() - 17)
        self.window.resize(1400, 1000)
        QTest.qWait(30)
        self.assertEqual(self.window.composer.sizes()[1], 0)
        QTest.mouseClick(self.window.collapsed_output_toggle_button, Qt.MouseButton.LeftButton)
        self.assert_default_height()
        self.assertEqual(self.window.output_panel.output_slides, [item, item])
        self.assertEqual(self.window.output_panel.selected_rows(), [1])
        self.assertEqual(self.window.output_toggle_action.text(), "결과물 접기")
        self.assertTrue(self.window.output_toggle_button.isVisible())
        self.assertFalse(self.window.collapsed_output_toggle_button.isVisible())

    def test_drag_can_shrink_below_old_minimum_and_collapse_then_button_restores(self):
        splitter = self.window.composer
        handle = splitter.handle(1)
        QTest.mousePress(handle, Qt.MouseButton.LeftButton, pos=handle.rect().center())
        QTest.mouseMove(handle, QPoint(handle.width() // 2, handle.height() // 2 + 190))
        QTest.mouseRelease(handle, Qt.MouseButton.LeftButton, pos=handle.rect().center())
        QTest.qWait(10)
        self.assertGreater(splitter.sizes()[1], 0)
        self.assertLess(splitter.sizes()[1], 182)
        QTest.mousePress(handle, Qt.MouseButton.LeftButton, pos=handle.rect().center())
        QTest.mouseMove(handle, QPoint(handle.width() // 2, splitter.height()))
        QTest.mouseRelease(handle, Qt.MouseButton.LeftButton, pos=handle.rect().center())
        QTest.qWait(10)
        self.assertEqual(splitter.sizes()[1], 0)
        self.assertEqual(self.window.output_toggle_action.text(), "결과물 펼치기")
        self.window.collapsed_output_toggle_button.click()
        self.assert_default_height()

    def test_button_collapses_any_custom_height(self):
        for height in (40, 150, 350):
            available = self.window.composer.height() - self.window.composer.handleWidth()
            self.window.composer.moveSplitter(available - height, 1)
            self.assertAlmostEqual(self.window.composer.sizes()[1], height, delta=2)
            self.window.output_toggle_button.click()
            self.assertEqual(self.window.composer.sizes()[1], 0)
            self.window.collapsed_output_toggle_button.click()
            self.assert_default_height()
