"""실제 Qt 선택·키 입력·드롭 이벤트로 출력 편집의 연결을 검증한다."""

import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QItemSelectionModel, QMimeData, QModelIndex, QPoint, QPointF, QTimer, Qt
from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.main import configure_application
from src.ui.main_window import MainWindow
from src.ui.slide_mime import SLIDE_MIME, make_slide_mime
from test_ui import FakeServiceFactory, wait_until


class OutputUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        configure_application(cls.app)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.a = self.root / "한글 A.pptx"
        self.b = self.root / "B.pptm"
        for source in (self.a, self.b):
            source.write_bytes(b"original")
        image = self.root / "thumbnail.png"
        Image.new("RGB", (480, 270), "#dbeafe").save(image)
        self.window = MainWindow(self.root / "cache", FakeServiceFactory(image, delay=0))
        self.window.show()
        self.window.add_sources([self.a, self.b])
        wait_until(lambda: not self.window.is_loading)
        self.panel = self.window.output_panel
        QTest.qWait(30)

    def tearDown(self):
        if self.window.is_loading:
            self.window.cancel_loading()
            wait_until(lambda: not self.window.is_loading)
        self.window.close()
        self.app.processEvents()
        self.temporary.cleanup()

    def source_select(self, rows):
        grid = self.window.slide_grid
        grid.view.selectionModel().clearSelection()
        for row in rows:
            grid.view.selectionModel().select(grid.model.index(row, 0), QItemSelectionModel.SelectionFlag.Select)

    def numbers(self):
        return [(slide.source_file_name, slide.slide_index) for slide in self.panel.output_slides]

    def source_mime(self, rows):
        model = self.window.slide_grid.model
        return model.mimeData([model.index(row, 0) for row in rows])

    def drop(self, mime, action, position):
        viewport = self.panel.view.viewport()
        enter = QDragEnterEvent(position, action, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(viewport, enter)
        if not enter.isAccepted():
            return False
        move = QDragMoveEvent(position, action, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(viewport, move)
        event = QDropEvent(QPointF(position), action, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(viewport, event)
        self.app.processEvents()
        return event.isAccepted()

    def add_all(self):
        self.source_select([0, 1, 2])
        self.window.slide_grid.add_button.click()

    def test_add_button_cross_source_and_repeated_slide(self):
        self.source_select([2, 0])
        self.window.slide_grid.add_button.click()
        self.window.source_panel.select_source(os.path.normcase(str(self.b)))
        self.source_select([1])
        self.window.slide_grid.add_button.click()
        self.window.slide_grid.add_button.click()
        self.assertEqual(self.numbers(), [(self.a.name, 1), (self.a.name, 3), (self.b.name, 2), (self.b.name, 2)])
        self.assertEqual(self.panel.selected_rows(), [3])

    def test_source_double_click_adds_clicked_slide(self):
        view = self.window.slide_grid.view
        view.doItemsLayout()
        position = view.visualRect(view.model().index(1, 0)).center()
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, position)
        QTest.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, position)
        self.assertEqual(self.numbers(), [(self.a.name, 2)])

    def test_source_drop_into_empty_and_between_output_items(self):
        self.assertTrue(self.drop(self.source_mime([0, 2]), Qt.DropAction.CopyAction, QPoint(30, 50)))
        self.assertEqual(self.numbers(), [(self.a.name, 1), (self.a.name, 3)])
        view = self.panel.view
        view.doItemsLayout()
        position = view.visualRect(view.model().index(1, 0)).topLeft() + QPoint(3, 50)
        self.assertTrue(self.drop(self.source_mime([1]), Qt.DropAction.CopyAction, position))
        self.assertEqual(self.numbers(), [(self.a.name, 1), (self.a.name, 2), (self.a.name, 3)])
        self.assertEqual(self.window.slide_grid.model.rowCount(), 3)

    def test_output_drop_moves_discontiguous_rows_once(self):
        self.add_all()
        self.add_all()
        model = self.panel.model
        mime = model.mimeData([model.index(1, 0), model.index(3, 0)])
        self.assertTrue(model.dropMimeData(mime, Qt.DropAction.MoveAction, 6, 0, QModelIndex()))
        self.assertEqual([slide.slide_index for slide in self.panel.output_slides], [1, 3, 2, 3, 2, 1])
        self.assertEqual(self.panel.selected_rows(), [4, 5])
        view = self.panel.view
        view.horizontalScrollBar().setValue(0)
        view.doItemsLayout()
        mime = model.mimeData([model.index(4, 0), model.index(5, 0)])
        self.assertTrue(self.drop(mime, Qt.DropAction.MoveAction, QPoint(10, 50)))
        self.assertEqual([slide.slide_index for slide in self.panel.output_slides], [2, 1, 1, 3, 2, 3])
        self.assertEqual(model.rowCount(), 6)

    def test_stale_wrong_window_and_malformed_drop_rejected(self):
        self.add_all()
        model = self.panel.model
        stale = model.mimeData([model.index(0, 0)])
        self.panel.add_slides([self.panel.output_slides[0]])
        self.assertFalse(model.dropMimeData(stale, Qt.DropAction.MoveAction, 0, 0, QModelIndex()))
        foreign = make_slide_mime("other-window", tuple(self.panel.output_slides))
        self.assertFalse(self.drop(foreign, Qt.DropAction.CopyAction, QPoint(10, 50)))
        malformed = QMimeData()
        malformed.setData(SLIDE_MIME, b"{broken")
        self.assertFalse(model.dropMimeData(malformed, Qt.DropAction.CopyAction, 0, 0, QModelIndex()))
        self.assertEqual(model.rowCount(), 4)

    def test_duplicate_delete_and_shortcuts_apply_to_occurrences(self):
        self.add_all()
        self.panel.select_rows([0, 2])
        self.panel.view.setFocus()
        QTest.keyClick(self.panel.view, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual([slide.slide_index for slide in self.panel.output_slides], [1, 1, 2, 3, 3])
        self.assertEqual(self.panel.selected_rows(), [1, 4])
        QTest.keyClick(self.panel.view, Qt.Key.Key_Delete)
        self.assertEqual([slide.slide_index for slide in self.panel.output_slides], [1, 2, 3])
        self.window.slide_grid.view.setFocus()
        QTest.keyClick(self.window.slide_grid.view, Qt.Key.Key_Delete)
        self.assertEqual(self.panel.model.rowCount(), 3)

    def test_moves_reselect_same_occurrences_and_update_numbers(self):
        self.add_all()
        self.panel.select_rows([2])
        self.panel.actions["first"].trigger()
        self.assertEqual([slide.slide_index for slide in self.panel.output_slides], [3, 1, 2])
        self.assertEqual(self.panel.selected_rows(), [0])
        self.assertFalse(self.panel.actions["up"].isEnabled())
        self.panel.actions["down"].trigger()
        self.assertEqual(self.panel.selected_rows(), [1])
        self.panel.actions["last"].trigger()
        self.assertEqual([slide.slide_index for slide in self.panel.output_slides], [1, 2, 3])
        self.assertEqual(self.panel.selected_rows(), [2])
        self.assertIn("3 ·", self.panel.model.data(self.panel.model.index(2, 0)))
        self.panel.clear_button.click()
        self.assertEqual(self.panel.output_slides, [])
        self.assertFalse(self.panel.clear_button.isEnabled())

    def test_output_ctrl_shift_selection(self):
        self.add_all()
        view = self.panel.view
        view.doItemsLayout()
        points = [view.visualRect(view.model().index(row, 0)).center() for row in range(3)]
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, points[0])
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, points[2])
        self.assertEqual(self.panel.selected_rows(), [0, 2])
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, points[0])
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, points[2])
        self.assertEqual(self.panel.selected_rows(), [0, 1, 2])

    def test_removing_sources_preserves_output_and_files(self):
        self.add_all()
        self.window.remove_action.trigger()
        self.window.clear_action.trigger()
        self.assertEqual(self.window.source_panel.list.count(), 0)
        self.assertEqual(self.panel.model.rowCount(), 3)
        self.panel.select_rows([1])
        self.panel.remove_selected()
        self.assertEqual(self.panel.model.rowCount(), 2)
        self.assertEqual(self.a.read_bytes(), b"original")
        self.assertEqual(self.b.read_bytes(), b"original")
        self.assertFalse(self.window.slide_grid.add_button.isEnabled())

    def test_context_menus_preserve_multiple_selection(self):
        grid = self.window.slide_grid
        self.source_select([0, 2])
        grid.view.doItemsLayout()

        def choose_source_action():
            menu = self.app.activePopupWidget()
            menu.actions()[0].trigger()
            menu.close()

        QTimer.singleShot(20, choose_source_action)
        grid._context_menu(grid.view.visualRect(grid.model.index(0, 0)).center())
        self.assertEqual([slide.slide_index for slide in self.panel.output_slides], [1, 3])
        self.panel.select_rows([0, 1])
        self.panel.view.doItemsLayout()

        def choose_output_action():
            menu = self.app.activePopupWidget()
            self.panel.actions["duplicate"].trigger()
            menu.close()

        QTimer.singleShot(20, choose_output_action)
        self.panel._context_menu(self.panel.view.visualRect(self.panel.model.index(1, 0)).center())
        self.assertEqual([slide.slide_index for slide in self.panel.output_slides], [1, 1, 3, 3])


if __name__ == "__main__":
    unittest.main()
