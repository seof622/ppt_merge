"""실제 Qt 이벤트 루프에서 UI 상태·선택·취소·종료를 검증한다."""

from dataclasses import dataclass, field
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QEventLoop, QMimeData, QObject, QPoint, QPointF, QTimer, Qt, QUrl, Slot
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.main import configure_application
from src.models.presentation_model import PresentationInfo
from src.models.slide_model import SlideItem
from src.ppt.errors import OperationCancelled
from src.ppt.thumbnail_service import ThumbnailProgress, ThumbnailResult
from src.ui.main_window import MainWindow


def wait_until(predicate, timeout=5000):
    if predicate():
        return
    loop = QEventLoop()
    poll = QTimer(loop)
    poll.setInterval(10)
    poll.timeout.connect(lambda: loop.quit() if predicate() else None)
    limit = QTimer(loop)
    limit.setSingleShot(True)
    limit.timeout.connect(loop.quit)
    poll.start()
    limit.start(timeout)
    loop.exec()
    if not predicate():
        raise AssertionError("Qt 작업이 제한 시간 안에 끝나지 않았습니다.")


@dataclass
class FakeServiceFactory:
    image: Path
    delay: float = 0.01
    threads: list[int] = field(default_factory=list)

    def __call__(self):
        owner = self

        class Service:
            def load(self, path, progress=None, cancel=None):
                owner.threads.append(threading.get_ident())
                if path.stem == "failed":
                    raise RuntimeError("PRIVATE HRESULT")
                items = []
                for number in range(1, 4):
                    time.sleep(owner.delay)
                    if cancel and cancel():
                        raise OperationCancelled("취소")
                    progress(ThumbnailProgress(str(path), "exporting", number, 3))
                    items.append(SlideItem(str(path), path.name, number, 255 + number,
                                           str(owner.image), f"슬라이드 {number}"))
                info = PresentationInfo(str(path), path.name, 960, 540, tuple(items))
                return ThumbnailResult(info, str(owner.image.parent), False, 3)

        return Service()


