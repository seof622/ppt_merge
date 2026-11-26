"""저장 상태·작은 창 배치와 확대 작업 취소를 사용자 흐름으로 검증한다."""
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QColorDialog, QFileDialog, QPushButton
from shiboken6 import isValid
from src.ppt.errors import ThumbnailError, check_cancel
from src.ppt.powerpoint_service import GenerationResult
from src.models.slide_model import SlideBackground
from src.ui.main_window import MainWindow
from src.ui.slide_preview import open_preview
import test_ui as fixture
from test_generation_ui import FakeGeneration


class UiRefinementTests(unittest.TestCase):
    setUpClass = classmethod(fixture.UiTests.setUpClass.__func__)
    setUp = fixture.UiTests.setUp
    load = fixture.UiTests.load

    def tearDown(self):
        for dialog in tuple(self.window._preview_dialogs):
            dialog.close()
        fixture.wait_until(lambda: not self.window._preview_dialogs)
        self.window.close()
        fixture.wait_until(lambda: not self.window.isVisible())
        fixture.UiTests.tearDown(self)

    def test_ppt_dirty_state_survives_autosave_and_undo_restores_saved_snapshot(self):
        self.load(self.a)
        panel = self.window.output_panel
        panel.add_slides(self.window.slide_grid.model.slides)
        saved = self.root / 'saved.pptx'
        saved.write_bytes(b'saved')
        self.window._on_generated(GenerationResult(str(saved), 3))
        self.window._update_actions()
        panel.select_rows([1])
        panel.duplicate_selected()
        QTest.qWait(400)
        self.assertEqual(self.window.workspace_status._full_text, '작업 목록 저장됨')
        self.assertEqual(self.window.output_save_state.text(), 'PPT 변경 사항 있음')
        self.assertEqual(self.window.open_file_button.text(), '이전 생성본 열기')
        self.assertEqual(self.window.generate_button.text(), 'PPT 다시 생성')
        self.assertEqual(saved.read_bytes(), b'saved')
        self.window.undo_action.trigger()
        self.assertEqual(self.window.output_save_state.text(), 'PPT 생성 완료')
        self.assertEqual(self.window.generate_button.text(), 'PPT로 저장')

    def test_column_capacity_drives_layout_and_zoom_does_not_change_order(self):
        self.load(self.a)
        self.window.output_panel.add_slides(self.window.slide_grid.model.slides)
        before = self.window.output_panel.output_slides
        self.window.resize(1320, 720)
        QTest.qWait(90)
        self.assertTrue(self.window._compact)
        self.assertFalse(self.window.mode_buttons['both'].isVisible())
        self.window.resize(1600, 900)
        QTest.qWait(90)
        self.assertFalse(self.window._compact)
        self.assertTrue(self.window.slide_grid.isVisible())
        self.assertTrue(self.window.output_panel.isVisible())
        self.window.slide_grid.zoom.setValue(300)
        self.window.output_panel.zoom.setValue(280)
        QTest.qWait(90)
        self.assertTrue(self.window._compact)
        self.assertEqual(self.window.output_panel.output_slides, before)

    def test_small_window_gives_slides_more_height_and_status_real_insets(self):
        self.load(self.a)
        self.window.resize(1000, 640)
        self.window.set_workspace_mode('source')
        QTest.qWait(90)
        grid = self.window.slide_grid
        self.assertGreaterEqual(grid.view.viewport().height(), 240)
        self.assertTrue(grid.view.viewport().rect().contains(grid.view.visualRect(grid.model.index(2, 0))))
        self.assertFalse(grid.hint.isVisible())
        point = self.window.status_text.mapTo(self.window, QPoint(0, 0))
        self.assertGreaterEqual(point.x(), 20)
        self.assertGreaterEqual(self.window.height() - point.y() - self.window.status_text.height(), 8)

    def test_empty_state_has_add_action_and_hides_unused_controls(self):
        grid = self.window.slide_grid
        self.assertTrue(grid.empty_add_button.isVisible())
        self.assertFalse(grid.search.isVisible())
        self.assertFalse(grid.footer_controls.isVisible())
        self.assertFalse(self.window.output_panel.selection_toolbar.isVisible())
        with patch.object(QFileDialog, 'getOpenFileNames', return_value=([], '')) as picker:
            grid.empty_add_button.click()
            picker.assert_called_once()

    def test_selected_long_filename_is_available_and_list_preserves_suffix(self):
        source = self.root / ('비슷한_업무명_' * 5 + '2026_확정.pptx')
        source.write_bytes(b'fake')
        self.load(source)
        panel = self.window.source_panel
        self.assertEqual(panel.list.textElideMode(), Qt.TextElideMode.ElideMiddle)
        self.assertEqual(panel.selected_name.text(), source.name)
        self.assertEqual(panel.selected_name.toolTip(), str(source.resolve()))
        self.assertTrue(panel.selected_name.isVisible())

    def test_output_background_scope_undo_restore_and_autosave(self):
        self.load(self.a)
        panel = self.window.output_panel
        first, second, _ = self.window.slide_grid.model.slides
        panel.add_slides((first, first, second))
        panel.select_rows([1])
        selected_menu, all_menu = [action.menu() for action in panel.background_button.menu().actions()]
        with patch.object(QColorDialog, 'getColor', return_value=QColor('#D25A24')):
            selected_menu.actions()[0].trigger()
        self.assertEqual([item.background.color if item.background else None for item in panel.output_slides],
                         [None, '#D25A24', None])
        self.assertEqual(panel.selected_rows(), [1])
        self.assertIsNone(self.window.slide_grid.model.slides[0].background)

        image = self.root / '배경.png'
        Image.new('RGB', (128, 72), '#346854').save(image)
        with patch.object(QFileDialog, 'getOpenFileName', return_value=(str(image), '')):
            all_menu.actions()[1].trigger()
        background = panel.output_slides[0].background
        self.assertEqual([item.background for item in panel.output_slides], [background] * 3)
        self.assertEqual(Path(background.image_path).read_bytes(), image.read_bytes())
        self.assertNotEqual(Path(background.image_path), image)

        panel.model.undo_stack.undo()
        self.assertEqual(panel.output_slides[1].background.color, '#D25A24')
        panel.model.undo_stack.redo()
        self.window._save_workspace()
        self.assertEqual(self.window._workspace_store.load()[1], panel.output_slides)
        selected_menu.actions()[-1].trigger()
        self.assertEqual([item.background for item in panel.output_slides], [background, None, background])
        all_menu.actions()[-1].trigger()
        self.assertEqual([item.background for item in panel.output_slides], [None, None, None])

    def test_background_change_refreshes_the_card_and_zoom_fallback(self):
        path = self.root / 'background-result.png'
        Image.new('RGB', (480, 270), '#C85A30').save(path)

        class BackgroundPreviewService:
            def load_background_previews(self, slides, cancel=None):
                for slide in slides:
                    yield slide, str(path)

        self.window.close()
        self.window.deleteLater()
        self.window = MainWindow(self.root / 'cache', self.factory,
                                 background_preview_factory=BackgroundPreviewService)
        self.window.show()
        self.window.set_workspace_mode('result')
        self.load(self.a)
        panel = self.window.output_panel
        panel.add_slides(self.window.slide_grid.model.slides)
        panel.select_rows([0])
        panel._change_background(SlideBackground(color='#C85A30'), False)
        changed = panel.output_slides[0]
        fixture.wait_until(lambda: panel.model.background_thumbnail(changed) is not None)
        fixture.wait_until(lambda: not self.window._background_previews.is_running)
        index = panel.model.index(0, 0)
        icon = panel.model.data(index, Qt.ItemDataRole.DecorationRole)
        self.assertEqual(icon.pixmap(160, 90).toImage().pixelColor(10, 10).name(), '#c85a30')
        dialog = open_preview(panel.view)
        self.assertEqual(dialog.image.pixmap().toImage().pixelColor(10, 10).name(), '#c85a30')
        self.assertEqual(dialog.quality.text(), '배경 미리보기')
        dialog.close()
        panel.model.undo_stack.undo()
        icon = panel.model.data(panel.model.index(0, 0), Qt.ItemDataRole.DecorationRole)
        self.assertEqual(icon.pixmap(160, 90).toImage().pixelColor(10, 10).name(), '#dbeafe')

    def test_saving_takes_priority_over_active_background_cards(self):
        started = threading.Event()
        cleaned = threading.Event()
        resume = threading.Event()
        generator = FakeGeneration()

        class BackgroundPreviewService:
            def load_background_previews(self, slides, cancel=None):
                if not started.is_set():
                    started.set()
                    try:
                        resume.wait(5)
                        check_cancel(cancel)
                    finally:
                        cleaned.set()
                for slide in slides:
                    yield slide, slide.thumbnail_path

        self.window.close()
        self.window.deleteLater()
        self.window = MainWindow(self.root / 'cache', self.factory, lambda: generator,
                                 background_preview_factory=BackgroundPreviewService)
        self.window.show()
        self.load(self.a)
        panel = self.window.output_panel
        panel.add_slides(self.window.slide_grid.model.slides)
        panel._change_background(SlideBackground(color='#C85A30'), True)
        output = self.root / 'result.pptx'
        try:
            fixture.wait_until(started.is_set)
            self.assertTrue(self.window.generate_button.isEnabled())
            self.assertTrue(self.window.start_generation(output))
            self.assertTrue(self.window.is_generating)
            self.assertIsNone(generator.prepared)
        finally:
            resume.set()
        fixture.wait_until(lambda: not self.window.is_generating)
        self.assertTrue(cleaned.is_set())
        self.assertTrue(output.exists())
        self.assertEqual(generator.generated.slides, tuple(panel.output_slides))

    def preview(self, factory):
        self.load(self.a)
        self.window._preview_factory = factory
        self.window.slide_grid.view.setCurrentIndex(self.window.slide_grid.model.index(0, 0))
        return open_preview(self.window.slide_grid.view)

    def test_close_parent_waits_for_preview_worker_cleanup(self):
        started = threading.Event()
        cleaned = threading.Event()
        class Service:
            def load_preview(self, slide, cancel=None):
                started.set()
                try:
                    while True:
                        check_cancel(cancel)
                        time.sleep(.005)
                finally:
                    cleaned.set()
        dialog = self.preview(Service)
        fixture.wait_until(started.is_set)
        self.assertTrue(self.window.is_busy)
        self.window.close()
        self.assertFalse(dialog.isVisible())
        fixture.wait_until(lambda: not self.window.isVisible())
        self.assertTrue(cleaned.is_set())
        self.assertFalse(self.window._preview_dialogs)

    def test_closing_output_preview_releases_modal_window_before_worker_cleanup(self):
        self.load(self.a)
        panel = self.window.output_panel
        panel.add_slides(self.window.slide_grid.model.slides)
        panel.select_rows([0])
        for action in ('button', 'escape'):
            with self.subTest(action=action):
                started = threading.Event()
                finish_cleanup = threading.Event()
                image = self.root / 'reopened-preview.png'
                Image.new('RGB', (1600, 900), '#b0c080').save(image)

                class Service:
                    def load_preview(self, slide, cancel=None):
                        if slide.slide_index == 1:
                            started.set()
                            finish_cleanup.wait(5)
                            check_cancel(cancel)
                        return str(image)

                self.window._preview_factory = Service
                dialog = open_preview(panel.view)
                try:
                    fixture.wait_until(started.is_set)
                    if action == 'button':
                        close = next(button for button in dialog.findChildren(QPushButton)
                                     if button.text() == '닫기 · Esc')
                        close.click()
                    else:
                        QTest.keyClick(dialog, Qt.Key.Key_Escape)
                    self.assertFalse(dialog.isVisible())
                    self.assertIsNone(self.app.activeModalWidget())
                    self.assertTrue(self.window.isVisible())
                    self.assertTrue(self.window.is_busy)
                    self.assertFalse(self.window.generate_button.isEnabled())
                    self.assertTrue(isValid(dialog))

                    panel.select_rows([1])
                    reopened = open_preview(panel.view)
                    self.assertTrue(reopened.isVisible())
                    self.assertEqual(reopened.quality.text(), '기본 미리보기')
                finally:
                    finish_cleanup.set()

                fixture.wait_until(lambda: reopened.quality.text() == '고해상도 미리보기')
                fixture.wait_until(lambda: not self.window.is_busy and not isValid(dialog))
                reopened.close()
                self.assertTrue(self.window.generate_button.isEnabled())
                panel.select_rows([0])

    def test_navigation_cancels_old_preview_and_only_displays_current_slide(self):
        started = threading.Event()
        image = self.root / 'high-resolution.png'
        Image.new('RGB', (1600, 900), '#b0c080').save(image)
        class Service:
            def load_preview(self, slide, cancel=None):
                if slide.slide_index == 1:
                    started.set()
                    while True:
                        check_cancel(cancel)
                        time.sleep(.005)
                return str(image)
        dialog = self.preview(Service)
        fixture.wait_until(started.is_set)
        dialog.move(1)
        fixture.wait_until(lambda: not dialog.is_loading)
        self.assertEqual(dialog.row, 1)
        self.assertEqual(dialog.quality.text(), '고해상도 미리보기')
        self.assertNotIn(dialog.slides[0], dialog._high_resolution)
        self.assertIn(dialog.slides[1], dialog._high_resolution)

    def test_preview_failure_keeps_cached_image_and_explains_fallback(self):
        class Service:
            def load_preview(self, slide, cancel=None):
                raise ThumbnailError('PowerPoint를 닫은 뒤 다시 시도하세요.')
        dialog = self.preview(Service)
        fixture.wait_until(lambda: '기본 미리보기 표시 중' in dialog.quality.text())
        self.assertFalse(dialog.image.pixmap().isNull())
        self.assertIn('PowerPoint', dialog.quality.text())


if __name__ == '__main__':
    unittest.main()
