"""UX 상태 전환과 사용 흐름을 실제 Qt 이벤트 루프에서 검증한다."""

import os
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from src.ppt.powerpoint_service import GenerationProgress, GenerationResult
from src.ppt.thumbnail_service import ThumbnailProgress
from src.ui.slide_grid import ElidedLabel
import test_ui as ui_fixture
import test_generation_ui as generation_fixture

wait_until = ui_fixture.wait_until


class UxTests(unittest.TestCase):
    setUpClass = classmethod(ui_fixture.UiTests.setUpClass.__func__)
    setUp = ui_fixture.UiTests.setUp
    load = ui_fixture.UiTests.load

    def tearDown(self):
        if self.window.is_generating:
            self.window.cancel_loading()
            wait_until(lambda: not self.window.is_generating)
        ui_fixture.UiTests.tearDown(self)

    def prepare_generation(self):
        self.load(self.a)
        self.window.output_panel.add_slides(self.window.slide_grid.model.slides[:2])
        generator = generation_fixture.FakeGeneration()
        self.window._generation_factory = lambda: generator
        return generator

    def test_loading_cancel_ignores_late_progress_and_retry_resets_button(self):
        self.factory.delay = 0.08
        self.window.add_sources([self.a, self.b])
        wait_until(lambda: bool(self.factory.threads))
        self.window.cancel_loading()
        text = self.window.status_text.toolTip()
        self.window._on_progress(str(self.a), ThumbnailProgress(str(self.a), "exporting", 1, 3))
        self.assertEqual(self.window.status_text.toolTip(), text)
        self.assertEqual(self.window.cancel_button.text(), "취소 중…")
        self.assertFalse(self.window.cancel_button.isEnabled())
        wait_until(lambda: not self.window.is_loading)
        self.assertIn("취소 2개", self.window.status_text.toolTip())
        self.window.reload_selected()
        self.assertEqual(self.window.cancel_button.text(), "취소")
        wait_until(lambda: not self.window.is_loading)

    def test_generation_cancel_and_close_ignore_late_progress(self):
        generator = self.prepare_generation()
        output = self.root / "cancelled.pptx"
        self.window.start_generation(output)
        wait_until(lambda: generator.generated is not None)
        self.window.cancel_loading()
        text = self.window.status_text.toolTip()
        self.window._on_generation_progress(GenerationProgress("copying", 10, 20))
        self.assertEqual(self.window.status_text.toolTip(), text)
        self.assertEqual(self.window.cancel_button.text(), "취소 중…")
        self.window.close()
        closing = self.window.status_text.toolTip()
        self.window._on_generation_progress(GenerationProgress("saving", 0, 0))
        self.assertEqual(self.window.status_text.toolTip(), closing)
        wait_until(lambda: not self.window.is_generating and not self.window.isVisible())
        self.assertFalse(output.exists())

    def test_saved_folder_unicode_url_and_previous_success_after_failure(self):
        generator = self.prepare_generation()
        folder = self.root / "한글 저장 폴더"
        folder.mkdir()
        output = folder / "결과.pptx"
        self.window.start_generation(output)
        self.assertFalse(self.window.open_output_button.isVisible())
        wait_until(lambda: not self.window.is_generating)
        self.assertTrue(self.window.open_output_button.isVisible())
        self.assertIn(str(output), self.window.status_text.toolTip())
        with patch("src.ui.main_window.QDesktopServices.openUrl", return_value=True) as open_url:
            self.window.open_output_button.click()
        self.assertEqual(open_url.call_args.args[0].toLocalFile(), str(folder).replace("\\", "/"))
        generator.fail = True
        self.window.start_generation(folder / "failed.pptx")
        wait_until(lambda: not self.window.is_generating)
        self.assertIsNone(self.window.last_generation_result)
        self.assertTrue(self.window.open_output_button.isVisible())
        with patch("src.ui.main_window.QDesktopServices.openUrl", return_value=True) as open_url:
            self.window.open_output_button.click()
        self.assertEqual(open_url.call_args.args[0].toLocalFile(), str(folder).replace("\\", "/"))

    def test_saved_folder_failure_is_visible_without_losing_sequence(self):
        self.prepare_generation()
        self.window._on_generated(GenerationResult(str(self.root / "output.pptx"), 2))
        self.window._update_actions()
        before = self.window.output_panel.output_slides
        with patch("src.ui.main_window.QDesktopServices.openUrl", return_value=False):
            self.window.open_output_button.click()
        self.assertTrue(self.window.notice.isVisible())
        self.assertIn("폴더를 열지 못", self.window.notice.text())
        self.assertEqual(self.window.output_panel.output_slides, before)
        self.window._on_generated(GenerationResult(str(self.root / "missing" / "output.pptx"), 2))
        with patch("src.ui.main_window.QDesktopServices.openUrl") as open_url:
            self.window.open_output_button.click()
        open_url.assert_not_called()
        self.assertIn("폴더를 찾을 수", self.window.notice.text())

    def test_add_then_duplicate_shortcut_without_clicking_output(self):
        self.load(self.a)
        grid = self.window.slide_grid
        grid.view.setFocus()
        grid.view.setCurrentIndex(grid.model.index(0, 0))
        grid.add_button.click()
        QTest.qWait(10)
        self.assertTrue(self.window.output_panel.view.hasFocus())
        self.assertIn("1장 담음", self.window.status_text.toolTip())
        QTest.keyClick(self.window.output_panel.view, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(len(self.window.output_panel.output_slides), 2)
        self.assertIn("한 번 더 담음", self.window.status_text.toolTip())
        self.assertEqual(self.window.output_panel.output_slides[0], self.window.output_panel.output_slides[1])
        QTest.keyClick(self.window.output_panel.view, Qt.Key.Key_Delete)
        self.assertEqual(len(self.window.output_panel.output_slides), 1)
        self.assertIn("1장 삭제", self.window.status_text.toolTip())

    def test_edit_feedback_does_not_overwrite_active_loading(self):
        self.load(self.a)
        slides = self.window.slide_grid.model.slides[:1]
        self.factory.delay = 0.08
        self.window.add_sources([self.b])
        text = self.window.status_text.toolTip()
        self.window.output_panel.add_slides(slides)
        self.assertEqual(self.window.status_text.toolTip(), text)
        wait_until(lambda: not self.window.is_loading)

    def test_batch_position_and_failure_summary_survive_source_removal(self):
        failed = self.root / "failed.pptx"
        failed.write_bytes(b"fake")
        with self.assertLogs("ppt_merge.worker", level="ERROR"):
            self.load(self.a, failed, self.b)
        key = os.path.normcase(str(self.b))
        self.window._active = (os.path.normcase(str(self.a)), key)
        self.window._on_progress(str(self.b), ThumbnailProgress(str(self.b), "exporting", 2, 3))
        self.assertIn("파일 2/2", self.window.status_text.toolTip())
        self.window._active = ()
        self.window._sources[key].status = "ready"
        self.window.source_panel.select_source(key)
        self.window.remove_selected()
        self.assertIn("읽기 실패 1개", self.window.status_text.toolTip())
        for row in range(self.window.source_panel.list.count()):
            self.assertFalse(self.window.source_panel.list.item(row).icon().isNull())

    def test_elided_status_tooltip_tracks_latest_text(self):
        label = ElidedLabel("이전 상태")
        label.resize(40, 20)
        label.setToolTip("이전 파일 경로")
        label.setText("현재 상태를 보여 주는 긴 안내")
        self.assertEqual(label.toolTip(), "현재 상태를 보여 주는 긴 안내")
        self.assertNotEqual(label.text(), label.toolTip())

    def test_open_saved_file_uses_unicode_path_and_retains_previous_success(self):
        generator = self.prepare_generation()
        output = self.root / "한글 결과 파일.pptx"
        self.window.start_generation(output)
        self.assertFalse(self.window.open_file_button.isVisible())
        wait_until(lambda: not self.window.is_generating)
        self.assertTrue(self.window.open_file_button.isVisible())
        with patch("src.ui.main_window.QDesktopServices.openUrl", return_value=True) as open_url:
            self.window.open_file_button.click()
        self.assertEqual(open_url.call_args.args[0].toLocalFile(), str(output).replace("\\", "/"))
        self.assertIn("다시 생성하려면 PowerPoint를 닫", self.window.status_text.toolTip())
        generator.fail = True
        self.window.start_generation(self.root / "failed.pptx")
        wait_until(lambda: not self.window.is_generating)
        self.assertTrue(self.window.open_file_button.isVisible())
        with patch("src.ui.main_window.QDesktopServices.openUrl", return_value=True) as open_url:
            self.window.open_file_button.click()
        self.assertEqual(open_url.call_args.args[0].toLocalFile(), str(output).replace("\\", "/"))

    def test_open_saved_file_reports_missing_file_and_launch_failure(self):
        self.prepare_generation()
        output = self.root / "saved.pptx"
        output.write_bytes(b"fake")
        self.window._on_generated(GenerationResult(str(output), 2))
        self.window._update_actions()
        before = self.window.output_panel.output_slides
        with patch("src.ui.main_window.QDesktopServices.openUrl", return_value=False) as open_url:
            self.window.open_file_button.click()
        open_url.assert_called_once()
        self.assertIn("파일을 열지 못", self.window.notice.text())
        output.unlink()
        with patch("src.ui.main_window.QDesktopServices.openUrl") as open_url:
            self.window.open_file_button.click()
        open_url.assert_not_called()
        self.assertIn("파일을 찾을 수", self.window.notice.text())
        self.assertEqual(self.window.output_panel.output_slides, before)

    def test_open_saved_file_is_blocked_during_work_and_close(self):
        self.prepare_generation()
        self.window._on_generated(GenerationResult(str(self.a), 2))
        self.window._update_actions()
        self.window.start_generation(self.root / "next.pptx")
        self.assertFalse(self.window.open_file_button.isVisible())
        with patch("src.ui.main_window.QDesktopServices.openUrl") as open_url:
            self.window._open_output_file()
            open_url.assert_not_called()
        self.window.close()
        with patch("src.ui.main_window.QDesktopServices.openUrl") as open_url:
            self.window._open_output_file()
            open_url.assert_not_called()
        wait_until(lambda: not self.window.is_generating and not self.window.isVisible())
