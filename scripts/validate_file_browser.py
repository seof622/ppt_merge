"""기존 실제 PPT 캐시로 UI와 앱 내 탐색 화면을 렌더한다. COM은 실행하지 않는다."""

import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QItemSelectionModel, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from src.main import configure_application
from src.ppt.thumbnail_service import ThumbnailService
from src.ui.file_browser import FileBrowserDialog
from src.ui.main_window import MainWindow


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
    paths = [ROOT / "tests/fixtures/basic/A.pptx", ROOT / "tests/fixtures/basic/B.pptx"]
    window.add_sources(paths)
    wait_until(lambda: not window.is_loading)
    assert all(state.result and state.result.cache_hit for state in window._sources.values())
    first, second = [state.result.presentation for state in window._sources.values()]
    window.output_panel.add_slides((first.slides[1], second.slides[3], first.slides[0], first.slides[1]))
    report = {"cache_only": True, "output_slides": 4, "captures": []}
    for width, height in ((1600, 900), (1000, 640)):
        window.resize(width, height)
        QTest.qWait(100)
        filename = f"main_{width}x{height}.png"
        assert window.grab().save(str(directory / filename))
        report["captures"].append(filename)
        assert window.output_panel.view.width() > 0
        assert window.generate_button.isVisible()
    browser = FileBrowserDialog(window, initial_root=ROOT / "tests/fixtures")
    browser.show()
    wait_until(lambda: browser.model.rowCount(browser.tree.rootIndex()) > 0)
    basic = browser.model.index(str(ROOT / "tests/fixtures/basic"))
    browser.tree.expand(basic)
    wait_until(lambda: browser.model.rowCount(basic) >= 3)
    browser.tree.selectionModel().select(browser.model.index(str(paths[0])),
                                         QItemSelectionModel.SelectionFlag.Select |
                                         QItemSelectionModel.SelectionFlag.Rows)
    assert browser.add_button.isEnabled()
    QTest.qWait(100)
    assert browser.grab().save(str(directory / "browser_tree.png"))
    browser.search.setText("advanced")
    wait_until(lambda: not browser._debounce.isActive() and not browser._threads)
    assert browser.results.count() >= 2
    QTest.qWait(100)
    assert browser.grab().save(str(directory / "browser_search.png"))
    report["search_matches"] = browser.results.count()
    browser.reject()
    wait_until(lambda: not browser._threads)
    browser.deleteLater()
    # 실제 모달 실행과 선택 결과 전달도 확인한다.
    selected = FileBrowserDialog(window, initial_root=paths[0].parent)
    def accept_file():
        index = selected.model.index(str(paths[0]))
        if not index.isValid():
            QTimer.singleShot(10, accept_file)
            return
        selected.tree.setCurrentIndex(index)
        selected.add_button.click()
    QTimer.singleShot(100, accept_file)
    assert selected.exec() == QDialog.DialogCode.Accepted
    assert len(selected.selected_files) == 1
    selected.deleteLater()
    window.close()
    app.processEvents()
    report["modal_selection"] = True
    report["qt_platform"] = app.platformName()
    report["passed"] = True
    (directory / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8")
    print(directory)


if __name__ == "__main__":
    main()
