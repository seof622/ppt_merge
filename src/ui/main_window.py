"""파일 목록·썸네일 화면과 QThread 작업 상태를 연결한다."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import os
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt, Slot
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QLabel, QMainWindow, QProgressBar, QPushButton,
                               QSplitter, QToolBar, QVBoxLayout, QWidget)

from src.ppt.thumbnail_service import ThumbnailProgress, ThumbnailResult, ThumbnailService
from src.ui.slide_grid import ElidedLabel, SlideGrid
from src.ui.source_panel import SourcePanel
from src.workers.ppt_worker import PptWorker


@dataclass
class SourceState:
    path: str
    status: str = "queued"
    result: ThumbnailResult | None = None
    error: str = ""


class MainWindow(QMainWindow):
    def __init__(self, cache_root: Path,
                 service_factory: Callable[[], ThumbnailService] | None = None) -> None:
        super().__init__()
        self.setWindowTitle("PPT Merge · 슬라이드 미리보기")
        self.resize(1600, 900)
        self.setMinimumSize(1000, 640)
        self.setAcceptDrops(True)
        self._service_factory = service_factory or (lambda: ThumbnailService(cache_root))
        self._sources: dict[str, SourceState] = {}
        self._pending: list[str] = []
        self._active: tuple[str, ...] = ()
        self._thread: QThread | None = None
        self._worker: PptWorker | None = None
        self._closing = False

        toolbar = QToolBar("파일 작업")
        toolbar.setMovable(False)
        toolbar.setObjectName("mainToolbar")
        self.addToolBar(toolbar)
        self.add_action = QAction("PPT 추가", self)
        self.add_action.setShortcut(QKeySequence.StandardKey.Open)
        self.add_action.triggered.connect(self.choose_files)
        toolbar.addAction(self.add_action)
        toolbar.addSeparator()
        self.remove_action = QAction("선택 파일 제거", self)
        self.remove_action.triggered.connect(self.remove_selected)
        toolbar.addAction(self.remove_action)
        self.clear_action = QAction("전체 비우기", self)
        self.clear_action.triggered.connect(self.clear_sources)
        toolbar.addAction(self.clear_action)
        toolbar.addSeparator()
        self.reload_action = QAction("다시 읽기", self)
        self.reload_action.setShortcut(QKeySequence("Ctrl+R"))
        self.reload_action.triggered.connect(self.reload_selected)
        toolbar.addAction(self.reload_action)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.notice = QLabel()
        self.notice.setObjectName("notice")
        self.notice.setWordWrap(True)
        self.notice.hide()
        layout.addWidget(self.notice)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.source_panel = SourcePanel()
        self.source_panel.setMinimumWidth(240)
        self.source_panel.setMaximumWidth(420)
        self.slide_grid = SlideGrid()
        splitter.addWidget(self.source_panel)
        splitter.addWidget(self.slide_grid)
        splitter.setSizes([290, 1310])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(container)
        self.source_panel.current_source_changed.connect(self._show_source)
        self.source_panel.selection_changed.connect(self._update_actions)

        status = self.statusBar()
        status.setSizeGripEnabled(True)
        self.status_text = ElidedLabel("PPT 파일을 추가하거나 창에 끌어 놓으세요.")
        status.addWidget(self.status_text, 1)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.hide()
        status.addPermanentWidget(self.progress_bar)
        self.cancel_button = QPushButton("취소")
        self.cancel_button.clicked.connect(self.cancel_loading)
        self.cancel_button.hide()
        status.addPermanentWidget(self.cancel_button)
        self._update_actions()

    @property
    def is_loading(self) -> bool:
        return self._thread is not None

    def choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "PowerPoint 파일 추가", "",
                                               "PowerPoint (*.pptx *.pptm)")
        self.add_sources(paths)

    def add_sources(self, paths: Iterable[str | Path]) -> None:
        if self._closing:
            return
        rejected = []
        added = []
        for value in paths:
            try:
                path = Path(value).resolve()
                if path.suffix.lower() not in (".pptx", ".pptm") or not path.is_file():
                    rejected.append(str(value))
                    continue
            except OSError:
                rejected.append(str(value))
                continue
            key = os.path.normcase(str(path))
            if key in self._sources:
                continue
            self._sources[key] = SourceState(str(path))
            self.source_panel.add_source(key, str(path))
            self._pending.append(key)
            added.append(key)
        if rejected:
            self.notice.setText(f"추가하지 못한 파일 {len(rejected)}개: 존재하는 PPTX 또는 PPTM 파일을 선택하세요.")
            self.notice.setToolTip("\n".join(rejected))
            self.notice.show()
        elif added:
            self.notice.hide()
        if added and not self.source_panel.current_key():
            self.source_panel.select_source(added[0])
        self._update_actions()
        self._start_pending()

    def _start_pending(self) -> None:
        if self.is_loading or not self._pending or self._closing:
            return
        self._active = tuple(self._pending)
        self._pending.clear()
        sources = tuple(self._sources[key].path for key in self._active)
        self._thread = QThread(self)
        self._worker = PptWorker(sources, self._service_factory)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run, Qt.ConnectionType.QueuedConnection)
        # 스레드·Python 서브클래스의 자동 연결 추론에 맡기지 않고 GUI 큐로 전달한다.
        self._worker.loaded.connect(self._on_loaded, Qt.ConnectionType.QueuedConnection)
        self._worker.progress.connect(self._on_progress, Qt.ConnectionType.QueuedConnection)
        self._worker.failed.connect(self._on_failed, Qt.ConnectionType.QueuedConnection)
        self._worker.cancelled.connect(self._on_cancelled, Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._thread.quit, Qt.ConnectionType.QueuedConnection)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._worker_finished, Qt.ConnectionType.QueuedConnection)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        self.status_text.setText("PPT를 불러오는 중입니다…")
        self._update_actions()
        self._thread.start()

    @Slot(str, object)
    def _on_loaded(self, path: str, result: ThumbnailResult) -> None:
        key = os.path.normcase(path)
        state = self._sources.get(key)
        if state is None:
            return
        state.result, state.error, state.status = result, "", "ready"
        suffix = " · 캐시" if result.cache_hit else ""
        self.source_panel.set_state(key, path, f"{result.presentation.slide_count}장{suffix}")
        if key == self.source_panel.current_key():
            self._show_source(key)

    @Slot(str, object)
    def _on_progress(self, path: str, event: ThumbnailProgress) -> None:
        key = os.path.normcase(path)
        state = self._sources.get(key)
        if state is None:
            return
        state.status = "loading"
        labels = {"checking": "파일 확인", "loading": "PPT 읽기", "exporting": "썸네일 생성",
                  "cached": "캐시 불러오기", "completed": "완료"}
        label = labels.get(event.stage, "불러오기")
        self.status_text.setText(f"{Path(path).name} · {label}"
                                 + (f" {event.completed}/{event.total}" if event.total else "…"))
        self.progress_bar.setRange(0, event.total if event.total else 0)
        self.progress_bar.setValue(event.completed)
        self.source_panel.set_state(key, path, "불러오는 중")
        if key == self.source_panel.current_key() and state.result is None:
            self._show_source(key)

    @Slot(str, str)
    def _on_failed(self, path: str, message: str) -> None:
        key = os.path.normcase(path)
        state = self._sources.get(key)
        if state:
            state.status, state.error = "failed", message
            state.result = None
            self.source_panel.set_state(key, path, "읽기 실패", message)
            if key == self.source_panel.current_key():
                self._show_source(key)

    @Slot(str)
    def _on_cancelled(self, path: str) -> None:
        key = os.path.normcase(path)
        if key in self._sources:
            self._mark_cancelled(key)

    def _mark_cancelled(self, key: str) -> None:
        state = self._sources[key]
        state.status = "cancelled"
        self.source_panel.set_state(key, state.path, "불러오기 취소")
        if key == self.source_panel.current_key():
            self._show_source(key)

    @Slot()
    def _worker_finished(self) -> None:
        thread = self._thread
        # finished 신호 직후에도 Qt의 스레드 로컬 정리가 남을 수 있다.
        # GUI를 멈추지 않고 실제 종료까지 참조를 유지한 뒤 해제한다.
        if thread is not None and not thread.wait(0):
            QTimer.singleShot(10, self._worker_finished)
            return
        self._thread = self._worker = None
        for key in self._active:
            if self._sources[key].status in ("queued", "loading"):
                self._mark_cancelled(key)
        self._active = ()
        if thread is not None:
            thread.deleteLater()
        self.progress_bar.hide()
        self.cancel_button.hide()
        ready = [state for state in self._sources.values() if state.status == "ready"]
        failed = sum(state.status == "failed" for state in self._sources.values())
        count = sum(state.result.presentation.slide_count for state in ready)
        self.status_text.setText(f"{len(ready)}개 파일 · {count}장 준비됨" + (f" · 읽기 실패 {failed}개" if failed else ""))
        self._update_actions()
        if self._closing:
            QTimer.singleShot(0, self.close)
        else:
            self._start_pending()

    def cancel_loading(self) -> None:
        for key in self._pending:
            self._mark_cancelled(key)
        self._pending.clear()
        if self._worker is not None:
            self._worker.request_cancel()
            self.cancel_button.setEnabled(False)
            self.status_text.setText("현재 슬라이드 작업을 마친 뒤 취소합니다…")

    @Slot(str)
    def _show_source(self, key: str) -> None:
        state = self._sources.get(key)
        if state is None:
            self.slide_grid.show_message("슬라이드 미리보기", "PPT 파일을 추가하면 이곳에 슬라이드가 표시됩니다.")
        elif state.status == "failed":
            self.slide_grid.show_message(Path(state.path).name, state.error + "\n\n문제를 해결한 뒤 ‘다시 읽기’를 누르세요.")
        elif state.result is not None:
            self.slide_grid.show_presentation(state.result.presentation)
        elif state.status == "cancelled":
            self.slide_grid.show_message(Path(state.path).name, "불러오기를 취소했습니다. ‘다시 읽기’로 재시도할 수 있습니다.")
        else:
            self.slide_grid.show_message(Path(state.path).name, "슬라이드를 불러오는 중입니다…")
        self._update_actions()

    def _update_actions(self) -> None:
        selected = bool(self.source_panel.selected_keys())
        available = not self.is_loading and not self._closing
        self.remove_action.setEnabled(selected and available)
        self.reload_action.setEnabled(selected and available)
        self.clear_action.setEnabled(bool(self._sources) and available)
        self.add_action.setEnabled(not self._closing)

    def remove_selected(self) -> None:
        if self.is_loading or self._closing:
            return
        keys = self.source_panel.selected_keys()
        for key in keys:
            self._sources.pop(key, None)
        self.source_panel.remove_sources(keys)
        self._show_source(self.source_panel.current_key())
        self._update_summary()

    def clear_sources(self) -> None:
        if self.is_loading or self._closing:
            return
        self._sources.clear()
        self._pending.clear()
        self.source_panel.clear_sources()
        self.notice.hide()
        self._show_source("")
        self._update_summary()

    def _update_summary(self) -> None:
        ready = [state for state in self._sources.values() if state.status == "ready"]
        count = sum(state.result.presentation.slide_count for state in ready)
        self.status_text.setText(f"{len(ready)}개 파일 · {count}장 준비됨")

    def reload_selected(self) -> None:
        if self.is_loading or self._closing:
            return
        for key in self.source_panel.selected_keys():
            self._sources[key].status = "queued"
            self._sources[key].error = ""
            self.source_panel.set_state(key, self._sources[key].path, "읽기 대기")
            self._pending.append(key)
        self._start_pending()

    def dragEnterEvent(self, event) -> None:
        if not self._closing and event.mimeData().hasUrls():
            if any(url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in (".pptx", ".pptm")
                   for url in event.mimeData().urls()):
                event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        self.add_sources(url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile())
        event.acceptProposedAction()

    def closeEvent(self, event) -> None:
        if self.is_loading:
            self._closing = True
            self.cancel_loading()
            self._update_actions()
            self.status_text.setText("PowerPoint 작업을 정리한 뒤 창을 닫습니다…")
            event.ignore()
        else:
            event.accept()
