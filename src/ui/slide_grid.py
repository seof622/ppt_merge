"""PNG 썸네일을 표시하고 Ctrl·Shift 다중 선택을 제공한다."""

from collections import OrderedDict

from PySide6.QtCore import QAbstractListModel, QModelIndex, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QListView,
                               QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from src.models.presentation_model import PresentationInfo
from src.models.slide_model import SlideItem


class ElidedLabel(QLabel):
    """긴 파일명은 줄이고 전체 경로는 툴팁에서 확인한다."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._refresh()

    def setText(self, text: str) -> None:
        self._full_text = text
        self._refresh()

    def _refresh(self) -> None:
        super().setText(self.fontMetrics().elidedText(self._full_text, Qt.TextElideMode.ElideRight,
                                                     max(0, self.width())))

    def resizeEvent(self, event) -> None:
        self._refresh()
        super().resizeEvent(event)


class SlideListModel(QAbstractListModel):
    """화면에서 요청하는 이미지에만 QIcon을 만들고 최대 128개를 유지한다."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.slides: tuple[SlideItem, ...] = ()
        self._icons: OrderedDict[int, QIcon] = OrderedDict()

    def set_slides(self, slides: tuple[SlideItem, ...]) -> None:
        self.beginResetModel()
        self.slides = slides
        self._icons.clear()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.slides)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.slides):
            return None
        slide = self.slides[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return f"{slide.slide_index}. {slide.title or '슬라이드'}"
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{slide.title or '슬라이드'}\n{slide.source_file}\n슬라이드 {slide.slide_index}"
        if role == Qt.ItemDataRole.SizeHintRole:
            return QSize(276, 210)
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
    def __init__(self, parent=None) -> None:
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
        layout.addLayout(header)
        self.hint = QLabel("Ctrl·Shift로 여러 슬라이드를 선택할 수 있습니다.")
        self.hint.setObjectName("mutedText")
        layout.addWidget(self.hint)
        self.stack = QStackedWidget()
        self.empty = QLabel()
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.setObjectName("emptyState")
        self.stack.addWidget(self.empty)
        self.view = QListView()
        self.view.setObjectName("slideView")
        self.model = SlideListModel(self.view)
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
        self.view.selectionModel().selectionChanged.connect(self._selection_changed)
        self.stack.addWidget(self.view)
        layout.addWidget(self.stack, 1)
        self.show_message("슬라이드 미리보기", "PPT 파일을 추가하면 이곳에 슬라이드가 표시됩니다.")

    def show_message(self, heading: str, message: str) -> None:
        self.model.set_slides(())
        self.heading.setText(heading)
        self.heading.setToolTip(heading)
        self.count.setText("")
        self.hint.hide()
        self.empty.setText(message)
        self.stack.setCurrentWidget(self.empty)

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

    def selected_slides(self) -> tuple[SlideItem, ...]:
        return tuple(self.model.slides[index.row()] for index in
                     sorted(self.view.selectionModel().selectedIndexes(), key=lambda i: i.row()))
