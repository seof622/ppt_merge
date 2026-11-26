"""출력 순서 편집 모델과 가로 썸네일 목록. COM 작업은 하지 않는다."""

from collections.abc import Callable, Iterable
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QEasingCurve, QModelIndex, QPoint, QRect, QRectF, QSize, Qt, Signal, QItemSelectionModel, QVariantAnimation
from PySide6.QtGui import QAction, QColor, QDrag, QFont, QKeySequence, QPainter, QPalette, QPen, QShortcut, QUndoCommand, QUndoStack
from PySide6.QtWidgets import (QAbstractItemView, QColorDialog, QFileDialog, QHBoxLayout, QLabel, QLayout, QListView, QMenu,
                               QComboBox, QMessageBox, QPushButton, QSlider, QSizePolicy, QStyle, QStyleOptionComboBox, QStyleOptionViewItem,
                               QToolButton, QVBoxLayout, QWidget)

from src.models.project_model import OutputSequence
from src.models.slide_model import SlideBackground, SlideItem
from src.ppt.errors import PowerPointError
from src.ppt.slide_background import import_background_image
from src.ui.slide_grid import SlideListModel
from src.ui.slide_mime import make_slide_mime, read_slide_mime
from src.ui.icons import icon, icon_button
from src.ui.theme import (ACCENT, MUTED, BADGE_TEXT, OUTPUT_SURFACE,
                          DROP_SURFACE, DROP_BORDER, SURFACE, CARD_TITLE_SIZE, CARD_LABEL_SIZE,
                          TEXT_WEIGHT, EMPHASIS_WEIGHT)
from src.ui.slide_delegate import SlideCardDelegate, drag_image, slide_card_size
from src.ui.slide_preview import open_preview


class SequenceEdit(QUndoCommand):
    def __init__(self, model, before, after, before_rows, after_rows, message):
        super().__init__(message)
        self.model, self.before, self.after = model, before, after
        self.before_rows, self.after_rows = before_rows, after_rows

    def undo(self):
        self.model.restore(self.before, self.before_rows)
        self.model.feedback.emit(f'실행 취소 · {self.text()}')

    def redo(self):
        self.model.restore(self.after, self.after_rows)
        self.model.feedback.emit(f'{self.text()} · 총 {self.model.rowCount()}장')


