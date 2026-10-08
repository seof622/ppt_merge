"""소스 파일 목록과 상태 표시. COM을 호출하지 않는다."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QFrame, QLabel, QListWidget, QListWidgetItem, QVBoxLayout


class SourcePanel(QFrame):
    current_source_changed = Signal(str)
    selection_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("sourcePanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(12)
        self.heading = QLabel("소스 파일 · 0개")
        self.heading.setObjectName("sectionTitle")
        layout.addWidget(self.heading)
        self.list = QListWidget()
        self.list.setObjectName("sourceList")
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setSpacing(4)
        self.list.setWordWrap(True)
        self.list.currentItemChanged.connect(self._current_changed)
        self.list.itemSelectionChanged.connect(self.selection_changed.emit)
        layout.addWidget(self.list, 1)
        hint = QLabel("PPTX · PPTM\n파일을 이 창에 끌어 놓아 추가할 수 있습니다.")
        hint.setWordWrap(True)
        hint.setObjectName("mutedText")
        layout.addWidget(hint)
        self._items: dict[str, QListWidgetItem] = {}

    def _current_changed(self, current, previous) -> None:
        self.current_source_changed.emit(current.data(Qt.ItemDataRole.UserRole) if current else "")

    def add_source(self, key: str, path: str) -> None:
        item = QListWidgetItem(f"{Path(path).name}\n읽기 대기")
        item.setData(Qt.ItemDataRole.UserRole, key)
        item.setToolTip(path)
        self._items[key] = item
        self.list.addItem(item)
        self.heading.setText(f"소스 파일 · {len(self._items)}개")

    def set_state(self, key: str, path: str, status: str, detail: str = "") -> None:
        item = self._items.get(key)
        if item:
            item.setText(f"{Path(path).name}\n{status}")
            item.setToolTip(path + (f"\n{detail}" if detail else ""))

    def select_source(self, key: str) -> None:
        if key in self._items:
            self.list.setCurrentItem(self._items[key])

    def selected_keys(self) -> list[str]:
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.list.selectedItems()]

    def current_key(self) -> str:
        item = self.list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else ""

    def remove_sources(self, keys: list[str]) -> None:
        for key in keys:
            item = self._items.pop(key, None)
            if item is not None:
                self.list.takeItem(self.list.row(item))
        self.heading.setText(f"소스 파일 · {len(self._items)}개")

    def clear_sources(self) -> None:
        self._items.clear()
        self.list.clear()
        self.heading.setText("소스 파일 · 0개")
