"""메인 UI의 폴더 트리·PPT 선택·검색·취소와 기존 추가 흐름을 검증한다."""

import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QFileInfo, QItemSelectionModel, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QStyle, QToolButton

from src.ui.file_browser import source_key
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


class MainSidebarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ui.UiTests.setUpClass()
        cls.app = ui.UiTests.app

    def setUp(self):
        ui.UiTests.setUp(self)
        self.panel = self.window.source_panel
        self.child = self.root / "하위 폴더"
        self.child.mkdir()
        self.grandchild = self.child / "세부 자료"
        self.grandchild.mkdir()
        self.nested = self.child / "최종.pptx"
        self.deep = self.grandchild / "깊은 자료.PPTM"
        self.nested.write_bytes(b"fake")
        self.deep.write_bytes(b"fake")
        (self.root / "숨김.txt").write_text("fixture")
        (self.root / "~$잠금.pptx").write_bytes(b"fake")
        self.panel.set_root(self.root)
        wait_until(lambda: self.panel.tree_model.rowCount(self.panel.tree.rootIndex()) == 3)

    def tearDown(self):
        self.window.close()
        wait_until(lambda: not self.window.is_busy and not self.panel.has_search)
        self.app.processEvents()
        self.temporary.cleanup()

    def index(self, path):
        return self.panel.tree_model.mapFromSource(self.panel.file_model.index(str(path)))

    def click(self, path):
        index = self.index(path)
        self.assertTrue(index.isValid())
        self.panel.tree.scrollTo(index)
        QTest.qWait(20)
        rect = self.panel.tree.visualRect(self.index(path))
        self.assertTrue(rect.isValid())
        QTest.mouseClick(self.panel.tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())

    def load(self, path):
        self.click(path)
        wait_until(lambda: not self.window.is_loading)

    def search(self, query, count):
        self.panel.search.setText(query)
        wait_until(lambda: not self.panel._debounce.isActive() and not self.panel.has_search)
        self.assertEqual(self.panel.results.count(), count)
        return self.panel.results.item(0)

    def assert_status_icon(self, item, status):
        expected = self.app.style().standardIcon(status).pixmap(24, 24).toImage()
        self.assertEqual(item.icon().pixmap(24, 24).toImage(), expected)

    def click_result(self, item):
        self.panel.results.scrollToItem(item)
        QTest.mouseClick(self.panel.results.viewport(), Qt.MouseButton.LeftButton,
                         pos=self.panel.results.visualItemRect(item).center())

    def test_root_children_include_folders_and_only_supported_files(self):
        model = self.panel.tree_model
        root = self.panel.tree.rootIndex()
        names = {Path(self.panel._path(model.index(row, 0, root))).name for row in range(model.rowCount(root))}
        self.assertEqual(names, {self.child.name, self.a.name, self.b.name})
        self.assertEqual(self.window.root_label.toolTip(), str(self.root))
        self.assertEqual(len(self.window._sources), 0)

    def test_only_root_picker_opens_a_dialog(self):
        with patch("src.ui.main_window.QFileDialog.getExistingDirectory", return_value=str(self.child)) as picker:
            self.window.add_action.trigger()
            self.assertEqual(self.panel.root_path, self.child)
            wait_until(lambda: self.panel.tree_model.rowCount(self.panel.tree.rootIndex()) == 2)
            self.click(self.grandchild)
            wait_until(lambda: self.panel.tree.isExpanded(self.index(self.grandchild)))
            picker.assert_called_once()
            self.assertIsNone(self.app.activeModalWidget())
        self.assertEqual(len(self.window._sources), 0)

    def test_cancel_root_picker_keeps_tree_and_invalid_root_is_rejected(self):
        with patch("src.ui.main_window.QFileDialog.getExistingDirectory", return_value=""):
            self.window.choose_files()
        self.assertEqual(self.panel.root_path, self.root)
        self.assertFalse(self.panel.set_root(self.root / "missing"))
        self.assertEqual(self.panel.root_path, self.root)

    def test_click_nested_folders_expands_in_main_and_ppt_loads_preview(self):
        self.click(self.child)
        wait_until(lambda: self.panel.tree_model.rowCount(self.index(self.child)) == 2)
        self.assertTrue(self.panel.tree.isExpanded(self.index(self.child)))
        self.click(self.grandchild)
        wait_until(lambda: self.panel.tree_model.rowCount(self.index(self.grandchild)) == 1)
        self.load(self.deep)
        self.assertTrue(self.panel.isVisible() and self.panel.originals_panel.isVisible())
        self.assertEqual(self.panel.current_key(), source_key(self.deep))
        self.assertEqual(self.window.slide_grid.model.rowCount(), 3)
        self.assertEqual(self.window.slide_grid.model.slides[0].source_file, str(self.deep))
        self.assertTrue(all(value != threading.get_ident() for value in self.factory.threads))
        self.assertIsNone(self.app.activeModalWidget())

    def test_switching_ready_files_reuses_loaded_sources_and_shows_badge(self):
        self.load(self.a)
        self.load(self.b)
        self.load(self.a)
        self.assertEqual(len(self.factory.threads), 2)
        self.assertEqual(self.panel.list.count(), 2)
        self.assertEqual([item.data(Qt.ItemDataRole.UserRole) for item in self.panel.list.selectedItems()],
                         [source_key(self.a)])
        self.assertIn("3장", self.panel.tree_model.data(self.index(self.a)))
        self.assertEqual(self.window.slide_grid.model.slides[0].source_file, str(self.a))

    def test_ctrl_selection_in_tree_preserves_multiple_sources(self):
        self.load(self.a)
        self.load(self.b)
        self.panel.tree.selectionModel().select(self.index(self.a),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
        self.assertEqual(set(self.panel.selected_keys()), {source_key(self.a), source_key(self.b)})
        self.window.remove_selected()
        self.assertEqual(self.panel.list.count(), 0)
        self.assertTrue(self.a.is_file() and self.b.is_file())

    def test_remove_then_click_same_file_loads_again(self):
        self.load(self.a)
        self.window.remove_selected()
        self.assertNotIn(source_key(self.a), self.window._sources)
        self.load(self.a)
        self.assertEqual(len(self.factory.threads), 2)

    def test_root_change_keeps_output_sources_and_original_preview(self):
        self.load(self.a)
        self.window.output_panel.add_slides([self.window.slide_grid.model.slides[0]])
        self.panel.set_root(self.child)
        self.assertEqual(self.panel.current_key(), source_key(self.a))
        self.assertEqual(self.panel.list.count(), 1)
        self.assertEqual(len(self.window.output_panel.output_slides), 1)
        self.panel.select_source(source_key(self.a))
        self.assertFalse(self.panel.tree.currentIndex().isValid())
        self.assertEqual(self.window.slide_grid.model.rowCount(), 3)

    def test_search_nested_file_selects_preview_in_main(self):
        workers, updates = [], []
        def search(root, query, batch, cancel):
            workers.append(threading.get_ident())
            return search_presentations(root, query, batch, cancel)
        self.panel.results.model().rowsInserted.connect(
            lambda *args: updates.append(threading.get_ident()), Qt.ConnectionType.DirectConnection)
        with patch("src.ui.file_browser.search_presentations", side_effect=search):
            self.panel.search.setText("최종")
            self.panel.search.setText("깊은")
            wait_until(lambda: self.panel.results.count() == 1 and not self.panel.has_search)
        self.assertTrue(workers and all(value != threading.get_ident() for value in workers))
        self.assertEqual(updates, [threading.get_ident()])
        item = self.panel.results.item(0)
        self.assertEqual(Path(item.data(Qt.ItemDataRole.UserRole)), self.deep)
        self.assertIn(self.child.name, item.text())
        self.click_result(item)
        wait_until(lambda: not self.window.is_loading)
        self.assert_status_icon(item, QStyle.StandardPixmap.SP_DialogApplyButton)
        self.assertIn("3장", item.text())
        self.assertIn("3장", item.toolTip())
        self.assertIn("3장", item.data(Qt.ItemDataRole.AccessibleTextRole))
        self.assertEqual(self.panel.stack.currentWidget(), self.panel.results)
        self.assertEqual(self.window.slide_grid.model.slides[0].source_file, str(self.deep))
        self.panel.search.clear()
        self.assertEqual(self.panel.stack.currentWidget(), self.panel.tree)
        self.assertEqual(self.panel.results.count(), 0)
        self.assertEqual(self.panel.current_key(), source_key(self.deep))

    def test_search_uses_presentation_file_association_icon(self):
        provider = self.panel.file_model.iconProvider()
        expected = self.window.add_action.icon()
        with patch.object(provider, "icon", return_value=expected) as association:
            item = self.search("깊은", 1)
            self.assertEqual(item.icon().pixmap(24, 24).toImage(), expected.pixmap(24, 24).toImage())
            self.assertTrue(any(isinstance(call.args[0], QFileInfo)
                                and Path(call.args[0].filePath()) == self.deep
                                for call in association.call_args_list))

    def test_search_restores_ready_badge_for_previously_loaded_file(self):
        self.load(self.a)
        item = self.search("한글", 1)
        self.assert_status_icon(item, QStyle.StandardPixmap.SP_DialogApplyButton)
        self.assertIn("3장", item.text())
        self.panel.search.clear()
        item = self.search("한글", 1)
        self.assert_status_icon(item, QStyle.StandardPixmap.SP_DialogApplyButton)
        self.assertIn("3장", item.text())
        self.assertEqual(len(self.factory.threads), 1)

    def test_clear_button_does_not_load_another_file_when_tree_regains_focus(self):
        self.app.setActiveWindow(self.window)
        item = self.search("깊은", 1)
        self.panel.results.scrollToItem(item)
        self.panel.results.setFocus()
        self.assertEqual(self.window._sources, {})
        QTest.mouseClick(self.panel.results.viewport(), Qt.MouseButton.LeftButton,
                         pos=self.panel.results.visualItemRect(item).center())
        wait_until(lambda: not self.window.is_loading)
        before = set(self.window._sources)
        self.assertEqual(before, {source_key(self.deep)})
        clear_button = self.panel.search.findChild(QToolButton)
        QTest.mouseClick(clear_button, Qt.MouseButton.LeftButton)
        QTest.qWait(150)
        wait_until(lambda: not self.window.is_loading)
        self.assertEqual(set(self.window._sources), before)
        self.assertEqual(len(self.factory.threads), 1)
        self.assertEqual(self.window.slide_grid.model.slides[0].source_file, str(self.deep))

    def test_clear_multiple_matches_does_not_load_a_sibling_result(self):
        self.app.setActiveWindow(self.window)
        self.panel.search.setText("ppt")
        wait_until(lambda: not self.panel._debounce.isActive() and not self.panel.has_search)
        self.assertEqual(self.panel.results.count(), 4)
        item = next(self.panel.results.item(row) for row in range(4)
                    if source_key(self.panel.results.item(row).data(Qt.ItemDataRole.UserRole)) == source_key(self.deep))
        self.panel.results.scrollToItem(item)
        self.panel.results.setFocus()
        self.assertEqual(self.window._sources, {})
        QTest.mouseClick(self.panel.results.viewport(), Qt.MouseButton.LeftButton,
                         pos=self.panel.results.visualItemRect(item).center())
        wait_until(lambda: not self.window.is_loading)
        self.assertEqual(set(self.window._sources), {source_key(self.deep)})
        QTest.mouseClick(self.panel.search.findChild(QToolButton), Qt.MouseButton.LeftButton)
        QTest.qWait(150)
        wait_until(lambda: not self.window.is_loading)
        self.assertEqual(set(self.window._sources), {source_key(self.deep)})
        self.assertEqual(len(self.factory.threads), 1)

    def test_search_keyboard_selection_loads_only_the_requested_file(self):
        self.app.setActiveWindow(self.window)
        self.search("ppt", 4)
        self.panel.results.setFocus()
        self.assertEqual(self.window._sources, {})
        target = Path(self.panel.results.item(1).data(Qt.ItemDataRole.UserRole))
        QTest.keyClick(self.panel.results, Qt.Key.Key_Down)
        wait_until(lambda: not self.window.is_loading)
        self.assertEqual(set(self.window._sources), {source_key(target)})
        self.assertEqual(self.window.slide_grid.model.slides[0].source_file, str(target))

    def test_tree_automatic_selection_does_not_load_until_keyboard_activation(self):
        self.app.setActiveWindow(self.window)
        self.panel.tree.setCurrentIndex(self.index(self.b))
        self.panel.tree.setFocus()
        self.assertEqual(self.window._sources, {})
        QTest.keyClick(self.panel.tree, Qt.Key.Key_Return)
        wait_until(lambda: not self.window.is_loading)
        self.assertEqual(set(self.window._sources), {source_key(self.b)})

    def test_clear_search_a_pptx_keeps_only_the_clicked_path(self):
        self.app.setActiveWindow(self.window)
        target = self.child / "A.pptx"
        target.write_bytes(b"fake")
        self.search("A.pptx", 2)
        item = next(self.panel.results.item(row) for row in range(2)
                    if source_key(self.panel.results.item(row).data(Qt.ItemDataRole.UserRole)) == source_key(target))
        self.panel.results.setFocus()
        self.click_result(item)
        wait_until(lambda: not self.window.is_loading)
        self.assertEqual(set(self.window._sources), {source_key(target)})
        QTest.mouseClick(self.panel.search.findChild(QToolButton), Qt.MouseButton.LeftButton)
        QTest.qWait(150)
        wait_until(lambda: not self.window.is_loading)
        self.assertEqual(set(self.window._sources), {source_key(target)})
        self.assertEqual(self.panel.current_key(), source_key(target))
        self.assertEqual(self.window.slide_grid.model.slides[0].source_file, str(target))
        self.assertEqual(len(self.factory.threads), 1)

    def test_search_remove_and_clear_reset_badges_and_allow_same_item_retry(self):
        item = self.search("한글", 1)
        original_icon = item.icon().pixmap(24, 24).toImage()
        self.assertFalse(original_icon.isNull())
        self.click_result(item)
        wait_until(lambda: not self.window.is_loading)
        self.window.remove_selected()
        self.assertNotIn("3장", item.text())
        self.assertEqual(item.toolTip(), str(self.a))
        self.assertEqual(item.icon().pixmap(24, 24).toImage(), original_icon)
        QTest.mouseClick(self.panel.results.viewport(), Qt.MouseButton.LeftButton,
                         pos=self.panel.results.visualItemRect(item).center())
        wait_until(lambda: not self.window.is_loading)
        self.assert_status_icon(item, QStyle.StandardPixmap.SP_DialogApplyButton)
        self.assertEqual(len(self.factory.threads), 2)
        self.window.clear_sources()
        self.assertNotIn("3장", item.text())
        self.assertEqual(item.icon().pixmap(24, 24).toImage(), original_icon)
        self.assertTrue(self.a.is_file())

    def test_search_loading_cancel_and_retry_update_status_icons(self):
        item = self.search("한글", 1)
        self.factory.delay = 0.06
        self.click_result(item)
        wait_until(lambda: self.window._sources[source_key(self.a)].status == "loading")
        self.assert_status_icon(item, QStyle.StandardPixmap.SP_BrowserReload)
        self.window.cancel_loading()
        wait_until(lambda: not self.window.is_loading)
        self.assert_status_icon(item, QStyle.StandardPixmap.SP_DialogCancelButton)
        self.assertNotIn("3장", item.text())
        self.factory.delay = 0
        self.window.reload_selected()
        wait_until(lambda: not self.window.is_loading)
        self.assert_status_icon(item, QStyle.StandardPixmap.SP_DialogApplyButton)
        self.assertIn("3장", item.text())

    def test_search_failed_file_displays_error_status(self):
        failed = self.root / "failed.pptx"
        failed.write_bytes(b"fake")
        item = self.search("failed", 1)
        with self.assertLogs("ppt_merge.worker", level="ERROR"):
            self.click_result(item)
            wait_until(lambda: not self.window.is_loading)
        self.assert_status_icon(item, QStyle.StandardPixmap.SP_MessageBoxCritical)
        self.assertNotIn("HRESULT", item.toolTip())
        self.assertIn("실패", item.toolTip())

    def test_stale_search_results_ignored_after_root_change(self):
        old = self.panel._search_token
        self.panel.set_root(self.child)
        self.panel._search_batch(old, [str(self.a)])
        self.panel._search_completed(old, SearchSummary(matches=1))
        self.assertEqual(self.panel.results.count(), 0)
        self.assertFalse(self.panel.search_status.isVisible())

    def test_search_close_cancels_without_blocking_main_ui(self):
        started = threading.Event()
        def slow(root, query, batch, cancel):
            started.set()
            while not cancel():
                time.sleep(0.01)
            time.sleep(0.06)
            return SearchSummary(cancelled=True)
        with patch("src.ui.file_browser.search_presentations", side_effect=slow):
            self.panel.search.setText("자료")
            wait_until(started.is_set)
            self.window.close()
            self.assertTrue(self.window.isVisible())
            ticks = []
            timer = QTimer()
            timer.timeout.connect(lambda: ticks.append(1))
            timer.start(10)
            wait_until(lambda: not self.panel.has_search and not self.window.isVisible())
            timer.stop()
            self.assertGreater(len(ticks), 0)

    def test_external_drop_remains_available_in_originals_card(self):
        self.panel.set_root(self.child)
        self.window.add_sources([self.a])
        wait_until(lambda: not self.window.is_loading)
        self.assertTrue(self.panel.originals_panel.isVisible())
        self.assertEqual(self.panel.current_key(), source_key(self.a))

    def test_add_inside_root_during_search_keeps_search_and_selects_original(self):
        self.panel.search.setText("일치하지 않음")
        wait_until(lambda: not self.panel._debounce.isActive() and not self.panel.has_search)
        self.window.add_sources([self.a])
        wait_until(lambda: not self.window.is_loading)
        self.assertEqual(self.panel.stack.currentWidget(), self.panel.results)
        self.assertEqual(self.panel.search.text(), "일치하지 않음")
        self.assertEqual(self.panel.current_key(), source_key(self.a))
        self.assertEqual(self.window.slide_grid.model.slides[0].source_file, str(self.a))

    def test_original_click_preserves_search_and_reuses_loaded_preview(self):
        self.load(self.a)
        self.load(self.b)
        result = self.search("한글", 1)
        item = self.panel._items[source_key(self.b)]
        QTest.mouseClick(self.panel.list.viewport(), Qt.MouseButton.LeftButton,
                         pos=self.panel.list.visualItemRect(item).center())
        self.assertEqual(self.panel.search.text(), "한글")
        self.assertEqual(self.panel.stack.currentWidget(), self.panel.results)
        self.assertEqual(self.panel.results.item(0), result)
        self.assertEqual(self.panel.selected_keys(), [source_key(self.b)])
        self.assertEqual(self.window.slide_grid.model.slides[0].source_file, str(self.b))
        self.assertEqual(len(self.factory.threads), 2)

    def test_originals_ctrl_selection_removes_only_selected_loaded_sources(self):
        self.load(self.a)
        self.load(self.b)
        self.search("한글", 1)
        for path, modifier in ((self.a, Qt.KeyboardModifier.NoModifier),
                               (self.b, Qt.KeyboardModifier.ControlModifier)):
            item = self.panel._items[source_key(path)]
            QTest.mouseClick(self.panel.list.viewport(), Qt.MouseButton.LeftButton, modifier,
                             pos=self.panel.list.visualItemRect(item).center())
        self.assertEqual(set(self.panel.selected_keys()), {source_key(self.a), source_key(self.b)})
        self.window.remove_selected()
        self.assertEqual(self.panel.list.count(), 0)
        self.assertEqual(self.panel.source_count.text(), "0개")
        self.assertEqual(self.panel.search.text(), "한글")
        self.assertTrue(self.a.is_file() and self.b.is_file())

    def test_icon_toolbar_has_accessible_root_picker_and_shortcut(self):
        toolbar = self.window.findChild(QToolButton)
        self.assertIsNotNone(toolbar)
        self.assertFalse(self.window.add_action.icon().isNull())
        self.assertEqual(self.window.add_action.shortcut().toString(), "Ctrl+O")
        self.assertIn("최상위", self.window.add_action.toolTip())
