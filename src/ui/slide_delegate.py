"""선택해도 원본 이미지의 색상을 그대로 유지하는 썸네일 카드."""

from pathlib import Path
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QStyledItemDelegate, QStyle
from src.ui.theme import ACCENT, BORDER, MUTED, TEXT


def drag_image(model, index, count):
    pixmap = QPixmap(180, 120)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    source = model.data(index, Qt.ItemDataRole.DecorationRole)
    if source:
        painter.drawPixmap(10, 0, source.pixmap(160, 90))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(ACCENT))
    painter.drawRoundedRect(QRect(24, 90, 132, 28), 6, 6)
    painter.setPen(QColor('white'))
    painter.drawText(QRect(24, 90, 132, 28), Qt.AlignmentFlag.AlignCenter, f'{count}장 이동')
    painter.end()
    return pixmap


class SlideCardDelegate(QStyledItemDelegate):
    def __init__(self, parent=None, output=False):
        super().__init__(parent)
        self.output = output

    def paint(self, painter, option, index):
        model = index.model()
        slide = model.slides[index.row()]
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        rect = option.rect.adjusted(2, 2, -2, -2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        painter.setBrush(QColor('#FFFFFF'))
        painter.setPen(QPen(QColor(ACCENT if selected else '#B7C8EC' if hover else BORDER), 2 if selected else 1))
        painter.drawRoundedRect(rect, 8, 8)
        image_rect = rect.adjusted(10, 10, -10, -65)
        image = model.data(index, Qt.ItemDataRole.DecorationRole)
        if image and not image.isNull():
            pixmap = image.pixmap(image_rect.size(), QIcon.Mode.Normal)
            target = pixmap.size().scaled(image_rect.size(), Qt.AspectRatioMode.KeepAspectRatio)
            dest = QRect(0, 0, target.width(), target.height())
            dest.moveCenter(image_rect.center())
            painter.drawPixmap(dest, pixmap)
        else:
            painter.setPen(QColor(MUTED))
            painter.drawText(image_rect, Qt.AlignmentFlag.AlignCenter, '미리보기 없음')
        title = slide.title or f'슬라이드 {slide.slide_index}'
        title = f'{index.row() + 1} · {title}' if self.output else f'{slide.slide_index} · {title}'
        text_rect = QRect(rect.left() + 12, rect.bottom() - 53, rect.width() - 24, 24)
        font = QFont(option.font)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(TEXT))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter,
                         painter.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight, text_rect.width()))
        font.setBold(False)
        font.setPixelSize(12)
        painter.setFont(font)
        painter.setPen(QColor(MUTED))
        count = getattr(model, 'usage_counts', {}).get((slide.source_file, slide.slide_id), 0)
        detail = f'원본 {slide.slide_index}번 · {Path(slide.source_file_name).stem}' if self.output else (f'결과에 {count}회 사용' if count else '선택해서 결과에 담기')
        painter.drawText(text_rect.translated(0, 25), Qt.AlignmentFlag.AlignVCenter,
                         painter.fontMetrics().elidedText(detail, Qt.TextElideMode.ElideRight, text_rect.width()))
        if selected:
            badge = QRect(rect.right() - 26, rect.top() + 8, 18, 18)
            painter.setBrush(QColor(ACCENT))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(badge)
            painter.setPen(QPen(QColor('white'), 2))
            painter.drawLine(badge.left()+4, badge.top()+9, badge.left()+7, badge.top()+12)
            painter.drawLine(badge.left()+7, badge.top()+12, badge.left()+14, badge.top()+5)
        if option.state & QStyle.StateFlag.State_HasFocus:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(ACCENT), 1, Qt.PenStyle.DotLine))
            painter.drawRoundedRect(rect.adjusted(4, 4, -4, -4), 5, 5)
        painter.restore()
