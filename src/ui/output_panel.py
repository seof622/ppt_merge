"""출력 순서 편집 모델과 가로 썸네일 목록. COM 작업은 하지 않는다."""

from collections.abc import Callable, Iterable
from uuid import uuid4

from PySide6.QtCore import QModelIndex, QSize, Qt, Signal, QItemSelectionModel
from PySide6.QtGui import QAction, QColor, QDrag, QKeySequence, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QListView, QMenu,
                               QVBoxLayout, QWidget)

from src.models.project_model import OutputSequence
from src.models.slide_model import SlideItem
from src.ui.slide_grid import SlideListModel
from src.ui.slide_mime import make_slide_mime, read_slide_mime
from src.ui.icons import icon, icon_button


class OutputListModel(SlideListModel):
    edited = Signal(object)
    feedback = Signal(str)

    def __init__(self, parent=None, drag_token: str = "") -> None:
        super().__init__(parent, drag_token)
        self.sequence = OutputSequence()
        self.origin = uuid4().hex
        self.revision = 0

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and 0 <= index.row() < self.rowCount():
            slide = self.slides[index.row()]
            if role == Qt.ItemDataRole.DisplayRole:
                return f"{index.row() + 1} · {slide.source_file_name}\n#{slide.slide_index}"
            if role == Qt.ItemDataRole.ToolTipRole:
                return f"출력 {index.row() + 1}번\n{slide.source_file}\n원본 슬라이드 {slide.slide_index}\n{slide.title or ''}"
            if role == Qt.ItemDataRole.SizeHintRole:
                return QSize(196, 156)
        return super().data(index, role)

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.ItemIsDropEnabled
        return super().flags(index)

    def supportedDragActions(self):
        return Qt.DropAction.MoveAction

    def supportedDropActions(self):
        return Qt.DropAction.CopyAction | Qt.DropAction.MoveAction

    def mimeData(self, indexes):
        rows = tuple(sorted({index.row() for index in indexes if index.isValid()}))
        return make_slide_mime(self.drag_token, tuple(self.slides[row] for row in rows),
                               origin=self.origin, revision=self.revision, rows=rows)

    def canDropMimeData(self, data, action, row, column, parent):
        payload = read_slide_mime(data, self.drag_token)
        if payload is None or column > 0 or not -1 <= row <= self.rowCount():
            return False
        if payload["origin"] == "source":
            return action == Qt.DropAction.CopyAction
        rows = payload["rows"]
        return (action == Qt.DropAction.MoveAction and payload["origin"] == self.origin
                and payload["revision"] == self.revision and bool(rows)
                and rows == sorted(set(rows)) and len(rows) == len(payload["slides"])
                and all(position < self.rowCount() for position in rows)
                and tuple(self.slides[position] for position in rows) == payload["slides"])

    def dropMimeData(self, data, action, row, column, parent):
        if action == Qt.DropAction.IgnoreAction:
            return True
        if not self.canDropMimeData(data, action, row, column, parent):
            return False
        payload = read_slide_mime(data, self.drag_token)
        target = row if row >= 0 else self.rowCount()
        if payload["origin"] == self.origin:
            self.edit(lambda: self.sequence.move(payload["rows"], target), f"{len(payload['rows'])}장 순서 변경")
        else:
            self.add_slides(payload["slides"], target)
        return True

    def edit(self, operation: Callable[[], list[int]], message: str = "") -> None:
        self.beginResetModel()
        rows = operation()
        self.slides = tuple(self.sequence.slides)
        self._icons.clear()
        self.revision += 1
        self.endResetModel()
        self.edited.emit(rows)
        if message:
            self.feedback.emit(f"{message} · 총 {self.rowCount()}장")

    def add_slides(self, slides: Iterable[SlideItem], target: int | None = None) -> None:
        additions = tuple(slides)
        if additions:
            self.edit(lambda: self.sequence.insert(additions, target), f"{len(additions)}장 담음")

    def clear(self) -> None:
        self.edit(lambda: self.sequence.remove(range(self.rowCount())), "출력 목록 비움")


