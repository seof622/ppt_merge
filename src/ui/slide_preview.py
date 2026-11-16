"""캐시 이미지를 큰 화면으로 확인한다. PowerPoint를 추가로 열지 않는다."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


class SlidePreview(QDialog):
    def __init__(self, slides, row, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.slides, self.row = tuple(slides), row
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

    def move(self, direction):
        self.row = max(0, min(len(self.slides) - 1, self.row + direction))
        self.refresh()

    def refresh(self):
        slide = self.slides[self.row]
        self.setWindowTitle(f'{slide.source_file_name} · 원본 {slide.slide_index}번')
        self.heading.setText(slide.title or '슬라이드')
        self.counter.setText(f'{self.row + 1} / {len(self.slides)} · 원본 {slide.slide_index}번')
        self.counter.setToolTip(slide.source_file)
        self.previous.setEnabled(self.row > 0)
        self.next.setEnabled(self.row < len(self.slides) - 1)
        pixmap = QPixmap(slide.thumbnail_path or '')
        if pixmap.isNull():
            self.image.setText('미리보기 이미지가 없습니다. 원본을 다시 읽어 주세요.')
        else:
            self.image.setPixmap(pixmap.scaled(self.image.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                              Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'image'):
            self.refresh()


def open_preview(view):
    index = view.currentIndex()
    if not index.isValid():
        indexes = view.selectionModel().selectedIndexes()
        index = indexes[0] if indexes else index
    if index.isValid():
        dialog = SlidePreview(view.model().slides, index.row(), view.window())
        dialog.open()
        return dialog
