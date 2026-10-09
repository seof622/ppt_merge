"""QThread에서 썸네일 서비스를 호출하고 일반 데이터만 화면에 전달한다."""

from collections.abc import Callable
import logging
from pathlib import Path
import threading

from PySide6.QtCore import QObject, Signal, Slot

from src.ppt.errors import OperationCancelled, PowerPointError
from src.ppt.thumbnail_service import ThumbnailService

LOGGER = logging.getLogger("ppt_merge.worker")


class PptWorker(QObject):
    loaded = Signal(str, object)
    progress = Signal(str, object)
    failed = Signal(str, str)
    cancelled = Signal(str)
    finished = Signal()

    def __init__(self, sources: tuple[str, ...], service_factory: Callable[[], ThumbnailService]) -> None:
        super().__init__()
        self._sources = sources
        self._service_factory = service_factory
        self._cancel = threading.Event()

    def request_cancel(self) -> None:
        # 워커의 이벤트 루프가 COM 호출로 바빠도 GUI에서 즉시 취소 신호를 설정한다.
        # QObject·COM 상태를 만지지 않고 스레드 안전한 Event만 변경한다.
        self._cancel.set()

    @Slot()
    def run(self) -> None:
        try:
            try:
                service = self._service_factory()
            except Exception:
                LOGGER.exception("썸네일 서비스 준비 실패")
                for path in self._sources:
                    self.failed.emit(path, "미리보기 작업을 시작하지 못했습니다. 실행 로그를 확인하세요.")
                return
            for path in self._sources:
                if self._cancel.is_set():
                    self.cancelled.emit(path)
                    break
                try:
                    result = service.load(Path(path),
                                          progress=lambda event: self.progress.emit(path, event),
                                          cancel=self._cancel.is_set)
                    self.loaded.emit(path, result)
                except OperationCancelled:
                    self.cancelled.emit(path)
                    break
                except PowerPointError as error:
                    LOGGER.warning("소스 파일 읽기 실패 %s: %s", path, error)
                    self.failed.emit(path, str(error))
                except Exception:
                    LOGGER.exception("소스 파일 작업 중 예외 %s", path)
                    self.failed.emit(path, "파일을 불러오는 중 오류가 발생했습니다. 실행 로그를 확인하세요.")
        finally:
            self.finished.emit()


class GenerationWorker(QObject):
    """생성 준비와 실행을 각각 QThread에서 처리한다."""

    prepared = Signal(object)
    generated = Signal(object)
    progress = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    finished = Signal()

    def __init__(self, service_factory, slides=(), output=None, *, plan=None,
                 overwrite=False, allow_mixed_sizes=False) -> None:
        super().__init__()
        self._service_factory = service_factory
        self._slides, self._output, self._plan = tuple(slides), output, plan
        self._overwrite, self._allow_mixed_sizes = overwrite, allow_mixed_sizes
        self._cancel = threading.Event()

    def request_cancel(self) -> None:
        self._cancel.set()

    @Slot()
    def run(self) -> None:
        try:
            service = self._service_factory()
            if self._plan is None:
                result = service.prepare(self._slides, Path(self._output), overwrite=self._overwrite,
                                         progress=self.progress.emit, cancel=self._cancel.is_set)
                self.prepared.emit(result)
            else:
                result = service.generate(self._plan, allow_mixed_sizes=self._allow_mixed_sizes,
                                          progress=self.progress.emit, cancel=self._cancel.is_set)
                self.generated.emit(result)
        except OperationCancelled:
            self.cancelled.emit()
        except PowerPointError as error:
            LOGGER.warning("PPT 생성 실패: %s", error)
            self.failed.emit(str(error))
        except Exception:
            LOGGER.exception("PPT 생성 작업 중 예외")
            self.failed.emit("PPT 생성 작업 중 오류가 발생했습니다. 실행 로그를 확인하세요.")
        finally:
            self.finished.emit()
