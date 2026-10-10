"""아이콘 전용 컨트롤에서도 툴팁과 접근성 이름을 유지한다."""

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QToolButton, QWidget


_PATHS = {
    "add-file": '<path d="M14 2H5v20h14V7z M14 2v5h5 M8 14h8 M12 10v8"/>',
    "remove": '<path d="M3 6h18 M9 6V3h6v3 M5 6l1 15h12l1-15 M10 10v7 M14 10v7"/>',
    "clear": '<path d="M4 5h9 M4 11h6 M4 17h6 M15 11l6 6 M21 11l-6 6"/>',
    "reload": '<path d="M20 7a9 9 0 1 0 1 8 M20 2v5h-5"/>',
    "add": '<path d="M12 4v16 M4 12h16"/>',
    "duplicate": '<rect x="8" y="8" width="13" height="13" rx="2"/><path d="M16 8V3H3v13h5"/>',
    "previous": '<path d="M15 5l-7 7 7 7"/>',
    "next": '<path d="M9 5l7 7-7 7"/>',
    "first": '<path d="M6 4v16 M18 5l-7 7 7 7"/>',
    "last": '<path d="M18 4v16 M6 5l7 7-7 7"/>',
    "folder": '<path d="M3 7V4h7l2 3h9v13H3z"/>',
    "file": '<path d="M14 2H5v20h14V7z M14 2v5h5 M8 12h8 M8 16h6"/>',
    "presentation": '<path d="M14 2H5v20h14V7z M14 2v5h5 M9 18v-7h3a2 2 0 0 1 0 4H9"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 0 1 6 0c0 2-3 2-3 5 M12 17v.2"/>',
    "search": '<circle cx="10" cy="10" r="6"/><path d="M15 15l6 6"/>',
}


def icon(name: str, foreground: str | None = None) -> QIcon:
    result = QIcon()
    for mode, color in ((QIcon.Mode.Normal, "#475569"),
                        (QIcon.Mode.Disabled, "#94a3b8"),
                        (QIcon.Mode.Active, "#2563eb")):
        if mode != QIcon.Mode.Disabled:
            if foreground is not None:
                color = foreground
            elif name == "presentation":
                color = "#c43e1c"
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
               f'fill="none" stroke="{color}" stroke-width="1.8" '
               f'stroke-linecap="round" stroke-linejoin="round">{_PATHS[name]}</svg>')
        pixmap = QPixmap(48, 48)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        QSvgRenderer(QByteArray(svg.encode())).render(painter)
        painter.end()
        result.addPixmap(pixmap, mode)
    return result


def icon_button(name: str, description: str, parent: QWidget | None = None) -> QToolButton:
    button = QToolButton(parent)
    button.setIcon(icon(name))
    button.setIconSize(QSize(20, 20))
    button.setFixedSize(36, 36)
    button.setToolTip(description)
    button.setAccessibleName(description)
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    return button
