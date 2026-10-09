"""실제 파일 트리·하위 폴더 검색·선택·취소와 기존 추가 흐름을 검증한다."""

import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QItemSelectionModel, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QToolButton

from src.ui.file_browser import FileBrowserDialog
from src.utils.file_search import SearchSummary, search_presentations
import test_ui as ui


def wait_until(predicate, timeout=5000):
    if predicate():
        return
    loop = QEventLoop()
    poll = QTimer()
    poll.setInterval(10)
    poll.timeout.connect(lambda: loop.quit() if predicate() else None)
    limit = QTimer()
    limit.setSingleShot(True)
    limit.timeout.connect(loop.quit)
    poll.start()
    limit.start(timeout)
    try:
        loop.exec()
    finally:
        poll.stop()
        limit.stop()
        poll.timeout.disconnect()
        limit.timeout.disconnect()
    if not predicate():
        raise AssertionError("Qt 작업이 제한 시간 안에 끝나지 않았습니다.")


class FileSearchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.child = self.root / "한글 폴더"
        self.child.mkdir()
        self.a = self.root / "보고서.PPTX"
        self.b = self.child / "보고서_최종.pptm"
        for path in (self.a, self.b, self.root / "보고서.pdf", self.root / "~$보고서.pptx"):
            path.write_bytes(b"fixture")

    def tearDown(self):
        self.temporary.cleanup()

    def search(self, query, **kwargs):
        paths = []
        summary = search_presentations(self.root, query, paths.extend, lambda: False, **kwargs)
        return paths, summary

    def test_recursive_unicode_supported_formats_and_lock_file_exclusion(self):
        paths, summary = self.search(" 보고서 ")
        self.assertEqual(set(paths), {str(self.a), str(self.b)})
        self.assertEqual(summary, SearchSummary(matches=2))
        self.assertEqual(self.search("pptX")[0], [str(self.a)])

    def test_empty_and_no_match_queries(self):
        self.assertEqual(self.search(" "), ([], SearchSummary()))
        self.assertEqual(self.search("없음"), ([], SearchSummary()))

    def test_result_limit(self):
        paths, summary = self.search("보고서", limit=1)
        self.assertEqual(len(paths), 1)
        self.assertTrue(summary.limited)

    def test_cancel_stops_during_enumeration(self):
        calls = []
        def cancel():
            calls.append(1)
            return len(calls) > 2
        paths = []
        summary = search_presentations(self.root, "보고서", paths.extend, cancel)
        self.assertTrue(summary.cancelled)
        self.assertEqual(paths, [])

    def test_permission_failure_isolated_from_other_folders(self):
        denied = self.root / "차단"
        denied.mkdir()
        scandir = os.scandir
        def guarded(directory):
            if Path(directory) == denied:
                raise PermissionError("접근 불가")
            return scandir(directory)
        with patch("src.utils.file_search.os.scandir", side_effect=guarded):
            paths, summary = self.search("보고서")
        self.assertEqual(set(paths), {str(self.a), str(self.b)})
        self.assertEqual(summary.skipped, 1)

    def test_linked_directory_is_not_followed(self):
        with patch("src.utils.file_search.Path.is_junction",
                   autospec=True, side_effect=lambda value: value == self.child):
            paths, summary = self.search("보고서")
        self.assertEqual(paths, [str(self.a)])
        self.assertEqual(summary.matches, 1)


class FileBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ui.UiTests.setUpClass()
        cls.app = ui.UiTests.app

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.a = self.root / "한글 자료.pptx"
        self.b = self.root / "Other.PPTM"
        self.a.write_bytes(b"fake")
        self.b.write_bytes(b"fake")
        (self.root / "숨길 자료.txt").write_text("fixture")
        self.child = self.root / "하위 폴더"
        self.child.mkdir()
        self.nested = self.child / "한글 자료_최종.pptx"
        self.nested.write_bytes(b"fake")
        self.dialog = FileBrowserDialog(initial_root=self.root)
        self.dialog.show()
        wait_until(lambda: self.dialog.model.rowCount(self.dialog.tree.rootIndex()) >= 3)

    def tearDown(self):
        self.dialog.reject()
        wait_until(lambda: not self.dialog._threads)
        self.dialog.deleteLater()
        self.app.processEvents()
        self.temporary.cleanup()

    def search(self, text):
        self.dialog.search.setText(text)
        wait_until(lambda: not self.dialog._debounce.isActive() and not self.dialog._threads)

    def test_tree_filters_files_but_keeps_folders_and_accepts_multi_selection(self):
        parent = self.dialog.tree.rootIndex()
        names = {self.dialog.model.fileName(self.dialog.model.index(row, 0, parent))
                 for row in range(self.dialog.model.rowCount(parent))}
        self.assertEqual(names, {self.a.name, self.b.name, self.child.name})
        selection = self.dialog.tree.selectionModel()
        for path in (self.a, self.b):
            index = self.dialog.model.index(str(path))
            selection.select(index, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        self.assertTrue(self.dialog.add_button.isEnabled())
        self.dialog.add_button.click()
        self.assertEqual(set(self.dialog.selected_files), {str(self.a).replace("\\", "/"),
                                                          str(self.b).replace("\\", "/")})
        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Accepted)

    def test_folder_selection_cannot_be_added(self):
        self.dialog.tree.setCurrentIndex(self.dialog.model.index(str(self.child)))
        self.assertFalse(self.dialog.add_button.isEnabled())
        self.dialog._tree_double_clicked(self.dialog.tree.currentIndex())
        self.assertTrue(self.dialog.isVisible())

    def test_default_root_uses_windows_desktop_location(self):
        with patch("src.ui.file_browser.QStandardPaths.writableLocation", return_value=str(self.root)):
            browser = FileBrowserDialog()
        self.assertEqual(browser.root_path, self.root)
        self.assertEqual(browser.location.currentText(), "바탕화면")
        browser.reject()
        browser.deleteLater()

    def test_search_nested_files_multi_select_and_accept(self):
        self.search("한글")
        self.assertEqual(self.dialog.results.count(), 2)
        self.assertEqual(self.dialog.stack.currentWidget(), self.dialog.results)
        for row in range(self.dialog.results.count()):
            item = self.dialog.results.item(row)
            self.assertIn("한글", item.text())
            item.setSelected(True)
        self.dialog.add_button.click()
        self.assertEqual(set(self.dialog.selected_files), {str(self.a), str(self.nested)})
        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Accepted)

    def test_clear_search_returns_to_tree_and_ignores_stale_batches(self):
        self.search("한글")
        token = self.dialog._token
        self.dialog.search.clear()
        self.dialog._on_batch(token, (str(self.a),))
        self.dialog._on_completed(token, SearchSummary(matches=100))
        self.assertEqual(self.dialog.results.count(), 0)
        self.assertEqual(self.dialog.stack.currentWidget(), self.dialog.tree)
        self.assertEqual(self.dialog.status.toolTip(), "PPTX · PPTM")
        self.assertFalse(self.dialog.add_button.isEnabled())

    def test_changed_root_keeps_query_and_limits_scope(self):
        self.search("한글")
        self.dialog.set_root(self.child)
        wait_until(lambda: not self.dialog._debounce.isActive() and not self.dialog._threads)
        self.assertEqual(self.dialog.results.count(), 1)
        self.assertEqual(self.dialog.results.item(0).data(Qt.ItemDataRole.UserRole), str(self.nested))
        self.assertEqual(self.dialog.root_path, self.child)
        self.assertEqual(self.dialog.path_label.toolTip(), str(self.child))

    def test_deleted_search_result_cannot_be_accepted(self):
        self.search("Other")
        self.dialog.results.item(0).setSelected(True)
        self.b.unlink()
        self.dialog.add_button.click()
        self.assertTrue(self.dialog.isVisible())
        self.assertEqual(self.dialog.selected_files, [])
        self.assertIn("삭제", self.dialog.status.toolTip())

    def test_search_runs_off_gui_thread_and_close_waits_responsively(self):
        started = threading.Event()
        threads = []
        def slow_search(root, query, on_batch, cancel):
            threads.append(threading.get_ident())
            started.set()
            time.sleep(0.08)
            while not cancel():
                time.sleep(0.01)
            return SearchSummary(cancelled=True)
        with patch("src.ui.file_browser.search_presentations", side_effect=slow_search):
            self.dialog.search.setText("한글")
            wait_until(started.is_set)
            ticks = []
            timer = QTimer()
            timer.setInterval(5)
            timer.timeout.connect(lambda: ticks.append(1))
            timer.start()
            self.dialog.close()
            self.assertTrue(self.dialog.isVisible())
            wait_until(lambda: not self.dialog.isVisible() and not self.dialog._threads)
            timer.stop()
        self.assertTrue(ticks)
        self.assertNotEqual(threads[0], threading.get_ident())
        self.assertEqual(self.dialog.result(), QDialog.DialogCode.Rejected)

    def test_search_debounce_and_query_change_cancel_previous_work(self):
        started = threading.Event()
        cancelled = threading.Event()
        actual_search = search_presentations
        def search(root, query, batch, cancel):
            if query == "이전":
                started.set()
                while not cancel():
                    time.sleep(0.01)
                cancelled.set()
                batch((str(self.b),))
                return SearchSummary(matches=1, cancelled=True)
            return actual_search(root, query, batch, cancel)
        with patch("src.ui.file_browser.search_presentations", side_effect=search):
            self.dialog.search.setText("이전")
            wait_until(started.is_set)
            self.search("한글")
        self.assertTrue(cancelled.is_set())
        self.assertEqual(self.dialog.results.count(), 2)
        self.assertTrue(all("한글" in self.dialog.results.item(i).text() for i in range(2)))


class FileBrowserIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ui.UiTests.setUpClass()
        cls.app = ui.UiTests.app

    setUp = ui.UiTests.setUp
    tearDown = ui.UiTests.tearDown
    def load(self, *paths):
        self.window.add_sources(paths)
        wait_until(lambda: not self.window.is_loading)

    def test_chooser_adds_files_through_existing_worker_and_remembers_root(self):
        opened = []
        def select_files(browser):
            opened.append(browser)
            browser.selected_files = [str(self.a), str(self.b)]
            browser.set_root(self.root)
            return QDialog.DialogCode.Accepted
        with patch("src.ui.main_window.FileBrowserDialog.exec", new=select_files):
            self.window.choose_files()
            wait_until(lambda: not self.window.is_loading)
            self.window.choose_files()
        wait_until(lambda: not self.window.is_loading)
        self.assertEqual(opened[1].root_path, self.root)
        self.assertEqual(self.window.source_panel.list.count(), 2)
        self.assertEqual(len(self.factory.threads), 2)

    def test_icon_actions_keep_tooltips_accessibility_and_shortcuts(self):
        self.load(self.a)
        self.window.slide_grid.view.setCurrentIndex(self.window.slide_grid.model.index(0, 0))
        self.window.slide_grid.add_button.click()
        for button in self.window.output_panel.findChildren(QToolButton):
            self.assertEqual(button.text(), "")
            self.assertFalse(button.icon().isNull())
            self.assertTrue(button.toolTip())
            self.assertTrue(button.accessibleName())
        QTest.keyClick(self.window.output_panel.view, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(len(self.window.output_panel.output_slides), 2)
        QTest.keyClick(self.window.output_panel.view, Qt.Key.Key_Delete)
        self.assertEqual(len(self.window.output_panel.output_slides), 1)
