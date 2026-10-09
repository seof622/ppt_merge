"""파일 목록·썸네일 화면과 QThread 작업 상태를 연결한다."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import os
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QThread, QTimer, QSize, Qt, QUrl, Slot
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QLabel, QMainWindow, QProgressBar, QPushButton,
                               QSizePolicy, QSplitter, QToolBar, QVBoxLayout, QMessageBox, QWidget)

from src.ppt.thumbnail_service import ThumbnailProgress, ThumbnailResult, ThumbnailService
from src.ui.slide_grid import ElidedLabel, SlideGrid
from src.ui.source_panel import SourcePanel
from src.ui.icons import icon
from src.ui.output_panel import OutputPanel
from src.workers.ppt_worker import PptWorker, GenerationWorker
from src.ppt.powerpoint_service import (PowerPointService, GenerationPlan, GenerationProgress, GenerationResult)


@dataclass
class SourceState:
    path: str
    status: str = "queued"
    result: ThumbnailResult | None = None
    error: str = ""


class MainWindow(QMainWindow):
    def __init__(self, cache_root: Path,
                 service_factory: Callable[[], ThumbnailService] | None = None,
                 generation_service_factory: Callable[[], PowerPointService] | None = None) -> None:
        super().__init__()
        self.setWindowTitle("PPT Merge · 슬라이드 결합")
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
        self._loading_cancelling = False
        self._generation_factory = generation_service_factory or PowerPointService
        self._generation_thread: QThread | None = None
        self._generation_worker: GenerationWorker | None = None
        self._prepared_plan: GenerationPlan | None = None
        self._generation_outcome = ""
        self._generation_cancelling = False
        self._allow_mixed_sizes: bool | None = None
        self.last_generation_result: GenerationResult | None = None
        self._last_saved_result: GenerationResult | None = None
        self._browser_root: Path | None = None

        toolbar = QToolBar("파일 작업")
        toolbar.setMovable(False)
        toolbar.setObjectName("mainToolbar")
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        toolbar.setIconSize(QSize(20, 20))
        self.addToolBar(toolbar)
        self.add_action = QAction("최상위 폴더 선택", self)
        self.add_action.setShortcut(QKeySequence.StandardKey.Open)
        self.add_action.triggered.connect(self.choose_files)
        toolbar.addAction(self.add_action)
        self.root_label = ElidedLabel("")
        self.root_label.setFixedWidth(360)
        self.root_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self.root_label.setAccessibleName("최상위 폴더 경로")
        toolbar.addWidget(self.root_label)
        toolbar.addSeparator()
        self.remove_action = QAction("선택 파일 제거", self)
        self.remove_action.triggered.connect(self.remove_selected)
        toolbar.addAction(self.remove_action)
        self.clear_action = QAction("파일 목록 비우기", self)
        self.clear_action.triggered.connect(self.clear_sources)
        toolbar.addAction(self.clear_action)
        toolbar.addSeparator()
        self.reload_action = QAction("다시 읽기", self)
        self.reload_action.setShortcut(QKeySequence("Ctrl+R"))
        self.reload_action.triggered.connect(self.reload_selected)
        toolbar.addAction(self.reload_action)
        toolbar.addSeparator()
        self.help_action = QAction("사용 안내", self)
        self.help_action.triggered.connect(self._show_help)
        toolbar.addAction(self.help_action)
        for action, name in ((self.add_action, "folder"), (self.remove_action, "remove"),
                             (self.clear_action, "clear"), (self.reload_action, "reload"),
                             (self.help_action, "help")):
            action.setIcon(icon(name))
            shortcut = action.shortcut().toString()
            action.setToolTip(action.text() + (f" ({shortcut})" if shortcut else ""))
            toolbar.widgetForAction(action).setAccessibleName(action.text())
        toolbar.widgetForAction(self.add_action).setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.add_action.setIconText("폴더")

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
        drag_token = uuid4().hex
        self.slide_grid = SlideGrid(drag_token=drag_token)
        self.output_panel = OutputPanel(drag_token=drag_token)
        self.slide_grid.add_requested.connect(self.output_panel.add_slides)
        splitter.addWidget(self.source_panel)
        splitter.addWidget(self.slide_grid)
        splitter.setSizes([290, 1310])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)
        composer = QSplitter(Qt.Orientation.Vertical)
        composer.addWidget(splitter)
        composer.addWidget(self.output_panel)
        composer.setSizes([590, 310])
        composer.setCollapsible(0, False)
        composer.setCollapsible(1, False)
        layout.addWidget(composer, 1)
        self.generate_button = QPushButton("PPT 생성…")
        self.generate_button.setIcon(icon("file"))
        self.generate_button.setMinimumHeight(36)
        self.generate_button.clicked.connect(self.choose_output)
        self.output_panel.footer.addWidget(self.generate_button)
        self.output_panel.model.modelReset.connect(self._update_actions)
        self.output_panel.model.feedback.connect(self._on_output_feedback)
        self.setCentralWidget(container)
        self.source_panel.current_source_changed.connect(self._show_source)
        self.source_panel.selection_changed.connect(self._update_actions)
        self.source_panel.file_selected.connect(self._select_sidebar_file)
        self.source_panel.root_changed.connect(self._root_changed)
        self.source_panel.search_finished.connect(self._sidebar_search_finished)
        self._root_changed(str(self.source_panel.root_path))

        status = self.statusBar()
        status.setSizeGripEnabled(True)
        self.status_text = ElidedLabel("PPTX · PPTM")
        status.addWidget(self.status_text, 1)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(200)
        self.progress_bar.hide()
        status.addPermanentWidget(self.progress_bar)
        self.cancel_button = QPushButton("취소")
        self.cancel_button.setIcon(icon("clear"))
        self.cancel_button.clicked.connect(self.cancel_loading)
        self.cancel_button.hide()
        status.addPermanentWidget(self.cancel_button)
        self.open_file_button = QPushButton("PPT 파일 열기")
        self.open_file_button.clicked.connect(self._open_output_file)
        self.open_file_button.hide()
        status.addPermanentWidget(self.open_file_button)
        self.open_output_button = QPushButton("저장 폴더 열기")
        self.open_output_button.clicked.connect(self._open_output_folder)
        self.open_output_button.hide()
        status.addPermanentWidget(self.open_output_button)
        for button, name in ((self.open_file_button, "file"), (self.open_output_button, "folder")):
            description = button.text()
            button.setIcon(icon(name))
            button.setText("")
            button.setToolTip(description)
            button.setAccessibleName(description)
        self._update_actions()

    @property
    def is_loading(self) -> bool:
        return self._thread is not None

    @property
    def is_generating(self) -> bool:
        return self._generation_thread is not None

    @property
    def is_busy(self) -> bool:
        return self.is_loading or self.is_generating

    @Slot(str)
    def _on_output_feedback(self, message: str) -> None:
        if not self.is_busy and not self._closing:
            self.status_text.setText(message)

    def _open_output_file(self) -> None:
        if self.is_busy or self._closing or self._last_saved_result is None:
            return
        path = Path(self._last_saved_result.output_path)
        if not path.is_file():
            self._show_generation_error("저장한 PPT 파일을 찾을 수 없습니다. 파일이 이동되거나 삭제되었는지 확인하세요.")
        elif not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            self._show_generation_error(f"PPT 파일을 열지 못했습니다. PowerPoint 연결 설정을 확인하세요: {path}")
        else:
            self.notice.hide()
            self.status_text.setText("PPT 파일 열기를 요청했습니다. 다시 생성하려면 PowerPoint를 닫아 주세요.")

    def _open_output_folder(self) -> None:
        if self.is_busy or self._closing or self._last_saved_result is None:
            return
        directory = Path(self._last_saved_result.output_path).parent
        if not directory.is_dir():
            self._show_generation_error("저장 폴더를 찾을 수 없습니다. 파일이 이동되었는지 확인하세요.")
        elif not QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory))):
            self._show_generation_error(f"저장 폴더를 열지 못했습니다. 탐색기에서 확인하세요: {directory}")

    def choose_output(self) -> None:
        if self.is_busy or self._closing:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "새 PowerPoint 저장", "result.pptx", "PowerPoint (*.pptx)",
            options=QFileDialog.Option.DontConfirmOverwrite)
        if not filename:
            return
        path = Path(filename)
        if not path.suffix:
            path = path.with_suffix(".pptx")
        originals = [state.path for state in self._sources.values()]
        originals += [slide.source_file for slide in self.output_panel.output_slides]
        if any(os.path.normcase(str(Path(source).resolve())) == os.path.normcase(str(path.resolve()))
               or (path.exists() and Path(source).exists() and path.samefile(source)) for source in originals):
            self._show_generation_error("원본 PowerPoint 파일에는 저장할 수 없습니다. 다른 경로를 선택하세요.")
            return
        overwrite = False
        if path.exists():
            overwrite = QMessageBox.question(
                self, "파일 덮어쓰기", f"기존 파일을 덮어쓸까요?\n{path}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes
            if not overwrite:
                return
        self.start_generation(path, overwrite=overwrite)

    def start_generation(self, output: Path, *, overwrite: bool = False,
                         allow_mixed_sizes: bool | None = None) -> bool:
        if self.is_busy or self._closing or not self.output_panel.output_slides:
            return False
        self._allow_mixed_sizes = allow_mixed_sizes
        self.last_generation_result = None
        self.notice.hide()
        self._launch_generation_worker(GenerationWorker(
            self._generation_factory, tuple(self.output_panel.output_slides), output, overwrite=overwrite))
        return True

    def _launch_generation_worker(self, worker: GenerationWorker) -> None:
        self._prepared_plan = None
        self._generation_outcome = ""
        self._generation_cancelling = False
        thread = QThread(self)
        self._generation_thread, self._generation_worker = thread, worker
        worker.moveToThread(thread)
        thread.started.connect(worker.run, Qt.ConnectionType.QueuedConnection)
        worker.prepared.connect(self._on_prepared, Qt.ConnectionType.QueuedConnection)
        worker.generated.connect(self._on_generated, Qt.ConnectionType.QueuedConnection)
        worker.progress.connect(self._on_generation_progress, Qt.ConnectionType.QueuedConnection)
        worker.failed.connect(self._show_generation_error, Qt.ConnectionType.QueuedConnection)
        worker.cancelled.connect(self._on_generation_cancelled, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(thread.quit, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(self._generation_finished, Qt.ConnectionType.QueuedConnection)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()
        self.cancel_button.setText("취소")
        self.cancel_button.setEnabled(True)
        self.cancel_button.show()
        self.status_text.setText("PPT 생성 작업을 준비합니다…")
        self._update_actions()
        thread.start()

    @Slot(object)
    def _on_prepared(self, plan: GenerationPlan) -> None:
        self._prepared_plan = plan

    @Slot(object)
    def _on_generated(self, result: GenerationResult) -> None:
        self.last_generation_result = result
        self._last_saved_result = result
        self.open_file_button.setToolTip(f"{result.output_path}\n다시 생성하려면 PowerPoint를 닫아 주세요.")
        self.open_output_button.setToolTip(f"{Path(result.output_path).name}\n{Path(result.output_path).parent}")
        self._generation_outcome = f"저장 완료 · {result.slide_count}장 · {result.output_path}"

    @Slot(object)
    def _on_generation_progress(self, event: GenerationProgress) -> None:
        if self._generation_cancelling or self._closing:
            return
        labels = {"checking": "원본 확인", "opening": "PowerPoint 시작", "copying": "슬라이드 결합",
                  "saving": "PPT 저장", "saved": "PowerPoint 정리", "verifying": "결과 확인", "publishing": "결과 파일 저장", "completed": "저장 완료"}
        self.progress_bar.setRange(0, event.total if event.stage in ("checking", "copying", "completed") else 0)
        self.progress_bar.setValue(event.completed)
        self.status_text.setText(labels.get(event.stage, "PPT 생성") +
                                 (f" · {event.completed}/{event.total}" if event.total else "…") +
                                 (f" · {Path(event.source_file).name}" if event.source_file else ""))

    @Slot(str)
    def _show_generation_error(self, message: str) -> None:
        self._generation_outcome = message
        self.notice.setText(message)
        self.notice.setToolTip(message)
        self.notice.show()

    @Slot()
    def _on_generation_cancelled(self) -> None:
        self._generation_outcome = "PPT 생성을 취소했습니다."

    @Slot()
    def _generation_finished(self) -> None:
        thread = self._generation_thread
        if thread is not None and not thread.wait(0):
            QTimer.singleShot(10, self._generation_finished)
            return
        plan = self._prepared_plan
        self._prepared_plan = None
        self._generation_thread = self._generation_worker = None
        if thread is not None:
            thread.deleteLater()
        self.progress_bar.hide()
        self.cancel_button.hide()
        self._update_actions()
        if self._closing:
            QTimer.singleShot(0, self.close)
            return
        if plan is not None and not self._generation_cancelling:
            allow = self._allow_mixed_sizes
            if plan.mixed_sizes and allow is None:
                descriptions = "\n".join(f"{Path(s.path).name}: {s.width_points:g} × {s.height_points:g} pt"
                                         for s in plan.sources)
                allow = QMessageBox.warning(
                    self, "슬라이드 크기가 다릅니다",
                    f"{descriptions}\n\n첫 출력 슬라이드의 크기로 저장합니다. "
                    "비율이 다른 슬라이드는 모양이나 배치가 달라질 수 있습니다. 계속할까요?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes
            if plan.mixed_sizes and not allow:
                self.status_text.setText("슬라이드 크기 확인 후 생성을 취소했습니다.")
                return
            self._launch_generation_worker(GenerationWorker(
                self._generation_factory, plan=plan, allow_mixed_sizes=bool(allow)))
        else:
            self.status_text.setText(self._generation_outcome or "PPT 생성을 취소했습니다.")
            self._start_pending()

    def choose_files(self) -> None:
        if self._closing or self.is_generating:
            return
        directory = QFileDialog.getExistingDirectory(
            self, "최상위 폴더 선택", str(self.source_panel.root_path))
        if directory:
            self.source_panel.set_root(directory)

    def _root_changed(self, path: str) -> None:
        self._browser_root = Path(path)
        self.root_label.setText(path)
        self.root_label.setToolTip(path)

    def _select_sidebar_file(self, path: str) -> None:
        if self._closing or self.is_generating:
            return
        key = os.path.normcase(str(Path(path).resolve()))
        self.add_sources([path])
        if key in self._sources:
            self._show_source(key)
            self._update_actions()

    def _sidebar_search_finished(self) -> None:
        if self._closing and not self.is_busy:
            QTimer.singleShot(0, self.close)

    def _show_help(self) -> None:
        QMessageBox.information(
            self, "사용 안내", "최상위 폴더: 좌상단 폴더 버튼 · Ctrl+O\n"
            "원본 선택: 왼쪽 폴더 펼치기 · PPT 클릭 · 파일 끌어 놓기\n"
            "슬라이드 담기: + 버튼 · 더블클릭 · 출력 영역에 끌어 놓기\n"
            "여러 항목 선택: Ctrl·Shift\n"
            "출력 편집: 드래그로 순서 변경 · Delete 삭제 · Ctrl+D 복제\n\n"
            "PPT 생성으로 저장하세요. 편집 목록은 앱 종료 시 초기화됩니다.")

    def add_sources(self, paths: Iterable[str | Path]) -> None:
        if self._closing or self.is_generating:
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
        if self.is_busy or not self._pending or self._closing:
            return
        self._loading_cancelling = False
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
        self.cancel_button.setText("취소")
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
        self.source_panel.set_state(key, path, f"{result.presentation.slide_count}장{suffix}", state="ready")
        if key == self.source_panel.current_key():
            self._show_source(key)

    @Slot(str, object)
    def _on_progress(self, path: str, event: ThumbnailProgress) -> None:
        if self._loading_cancelling or self._closing:
            return
        key = os.path.normcase(path)
        state = self._sources.get(key)
        if state is None:
            return
        state.status = "loading"
        labels = {"checking": "파일 확인", "loading": "PPT 읽기", "exporting": "썸네일 생성",
                  "cached": "캐시 불러오기", "completed": "완료"}
        label = labels.get(event.stage, "불러오기")
        position = f"파일 {self._active.index(key) + 1}/{len(self._active)} · " if key in self._active else ""
        self.status_text.setText(f"{position}{Path(path).name} · {label}"
                                 + (f" {event.completed}/{event.total}" if event.total else "…"))
        self.progress_bar.setRange(0, event.total if event.total else 0)
        self.progress_bar.setValue(event.completed)
        self.source_panel.set_state(key, path, "불러오는 중", label, state="loading")
        if key == self.source_panel.current_key() and state.result is None:
            self._show_source(key)

    @Slot(str, str)
    def _on_failed(self, path: str, message: str) -> None:
        key = os.path.normcase(path)
        state = self._sources.get(key)
        if state:
            state.status, state.error = "failed", message
            state.result = None
            self.source_panel.set_state(key, path, "읽기 실패", message, state="failed")
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
        self.source_panel.set_state(key, state.path, "불러오기 취소", state="cancelled")
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
        self._update_summary()
        self._update_actions()
        if self._closing:
            QTimer.singleShot(0, self.close)
        else:
            self._start_pending()

    def cancel_loading(self) -> None:
        if self._generation_worker is not None:
            self._generation_cancelling = True
            self.cancel_button.setText("취소 중…")
            self._generation_worker.request_cancel()
            self.cancel_button.setEnabled(False)
            self.status_text.setText("현재 작업을 마친 뒤 PPT 생성을 취소합니다…")
        for key in self._pending:
            self._mark_cancelled(key)
        self._pending.clear()
        if self._worker is not None:
            self._loading_cancelling = True
            self.cancel_button.setText("취소 중…")
            self._worker.request_cancel()
            self.cancel_button.setEnabled(False)
            self.status_text.setText("현재 슬라이드 작업을 마친 뒤 취소합니다…")

    @Slot(str)
    def _show_source(self, key: str) -> None:
        state = self._sources.get(key)
        if state is None:
            self.slide_grid.show_message("슬라이드", "PPT를 추가하세요")
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
        available = not self.is_busy and not self._closing
        self.open_file_button.setVisible(self._last_saved_result is not None and available)
        self.open_output_button.setVisible(self._last_saved_result is not None and available)
        self.remove_action.setEnabled(selected and available)
        self.reload_action.setEnabled(selected and available)
        self.clear_action.setEnabled(bool(self._sources) and available)
        self.add_action.setEnabled(not self._closing and not self.is_generating)
        self.generate_button.setEnabled(bool(self.output_panel.output_slides) and available)
        self.output_panel.setEnabled(not self.is_generating and not self._closing)
        self.slide_grid.setEnabled(not self.is_generating and not self._closing)
        self.source_panel.setEnabled(not self.is_generating and not self._closing)

    def remove_selected(self) -> None:
        if self.is_busy or self._closing:
            return
        keys = self.source_panel.selected_keys()
        for key in keys:
            self._sources.pop(key, None)
        self.source_panel.remove_sources(keys)
        self._show_source(self.source_panel.current_key())
        self._update_summary()

    def clear_sources(self) -> None:
        if self.is_busy or self._closing:
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
        failed = sum(state.status == "failed" for state in self._sources.values())
        cancelled = sum(state.status == "cancelled" for state in self._sources.values())
        self.status_text.setText(f"{len(ready)}개 파일 · {count}장 준비됨"
                                 + (f" · 읽기 실패 {failed}개" if failed else "")
                                 + (f" · 취소 {cancelled}개" if cancelled else ""))

    def reload_selected(self) -> None:
        if self.is_busy or self._closing:
            return
        for key in self.source_panel.selected_keys():
            self._sources[key].status = "queued"
            self._sources[key].error = ""
            self.source_panel.set_state(key, self._sources[key].path, "읽기 대기")
            self._pending.append(key)
        self._start_pending()

    def dragEnterEvent(self, event) -> None:
        if not self._closing and not self.is_generating and event.mimeData().hasUrls():
            if any(url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in (".pptx", ".pptm")
                   for url in event.mimeData().urls()):
                event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        self.add_sources(url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile())
        event.acceptProposedAction()

    def closeEvent(self, event) -> None:
        self.source_panel.shutdown_search()
        if self.is_busy or self.source_panel.has_search:
            self._closing = True
            self.cancel_loading()
            self._update_actions()
            self.status_text.setText("진행 중인 작업을 정리한 뒤 창을 닫습니다…")
            event.ignore()
        else:
            event.accept()
