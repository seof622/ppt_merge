"""기본 캐시를 먼저 보여 주고 선택한 한 장의 고해상도 이미지를 준비한다."""

from PySide6.QtCore import Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
from src.workers.ppt_worker import PreviewWorker


class SlidePreview(QDialog):
    released = Signal()

    def __init__(self, slides, row, parent=None, service_factory=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.slides, self.row = tuple(slides), row
        self._factory = service_factory
        self._thread = self._worker = None
        self._closing = False
        self._pending = None
        self._high_resolution = {}
        self.resize(1050, 740)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        self.heading = QLabel()
        self.heading.setObjectName('sectionTitle')
        self.heading.setWordWrap(True)
        layout.addWidget(self.heading)
        self.image = QLabel()
        self.image.setMinimumSize(240, 160)
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image, 1)
        self.quality = QLabel('기본 미리보기')
        self.quality.setObjectName('mutedText')
        self.quality.setWordWrap(True)
        layout.addWidget(self.quality)
        footer = QHBoxLayout()
        self.previous = QPushButton('← 이전')
        self.next = QPushButton('다음 →')
        self.previous.clicked.connect(lambda: self.move(-1))
        self.next.clicked.connect(lambda: self.move(1))
        self.counter = QLabel()
        footer.addWidget(self.previous)
        footer.addWidget(self.counter)
        footer.addWidget(self.next)
        footer.addStretch()
        close = QPushButton('닫기 · Esc')
        close.clicked.connect(self.close)
        footer.addWidget(close)
        layout.addLayout(footer)
        for key, direction in (('Left', -1), ('Right', 1)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(lambda step=direction: self.move(step))
        self.refresh()
        if self._factory:
            QTimer.singleShot(0, self._request_preview)

    @property
    def is_loading(self):
        return self._thread is not None

    @Slot()
    def _resume_preview(self):
        window = self.parentWidget()
        if not self._closing and not window.is_busy and not window._closing:
            self._factory = window._preview_factory
            self._request_preview()

    def _request_preview(self):
        if self._closing or not self._factory:
            return
        slide = self.slides[self.row]
        if slide in self._high_resolution:
            self.quality.setText('고해상도 미리보기')
            return
        if self.is_loading:
            self._pending = slide
            self._worker.request_cancel()
            self.quality.setText('선택한 슬라이드의 고해상도 미리보기를 준비합니다…')
            return
        self._pending = None
        self.quality.setText('고해상도 미리보기를 준비합니다…')
        thread = QThread(self)
        worker = PreviewWorker(slide, self._factory)
        worker.moveToThread(thread)
        self._thread, self._worker = thread, worker
        thread.started.connect(worker.run)
        worker.loaded.connect(self._loaded, Qt.ConnectionType.QueuedConnection)
        worker.failed.connect(self._failed, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(thread.quit)
        thread.finished.connect(self._worker_finished)
        thread.start()

    @Slot(object, str)
    def _loaded(self, slide, path):
        self._high_resolution[slide] = path
        if slide == self.slides[self.row] and not self._closing:
            self.refresh()
            self.quality.setText('고해상도 미리보기')

    @Slot(object, str)
    def _failed(self, slide, message):
        if slide == self.slides[self.row] and not self._closing:
            self.quality.setText('기본 미리보기 표시 중 · ' + message)

    @Slot()
    def _worker_finished(self):
        thread = self._thread
        if thread is not None and not thread.wait(0):
            QTimer.singleShot(10, self._worker_finished)
            return
        self._thread = self._worker = None
        if thread is not None:
            thread.deleteLater()
        if self._closing:
            self.deleteLater()
            self.released.emit()
        elif self._pending is not None:
            self._pending = None
            self._request_preview()

    def move(self, direction):
        row = max(0, min(len(self.slides) - 1, self.row + direction))
        if row == self.row:
            return
        self.row = row
        self.refresh()
        self._request_preview()

    def refresh(self):
        slide = self.slides[self.row]
        self.setWindowTitle(f'{slide.source_file_name} · 원본 {slide.slide_index}번')
        self.heading.setText(slide.title or '슬라이드')
        self.counter.setText(f'{self.row + 1} / {len(self.slides)} · 원본 {slide.slide_index}번')
        self.counter.setToolTip(slide.source_file)
        self.previous.setEnabled(self.row > 0)
        self.next.setEnabled(self.row < len(self.slides) - 1)
        pixmap = QPixmap(self._high_resolution.get(slide, slide.thumbnail_path) or '')
        if pixmap.isNull():
            self.image.setText('미리보기 이미지가 없습니다. 원본을 다시 읽어 주세요.')
        else:
            self.image.setPixmap(pixmap.scaled(self.image.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'image'):
            self.refresh()

    def done(self, result):
        if self._closing:
            return
        self._closing = True
        self._pending = None
        loading = self.is_loading
        if loading:
            # 창은 즉시 닫고 자식 QThread가 정리될 때까지 객체를 유지한다.
            self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
            self._worker.request_cancel()
        super().done(result)
        if not loading:
            self.released.emit()


def open_preview(view):
    index = view.currentIndex()
    if not index.isValid():
        indexes = view.selectionModel().selectedIndexes()
        index = indexes[0] if indexes else index
    if index.isValid():
        window = view.window()
        factory = (getattr(window, '_preview_factory', None)
                   if not getattr(window, 'is_busy', False) and not getattr(window, '_closing', False) else None)
        dialog = SlidePreview(view.model().slides, index.row(), window, service_factory=factory)
        if hasattr(window, '_preview_dialogs'):
            for previous in window._preview_dialogs:
                if previous.is_loading and previous._closing:
                    previous.released.connect(dialog._resume_preview)
            window._preview_dialogs.add(dialog)
            dialog.finished.connect(window._update_actions)
            dialog.released.connect(lambda: window._preview_released(dialog))
        dialog.open()
        return dialog