class OutputListModel(SlideListModel):
    edited = Signal(object)
    feedback = Signal(str)
    background_preview_requested = Signal(object)

    def __init__(self, parent=None, drag_token: str = "") -> None:
        super().__init__(parent, drag_token)
        self.card_size = slide_card_size(224, output=True)
        self.sequence = OutputSequence()
        self.origin = uuid4().hex
        self.revision = 0
        self.undo_stack = QUndoStack(self)
        self.undo_stack.setUndoLimit(100)
        self.selection_rows = lambda: []
        self._background_images: dict[SlideItem, str] = {}
        self._background_errors: dict[SlideItem, str] = {}

    def background_thumbnail(self, slide: SlideItem) -> str | None:
        return self._background_images.get(slide)

    def needs_background_thumbnail(self, slide: SlideItem) -> bool:
        return slide.background is not None and slide not in self._background_images and slide not in self._background_errors

    def background_preview_text(self, slide: SlideItem) -> str:
        if slide in self._background_images:
            return "배경 변경"
        if slide in self._background_errors:
            return "배경 미리보기 실패"
        return "배경 미리보기 준비 중"

    def set_background_thumbnail(self, slide: SlideItem, path: str) -> None:
        if slide.background is not None:
            self._background_images[slide] = path
            self._background_errors.pop(slide, None)
            self._refresh_background_thumbnail(slide)

    def fail_background_thumbnail(self, slide: SlideItem, message: str) -> None:
        if slide not in self._background_images:
            self._background_errors[slide] = message
            self._refresh_background_thumbnail(slide)

    def _refresh_background_thumbnail(self, slide: SlideItem) -> None:
        for row, current in enumerate(self.slides):
            if current == slide:
                self._icons.pop(row, None)
                index = self.index(row, 0)
                self.dataChanged.emit(index, index, [Qt.ItemDataRole.DecorationRole, Qt.ItemDataRole.ToolTipRole])

    def _thumbnail_path(self, slide: SlideItem) -> str | None:
        return self.background_thumbnail(slide) or super()._thumbnail_path(slide)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if index.isValid() and 0 <= index.row() < self.rowCount():
            slide = self.slides[index.row()]
            if role == Qt.ItemDataRole.DecorationRole and self.needs_background_thumbnail(slide):
                self.background_preview_requested.emit(slide)
            if role == Qt.ItemDataRole.DisplayRole:
                if self.card_size.height() < 156:
                    return f"{index.row() + 1} · #{slide.slide_index} · {slide.source_file_name}"
                return f"{index.row() + 1} · {slide.title or '슬라이드'}\n{slide.source_file_name} · 원본 {slide.slide_index}번"
            if role == Qt.ItemDataRole.ToolTipRole:
                text = f"출력 {index.row() + 1}번\n{slide.source_file}\n원본 슬라이드 {slide.slide_index}\n{slide.title or ''}"
                if slide.background is not None:
                    text += f"\n배경색 {slide.background.color}" if slide.background.color else "\n이미지 배경"
                    text += f"\n{self._background_errors.get(slide, self.background_preview_text(slide))}"
                return text
            if role == Qt.ItemDataRole.SizeHintRole:
                return self.card_size
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
        before = tuple(self.sequence.slides)
        before_rows = self.selection_rows()
        rows = operation()
        after = tuple(self.sequence.slides)
        self.sequence.slides[:] = before
        if before != after:
            self.undo_stack.push(SequenceEdit(self, before, after, before_rows, rows, message))

    def restore(self, slides, rows=()):
        self.beginResetModel()
        self.sequence.slides[:] = slides
        self.slides = tuple(self.sequence.slides)
        self._icons.clear()
        self.revision += 1
        self.endResetModel()
        self.edited.emit(list(rows))

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
        self._preview_order: list[int | None] | None = None
        self._preview_count = 0
        self._preview_moving = False
        self._preview_starts: dict[int, QRectF] = {}
        self._preview_targets: dict[int, QRectF] = {}
        self._preview_animation = QVariantAnimation(self)
        self._preview_animation.setDuration(150)
        self._preview_animation.setStartValue(0.0)
        self._preview_animation.setEndValue(1.0)
        self._preview_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._preview_animation.valueChanged.connect(lambda value: self.viewport().update())
        self.setObjectName("outputView")
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
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
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.thumbnail_width = 224

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._resize_cards()

    def _resize_cards(self):
        model = self.model()
        if model is None:
            return
        width = min(self.thumbnail_width, max(100, self.viewport().width() - 2 * self.spacing() - 16))
        if not self.isWrapping():
            available = self.viewport().height() - 2 * self.spacing() - 4
            width = min(width, max(100, int((available - 62) * 16 / 9)))
        size = slide_card_size(width, output=True)
        if model.card_size != size:
            model.card_size = size
            self.setIconSize(QSize(width, round(width * 9 / 16)))
            self.doItemsLayout()

    def set_thumbnail_width(self, width):
        self.thumbnail_width = width
        self._resize_cards()
        self.viewport().update()

    def startDrag(self, supported_actions) -> None:
        indexes = self.selectionModel().selectedIndexes()
        if not indexes:
            return
        drag = QDrag(self)
        drag.setMimeData(self.model().mimeData(indexes))
        drag.setPixmap(drag_image(self.model(), indexes[0], len(indexes)))
        try:
            drag.exec(Qt.DropAction.MoveAction)
        finally:
            self.clear_drop_preview()
            drag.deleteLater()

    def _columns(self) -> int:
        if not self.isWrapping():
            return max(1, self.model().rowCount() + 1)
        return max(1, self.viewport().width() // (self.model().card_size.width() + self.spacing()))

    def _slot_rect(self, slot: int) -> QRect:
        """모델을 바꾸지 않고 슬롯의 콘텐츠 좌표를 구한다."""
        size, spacing = self.model().card_size, self.spacing()
        columns = self._columns()
        return QRect(spacing + (slot % columns) * (size.width() + spacing),
                     spacing + (slot // columns) * (size.height() + spacing),
                     size.width(), size.height())

    def _viewport_rect(self, rect: QRectF) -> QRectF:
        return rect.translated(-self.horizontalScrollBar().value(), -self.verticalScrollBar().value())

    def insertion_row(self, point) -> int:
        point = point + QPoint(self.horizontalScrollBar().value(), self.verticalScrollBar().value())
        size, spacing = self.model().card_size, self.spacing()
        columns = self._columns()
        line = max(0, point.y() // (size.height() + spacing))
        column = min(columns - 1, max(0, point.x() // (size.width() + spacing)))
        slot = line * columns + column
        if point.x() > self._slot_rect(slot).center().x():
            slot += 1
        return min(slot, self.model().rowCount())

    def _animated_rect(self, row: int) -> QRectF:
        target = self._preview_targets[row]
        start = self._preview_starts.get(row, target)
        progress = float(self._preview_animation.currentValue() or 0.0)
        return QRectF(start.x() + (target.x() - start.x()) * progress,
                      start.y() + (target.y() - start.y()) * progress,
                      target.width(), target.height())

    def _show_drop_preview(self, order, count, moving):
        if order == self._preview_order:
            return
        starts = {row: (self._animated_rect(row) if row in self._preview_targets
                        else QRectF(self._slot_rect(row))) for row in order if row is not None}
        self._preview_animation.stop()
        self._preview_order = order
        self._preview_count, self._preview_moving = count, moving
        self._preview_starts = starts
        self._preview_targets = {row: QRectF(self._slot_rect(slot))
                                 for slot, row in enumerate(order) if row is not None}
        self.updateGeometries()
        # 스크롤바가 나타나 열 수가 바뀐 경우에도 최종 슬롯 위치를 맞춘다.
        self._preview_targets = {row: QRectF(self._slot_rect(slot))
                                 for slot, row in enumerate(order) if row is not None}
        self._preview_animation.start()

    def clear_drop_preview(self):
        self._preview_animation.stop()
        self._insert_row = None
        self._preview_order = None
        self._preview_starts.clear()
        self._preview_targets.clear()
        self.updateGeometries()
        self.viewport().update()

    def updateGeometries(self):
        super().updateGeometries()
        if self._preview_order is None or self.model() is None:
            return
        size, spacing = self.model().card_size, self.spacing()
        if self.isWrapping():
            lines = (len(self._preview_order) + self._columns() - 1) // self._columns()
            self.verticalScrollBar().setRange(0, max(0, lines * (size.height() + spacing) - self.viewport().height()))
        else:
            self.horizontalScrollBar().setRange(0, max(0, len(self._preview_order) * (size.width() + spacing) - self.viewport().width()))

    def _accept_drag(self, event) -> None:
        model = self.model()
        payload = read_slide_mime(event.mimeData(), model.drag_token)
        action = (Qt.DropAction.MoveAction if payload and payload["origin"] == model.origin
                  else Qt.DropAction.CopyAction)
        moving = bool(payload and payload["origin"] == model.origin)
        removed = set(payload["rows"]) if moving else set()
        remaining = [row for row in range(model.rowCount()) if row not in removed]
        slot = min(self.insertion_row(event.position().toPoint()), len(remaining))
        row = remaining[slot] if slot < len(remaining) else model.rowCount()
        if model.canDropMimeData(event.mimeData(), action, row, 0, QModelIndex()):
            self._insert_row = row
            order = remaining[:slot] + [None] + remaining[slot:]
            self._show_drop_preview(order, len(payload["slides"]), moving)
            event.setDropAction(action)
            event.accept()
        else:
            self.clear_drop_preview()
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
        self.clear_drop_preview()
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        self._accept_drag(event)
        if event.isAccepted():
            target = self._insert_row
            self.clear_drop_preview()
            if not self.model().dropMimeData(event.mimeData(), event.dropAction(),
                                             target, 0, QModelIndex()):
                event.ignore()
        self.clear_drop_preview()

    def paintEvent(self, event) -> None:
        if self._preview_order is not None:
            self._paint_drop_preview()
            return
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        if self.model().rowCount() == 0:
            painter.setPen(self.palette().color(QPalette.ColorRole.PlaceholderText))
            painter.drawText(self.viewport().rect(), Qt.AlignmentFlag.AlignCenter,
                             "만들 PPT가 비어 있습니다\n원본에서 슬라이드를 선택해 담거나 여기로 끌어 놓으세요")
        painter.end()

    def _paint_drop_preview(self):
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.viewport().rect(), QColor(OUTPUT_SURFACE))
        for slot, row in enumerate(self._preview_order):
            if row is None:
                continue
            rect = self._viewport_rect(self._animated_rect(row)).toRect()
            if not rect.intersects(self.viewport().rect()):
                continue
            option = QStyleOptionViewItem()
            self.initViewItemOption(option)
            option.rect = rect
            option.state = QStyle.StateFlag.State_Enabled
            if self.selectionModel().isSelected(self.model().index(row, 0)):
                option.state |= QStyle.StateFlag.State_Selected
            self.itemDelegate().paint(painter, option, self.model().index(row, 0))
        slot = self._preview_order.index(None)
        rect = self._viewport_rect(QRectF(self._slot_rect(slot))).toRect().adjusted(4, 4, -4, -4)
        painter.setBrush(QColor(DROP_SURFACE))
        painter.setPen(QPen(QColor(DROP_BORDER), 1.5))
        painter.drawRoundedRect(rect, 9, 9)
        center = rect.center()
        circle = QRect(center.x() - 15, center.y() - 43, 30, 30)
        painter.setBrush(QColor(SURFACE))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(circle)
        painter.setPen(QPen(QColor(ACCENT), 1.8))
        painter.drawLine(circle.center() + QPoint(-6, 0), circle.center() + QPoint(6, 0))
        painter.drawLine(circle.center() + QPoint(0, -6), circle.center() + QPoint(0, 6))
        font = QFont(self.font())
        font.setPixelSize(CARD_TITLE_SIZE)
        font.setWeight(QFont.Weight(EMPHASIS_WEIGHT))
        painter.setFont(font)
        painter.setPen(QColor(BADGE_TEXT))
        painter.drawText(QRect(rect.left() + 4, center.y() - 4, rect.width() - 8, 24),
                         Qt.AlignmentFlag.AlignCenter, '여기에 놓기')
        font.setPixelSize(CARD_LABEL_SIZE)
        font.setWeight(QFont.Weight(TEXT_WEIGHT))
        painter.setFont(font)
        painter.setPen(QColor(MUTED))
        label = f'{slot + 1}번째 · {self._preview_count}장 {"이동" if self._preview_moving else "추가"}'
        painter.drawText(QRect(rect.left() + 4, center.y() + 22, rect.width() - 8, 22),
                         Qt.AlignmentFlag.AlignCenter, label)
        painter.end()


class ViewModeComboBox(QComboBox):
    """표시 방식 컨트롤에도 공통 선 아이콘을 사용한다."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._chevron = icon('chevron-down')

    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        arrow = self.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, option,
                                            QStyle.SubControl.SC_ComboBoxArrow, self)
        painter = QPainter(self)
        target = arrow.adjusted(4, 0, -4, 0)
        target.setHeight(16)
        target.moveCenter(arrow.center())
        self._chevron.paint(painter, target)
        painter.end()


class OutputPanel(QWidget):
    def __init__(self, parent=None, drag_token: str = "", *, background_directory: Path) -> None:
        super().__init__(parent)
        self._background_directory = background_directory
        self.setObjectName("outputPanel")
        self._compact_controls = False
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        layout = QVBoxLayout(self)
        # 헤더·버튼의 크기 힌트가 splitter의 최소 높이로 전파되지 않게 한다.
        layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)
        self.header = QHBoxLayout()
        self.header.setSpacing(8)
        heading = QLabel("만들 PPT")
        heading.setObjectName("sectionTitle")
        self.count = QLabel("0장 · 0장 선택")
        self.count.setObjectName("mutedText")
        self.header.addWidget(heading)
        self.header.addStretch(1)
        count_row = self.count_row = QHBoxLayout()
        count_row.addWidget(self.count)
        count_row.addStretch()
        self.clear_button = icon_button("clear", "출력 비우기", self)
        self.clear_button.clicked.connect(lambda: self.model.clear())
        tools = QHBoxLayout()
        tools.setSpacing(4)
        self.actions: dict[str, QAction] = {}
        self.tool_buttons: dict[str, QToolButton] = {}
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
            if key in ('remove', 'duplicate'):
                button.setText('삭제' if key == 'remove' else '복제')
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                button.setFixedWidth(72)
            description = "선택한 슬라이드를 한 번 더 담기" if key == "duplicate" else text
            action.setToolTip(f"{description} ({shortcut})")
            button.setToolTip(action.toolTip())
            button.clicked.connect(action.trigger)
            action.changed.connect(lambda a=action, b=button: b.setEnabled(a.isEnabled()))
            self.actions[key] = action
            self.tool_buttons[key] = button
            tools.addWidget(button)
        self.more_button = icon_button("more", "순서 이동 메뉴", self)
        self.more_button.setObjectName("outputMore")
        move_menu = QMenu(self.more_button)
        for key in ("up", "down", "first", "last"):
            move_menu.addAction(self.actions[key])
        self.more_button.setMenu(move_menu)
        self.more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_button.hide()
        tools.addWidget(self.more_button)
        layout.addLayout(self.header)
        layout.addLayout(count_row)
        self.selection_toolbar = QWidget()
        selection_layout = QHBoxLayout(self.selection_toolbar)
        selection_layout.setContentsMargins(0, 0, 0, 0)
        selection_layout.addLayout(tools)
        selection_layout.addStretch()
        self.background_button = QPushButton("배경", self)
        self.background_button.setObjectName("resultAction")
        self.background_button.setToolTip("선택한 슬라이드 또는 전체 슬라이드의 배경 변경")
        self.background_menu = QMenu("배경", self.background_button)
        self._selected_background = self.background_menu.addMenu("선택한 슬라이드")
        self._all_background = self.background_menu.addMenu("전체 슬라이드")
        self._reset_background_actions = {}
        for all_slides, menu in ((False, self._selected_background), (True, self._all_background)):
            menu.addAction("단색…", lambda checked=False, scope=all_slides: self._choose_background_color(scope))
            menu.addAction("이미지…", lambda checked=False, scope=all_slides: self._choose_background_image(scope))
            menu.addSeparator()
            self._reset_background_actions[all_slides] = menu.addAction(
                "원래 배경", lambda checked=False, scope=all_slides: self._change_background(None, scope))
        self.background_button.setMenu(self.background_menu)
        selection_layout.addWidget(self.background_button)
        selection_layout.addWidget(self.clear_button)
        layout.addWidget(self.selection_toolbar)
        self.view = OutputListView(self)
        self.model = OutputListModel(self.view, drag_token)
        self.view.setModel(self.model)
        self.model.modelReset.connect(self.view.clear_drop_preview)
        self.view.setItemDelegate(SlideCardDelegate(self.view, output=True))
        self.model.selection_rows = self.selected_rows
        # 스크롤 영역의 실제 드롭 대상은 내부 viewport이다.
        self.view.viewport().setAcceptDrops(True)
        self.model.edited.connect(self.select_rows)
        self.view.selectionModel().selectionChanged.connect(self._update_actions)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._context_menu)
        self.view.doubleClicked.connect(lambda index: open_preview(self.view))
        layout.addWidget(self.view, 1)
        self.view.setAccessibleName("출력 슬라이드 순서")
        self.view.setToolTip("왼쪽부터 최종 순서 · Ctrl·Shift 선택 · 드래그로 순서 변경\n"
                             "Delete 삭제 · Ctrl+D 복제 · Space 확대 · Ctrl+Z 실행 취소")
        self.options_widget = QWidget()
        options = QHBoxLayout(self.options_widget)
        options.setContentsMargins(0, 0, 0, 0)
        self.preview_button = QPushButton('확대 보기')
        self.preview_button.setObjectName('quietButton')
        self.preview_button.clicked.connect(lambda: open_preview(self.view))
        options.addWidget(self.preview_button)
        self.view_mode = ViewModeComboBox()
        self.view_mode.setObjectName('viewModeCombo')
        self.view_mode.addItems(['격자 보기', '가로 목록'])
        self.view_mode.setAccessibleName('결과 슬라이드 표시 방식')
        self.view_mode.currentIndexChanged.connect(self._view_mode_changed)
        options.addWidget(self.view_mode)
        options.addStretch()
        zoom_label = QLabel('크기')
        zoom_label.setObjectName('mutedText')
        options.addWidget(zoom_label)
        self.zoom = QSlider(Qt.Orientation.Horizontal)
        self.zoom.setRange(150, 280)
        self.zoom.setValue(224)
        self.zoom.setMaximumWidth(100)
        self.zoom.setAccessibleName('결과 썸네일 크기')
        self.zoom.valueChanged.connect(self.view.set_thumbnail_width)
        options.addWidget(self.zoom)
        layout.addWidget(self.options_widget)
        shortcut = QShortcut(QKeySequence('Space'), self.view)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(lambda: open_preview(self.view))
        # 버튼 줄은 접히는 미리보기와 분리해 MainWindow가 하단에 배치한다.
        self.footer_widget = QWidget(self)
        self.footer_widget.setObjectName("outputFooter")
        self.footer_widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.footer = QHBoxLayout(self.footer_widget)
        self.footer.setContentsMargins(16, 8, 16, 12)
        self.footer.setSpacing(8)
        self.footer.addStretch(1)
        self._update_actions()

    def set_compact(self, compact):
        if self._compact_controls == compact:
            return
        self._compact_controls = compact
        self.layout().setContentsMargins(20, 12 if compact else 20, 20, 12 if compact else 16)
        self.layout().setSpacing(8 if compact else 12)
        if compact:
            self.count_row.removeWidget(self.count)
            self.header.insertWidget(1, self.count)
        else:
            self.header.removeWidget(self.count)
            self.count_row.insertWidget(0, self.count)
        self.view._resize_cards()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not hasattr(self, "more_button"):
            return
        compact = self.width() < 680
        for key in ("up", "down", "first", "last"):
            self.tool_buttons[key].setVisible(not compact)
        self.more_button.setVisible(compact)

    def _view_mode_changed(self, mode):
        self.view.setWrapping(mode == 0)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded if mode == 0
                                             else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.set_thumbnail_width(self.zoom.value())
        self.view.doItemsLayout()

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

    def _background_rows(self, all_slides: bool) -> list[int]:
        return list(range(self.model.rowCount())) if all_slides else self.selected_rows()

    def _choose_background_color(self, all_slides: bool) -> None:
        rows = self._background_rows(all_slides)
        if not rows:
            return
        background = self.model.slides[rows[0]].background
        initial = QColor(background.color if background and background.color else "#FFFFFF")
        color = QColorDialog.getColor(initial, self, "배경색 선택")
        if color.isValid():
            self._change_background(SlideBackground(color=color.name()), all_slides)

    def _choose_background_image(self, all_slides: bool) -> None:
        if not self._background_rows(all_slides):
            return
        path, _ = QFileDialog.getOpenFileName(self, "배경 이미지 선택", "", "이미지 (*.png *.jpg *.jpeg)")
        if not path:
            return
        try:
            background = import_background_image(Path(path), self._background_directory)
        except PowerPointError as error:
            QMessageBox.warning(self, "배경 이미지를 열 수 없습니다", str(error))
            return
        self._change_background(background, all_slides)

    def _change_background(self, background: SlideBackground | None, all_slides: bool) -> None:
        rows = self._background_rows(all_slides)
        selected = self.selected_rows()

        def apply() -> list[int]:
            self.model.sequence.set_background(rows, background)
            return selected

        message = "배경 변경" if background is not None else "원래 배경으로 복원"
        self.model.edit(apply, f"{len(rows)}장 {message}")

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
        self.selection_toolbar.setVisible(count > 0)
        self.options_widget.setVisible(count > 0)
        self.count.setText(f"{count}장 · {len(rows)}장 선택")
        self.actions["remove"].setEnabled(bool(rows))
        self.actions["duplicate"].setEnabled(bool(rows))
        for key in ("up", "first"):
            self.actions[key].setEnabled(bool(rows) and rows != list(range(len(rows))))
        for key in ("down", "last"):
            self.actions[key].setEnabled(bool(rows) and rows != list(range(count - len(rows), count)))
        self.clear_button.setEnabled(count > 0)
        self._selected_background.setEnabled(bool(rows))
        self._reset_background_actions[False].setEnabled(
            any(self.model.slides[row].background is not None for row in rows))
        self._reset_background_actions[True].setEnabled(any(slide.background is not None for slide in self.model.slides))
        if hasattr(self, 'preview_button'):
            self.preview_button.setEnabled(bool(rows))

    def _context_menu(self, position) -> None:
        index = self.view.indexAt(position)
        if not index.isValid():
            return
        if not self.view.selectionModel().isSelected(index):
            self.view.setCurrentIndex(index)
        menu = QMenu(self)
        for action in self.actions.values():
            menu.addAction(action)
        menu.addSeparator()
        menu.addMenu(self.background_menu)
        menu.addAction('확대 보기 · Space', lambda: open_preview(self.view))
        menu.exec(self.view.viewport().mapToGlobal(position))
