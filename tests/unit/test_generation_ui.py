"""생성 준비·실행의 스레드 연결, 취소와 종료 시 UI 상태를 검증한다."""

from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from src.ppt.errors import GenerationError, check_cancel
from src.ppt.powerpoint_service import GenerationPlan, GenerationSource, GenerationResult, GenerationProgress
from src.ui.main_window import MainWindow
import test_ui as ui_fixture

wait_until = ui_fixture.wait_until


class FakeGeneration:
    def __init__(self):
        self.threads = []
        self.prepared = self.generated = None
        self.mixed = False
        self.fail = False

    def prepare(self, slides, output, *, overwrite=False, progress=None, cancel=None):
        self.threads.append(threading.get_ident())
        check_cancel(cancel)
        self.prepared = tuple(slides)
        source = GenerationSource(slides[0].source_file, "revision", 960, 540)
        sources = (source, GenerationSource("B.pptx", "revision", 720, 540)) if self.mixed else (source,)
        return GenerationPlan(tuple(slides), sources, str(output), None, overwrite)

    def generate(self, plan, *, allow_mixed_sizes=False, progress=None, cancel=None):
        self.threads.append(threading.get_ident())
        self.generated = plan
        for i in range(1, 21):
            time.sleep(0.01)
            check_cancel(cancel)
            progress(GenerationProgress("copying", i, 20))
        if self.fail:
            raise GenerationError("안내할 생성 오류")
        Path(plan.output_path).write_bytes(b"generated")
        return GenerationResult(plan.output_path, len(plan.slides))


class GenerationUiTests(unittest.TestCase):
    setUpClass = classmethod(ui_fixture.UiTests.setUpClass.__func__)
    load = ui_fixture.UiTests.load
    def setUp(self):
        ui_fixture.UiTests.setUp(self)
        self.generator = FakeGeneration()
        self.window._generation_factory = lambda: self.generator
        self.output = self.root / "output.pptx"
        self.load(self.a, self.b)
        self.window.output_panel.add_slides(self.window.slide_grid.model.slides[:2])

    def tearDown(self):
        if self.window.is_generating:
            self.window.cancel_loading()
            wait_until(lambda: not self.window.is_generating)
        ui_fixture.UiTests.tearDown(self)

    def test_generate_in_worker_and_keep_exact_snapshot(self):
        self.assertTrue(self.window.generate_button.isEnabled())
        self.assertTrue(self.window.start_generation(self.output))
        self.assertFalse(self.window.generate_button.isEnabled())
        self.assertFalse(self.window.output_panel.isEnabled())
        self.assertFalse(self.window.start_generation(self.output))
        wait_until(lambda: not self.window.is_generating)
        self.assertTrue(self.output.exists())
        self.assertEqual(self.generator.generated.slides, tuple(self.window.output_panel.output_slides))
        self.assertTrue(all(t != threading.get_ident() for t in self.generator.threads))
        self.assertEqual(self.window.last_generation_result.slide_count, 2)
        self.assertTrue(self.window.generate_button.isEnabled())
        self.assertTrue(self.window.output_panel.isEnabled())

    def test_cancel_keeps_sequence_and_no_output(self):
        before = self.window.output_panel.output_slides
        self.window.start_generation(self.output)
        wait_until(lambda: self.generator.generated is not None)
        self.window.cancel_loading()
        wait_until(lambda: not self.window.is_generating)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.window.output_panel.output_slides, before)
        self.assertIn("취소", self.window.status_text.text())

    def test_close_waits_for_generation_cleanup(self):
        self.window.start_generation(self.output)
        wait_until(lambda: self.generator.generated is not None)
        self.window.close()
        wait_until(lambda: not self.window.is_generating and not self.window.isVisible())
        self.assertTrue(self.window._closing)
        self.assertFalse(self.output.exists())

    def test_error_restores_editing_and_shows_message(self):
        self.generator.fail = True
        self.window.start_generation(self.output)
        wait_until(lambda: not self.window.is_generating)
        self.assertIn("안내할 생성 오류", self.window.notice.text())
        self.assertTrue(self.window.output_panel.isEnabled())
        self.assertFalse(self.output.exists())

    def test_mixed_size_rejects_before_generation(self):
        self.generator.mixed = True
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.No) as warning:
            self.window.start_generation(self.output)
            wait_until(lambda: not self.window.is_generating)
        warning.assert_called_once()
        self.assertIsNone(self.generator.generated)
        self.assertFalse(self.output.exists())

    def test_mixed_size_approved_generates(self):
        self.generator.mixed = True
        with patch.object(QMessageBox, "warning", return_value=QMessageBox.StandardButton.Yes):
            self.window.start_generation(self.output)
            wait_until(lambda: not self.window.is_generating)
        self.assertTrue(self.output.exists())

    def test_output_dialog_never_overwrites_loaded_original(self):
        with patch("src.ui.main_window.QFileDialog.getSaveFileName", return_value=(str(self.a), "")):
            self.window.choose_output()
        self.assertIn("원본", self.window.notice.text())
        self.assertFalse(self.window.is_generating)
        self.assertEqual(self.a.read_bytes(), b"fake")