class UiTests(unittest.TestCase):
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
        self.a.write_bytes(b"fake")
        self.b.write_bytes(b"fake")
        image = self.root / "thumbnail.png"
        Image.new("RGB", (480, 270), "#dbeafe").save(image)
        self.factory = FakeServiceFactory(image)
        self.window = MainWindow(self.root / "cache", self.factory)
        self.window.show()
        QTest.qWait(30)

    def tearDown(self):
        if self.window.is_loading:
            self.window.cancel_loading()
            wait_until(lambda: not self.window.is_loading)
        self.window.close()
        self.app.processEvents()
        self.temporary.cleanup()

    def load(self, *paths):
        self.window.add_sources(paths)
        wait_until(lambda: not self.window.is_loading)

    def test_add_deduplicate_and_switch_sources_in_worker(self):
        self.load(self.a, self.a, self.b, self.root / "missing.pptx")
        self.assertEqual(self.window.source_panel.list.count(), 2)
        self.assertEqual(len(self.window._sources), 2)
        self.assertTrue(self.window.notice.isVisible())
        self.assertEqual(self.window.slide_grid.model.rowCount(), 3)
        key = os.path.normcase(str(self.b))
        self.window.source_panel.select_source(key)
        self.assertEqual(self.window.slide_grid.model.slides[0].source_file, str(self.b))
        self.assertTrue(all(thread != threading.get_ident() for thread in self.factory.threads))

    def test_one_failure_is_isolated_and_raw_error_hidden(self):
        failed = self.root / "failed.pptx"
        failed.write_bytes(b"fake")
        with self.assertLogs("ppt_merge.worker", level="ERROR"):
            self.load(failed, self.b)
        bad_state = self.window._sources[os.path.normcase(str(failed))]
        good_state = self.window._sources[os.path.normcase(str(self.b))]
        self.assertEqual(bad_state.status, "failed")
        self.assertEqual(good_state.status, "ready")
        self.assertNotIn("HRESULT", self.window.slide_grid.empty.text())
        self.window.source_panel.select_source(os.path.normcase(str(self.b)))
        self.assertEqual(self.window.slide_grid.model.rowCount(), 3)

    def test_files_added_while_loading_are_not_lost(self):
        self.factory.delay = 0.05
        self.window.add_sources([self.a])
        self.window.add_sources([self.b])
        wait_until(lambda: not self.window.is_loading)
        self.assertEqual([state.status for state in self.window._sources.values()], ["ready", "ready"])
        self.assertEqual(len(self.factory.threads), 2)

    def test_cancel_and_retry(self):
        self.factory.delay = 0.06
        self.window.add_sources([self.a, self.b])
        QTimer.singleShot(40, self.window.cancel_button.click)
        wait_until(lambda: not self.window.is_loading)
        self.assertTrue(all(state.status == "cancelled" for state in self.window._sources.values()))
        self.assertTrue(self.window.reload_action.isEnabled())
        self.factory.delay = 0
        self.window.reload_action.trigger()
        wait_until(lambda: not self.window.is_loading)
        self.assertEqual(self.window._sources[os.path.normcase(str(self.a))].status, "ready")

    def test_close_waits_for_worker_without_freezing_gui(self):
        self.factory.delay = 0.06
        self.window.add_sources([self.a])
        # 작업 시작 전에 취소되어 타이머가 돌 틈이 없는 경우를 제외한다.
        wait_until(lambda: bool(self.factory.threads))
        self.window.close()
        self.assertTrue(self.window.isVisible())
        self.assertFalse(self.window.add_action.isEnabled())
        ticks = []
        timer = QTimer()
        timer.setInterval(10)
        timer.timeout.connect(lambda: ticks.append(1))
        timer.start()
        wait_until(lambda: not self.window.is_loading and not self.window.isVisible())
        timer.stop()
        self.assertGreater(len(ticks), 0)

    def test_remove_and_clear_leave_original_files_intact(self):
        self.load(self.a, self.b)
        self.window.remove_action.trigger()
        self.assertEqual(self.window.source_panel.list.count(), 1)
        self.assertEqual(self.window.slide_grid.model.slides[0].source_file, str(self.b))
        self.window.clear_action.trigger()
        self.assertEqual(self.window.slide_grid.model.rowCount(), 0)
        self.assertEqual(self.window.source_panel.list.count(), 0)
        self.assertTrue(self.a.is_file() and self.b.is_file())
        self.assertTrue(self.factory.image.is_file())

    def test_ctrl_and_shift_thumbnail_selection(self):
        self.load(self.a)
        view = self.window.slide_grid.view
        view.doItemsLayout()
        QTest.qWait(50)
        positions = [view.visualRect(view.model().index(number, 0)).center() for number in range(3)]
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, positions[0])
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ControlModifier, positions[1])
        self.assertEqual(len(self.window.slide_grid.selected_slides()), 2)
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, positions[0])
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.ShiftModifier, positions[2])
        self.assertEqual([slide.slide_index for slide in self.window.slide_grid.selected_slides()], [1, 2, 3])

    def test_local_file_drop(self):
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(self.a)), QUrl.fromLocalFile(str(self.b))])
        enter = QDragEnterEvent(QPoint(30, 30), Qt.DropAction.CopyAction, mime,
                                Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(self.window, enter)
        self.assertTrue(enter.isAccepted())
        drop = QDropEvent(QPointF(30, 30), Qt.DropAction.CopyAction, mime,
                          Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(self.window, drop)
        wait_until(lambda: not self.window.is_loading)
        self.assertEqual(self.window.source_panel.list.count(), 2)

    def test_worker_signals_reach_gui_thread(self):
        threads = []

        class Receiver(QObject):
            @Slot(str, object)
            def receive(self, path, event):
                threads.append(threading.get_ident())

        receiver = Receiver(self.window)
        self.window.add_sources([self.a])
        self.window._worker.progress.connect(receiver.receive, Qt.ConnectionType.QueuedConnection)
        wait_until(lambda: not self.window.is_loading)
        self.assertTrue(threads)
        self.assertTrue(all(thread == threading.get_ident() for thread in threads))


if __name__ == "__main__":
    unittest.main()
