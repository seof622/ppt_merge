"""메인 화면의 폴더 탐색과 읽은 원본 목록. COM을 호출하지 않는다."""
from pathlib import Path
from PySide6.QtCore import QDir, QStandardPaths, QTimer, Qt, Signal, Slot
from PySide6.QtWidgets import (QAbstractItemView, QFileSystemModel, QFrame, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QStackedWidget, QStyle, QTabWidget, QTreeView, QVBoxLayout)
from src.ui.file_browser import FileSearchThread, SourceTreeModel, source_key

class SourcePanel(QFrame):
    current_source_changed = Signal(str)
    selection_changed = Signal()
    file_selected = Signal(str)
    root_changed = Signal(str)
    search_finished = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sourcePanel")
        self._items: dict[str, QListWidgetItem] = {}
        self._search_threads: list[FileSearchThread] = []
        self._search_token = 0
        self._closing = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 14, 12, 12)
        self.heading = QLabel("파일")
        self.heading.setObjectName("sectionTitle")
        layout.addWidget(self.heading)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        explorer = QFrame()
        inner = QVBoxLayout(explorer)
        inner.setContentsMargins(0, 10, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("PPT 검색")
        self.search.setAccessibleName("최상위 폴더 아래의 PPT 파일명 검색")
        self.search.setClearButtonEnabled(True)
        inner.addWidget(self.search)
        self.stack = QStackedWidget()
        inner.addWidget(self.stack, 1)
        self.file_model = QFileSystemModel(self)
        self.file_model.setReadOnly(True)
        self.file_model.setOption(QFileSystemModel.Option.DontUseCustomDirectoryIcons)
        self.file_model.setFilter(QDir.Filter.AllDirs | QDir.Filter.Files | QDir.Filter.NoDotAndDotDot)
        self.file_model.setNameFilters(["*.pptx", "*.pptm"])
        self.file_model.setNameFilterDisables(False)
        self.tree_model = SourceTreeModel(self)
        self.tree_model.setSourceModel(self.file_model)
        self.tree = QTreeView()
        self.tree.setModel(self.tree_model)
        self.tree.setHeaderHidden(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setAccessibleName("폴더와 PPT 파일 탐색")
        self.tree.setToolTip("폴더를 눌러 펼치기 · PPT를 눌러 슬라이드 보기")
        for column in range(1, 4):
            self.tree.hideColumn(column)
        self.stack.addWidget(self.tree)
        self.results = QListWidget()
        self.results.setObjectName("fileSearchResults")
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.stack.addWidget(self.results)
        self.search_status = QLabel()
        self.search_status.setObjectName("mutedText")
        self.search_status.setWordWrap(True)
        self.search_status.hide()
        inner.addWidget(self.search_status)
        self.tabs.addTab(explorer, "폴더")
        self.list = QListWidget()
        self.list.setObjectName("sourceList")
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setSpacing(4)
        self.list.setWordWrap(True)
        self.tabs.addTab(self.list, "원본 (0)")
        self.list.setToolTip("읽은 원본 · 파일 끌어 놓기로 추가 · Ctrl·Shift로 여러 파일 선택")
        self.list.currentItemChanged.connect(self._current_changed)
        self.list.itemSelectionChanged.connect(self.selection_changed.emit)
        self.tabs.currentChanged.connect(self._tab_changed)
        self.tree.selectionModel().currentChanged.connect(self._tree_current_changed)
        self.tree.selectionModel().selectionChanged.connect(lambda selected, deselected: self.selection_changed.emit())
        self.tree.clicked.connect(self._tree_clicked)
        self.file_model.directoryLoaded.connect(self._directory_loaded)
        self.results.currentItemChanged.connect(self._result_changed)
        self.results.itemClicked.connect(lambda item: self.file_selected.emit(item.data(Qt.ItemDataRole.UserRole)))
        self.results.itemSelectionChanged.connect(self.selection_changed.emit)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._start_search)
        self.search.textChanged.connect(self._query_changed)
        desktop = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
        self.set_root(Path(desktop) if desktop and Path(desktop).is_dir() else Path.home())

    def set_root(self, path: str | Path) -> bool:
        root = Path(path).resolve()
        if not root.is_dir():
            return False
        self._debounce.stop()
        self._cancel_search()
        self.search.clear()
        self.root_path = root
        self.results.clear()
        self.stack.setCurrentWidget(self.tree)
        self.search_status.hide()
        self.tree.clearSelection()
        self.tree.setCurrentIndex(self.tree_model.index(-1, 0))
        index = self.file_model.setRootPath(str(root))
        self.tree.setRootIndex(self.tree_model.mapFromSource(index))
        self.tabs.setCurrentIndex(0)
        self.root_changed.emit(str(root))
        self.selection_changed.emit()
        return True

    def _path(self, index) -> str:
        return self.file_model.filePath(self.tree_model.mapToSource(index)) if index.isValid() else ""

    def _tree_current_changed(self, current, previous) -> None:
        if self.tabs.currentIndex() == 0 and self.stack.currentWidget() == self.tree:
            self._tree_clicked(current)

    def _tree_clicked(self, index) -> None:
        source = self.tree_model.mapToSource(index)
        if not source.isValid():
            return
        if self.file_model.isDir(source):
            if self.file_model.canFetchMore(source):
                self.file_model.fetchMore(source)
            self.tree.expand(index)
        else:
            self.file_selected.emit(self.file_model.filePath(source))

    def _directory_loaded(self, path: str) -> None:
        index = self.tree.currentIndex()
        if self._path(index) == path:
            self.tree.expand(index)

    def _result_changed(self, current, previous) -> None:
        if current and self.tabs.currentIndex() == 0:
            self.file_selected.emit(current.data(Qt.ItemDataRole.UserRole))

    def _current_changed(self, current, previous) -> None:
        if self.tabs.currentIndex() == 1:
            self.current_source_changed.emit(current.data(Qt.ItemDataRole.UserRole) if current else "")

    def _tab_changed(self, index) -> None:
        self.current_source_changed.emit(self.current_key())
        self.selection_changed.emit()

    def add_source(self, key: str, path: str) -> None:
        item = QListWidgetItem(Path(path).name)
        item.setData(Qt.ItemDataRole.UserRole, key)
        self._items[key] = item
        self.list.addItem(item)
        self.set_state(key, path, "읽기 대기")
        self.tabs.setTabText(1, f"원본 ({len(self._items)})")

    def set_state(self, key: str, path: str, status: str, detail: str = "", *, state: str = "queued") -> None:
        self.tree_model.set_state(path, status, detail, state)
        item = self._items.get(key)
        if item:
            icons = {"ready": QStyle.StandardPixmap.SP_DialogApplyButton,
                "loading": QStyle.StandardPixmap.SP_BrowserReload, "failed": QStyle.StandardPixmap.SP_MessageBoxCritical,
                "cancelled": QStyle.StandardPixmap.SP_DialogCancelButton}
            item.setIcon(self.style().standardIcon(icons.get(state, QStyle.StandardPixmap.SP_FileIcon)))
            item.setText(Path(path).name + (f"\n{status.split(' · ')[0]}" if state == "ready" else ""))
            item.setData(Qt.ItemDataRole.AccessibleTextRole, f"{Path(path).name} · {status}")
            item.setToolTip(f"{path}\n{status}" + (f"\n{detail}" if detail else ""))

    def select_source(self, key: str) -> None:
        if key not in self._items:
            return
        self.list.setCurrentItem(self._items[key])
        current = self.results.currentItem()
        if (self.tabs.currentIndex() == 0 and self.stack.currentWidget() == self.results
                and current and source_key(current.data(Qt.ItemDataRole.UserRole)) == key):
            self.current_source_changed.emit(key)
            return
        if self.stack.currentWidget() == self.results:
            self.search.clear()
        path = Path(key)
        if path.is_relative_to(self.root_path):
            index = self.tree_model.mapFromSource(self.file_model.index(str(path)))
            if index.isValid():
                self.tabs.setCurrentIndex(0)
                self.tree.setCurrentIndex(index)
                self.tree.scrollTo(index)
                self.current_source_changed.emit(key)
                return
        self.tabs.setCurrentIndex(1)
        self.current_source_changed.emit(key)

    def selected_keys(self) -> list[str]:
        if self.tabs.currentIndex() == 1:
            return [item.data(Qt.ItemDataRole.UserRole) for item in self.list.selectedItems()]
        paths = ([item.data(Qt.ItemDataRole.UserRole) for item in self.results.selectedItems()]
            if self.stack.currentWidget() == self.results else
            [self._path(index) for index in self.tree.selectionModel().selectedRows()])
        return [source_key(path) for path in paths if source_key(path) in self._items]

    def current_key(self) -> str:
        if self.tabs.currentIndex() == 1:
            item = self.list.currentItem()
            return item.data(Qt.ItemDataRole.UserRole) if item else ""
        if self.stack.currentWidget() == self.results:
            item = self.results.currentItem()
            path = item.data(Qt.ItemDataRole.UserRole) if item else ""
        else:
            path = self._path(self.tree.currentIndex())
        key = source_key(path) if path else ""
        return key if key in self._items else ""

    def remove_sources(self, keys: list[str]) -> None:
        for key in keys:
            item = self._items.pop(key, None)
            self.tree_model.remove_state(key)
            if item is not None:
                self.list.takeItem(self.list.row(item))
        self.tabs.setTabText(1, f"원본 ({len(self._items)})")

    def clear_sources(self) -> None:
        for key in tuple(self._items):
            self.tree_model.remove_state(key)
        self._items.clear()
        self.list.clear()
        self.tabs.setTabText(1, "원본 (0)")

    def _cancel_search(self) -> None:
        self._search_token += 1
        for thread in self._search_threads:
            thread.requestInterruption()

    def _query_changed(self, text: str) -> None:
        self._debounce.stop()
        self._cancel_search()
        self.results.clear()
        if text.strip() and not self._closing:
            self.stack.setCurrentWidget(self.results)
            self.search_status.setText("검색 중…")
            self.search_status.show()
            self._debounce.start()
        else:
            self.stack.setCurrentWidget(self.tree)
            self.search_status.hide()
        self.selection_changed.emit()

    def _start_search(self) -> None:
        query = self.search.text().strip()
        if not query or self._closing:
            return
        thread = FileSearchThread(self._search_token, self.root_path, query, self)
        self._search_threads.append(thread)
        thread.batch_found.connect(self._search_batch, Qt.ConnectionType.QueuedConnection)
        thread.completed.connect(self._search_completed, Qt.ConnectionType.QueuedConnection)
        thread.finished.connect(self._on_search_thread_finished, Qt.ConnectionType.QueuedConnection)
        thread.start()

    @Slot(int, object)
    def _search_batch(self, token: int, paths) -> None:
        if token != self._search_token or self._closing:
            return
        for path in paths:
            item = QListWidgetItem(str(Path(path).relative_to(self.root_path)))
            item.setData(Qt.ItemDataRole.UserRole, path)
            item.setToolTip(path)
            item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
            self.results.addItem(item)

    @Slot(int, object)
    def _search_completed(self, token: int, summary) -> None:
        if token == self._search_token and not self._closing:
            self.search_status.setText(f"{summary.matches}개" + (" · 최대 2,000개" if summary.limited else "")
                + (f" · 접근 불가 {summary.skipped}개" if summary.skipped else ""))

    @Slot()
    def _on_search_thread_finished(self) -> None:
        self._search_thread_finished(self.sender())

    def _search_thread_finished(self, thread: FileSearchThread) -> None:
        if not thread.wait(0):
            QTimer.singleShot(10, lambda: self._search_thread_finished(thread))
            return
        self._search_threads.remove(thread)
        thread.deleteLater()
        if not self._search_threads:
            self.search_finished.emit()

    @property
    def has_search(self) -> bool:
        return bool(self._search_threads)

    def shutdown_search(self) -> None:
        self._closing = True
        self._debounce.stop()
        self._cancel_search()
