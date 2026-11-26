"""이미지를 중심으로 번호·제목과 선택 상태를 간결하게 표시한다."""

from pathlib import Path
from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QStyledItemDelegate, QStyle
from src.ui.theme import (ACCENT, BORDER, MUTED, TEXT, BADGE_SURFACE, BADGE_TEXT,
                          CARD_SURFACE, HOVER_BORDER, ON_ACCENT, CARD_TITLE_SIZE,
                          CARD_DETAIL_SIZE, CARD_LABEL_SIZE, CARD_BADGE_SIZE,
                          TEXT_WEIGHT, EMPHASIS_WEIGHT)


def slide_card_size(width: int, output: bool = False) -> QSize:
    """원본에는 제목 한 줄, 결과에는 출처 한 줄의 공간을 확보한다."""
    return QSize(width + 12, round(width * 9 / 16) + (62 if output else 44))


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
    painter.setPen(QColor(ON_ACCENT))
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
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect.adjusted(2, 2, -2, -2)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hover = bool(option.state & QStyle.StateFlag.State_MouseOver)
        focused = bool(option.state & QStyle.StateFlag.State_HasFocus)
        image_width = rect.width() - 8
        image_rect = QRect(rect.left() + 4, rect.top() + 4, image_width, round(image_width * 9 / 16))
        frame = image_rect.adjusted(-2, -2, 2, 2)
        painter.setBrush(QColor(CARD_SURFACE))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(frame, 5, 5)
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
        # 원본 이미지는 착색하거나 자르지 않고 바깥 테두리로 선택을 표시한다.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(ACCENT if selected or focused else HOVER_BORDER if hover else BORDER),
                            2 if selected or focused else 1))
        painter.drawRoundedRect(frame, 5, 5)
        font = QFont(option.font)
        font.setPixelSize(CARD_LABEL_SIZE)
        font.setWeight(QFont.Weight(TEXT_WEIGHT))
        painter.setFont(font)
        number = index.row() + 1 if self.output else slide.slide_index
        number_width = max(26, painter.fontMetrics().horizontalAdvance(str(number)) + 10)
        caption = QRect(image_rect.left(), image_rect.bottom() + 10, image_rect.width(), 22)
        painter.setPen(QColor(ACCENT if selected else MUTED))
        painter.drawText(QRect(caption.left(), caption.top(), number_width, caption.height()),
                         Qt.AlignmentFlag.AlignVCenter, f'{number:02d}')
        font.setPixelSize(CARD_TITLE_SIZE)
        font.setWeight(QFont.Weight(EMPHASIS_WEIGHT))
        painter.setFont(font)
        painter.setPen(QColor(TEXT))
        title_rect = caption.adjusted(number_width, 0, 0, 0)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignVCenter,
                         painter.fontMetrics().elidedText(slide.title or '슬라이드',
                                                         Qt.TextElideMode.ElideRight, title_rect.width()))
        if self.output:
            font.setPixelSize(CARD_DETAIL_SIZE)
            font.setWeight(QFont.Weight(TEXT_WEIGHT))
            painter.setFont(font)
            painter.setPen(QColor(MUTED))
            detail = f'{Path(slide.source_file_name).stem} · 원본 {slide.slide_index}'
            detail_rect = QRect(caption.left(), caption.bottom(), caption.width(), 20)
            painter.drawText(detail_rect, Qt.AlignmentFlag.AlignVCenter,
                             painter.fontMetrics().elidedText(detail, Qt.TextElideMode.ElideRight,
                                                             detail_rect.width()))
        else:
            count = getattr(model, 'usage_counts', {}).get((slide.source_file, slide.slide_id), 0)
            if count:
                font.setPixelSize(CARD_BADGE_SIZE)
                font.setWeight(QFont.Weight(EMPHASIS_WEIGHT))
                painter.setFont(font)
                label = f'담김 {count}'
                badge_width = painter.fontMetrics().horizontalAdvance(label) + 16
                badge = QRect(image_rect.left() + 6, image_rect.bottom() - 26, badge_width, 21)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(BADGE_SURFACE))
                painter.drawRoundedRect(badge, 5, 5)
                painter.setPen(QColor(BADGE_TEXT))
                painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, label)
        if selected:
            badge = QRect(image_rect.right() - 24, image_rect.top() + 6, 18, 18)
            painter.setBrush(QColor(ACCENT))
            painter.setPen(QPen(QColor(ON_ACCENT), 1.5))
            painter.drawEllipse(badge)
            painter.setPen(QPen(QColor(ON_ACCENT), 1.8))
            painter.drawLine(badge.left()+4, badge.top()+9, badge.left()+7, badge.top()+12)
            painter.drawLine(badge.left()+7, badge.top()+12, badge.left()+14, badge.top()+5)
        painter.restore()
