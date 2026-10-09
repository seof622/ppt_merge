"""화면에 전달할 수 있는 PPT 작업 오류와 취소 신호."""

from collections.abc import Callable
import os

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


class GenerationError(PowerPointError):
    pass


class OperationCancelled(PowerPointError):
    pass


def check_cancel(cancel: CancelCallback | None) -> None:
    if cancel is not None and cancel():
        raise OperationCancelled("작업을 취소했습니다.")


def _is_shared_file(error: OSError) -> bool:
    if getattr(error, "winerror", None) in (32, 33):
        return True
    # Python 파일 스트림은 Windows 공유 오류도 errno=13으로 전달할 수 있다.
    # 읽기 전용 OPEN_EXISTING으로 현재 공유 상태만 확인하고 핸들을 즉시 닫는다.
    if os.name != "nt" or not isinstance(error, PermissionError) or not error.filename:
        return False
    try:
        import pywintypes
        import win32file
    except ImportError:
        return False
    try:
        handle = win32file.CreateFile(str(error.filename), 0x80000000, 7, None, 3, 0, None)
    except pywintypes.error as native_error:
        return native_error.winerror in (32, 33)
    else:
        handle.Close()
        return False


def file_error_message(error: OSError) -> str:
    if _is_shared_file(error):
        return "파일이 다른 프로그램에서 사용 중입니다. 해당 파일을 닫고 다시 시도하세요."
    if isinstance(error, PermissionError):
        return "파일을 읽거나 저장할 권한이 없습니다. 읽기 전용 상태와 폴더 권한을 확인하세요."
    return "파일을 읽거나 저장하지 못했습니다. 경로·권한과 로그를 확인하세요."
