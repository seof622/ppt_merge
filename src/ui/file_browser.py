"""앱 안의 PPT 폴더 트리와 취소 가능한 하위 폴더 검색."""

from pathlib import Path

from PySide6.QtCore import QDir, QThread, QTimer, Qt, QStandardPaths, Signal, Slot
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QFileDialog,
                               QFileSystemModel, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMessageBox, QPushButton,
                               QStackedWidget, QTreeView, QVBoxLayout)

from src.ui.icons import icon, icon_button
from src.ui.slide_grid import ElidedLabel
from src.utils.file_search import SearchSummary, is_presentation, search_presentations


class FileSearchThread(QThread):
    batch_found = Signal(int, object)
    completed = Signal(int, object)

    def __init__(self, token: int, root: Path, query: str, parent=None) -> None:
        super().__init__(parent)
        self.token, self.root, self.query = token, root, query

    def run(self) -> None:
        summary = search_presentations(
            self.root, self.query, lambda paths: self.batch_found.emit(self.token, paths),
            self.isInterruptionRequested)
        self.completed.emit(self.token, summary)


class FileBrowserDialog(QDialog):
    def __init__(self, parent=None, *, initial_root: Path | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PPT 추가")
        self.resize(850, 620)
        self.setMinimumSize(560, 400)
        self.selected_files: list[str] = []
        self._token = 0
        self._threads: list[FileSearchThread] = []
        self._pending_result: int | None = None
        self._root = Path.home()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)
        locations = QHBoxLayout()
        self.location = QComboBox()
        self.location.setAccessibleName("탐색 시작 폴더")
        self.location.setToolTip("탐색 시작 폴더")
        for label, kind in (("바탕화면", QStandardPaths.StandardLocation.DesktopLocation),
                            ("문서", QStandardPaths.StandardLocation.DocumentsLocation),
                            ("다운로드", QStandardPaths.StandardLocation.DownloadLocation),
                            ("홈", QStandardPaths.StandardLocation.HomeLocation)):
            directory = QStandardPaths.writableLocation(kind)
            if directory and Path(directory).is_dir():
                self.location.addItem(icon("folder"), label, directory)
        locations.addWidget(self.location)
        self.path_label = ElidedLabel("")
        locations.addWidget(self.path_label, 1)
        self.folder_button = icon_button("folder", "시작 폴더 선택", self)
        self.folder_button.clicked.connect(self.choose_root)
        locations.addWidget(self.folder_button)
        layout.addLayout(locations)
        self.search = QLineEdit()
        self.search.setPlaceholderText("파일명 검색 · 하위 폴더 포함")
        self.search.setAccessibleName("PPT 파일명 검색")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(icon("search"), QLineEdit.ActionPosition.LeadingPosition)
        layout.addWidget(self.search)
        self.stack = QStackedWidget()
        self.tree = QTreeView()
        self.tree.setAccessibleName("PPT 폴더 트리")
        self.model = QFileSystemModel(self)
        self.model.setReadOnly(True)
        self.model.setFilter(QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)
        self.model.setNameFilters(["*.pptx", "*.pptm"])
        self.model.setNameFilterDisables(False)
        self.model.setOption(QFileSystemModel.Option.DontUseCustomDirectoryIcons, True)
        self.tree.setModel(self.model)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setUniformRowHeights(True)
        self.tree.setHeaderHidden(True)
        for column in range(1, self.model.columnCount()):
            self.tree.hideColumn(column)
        self.tree.doubleClicked.connect(self._tree_double_clicked)
        self.tree.selectionModel().selectionChanged.connect(self._update_selection)
        self.stack.addWidget(self.tree)
        self.results = QListWidget()
        self.results.setObjectName("fileSearchResults")
        self.results.setAccessibleName("PPT 검색 결과")
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.results.itemSelectionChanged.connect(self._update_selection)
        self.results.itemDoubleClicked.connect(lambda item: self._accept_selection())
        self.stack.addWidget(self.results)
        layout.addWidget(self.stack, 1)
        footer = QHBoxLayout()
        self.status = ElidedLabel("PPTX · PPTM")
        footer.addWidget(self.status, 1)
        self.cancel_button = QPushButton("취소")
        self.cancel_button.clicked.connect(self.reject)
        footer.addWidget(self.cancel_button)
        self.add_button = QPushButton("추가")
        self.add_button.setDefault(True)
        self.add_button.clicked.connect(self._accept_selection)
        footer.addWidget(self.add_button)
        layout.addLayout(footer)
        self.tree.setToolTip("Ctrl·Shift로 여러 PPT 선택 · 더블클릭으로 추가")
        self.results.setToolTip("Ctrl·Shift로 여러 PPT 선택 · 더블클릭으로 추가")
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._start_search)
        self.search.textChanged.connect(self._query_changed)
        self.location.currentIndexChanged.connect(self._location_changed)
        start = initial_root or Path(self.location.currentData() or Path.home())
        self.set_root(start)

    @property
    def root_path(self) -> Path:
        return self._root

    def choose_root(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "탐색 시작 폴더", str(self._root))
        if directory:
            self.set_root(Path(directory))

    def _location_changed(self, index: int) -> None:
        directory = self.location.itemData(index)
        if directory:
            self.set_root(Path(directory))

    def set_root(self, directory: Path) -> None:
        directory = directory.resolve()
        if not directory.is_dir():
            QMessageBox.warning(self, "폴더 확인", "폴더를 찾을 수 없습니다.")
            return
        self._root = directory
        self.path_label.setText(str(directory))
        self.location.blockSignals(True)
        index = next((i for i in range(self.location.count())
                      if Path(self.location.itemData(i)).resolve() == directory), -1)
        if index < 0:
            self.location.addItem(icon("folder"), directory.name or str(directory), str(directory))
            index = self.location.count() - 1
        self.location.setCurrentIndex(index)
        self.location.blockSignals(False)
        self.tree.clearSelection()
        self.tree.setRootIndex(self.model.setRootPath(str(directory)))
        self._query_changed(self.search.text())

    def _invalidate_search(self) -> None:
        self._token += 1
        self._debounce.stop()
        for thread in self._threads:
            thread.requestInterruption()

    def _query_changed(self, text: str) -> None:
        if self._pending_result is not None:
            return
        self._invalidate_search()
        self.results.clear()
        if text.strip():
            self.tree.clearSelection()
            self.stack.setCurrentWidget(self.results)
            self.status.setText("검색 중…")
            self._debounce.start()
        else:
            self.stack.setCurrentWidget(self.tree)
            self.status.setText("PPTX · PPTM")
        self._update_selection()

    def _start_search(self) -> None:
        if self._pending_result is not None or not self.search.text().strip():
            return
        thread = FileSearchThread(self._token, self._root, self.search.text(), self)
        self._threads.append(thread)
        thread.batch_found.connect(self._on_batch, Qt.ConnectionType.QueuedConnection)
        thread.completed.connect(self._on_completed, Qt.ConnectionType.QueuedConnection)
        thread.finished.connect(self._cleanup_threads, Qt.ConnectionType.QueuedConnection)
        thread.start()

    @Slot(int, object)
    def _on_batch(self, token: int, paths: tuple[str, ...]) -> None:
        if token != self._token or self._pending_result is not None:
            return
        for value in paths:
            relative = Path(value).relative_to(self._root)
            item = QListWidgetItem(icon("file"), str(relative))
            item.setData(Qt.ItemDataRole.UserRole, value)
            item.setToolTip(value)
            self.results.addItem(item)
        self.status.setText(f"{self.results.count()}개 · 검색 중…")

    @Slot(int, object)
    def _on_completed(self, token: int, summary: SearchSummary) -> None:
        if token != self._token or self._pending_result is not None:
            return
        text = f"{summary.matches}개" if summary.matches else "검색 결과 없음"
        if summary.limited:
            text += " · 2,000개까지만 표시 · 검색어를 좁혀 주세요"
        if summary.skipped:
            text += f" · 접근 불가 {summary.skipped}개"
        self.status.setText(text)

    @Slot()
    def _cleanup_threads(self) -> None:
        for thread in self._threads[:]:
            if thread.wait(0):
                self._threads.remove(thread)
                thread.deleteLater()
        if self._threads and all(thread.isFinished() for thread in self._threads):
            QTimer.singleShot(10, self._cleanup_threads)
        if self._pending_result is not None and not self._threads:
            super().done(self._pending_result)

    def _selection(self) -> list[str]:
        if self.stack.currentWidget() == self.results:
            values = [item.data(Qt.ItemDataRole.UserRole) for item in self.results.selectedItems()]
        else:
            values = [self.model.filePath(index) for index in
                      self.tree.selectionModel().selectedRows(0) if not self.model.isDir(index)]
        return [value for value in values if is_presentation(value)]

    def _update_selection(self, *args) -> None:
        count = len(self._selection())
        self.add_button.setText(f"추가 ({count})" if count else "추가")
        self.add_button.setEnabled(count > 0)

    def _tree_double_clicked(self, index) -> None:
        if not self.model.isDir(index):
            self._accept_selection()

    def _accept_selection(self) -> None:
        paths = self._selection()
        if not paths:
            return
        if any(not Path(value).is_file() for value in paths):
            self.status.setText("파일이 이동되거나 삭제되었습니다. 다시 선택하세요.")
            return
        self.selected_files = paths
        self.accept()

    def done(self, result: int) -> None:
        self._invalidate_search()
        self._pending_result = result
        if self._threads:
            self.search.setEnabled(False)
            self.location.setEnabled(False)
            self.folder_button.setEnabled(False)
            self.add_button.setEnabled(False)
            self.cancel_button.setEnabled(False)
            self.status.setText("검색 정리 중…")
            self._cleanup_threads()
        else:
            super().done(result)

    def accept(self) -> None:
        self.done(QDialog.DialogCode.Accepted)

    def reject(self) -> None:
        self.done(QDialog.DialogCode.Rejected)

    def closeEvent(self, event) -> None:
        event.ignore()
        self.reject()
