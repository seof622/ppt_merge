"""메인 사이드바의 파일 모델과 취소 가능한 PPT 검색."""

import os
from pathlib import Path

from PySide6.QtCore import QSortFilterProxyModel, QThread, Qt, Signal
from PySide6.QtWidgets import QApplication, QStyle

from src.utils.file_search import is_presentation, search_presentations


def source_key(path: str | Path) -> str:
    return os.path.normcase(str(Path(path)))


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


class SourceTreeModel(QSortFilterProxyModel):
    """폴더와 PPT를 함께 보여 주고 이미 읽은 PPT에는 상태를 표시한다."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.states: dict[str, tuple[str, str, str]] = {}

    def filterAcceptsRow(self, row, parent) -> bool:
        index = self.sourceModel().index(row, 0, parent)
        return self.sourceModel().isDir(index) or is_presentation(self.sourceModel().filePath(index))

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        source = self.mapToSource(index)
        path = self.sourceModel().filePath(source)
        status = self.states.get(source_key(path))
        if status and index.column() == 0:
            text, detail, state = status
            if role == Qt.ItemDataRole.ToolTipRole:
                return f"{path}\n{text}" + (f"\n{detail}" if detail else "")
            if role == Qt.ItemDataRole.AccessibleTextRole:
                return f"{Path(path).name} · {text}"
            if role == Qt.ItemDataRole.DisplayRole and state == "ready":
                return f"{Path(path).name} · {text.split(' · ')[0]}"
            if role == Qt.ItemDataRole.DecorationRole:
                icons = {"ready": QStyle.StandardPixmap.SP_DialogApplyButton,
                         "loading": QStyle.StandardPixmap.SP_BrowserReload,
                         "failed": QStyle.StandardPixmap.SP_MessageBoxCritical,
                         "cancelled": QStyle.StandardPixmap.SP_DialogCancelButton}
                return QApplication.style().standardIcon(icons.get(state, QStyle.StandardPixmap.SP_FileIcon))
        if role == Qt.ItemDataRole.ToolTipRole:
            return path
        return super().data(index, role)

    def set_state(self, path: str, status: str, detail: str, state: str) -> None:
        self.states[source_key(path)] = (status, detail, state)
        self.refresh_path(path)

    def remove_state(self, path: str) -> None:
        self.states.pop(source_key(path), None)
        self.refresh_path(path)

    def refresh_path(self, path: str) -> None:
        index = self.mapFromSource(self.sourceModel().index(path))
        if index.isValid():
            self.dataChanged.emit(index, index)
