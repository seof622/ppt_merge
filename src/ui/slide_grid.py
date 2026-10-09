"""PNG 썸네일을 표시하고 Ctrl·Shift 다중 선택을 제공한다."""

from collections import OrderedDict

from PySide6.QtCore import QAbstractListModel, QModelIndex, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QListView, QMenu, QPushButton,
                               QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from src.models.presentation_model import PresentationInfo
from src.models.slide_model import SlideItem
from src.ui.slide_mime import SLIDE_MIME, make_slide_mime


class ElidedLabel(QLabel):
    """긴 파일명은 줄이고 전체 경로는 툴팁에서 확인한다."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self._full_text = text
        self.setToolTip(text)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._refresh()

    def setText(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._refresh()

    def _refresh(self) -> None:
        super().setText(self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideRight,
                                                     max(0, self.width())))

    def resizeEvent(self, event) -> None:
        self._refresh()
        super().resizeEvent(event)


class SlideListModel(QAbstractListModel):
    """화면에서 요청하는 이미지에만 QIcon을 만들고 최대 128개를 유지한다."""

    def __init__(self, parent=None, drag_token: str = "") -> None:
        super().__init__(parent)
        self.drag_token = drag_token
        self.card_size = QSize(276, 210)
        self.slides: tuple[SlideItem, ...] = ()
        self._icons: OrderedDict[int, QIcon] = OrderedDict()

    def set_slides(self, slides: tuple[SlideItem, ...]) -> None:
        self.beginResetModel()
        self.slides = slides
        self._icons.clear()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.slides)

    def flags(self, index):
        flags = super().flags(index)
        return flags | Qt.ItemFlag.ItemIsDragEnabled if index.isValid() else flags

    def mimeTypes(self):
        return [SLIDE_MIME]

    def mimeData(self, indexes):
        rows = sorted({index.row() for index in indexes if index.isValid()})
        return make_slide_mime(self.drag_token, tuple(self.slides[row] for row in rows))

    def supportedDragActions(self):
        return Qt.DropAction.CopyAction

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.slides):
            return None
        slide = self.slides[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return f"{slide.slide_index}. {slide.title or '슬라이드'}"
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{slide.title or '슬라이드'}\n{slide.source_file}\n슬라이드 {slide.slide_index}"
        if role == Qt.ItemDataRole.SizeHintRole:
            return self.card_size
        if role == Qt.ItemDataRole.UserRole:
            return slide
        if role == Qt.ItemDataRole.DecorationRole:
            number = index.row()
            if number not in self._icons:
                pixmap = QPixmap(slide.thumbnail_path or "")
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(248, 144, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
                self._icons[number] = QIcon(pixmap)
                if len(self._icons) > 128:
                    self._icons.popitem(last=False)
            self._icons.move_to_end(number)
            return self._icons[number]
        return None


class SlideGrid(QWidget):
    add_requested = Signal(object)

    def __init__(self, parent=None, drag_token: str = "") -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 16, 16)
        layout.setSpacing(8)
        header = QHBoxLayout()
        self.heading = ElidedLabel("슬라이드 미리보기")
        self.heading.setObjectName("sectionTitle")
        self.count = QLabel("")
        self.count.setObjectName("mutedText")
        header.addWidget(self.heading, 1)
        header.addWidget(self.count)
        self.add_button = QPushButton("선택 슬라이드 담기")
        self.add_button.clicked.connect(self.add_selected)
        header.addWidget(self.add_button)
        layout.addLayout(header)
        self.hint = QLabel("Ctrl·Shift 선택 · 더블클릭 또는 아래 출력 목록에 끌어 놓아 담기")
        self.hint.setObjectName("mutedText")
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)
        self.stack = QStackedWidget()
        self.empty = QLabel()
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.setObjectName("emptyState")
        self.stack.addWidget(self.empty)
        self.view = QListView()
        self.view.setObjectName("slideView")
        self.model = SlideListModel(self.view, drag_token)
        self.view.setModel(self.model)
        self.view.setViewMode(QListView.ViewMode.IconMode)
        self.view.setResizeMode(QListView.ResizeMode.Adjust)
        self.view.setMovement(QListView.Movement.Static)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.view.setIconSize(QSize(248, 144))
        self.view.setSpacing(10)
        self.view.setWordWrap(False)
        self.view.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.view.setUniformItemSizes(True)
        self.view.setLayoutMode(QListView.LayoutMode.Batched)
        self.view.setBatchSize(40)
        self.view.setDragEnabled(True)
        self.view.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.view.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.view.doubleClicked.connect(self._double_clicked)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._context_menu)
        self.view.selectionModel().selectionChanged.connect(self._selection_changed)
        self.stack.addWidget(self.view)
        layout.addWidget(self.stack, 1)
        self.show_message("슬라이드 미리보기", "PPT 파일을 추가하면 이곳에 슬라이드가 표시됩니다.")

    def show_message(self, heading: str, message: str) -> None:
        self.model.set_slides(())
        self.heading.setText(heading)
        self.heading.setToolTip(heading)
        self.count.setText("")
        self.add_button.setEnabled(False)
        self.hint.hide()
        self.empty.setText(message)
        self.stack.setCurrentWidget(self.empty)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not hasattr(self, "view"):
            return
        # 높이가 작은 창에서도 썸네일과 번호를 한 장씩 온전히 볼 수 있게 한다.
        compact = self.view.height() < 230
        size = QSize(196, 136) if compact else QSize(276, 210)
        if self.model.card_size != size:
            self.model.card_size = size
            self.view.setIconSize(QSize(160, 90) if compact else QSize(248, 144))
            self.view.doItemsLayout()

    def show_presentation(self, info: PresentationInfo) -> None:
        self.model.set_slides(info.slides)
        self.heading.setText(info.source_file_name)
        self.heading.setToolTip(info.source_file)
        self.hint.show()
        self._selection_changed()
        if info.slide_count:
            self.stack.setCurrentWidget(self.view)
        else:
            self.empty.setText("이 PPT에는 슬라이드가 없습니다.")
            self.stack.setCurrentWidget(self.empty)

    def _selection_changed(self, *args) -> None:
        selected = len(self.view.selectionModel().selectedIndexes())
        self.count.setText(f"{self.model.rowCount()}장 · {selected}장 선택")
        self.add_button.setEnabled(selected > 0)

    def add_selected(self) -> None:
        slides = self.selected_slides()
        if slides:
            self.add_requested.emit(slides)

    def _double_clicked(self, index) -> None:
        if index.isValid():
            self.add_requested.emit((self.model.slides[index.row()],))

    def _context_menu(self, position) -> None:
        index = self.view.indexAt(position)
        if not index.isValid():
            return
        if not self.view.selectionModel().isSelected(index):
            self.view.setCurrentIndex(index)
        menu = QMenu(self)
        menu.addAction("선택 슬라이드 담기", self.add_selected)
        menu.exec(self.view.viewport().mapToGlobal(position))

    def selected_slides(self) -> tuple[SlideItem, ...]:
        return tuple(self.model.slides[index.row()] for index in
                     sorted(self.view.selectionModel().selectedIndexes(), key=lambda i: i.row()))
