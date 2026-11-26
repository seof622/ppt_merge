"""PNG 썸네일을 표시하고 Ctrl·Shift 다중 선택을 제공한다."""

from collections import OrderedDict

from PySide6.QtCore import QAbstractListModel, QModelIndex, QSize, Qt, Signal
from PySide6.QtGui import QDrag, QIcon, QPixmap, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QBoxLayout, QHBoxLayout, QLabel, QListView, QMenu,
                               QLineEdit, QPushButton, QSlider, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from src.models.presentation_model import PresentationInfo
from src.models.slide_model import SlideItem
from src.ui.slide_mime import SLIDE_MIME, make_slide_mime
from src.ui.icons import icon
from src.ui.slide_delegate import SlideCardDelegate, drag_image, slide_card_size
from src.ui.slide_preview import open_preview


class ElidedLabel(QLabel):
    """긴 파일명은 줄이고 전체 경로는 툴팁에서 확인한다."""

    def __init__(self, text: str, elide_mode=Qt.TextElideMode.ElideRight) -> None:
        super().__init__()
        self._full_text = text
        self.elide_mode = elide_mode
        self.setToolTip(text)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._refresh()

    def setText(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._refresh()

    def _refresh(self) -> None:
        super().setText(self.fontMetrics().elidedText(self._full_text, self.elide_mode,
                                                     max(0, self.width())))

    def resizeEvent(self, event) -> None:
        self._refresh()
        super().resizeEvent(event)


class SlideListModel(QAbstractListModel):
    """화면에서 요청하는 이미지에만 QIcon을 만들고 최대 128개를 유지한다."""

    def __init__(self, parent=None, drag_token: str = "") -> None:
        super().__init__(parent)
        self.drag_token = drag_token
        self.card_size = slide_card_size(240)
        self.slides: tuple[SlideItem, ...] = ()
        self._icons: OrderedDict[int, QIcon] = OrderedDict()
        self.usage_counts = {}

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
                    pixmap = pixmap.scaled(360, 220, Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
                self._icons[number] = QIcon(pixmap)
                if len(self._icons) > 128:
                    self._icons.popitem(last=False)
            self._icons.move_to_end(number)
            return self._icons[number]
        return None


class SourceSlideView(QListView):
    resized = Signal()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.resized.emit()

    def startDrag(self, supported_actions):
        indexes = sorted(self.selectionModel().selectedIndexes(), key=lambda i: i.row())
        if not indexes:
            return
        drag = QDrag(self)
        drag.setMimeData(self.model().mimeData(indexes))
        drag.setPixmap(drag_image(self.model(), indexes[0], len(indexes)))
        try:
            drag.exec(Qt.DropAction.CopyAction)
        finally:
            drag.deleteLater()


class SlideGrid(QWidget):
    add_requested = Signal(object)
    add_files_requested = Signal()

    def __init__(self, parent=None, drag_token: str = "") -> None:
        super().__init__(parent)
        self.setObjectName("slidePanel")
        self._all_slides = ()
        self._search_text = {}
        self._usage_counts = {}
        self._compact_controls = False
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)
        title = QLabel('원본 슬라이드')
        title.setObjectName('sectionTitle')
        layout.addWidget(title)
        header = QHBoxLayout()
        header.setSpacing(8)
        self.heading = ElidedLabel("슬라이드", Qt.TextElideMode.ElideMiddle)
        self.heading.setObjectName("mutedText")
        self.count = QLabel("")
        self.count.setObjectName("mutedText")
        header.addWidget(self.heading, 1)
        header.addWidget(self.count)
        self.add_button = QPushButton('선택해서 담기 →')
        self.add_button.setAccessibleName('선택 슬라이드 담기')
        self.add_button.clicked.connect(self.add_selected)
        layout.addLayout(header)
        self.search = QLineEdit()
        self.search.setObjectName('slideSearch')
        self.search.setFixedHeight(36)
        self.search.addAction(icon('search'), QLineEdit.ActionPosition.LeadingPosition)
        self.search.setPlaceholderText('이 PPT의 슬라이드 제목·내용 검색')
        self.search.setAccessibleName('현재 PPT의 슬라이드 제목과 본문 검색')
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter_slides)
        layout.addWidget(self.search)
        hint = self.hint = QLabel('더블클릭으로 담기 · 결과 영역으로 드래그')
        hint.setObjectName('mutedText')
        layout.addWidget(hint)
        self.stack = QStackedWidget()
        self.empty = QLabel()
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.setObjectName("emptyState")
        self.empty_page = QWidget()
        empty_layout = QVBoxLayout(self.empty_page)
        empty_layout.addStretch()
        empty_layout.addWidget(self.empty)
        self.empty_add_button = QPushButton('PPT 추가')
        self.empty_add_button.setObjectName('primaryButton')
        self.empty_add_button.clicked.connect(self.add_files_requested.emit)
        empty_layout.addWidget(self.empty_add_button, 0, Qt.AlignmentFlag.AlignHCenter)
        self.drop_hint = QLabel('파일을 이 창으로 끌어 놓아도 됩니다')
        self.drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_hint.setObjectName('mutedText')
        empty_layout.addWidget(self.drop_hint)
        empty_layout.addStretch()
        self.stack.addWidget(self.empty_page)
        self.view = SourceSlideView()
        self.view.setObjectName("slideView")
        self.view.setAccessibleName("원본 슬라이드")
        self.view.setToolTip("Ctrl·Shift 선택 · 더블클릭 또는 출력 목록에 끌어 놓아 담기")
        self.model = SlideListModel(self.view, drag_token)
        self.view.setModel(self.model)
        self.view.resized.connect(self._resize_cards)
        self.view.setItemDelegate(SlideCardDelegate(self.view))
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
        self.footer_controls = QWidget()
        self.footer_layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self.footer_controls)
        self.footer_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_widget = QWidget()
        controls = QHBoxLayout(self.controls_widget)
        controls.setContentsMargins(0, 0, 0, 0)
        self.preview_button = QPushButton('확대 보기')
        self.preview_button.setObjectName('quietButton')
        self.preview_button.setToolTip('선택한 슬라이드 크게 보기 · Space')
        self.preview_button.clicked.connect(lambda: open_preview(self.view))
        controls.addWidget(self.preview_button)
        controls.addStretch()
        zoom_label = self.zoom_label = QLabel('크기')
        zoom_label.setObjectName('mutedText')
        controls.addWidget(zoom_label)
        self.zoom = QSlider(Qt.Orientation.Horizontal)
        self.zoom.setRange(160, 300)
        self.zoom.setValue(240)
        self.zoom.setMaximumWidth(110)
        self.zoom.setAccessibleName('원본 썸네일 크기')
        self.zoom.valueChanged.connect(self._resize_cards)
        controls.addWidget(self.zoom)
        self.footer_layout.addWidget(self.controls_widget)
        self.actions_widget = QWidget()
        actions = QHBoxLayout(self.actions_widget)
        actions.setContentsMargins(0, 0, 0, 0)
        self.all_button = QPushButton('전체 담기')
        self.all_button.clicked.connect(lambda: self.add_requested.emit(self.model.slides))
        actions.addWidget(self.all_button)
        actions.addWidget(self.add_button, 1)
        self.add_button.setObjectName('addSlidesButton')
        self.footer_layout.addWidget(self.actions_widget, 1)
        layout.addWidget(self.footer_controls)
        shortcut = QShortcut(QKeySequence('Space'), self.view)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(lambda: open_preview(self.view))
        self.show_message("슬라이드", "PPT를 추가하세요")

    def show_message(self, heading: str, message: str) -> None:
        self._all_slides = ()
        self._search_text = {}
        self.model.set_slides(())
        self.heading.setText(heading)
        self.heading.setToolTip(heading)
        self.count.setText("")
        self.add_button.setEnabled(False)
        self.empty.setText(message)
        self.stack.setCurrentWidget(self.empty_page)
        self.all_button.setEnabled(False)
        self.preview_button.setEnabled(False)
        self.search.setEnabled(False)
        self._show_tools(False)

    def _show_tools(self, loaded):
        self.search.setVisible(loaded)
        self.hint.setVisible(loaded and not self._compact_controls)
        self.footer_controls.setVisible(loaded)
        self.empty_add_button.setVisible(not loaded)
        self.drop_hint.setVisible(not loaded)

    def set_compact(self, compact):
        if compact == self._compact_controls:
            return
        self._compact_controls = compact
        self.layout().setContentsMargins(20, 12 if compact else 20, 20, 12 if compact else 16)
        self.layout().setSpacing(8 if compact else 12)
        self.footer_layout.setDirection(QBoxLayout.Direction.LeftToRight if compact else QBoxLayout.Direction.TopToBottom)
        self.zoom_label.setVisible(not compact)
        self.zoom.setMaximumWidth(80 if compact else 110)
        self.preview_button.setText('확대' if compact else '확대 보기')
        self._show_tools(bool(self._all_slides))
        self._selection_changed()
        self._resize_cards()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not hasattr(self, "view"):
            return
        self._resize_cards()

    def _resize_cards(self, *args):
        width = self.zoom.value() if hasattr(self, 'zoom') else 240
        available = self.view.viewport().height() - 2 * self.view.spacing() - 4
        if available > 0:
            width = min(width, max(80, int((available - 44) * 16 / 9)))
        # 좁은 패널에서도 카드의 좌우가 잘리지 않게 한다.
        width = min(width, max(100, self.view.viewport().width() - 2 * self.view.spacing() - 16))
        if self._compact_controls and self.model.rowCount() >= 3 and self.view.viewport().width() >= 600:
            # 낮은 창에서는 세 장을 한 줄에 보여 주어 한 장만 다음 줄에 잘리지 않게 한다.
            width = min(width, (self.view.viewport().width() - 6 * 8 - 6) // 3 - 12)
        size = slide_card_size(width)
        if self.model.card_size != size:
            self.model.card_size = size
            self.view.setIconSize(QSize(width, round(width * 9 / 16)))
            self.view.setSpacing(8)
            self.view.doItemsLayout()
            self.view.viewport().update()

    def show_presentation(self, info: PresentationInfo, search_text=None) -> None:
        same = bool(self._all_slides and self._all_slides[0].source_file == info.source_file)
        self._all_slides = info.slides
        self._search_text = search_text or {}
        if not same:
            self.search.blockSignals(True)
            self.search.clear()
            self.search.blockSignals(False)
        self.search.setEnabled(True)
        self._show_tools(True)
        self._filter_slides()
        self.heading.setText(info.source_file_name)
        self.heading.setToolTip(info.source_file)
        self._selection_changed()
        if self.model.rowCount():
            self.stack.setCurrentWidget(self.view)
        elif not info.slide_count:
            self.empty.setText("이 PPT에는 슬라이드가 없습니다.")
            self.stack.setCurrentWidget(self.empty_page)

    def _filter_slides(self, *args):
        query = self.search.text().strip().casefold()
        selected = {(s.source_file, s.slide_id) for s in self.selected_slides()}
        slides = tuple(s for s in self._all_slides
                       if not query or query in f'{s.slide_index} {s.title or ""} {self._search_text.get(s.slide_index, "")}'.casefold())
        self.model.set_slides(slides)
        for row, slide in enumerate(slides):
            if (slide.source_file, slide.slide_id) in selected:
                from PySide6.QtCore import QItemSelectionModel
                self.view.selectionModel().select(self.model.index(row, 0), QItemSelectionModel.SelectionFlag.Select)
        self.all_button.setText(f'{"검색 결과" if query else "전체"} {len(slides)}장 담기')
        self.all_button.setEnabled(bool(slides))
        self.stack.setCurrentWidget(self.view if slides else self.empty_page)
        self.empty.setText('검색 결과가 없습니다.' if query else 'PPT를 추가하거나 파일을 끌어 놓으세요.')
        self._resize_cards()
        self._selection_changed()

    def set_usage(self, slides):
        counts = {}
        for slide in slides:
            key = (slide.source_file, slide.slide_id)
            counts[key] = counts.get(key, 0) + 1
        self.model.usage_counts = counts
        self.view.viewport().update()

    def _selection_changed(self, *args) -> None:
        selected = len(self.view.selectionModel().selectedIndexes())
        self.count.setText(f"{self.model.rowCount()}장 · {selected}장 선택")
        self.add_button.setEnabled(selected > 0)
        self.add_button.setText((f'{selected}장 담기 →' if self._compact_controls else f'선택한 {selected}장 담기 →')
                               if selected else '선택해서 담기 →')
        self.preview_button.setEnabled(selected > 0)

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
        menu.addAction('확대 보기 · Space', lambda: open_preview(self.view))
        menu.exec(self.view.viewport().mapToGlobal(position))

    def selected_slides(self) -> tuple[SlideItem, ...]:
        return tuple(self.model.slides[index.row()] for index in
                     sorted(self.view.selectionModel().selectedIndexes(), key=lambda i: i.row()))
