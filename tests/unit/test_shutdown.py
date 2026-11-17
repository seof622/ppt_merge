"""실제 앱 진입점의 정상 종료를 별도 프로세스 종료 코드까지 검증한다."""

import os
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]

SMOKE = """
import ctypes
import logging
import sys
import tempfile
from pathlib import Path
if sys.platform == 'win32':
    ctypes.windll.kernel32.SetErrorMode(3)
from PIL import Image
from PySide6.QtCore import QTimer
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QDragEnterEvent
from PySide6.QtWidgets import QApplication
import src.main as entry
from src.ui.main_window import MainWindow
from src.ui.slide_preview import SlidePreview
from test_ui import FakeServiceFactory

dragging = sys.argv[1] == 'dragging'
loaded = sys.argv[1] in ('loaded', 'dragging')
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    image = root / 'thumbnail.png'
    Image.new('RGB', (480, 270), '#dbeafe').save(image)
    source = root / 'sample.pptx'
    source.write_bytes(b'fake')
    class SmokeWindow(MainWindow):
        def __init__(self, cache_root):
            super().__init__(cache_root, FakeServiceFactory(image, delay=0))
            self.timer = QTimer(self)
            self.timer.setInterval(10)
            self.timer.timeout.connect(self.finish_when_ready)
        def show(self):
            super().show()
            self.timer.start()
        def finish_when_ready(self):
            if self.is_loading or self._restoring:
                return
            if loaded and self.slide_grid.model.rowCount() != 3:
                return
            self.timer.stop()
            if loaded:
                slides = self.slide_grid.model.slides
                self.output_panel.add_slides(slides)
                preview = SlidePreview(slides, 0, self)
                preview.open()
                if dragging:
                    mime = self.slide_grid.model.mimeData([self.slide_grid.model.index(0, 0)])
                    event = QDragEnterEvent(QPoint(20, 40), Qt.DropAction.CopyAction, mime,
                                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
                    QApplication.sendEvent(self.output_panel.view.viewport(), event)
                    assert event.isAccepted()
            self.close()
    entry.MainWindow = SmokeWindow
    entry.ROOT = root
    sys.argv = ['ppt-merge', str(source)] if loaded else ['ppt-merge']
    code = entry.main()
    assert code == 0, code
    assert QApplication.instance() is None
    assert (not loaded) or (root / 'workspace.json').is_file()
    print('shutdown complete', flush=True)
    logging.shutdown()
"""


class ShutdownTests(unittest.TestCase):
    def test_entrypoint_exits_cleanly_empty_and_after_loading_with_preview(self):
        env = os.environ.copy()
        env['QT_QPA_PLATFORM'] = 'offscreen'
        env['PYTHONPATH'] = os.pathsep.join((str(ROOT), str(ROOT / 'tests/unit')))
        for scenario in ('empty', 'loaded', 'dragging'):
            with self.subTest(scenario=scenario):
                result = subprocess.run(
                    [sys.executable, '-X', 'utf8', '-X', 'faulthandler', '-c', SMOKE, scenario],
                    cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8',
                    errors='replace', timeout=20,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn('shutdown complete', result.stdout)
                self.assertNotIn('access violation', result.stderr)


if __name__ == '__main__':
    unittest.main()
