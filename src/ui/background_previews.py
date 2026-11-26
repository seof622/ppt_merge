"""출력 카드에서 요청한 배경 미리보기를 백그라운드에서 준비한다."""

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from src.workers.ppt_worker import BackgroundPreviewWorker


class BackgroundPreviews(QObject):
    finished = Signal()

    def __init__(self, parent, model, service_factory, can_start):
        super().__init__(parent)
        self._model = model
        self._service_factory = service_factory
        self._can_start = can_start
        self._pending = {}
        self._active = ()
        self._thread = self._worker = None
        self._timer = QTimer(self, singleShot=True, interval=40)
        self._timer.timeout.connect(self._start)
        if service_factory is not None:
            model.background_preview_requested.connect(self._request)
            model.modelReset.connect(self._model_changed)

    @property
    def is_running(self) -> bool:
        return self._thread is not None

    def cancel(self) -> None:
        if self._worker is not None:
            self._worker.request_cancel()

    def schedule(self) -> None:
        if self._pending and not self.is_running and not self._timer.isActive() and self._can_start():
            self._timer.start()

    @Slot(object)
    def _request(self, slide) -> None:
        if slide not in self._active:
            self._pending[slide] = None
            self.schedule()

    @Slot()
    def _model_changed(self) -> None:
        if self.is_running and not set(self._active).intersection(self._model.slides):
            self.cancel()

    @Slot()
    def _start(self) -> None:
        if self.is_running or not self._can_start():
            return
        current = set(self._model.slides)
        slides = tuple(slide for slide in self._pending
                       if slide in current and self._model.needs_background_thumbnail(slide))
        self._pending.clear()
        if not slides:
            return
        thread = QThread(self)
        worker = BackgroundPreviewWorker(slides, self._service_factory)
        worker.moveToThread(thread)
        self._thread, self._worker, self._active = thread, worker, slides
        thread.started.connect(worker.run)
        worker.loaded.connect(self._loaded)
        worker.failed.connect(self._failed)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(thread.quit)
        thread.finished.connect(self._thread_finished)
        thread.start()

    @Slot(object, str)
    def _loaded(self, slide, path) -> None:
        self._model.set_background_thumbnail(slide, path)

    @Slot(object, str)
    def _failed(self, slide, message) -> None:
        self._model.fail_background_thumbnail(slide, message)

    @Slot()
    def _thread_finished(self) -> None:
        thread = self._thread
        if not thread.wait(0):
            QTimer.singleShot(10, self._thread_finished)
            return
        self._thread = self._worker = None
        for slide in self._active:
            if self._model.needs_background_thumbnail(slide):
                self._pending[slide] = None
        self._active = ()
        thread.deleteLater()
        self.finished.emit()
        self.schedule()
