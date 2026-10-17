"""창 재실행 후 경로 복원과 성공·취소·실패 시의 저장 기준을 검증한다."""

from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QMessageBox

from src.ui.main_window import MainWindow
from src.utils.path_preferences import PathPreferences
import test_generation_ui as generation_fixture
import test_ui as ui_fixture


class PathPreferencesTests(unittest.TestCase):
    setUpClass = classmethod(ui_fixture.UiTests.setUpClass.__func__)
    setUp = ui_fixture.UiTests.setUp
    tearDown = generation_fixture.GenerationUiTests.tearDown
    load = ui_fixture.UiTests.load

    def restart(self):
        self.window.close()
        self.app.processEvents()
        self.window = MainWindow(self.root / "cache", self.factory)
        self.window.show()
        self.app.processEvents()

    def dialog_default(self):
        with patch("src.ui.main_window.QFileDialog.getSaveFileName", return_value=("", "")) as dialog:
            self.window.choose_output()
        return dialog.call_args.args[2]

    def generate(self, output):
        self.window.start_generation(output)
        ui_fixture.wait_until(lambda: not self.window.is_generating)

    def prepare_generation(self):
        self.load(self.a)
        self.window.output_panel.add_slides(self.window.slide_grid.model.slides[:1])
        self.generator = generation_fixture.FakeGeneration()
        self.window._generation_factory = lambda: self.generator

    def test_first_run_keeps_default_and_does_not_create_settings(self):
        self.assertEqual(self.dialog_default(), "result.pptx")
        self.assertFalse((self.root / "settings.ini").exists())

    def test_root_picker_persists_to_disk_and_restores_on_restart(self):
        chosen = self.root / "한글 폴더"
        chosen.mkdir()
        with patch("src.ui.main_window.QFileDialog.getExistingDirectory", return_value=str(chosen)):
            self.window.choose_files()
        # 별도 Python 프로세스로도 읽어 같은 프로세스의 QSettings 캐시에 의존하지 않는다.
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-c",
             "import sys; from pathlib import Path; "
             "from src.utils.path_preferences import PathPreferences; "
             "print(PathPreferences(Path(sys.argv[1])).root_path)", str(self.root / "settings.ini")],
            capture_output=True, text=True, encoding="utf-8", check=True)
        self.assertEqual(Path(result.stdout.strip()), chosen)
        self.restart()
        self.assertEqual(self.window.source_panel.root_path, chosen)
        self.assertEqual(self.window.root_label.toolTip(), str(chosen))
        self.assertEqual(self.window._sources, {})

    def test_cancelled_root_picker_preserves_previous_root(self):
        self.window.source_panel.set_root(self.root)
        with patch("src.ui.main_window.QFileDialog.getExistingDirectory", return_value=""):
            self.window.choose_files()
        self.restart()
        self.assertEqual(self.window.source_panel.root_path, self.root)

    def test_missing_root_uses_default_and_keeps_saved_preference(self):
        default = self.window.source_panel.root_path
        missing = self.root / "삭제된 폴더"
        preferences = PathPreferences(self.root / "settings.ini")
        preferences.remember_root(str(missing))
        self.restart()
        self.assertEqual(self.window.source_panel.root_path, default)
        self.assertEqual(preferences.root_path, str(missing))

    def test_success_restores_full_output_path_even_if_file_was_deleted(self):
        self.prepare_generation()
        directory = self.root / "저장 폴더"
        directory.mkdir()
        output = directory / "지난 발표 자료.pptx"
        self.generate(output)
        self.assertEqual(self.dialog_default(), str(output))
        output.unlink()
        self.restart()
        self.assertEqual(self.dialog_default(), str(output))

    def test_missing_output_directory_keeps_filename_in_current_root(self):
        self.window.source_panel.set_root(self.root)
        missing = self.root / "삭제된 저장 폴더" / "지난 자료.pptx"
        PathPreferences(self.root / "settings.ini").remember_output(str(missing))
        self.restart()
        self.assertEqual(self.dialog_default(), str(self.root / missing.name))

    def test_cancel_failure_and_rejected_overwrite_preserve_last_success(self):
        self.prepare_generation()
        previous = self.root / "성공.pptx"
        self.generate(previous)
        next_output = self.root / "다음.pptx"
        self.window.start_generation(next_output)
        ui_fixture.wait_until(lambda: self.window._prepared_plan is not None
                              or self.generator.generated.output_path == str(next_output))
        self.window.cancel_loading()
        ui_fixture.wait_until(lambda: not self.window.is_generating)
        self.assertEqual(self.dialog_default(), str(previous))
        self.generator.fail = True
        self.generate(next_output)
        self.assertEqual(self.dialog_default(), str(previous))
        next_output.write_bytes(b"existing")
        with patch("src.ui.main_window.QFileDialog.getSaveFileName", return_value=(str(next_output), "")), \
                patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            self.window.choose_output()
        self.restart()
        self.assertEqual(self.dialog_default(), str(previous))
        self.assertEqual(next_output.read_bytes(), b"existing")

    def test_extension_is_remembered_and_overwrite_confirmation_is_kept(self):
        self.prepare_generation()
        output = self.root / "확장자 없는 이름"
        with patch("src.ui.main_window.QFileDialog.getSaveFileName", return_value=(str(output), "")):
            self.window.choose_output()
            ui_fixture.wait_until(lambda: not self.window.is_generating)
        output = output.with_suffix(".pptx")
        self.assertEqual(self.dialog_default(), str(output))
        with patch("src.ui.main_window.QFileDialog.getSaveFileName", return_value=(str(output), "")), \
                patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No) as confirm:
            self.window.choose_output()
        confirm.assert_called_once()
        self.assertFalse(self.window.is_generating)
