"""기존 실제 PPT 캐시로 UI와 앱 내 탐색 화면을 렌더한다. COM은 실행하지 않는다."""

import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QStyle, QToolButton

from src.main import configure_application
from src.ppt.thumbnail_service import ThumbnailService
from src.ui.main_window import MainWindow
from src.ui.file_browser import source_key


def wait_until(predicate, timeout=10):
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
    limit.start(timeout * 1000)
    try:
        loop.exec()
    finally:
        poll.stop()
        limit.stop()
        poll.timeout.disconnect()
        limit.timeout.disconnect()
    if not predicate():
        raise AssertionError("화면 검증 제한 시간 초과")


def no_com():
    raise AssertionError("기존 캐시가 필요합니다. 화면 검증에서 COM을 실행하지 않습니다.")


def main() -> None:
    directory = Path(tempfile.mkdtemp(prefix="file_browser_validation_", dir=ROOT / "output"))
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    configure_application(app)
    window = MainWindow(ROOT / "cache", lambda: ThumbnailService(ROOT / "cache", backend_factory=no_com))
    window.show()
    app.setActiveWindow(window)
    paths = [ROOT / "tests/fixtures/basic/A.pptx", ROOT / "tests/fixtures/basic/B.pptx"]
    panel = window.source_panel
    panel.set_root(ROOT / "tests/fixtures")
    wait_until(lambda: panel.tree_model.rowCount(panel.tree.rootIndex()) >= 2)
    basic_path = ROOT / "tests/fixtures/basic"
    def index(path):
        return panel.tree_model.mapFromSource(panel.file_model.index(str(path)))
    def click(path):
        panel.tree.scrollTo(index(path))
        QTest.qWait(50)
        QTest.mouseClick(panel.tree.viewport(), Qt.MouseButton.LeftButton,
                         pos=panel.tree.visualRect(index(path)).center())
    click(basic_path)
    wait_until(lambda: panel.tree_model.rowCount(index(basic_path)) >= 3)
    assert panel.tree.isExpanded(index(basic_path))
    panel.search.setText("A.pptx")
    wait_until(lambda: not panel._debounce.isActive() and not panel.has_search)
    assert panel.results.count() == 1
    search_item = panel.results.item(0)
    assert not search_item.icon().isNull()
    QTest.qWait(100)
    assert window.grab().save(str(directory / "main_search_before.png"))
    QTest.mouseClick(panel.results.viewport(), Qt.MouseButton.LeftButton,
                     pos=panel.results.visualItemRect(search_item).center())
    wait_until(lambda: not window.is_loading)
    assert window.slide_grid.model.rowCount() == 4
    assert "4장" in search_item.text()
    expected = app.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
    assert search_item.icon().pixmap(24, 24).toImage() == expected.pixmap(24, 24).toImage()
    QTest.qWait(100)
    assert window.grab().save(str(directory / "main_search_ready.png"))
    QTest.mouseClick(panel.search.findChild(QToolButton), Qt.MouseButton.LeftButton)
    QTest.qWait(150)
    wait_until(lambda: not window.is_loading)
    assert set(window._sources) == {source_key(paths[0])}
    assert panel.current_key() == source_key(paths[0])
    assert window.grab().save(str(directory / "main_search_cleared.png"))
    click(paths[1])
    wait_until(lambda: not window.is_loading)
    assert all(state.result and state.result.cache_hit for state in window._sources.values())
    first, second = [state.result.presentation for state in window._sources.values()]
    window.output_panel.add_slides((first.slides[1], second.slides[3], first.slides[0], first.slides[1]))
    report = {"cache_only": True, "output_slides": 4, "search_icon_present": True,
              "search_ready_badge": True, "search_clear_preserves_source": True,
              "captures": ["main_search_before.png", "main_search_ready.png", "main_search_cleared.png"]}
    for width, height in ((1600, 900), (1000, 640)):
        window.resize(width, height)
        QTest.qWait(100)
        filename = f"main_{width}x{height}.png"
        assert window.grab().save(str(directory / filename))
        report["captures"].append(filename)
        assert window.output_panel.view.width() > 0
        assert window.generate_button.isVisible()
        assert panel.isVisible() and panel.originals_panel.isVisible()
        assert panel.geometry().right() < panel.originals_panel.geometry().left()
        assert panel.originals_panel.geometry().right() < window.slide_grid.geometry().left()
    assert app.activeModalWidget() is None
    report["separate_originals_card"] = True
    panel.search.setText("advanced")
    wait_until(lambda: not panel._debounce.isActive() and not panel.has_search)
    assert panel.results.count() >= 2
    QTest.qWait(100)
    assert window.grab().save(str(directory / "main_search.png"))
    report["search_matches"] = panel.results.count()
    original = panel._items[source_key(paths[0])]
    QTest.mouseClick(panel.list.viewport(), Qt.MouseButton.LeftButton,
                     pos=panel.list.visualItemRect(original).center())
    assert panel.search.text() == "advanced"
    assert panel.stack.currentWidget() == panel.results
    assert panel.current_key() == source_key(paths[0])
    assert window.slide_grid.model.slides[0].source_file == str(paths[0])
    report["original_selection_preserves_search"] = True
    panel.search.clear()
    QTest.qWait(150)
    assert set(window._sources) == {source_key(path) for path in paths}
    assert panel.stack.currentWidget() == panel.tree
    window.close()
    wait_until(lambda: not panel.has_search and not window.is_busy)
    app.processEvents()
    report["main_sidebar_selection"] = True
    report["no_navigation_dialog"] = True
    report["qt_platform"] = app.platformName()
    report["passed"] = True
    (directory / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print(directory)


if __name__ == "__main__":
    main()
