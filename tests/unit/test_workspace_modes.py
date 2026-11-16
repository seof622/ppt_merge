"""나란히 보기와 집중 편집 사이에서 순서·선택·저장 버튼을 유지한다."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from src.main import configure_application
from src.models.slide_model import SlideItem
from src.ui.main_window import MainWindow


class WorkspaceModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        configure_application(cls.app)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.window = MainWindow(Path(self.temp.name)/'cache')
        self.window.show()
        QTest.qWait(30)

    def tearDown(self):
        self.window.close()
        self.app.processEvents()
        self.temp.cleanup()

    def test_wide_workspace_shows_both_panels_at_full_height(self):
        for height in (640, 900):
            self.window.resize(1600, height)
            QTest.qWait(30)
            self.assertTrue(self.window.slide_grid.isVisible())
            self.assertTrue(self.window.output_panel.isVisible())
            self.assertEqual(self.window.slide_grid.height(), self.window.output_panel.height())

    def test_focused_result_retains_selected_occurrence_and_save_button(self):
        item=SlideItem('A.pptx','A.pptx',1,256)
        self.window.output_panel.add_slides([item,item])
        self.window.output_panel.select_rows([1])
        self.window.output_toggle_button.click()
        self.assertFalse(self.window.slide_grid.isVisible())
        self.assertTrue(self.window.output_panel.isVisible())
        self.assertTrue(self.window.generate_button.isVisible())
        self.window.mode_buttons['both'].click()
        self.assertTrue(self.window.slide_grid.isVisible())
        self.assertEqual(self.window.output_panel.selected_rows(),[1])
        self.assertEqual(self.window.output_panel.output_slides,[item,item])

    def test_narrow_window_switches_views_and_returns_to_wide_layout(self):
        self.window.resize(1000,640)
        QTest.qWait(30)
        self.assertTrue(self.window.slide_grid.isVisible())
        self.assertFalse(self.window.output_panel.isVisible())
        self.window.mode_buttons['result'].click()
        self.assertFalse(self.window.slide_grid.isVisible())
        self.assertTrue(self.window.output_panel.isVisible())
        self.window.resize(1600,900)
        QTest.qWait(30)
        self.assertTrue(self.window.slide_grid.isVisible())
        self.assertTrue(self.window.output_panel.isVisible())

    def test_panel_resize_does_not_change_sequence(self):
        items=[SlideItem('A.pptx','A.pptx',n,255+n) for n in range(1,4)]
        self.window.output_panel.add_slides(items)
        self.window.composer.moveSplitter(400,1)
        self.window.output_toggle_button.click()
        self.window.mode_buttons['both'].click()
        self.assertEqual(self.window.output_panel.output_slides,items)