class OutputListView(QListView):
    """모델에서 이동을 완료하므로 Qt의 기본 원본 행 삭제를 실행하지 않는다."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._insert_row: int | None = None
        self.setObjectName("outputView")
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(False)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setIconSize(QSize(160, 90))
        self.setSpacing(8)
        self.setWordWrap(False)
        self.setUniformItemSizes(True)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumHeight(182)

    def startDrag(self, supported_actions) -> None:
        indexes = self.selectionModel().selectedIndexes()
        if not indexes:
            return
        drag = QDrag(self)
        drag.setMimeData(self.model().mimeData(indexes))
        pixmap = self.model().data(indexes[0], Qt.ItemDataRole.DecorationRole).pixmap(160, 90)
        drag.setPixmap(pixmap)
        try:
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            drag.deleteLater()

    def insertion_row(self, point) -> int:
        for row in range(self.model().rowCount()):
            if point.x() < self.visualRect(self.model().index(row, 0)).center().x():
                return row
        return self.model().rowCount()

    def _accept_drag(self, event) -> None:
        model = self.model()
        payload = read_slide_mime(event.mimeData(), model.drag_token)
        action = (Qt.DropAction.MoveAction if payload and payload["origin"] == model.origin
                  else Qt.DropAction.CopyAction)
        row = self.insertion_row(event.position().toPoint())
        if model.canDropMimeData(event.mimeData(), action, row, 0, QModelIndex()):
            self._insert_row = row
            event.setDropAction(action)
            event.accept()
        else:
            self._insert_row = None
            event.ignore()
        self.viewport().update()

    def dragEnterEvent(self, event) -> None:
        super().dragEnterEvent(event)
        self._accept_drag(event)

    def dragMoveEvent(self, event) -> None:
        # 기본 처리는 가장자리의 자동 스크롤을 유지한다.
        super().dragMoveEvent(event)
        self._accept_drag(event)

    def dragLeaveEvent(self, event) -> None:
        self._insert_row = None
        self.viewport().update()
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        self._accept_drag(event)
        if event.isAccepted():
            if not self.model().dropMimeData(event.mimeData(), event.dropAction(),
                                             self._insert_row, 0, QModelIndex()):
                event.ignore()
        self._insert_row = None
        self.viewport().update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        if self.model().rowCount() == 0:
            painter.setPen(QColor("#64748b"))
            painter.drawText(self.viewport().rect(), Qt.AlignmentFlag.AlignCenter,
                             "슬라이드를 끌어 놓으세요")
        if self._insert_row is not None:
            row = self._insert_row
            if self.model().rowCount() == 0:
                x = 8
            elif row == self.model().rowCount():
                x = self.visualRect(self.model().index(row - 1, 0)).right() + 4
            else:
                x = self.visualRect(self.model().index(row, 0)).left() - 4
            painter.setPen(QPen(QColor("#2563eb"), 3))
            painter.drawLine(max(2, x), 8, max(2, x), min(165, self.viewport().height() - 8))
        painter.end()


class OutputPanel(QWidget):
    def __init__(self, parent=None, drag_token: str = "") -> None:
        super().__init__(parent)
        self.setObjectName("outputPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        header = QHBoxLayout()
        header.setSpacing(8)
        heading = QLabel("결과물 미리보기")
        heading.setObjectName("sectionTitle")
        self.count = QLabel("0장 · 0장 선택")
        self.count.setObjectName("mutedText")
        header.addWidget(heading)
        header.addWidget(self.count, 1)
        self.clear_button = icon_button("clear", "출력 비우기", self)
        self.clear_button.clicked.connect(lambda: self.model.clear())
        tools = QHBoxLayout()
        tools.setSpacing(4)
        self.actions: dict[str, QAction] = {}
        commands = (("remove", "선택 삭제", "Delete", self.remove_selected),
                    ("duplicate", "복제", "Ctrl+D", self.duplicate_selected),
                    ("up", "앞으로", "Alt+Up", lambda: self.step_selected(-1)),
                    ("down", "뒤로", "Alt+Down", lambda: self.step_selected(1)),
                    ("first", "맨 앞으로", "Alt+Home", lambda: self.move_selected(0)),
                    ("last", "맨 뒤로", "Alt+End", lambda: self.move_selected(self.model.rowCount())))
        for key, text, shortcut, callback in commands:
            action = QAction(text, self)
            action.setShortcut(QKeySequence(shortcut))
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            action.triggered.connect(callback)
            self.addAction(action)
            icon_name = {"remove": "remove", "duplicate": "duplicate", "up": "previous",
                         "down": "next", "first": "first", "last": "last"}[key]
            action.setIcon(icon(icon_name))
            button = icon_button(icon_name, text, self)
            description = "선택한 슬라이드를 한 번 더 담기" if key == "duplicate" else text
            action.setToolTip(f"{description} ({shortcut})")
            button.setToolTip(action.toolTip())
            button.clicked.connect(action.trigger)
            action.changed.connect(lambda a=action, b=button: b.setEnabled(a.isEnabled()))
            self.actions[key] = action
            tools.addWidget(button)
        header.addLayout(tools)
        header.addWidget(self.clear_button)
        layout.addLayout(header)
        self.view = OutputListView(self)
        self.model = OutputListModel(self.view, drag_token)
        self.view.setModel(self.model)
        # 스크롤 영역의 실제 드롭 대상은 내부 viewport이다.
        self.view.viewport().setAcceptDrops(True)
        self.model.edited.connect(self.select_rows)
        self.view.selectionModel().selectionChanged.connect(self._update_actions)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._context_menu)
        layout.addWidget(self.view, 1)
        self.view.setAccessibleName("출력 슬라이드 순서")
        self.view.setToolTip("왼쪽부터 최종 순서 · Ctrl·Shift 선택 · 드래그로 순서 변경\n"
                             "Delete 삭제 · Ctrl+D 복제 · 목록은 앱 종료 시 초기화됩니다.")
        self.footer = QHBoxLayout()
        self.footer.setSpacing(8)
        self.footer.addStretch(1)
        layout.addLayout(self.footer)
        self._update_actions()

    @property
    def output_slides(self) -> list[SlideItem]:
        return list(self.model.slides)

    def selected_rows(self) -> list[int]:
        return sorted(index.row() for index in self.view.selectionModel().selectedIndexes())

    def select_rows(self, rows: list[int]) -> None:
        selection = self.view.selectionModel()
        selection.clearSelection()
        for row in rows:
            selection.select(self.model.index(row, 0), QItemSelectionModel.SelectionFlag.Select)
        if rows:
            index = self.model.index(rows[0], 0)
            selection.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
            self.view.scrollTo(index)
            self.view.setFocus(Qt.FocusReason.OtherFocusReason)
        self._update_actions()

    def add_slides(self, slides: Iterable[SlideItem]) -> None:
        self.model.add_slides(slides)

    def remove_selected(self) -> None:
        rows = self.selected_rows()
        if rows:
            self.model.edit(lambda: self.model.sequence.remove(rows), f"{len(rows)}장 삭제")

    def duplicate_selected(self) -> None:
        rows = self.selected_rows()
        if rows:
            self.model.edit(lambda: self.model.sequence.duplicate(rows), f"{len(rows)}장 복제 — 같은 슬라이드를 한 번 더 담음")

    def step_selected(self, direction: int) -> None:
        rows = self.selected_rows()
        if rows:
            self.model.edit(lambda: self.model.sequence.step(rows, direction), f"{len(rows)}장 순서 변경")

    def move_selected(self, target: int) -> None:
        rows = self.selected_rows()
        if rows:
            self.model.edit(lambda: self.model.sequence.move(rows, target), f"{len(rows)}장 순서 변경")

    def _update_actions(self, *args) -> None:
        rows = self.selected_rows()
        count = self.model.rowCount()
        self.count.setText(f"{count}장 · {len(rows)}장 선택")
        self.actions["remove"].setEnabled(bool(rows))
        self.actions["duplicate"].setEnabled(bool(rows))
        for key in ("up", "first"):
            self.actions[key].setEnabled(bool(rows) and rows != list(range(len(rows))))
        for key in ("down", "last"):
            self.actions[key].setEnabled(bool(rows) and rows != list(range(count - len(rows), count)))
        self.clear_button.setEnabled(count > 0)

    def _context_menu(self, position) -> None:
        index = self.view.indexAt(position)
        if not index.isValid():
            return
        if not self.view.selectionModel().isSelected(index):
            self.view.setCurrentIndex(index)
        menu = QMenu(self)
        for action in self.actions.values():
            menu.addAction(action)
        menu.exec(self.view.viewport().mapToGlobal(position))
