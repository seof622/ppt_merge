"""화면에 전달할 수 있는 PPT 작업 오류와 취소 신호."""

from collections.abc import Callable

CancelCallback = Callable[[], bool]


class PowerPointError(RuntimeError):
    pass


class PowerPointBusyError(PowerPointError):
    pass


class PresentationOpenError(PowerPointError):
    pass


class ThumbnailError(PowerPointError):
    pass


class SourceChangedError(ThumbnailError):
    pass


class OperationCancelled(PowerPointError):
    pass


def check_cancel(cancel: CancelCallback | None) -> None:
    if cancel is not None and cancel():
        raise OperationCancelled("썸네일 작업을 취소했습니다.")
