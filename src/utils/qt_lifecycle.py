"""화면 객체를 QApplication보다 먼저 해제한다."""

import gc

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication


def shutdown_application(app: QApplication) -> None:
    # 이벤트 루프가 끝난 뒤에도 close()만으로는 창과 자식 모델이 삭제되지 않는다.
    for widget in app.topLevelWidgets():
        widget.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()
    app.shutdown()
