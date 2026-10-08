"""한 작업 스레드에서만 사용하는 앱 소유 PowerPoint 세션."""

from __future__ import annotations

import gc
import logging
from pathlib import Path
import threading
import time
from typing import Any

from src.models.presentation_model import PresentationInfo
from src.models.slide_model import SlideItem
from src.ppt.errors import (CancelCallback, PowerPointBusyError, PowerPointError,
                            PresentationOpenError, ThumbnailError, check_cancel)
from src.utils.process_utils import process_pids

LOGGER = logging.getLogger("ppt_merge.powerpoint")


class PresentationManager:
    """COM 객체를 밖으로 노출하지 않고 읽기와 PNG 내보내기를 수행한다."""

    def __init__(self) -> None:
        self._app: Any = None
        self._documents: dict[Path, Any] = {}
        self._com: Any = None
        self._thread_id: int | None = None
        self._pid: int | None = None
        self.cleanup: dict[str, Any] = {}

    def __enter__(self) -> PresentationManager:
        if self._thread_id is not None:
            raise PowerPointError("이미 사용 중인 PowerPoint 작업입니다.")
        try:
            before = process_pids("POWERPNT.EXE")
        except Exception as error:
            LOGGER.exception("PowerPoint 실행 상태 확인 실패")
            raise PowerPointError("PowerPoint 실행 상태를 확인하지 못했습니다. 로그를 확인하세요.") from error
        if before:
            raise PowerPointBusyError("열어 둔 자료를 저장하고 PowerPoint를 닫은 뒤 다시 시도하세요.")
        try:
            import pythoncom
            import win32com.client
        except ImportError as error:
            raise PowerPointError("PowerPoint 작업에 필요한 pywin32가 설치되어 있지 않습니다.") from error
        pythoncom.CoInitialize()
        self._com = pythoncom
        self._thread_id = threading.get_ident()
        try:
            self._app = win32com.client.DispatchEx("PowerPoint.Application")
            created = process_pids("POWERPNT.EXE") - before
            if len(created) != 1:
                raise PowerPointError("앱 소유 PowerPoint를 식별하지 못했습니다.")
            self._pid = pid = created.pop()
            self._app.DisplayAlerts = 1
            self._app.AutomationSecurity = 3
            LOGGER.info("PowerPoint 작업 시작 pid=%s version=%s", pid, self._app.Version)
            return self
        except BaseException as error:
            LOGGER.exception("PowerPoint 시작 실패")
            self._close()
            if not isinstance(error, Exception):
                raise
            raise PowerPointError("Microsoft PowerPoint를 시작하지 못했습니다. 설치 상태와 로그를 확인하세요.") from error

    def _assert_thread(self) -> None:
        if self._thread_id != threading.get_ident():
            raise PowerPointError("PowerPoint 작업은 세션을 시작한 스레드에서 실행해야 합니다.")

    def _open(self, path: Path) -> Any:
        self._assert_thread()
        path = path.resolve()
        if path not in self._documents:
            try:
                self._documents[path] = self._app.Presentations.Open(str(path), True, False, False)
                LOGGER.info("읽기 전용 프레젠테이션 열기 %s", path)
            except Exception as error:
                LOGGER.exception("프레젠테이션 열기 실패 %s", path)
                raise PresentationOpenError(
                    "PowerPoint 파일을 열지 못했습니다. 파일 손상·암호 보호 여부와 로그를 확인하세요."
                ) from error
        return self._documents[path]

    def read_presentation(self, path: Path, cancel: CancelCallback | None = None) -> PresentationInfo:
        presentation = slide = shape = None
        try:
            presentation = self._open(path)
            items = []
            for index in range(1, int(presentation.Slides.Count) + 1):
                check_cancel(cancel)
                slide = presentation.Slides.Item(index)
                title = None
                if slide.Shapes.HasTitle:
                    shape = slide.Shapes.Title
                    title = str(shape.TextFrame.TextRange.Text).strip() or None
                else:
                    for shape in slide.Shapes:
                        if shape.HasTextFrame and shape.TextFrame.HasText:
                            value = str(shape.TextFrame.TextRange.Text).strip()
                            if value:
                                title = value.splitlines()[0]
                                break
                items.append(SlideItem(str(path), path.name, index, int(slide.SlideID), title=title))
                shape = slide = None
            return PresentationInfo(str(path), path.name, float(presentation.PageSetup.SlideWidth),
                                    float(presentation.PageSetup.SlideHeight), tuple(items))
        except PowerPointError:
            raise
        except Exception as error:
            LOGGER.exception("슬라이드 정보 읽기 실패 %s", path)
            raise PresentationOpenError("슬라이드 정보를 읽지 못했습니다. 로그를 확인하세요.") from error
        finally:
            presentation = slide = shape = None

    def export_slide(self, path: Path, index: int, target: Path, width: int, height: int) -> None:
        presentation = slide = None
        try:
            presentation = self._open(path)
            slide = presentation.Slides.Item(index)
            slide.Export(str(target), "PNG", width, height)
            LOGGER.info("썸네일 내보내기 %s #%s %sx%s", path.name, index, width, height)
        except Exception as error:
            LOGGER.exception("썸네일 내보내기 실패 %s #%s", path, index)
            raise ThumbnailError("슬라이드 미리보기를 만들지 못했습니다. 로그를 확인하세요.") from error
        finally:
            presentation = slide = None

    def _close(self) -> None:
        self._assert_thread()
        errors = []
        presentation = None
        for presentation in reversed(list(self._documents.values())):
            try:
                presentation.Saved = True
                presentation.Close()
            except Exception:
                LOGGER.exception("프레젠테이션 닫기 실패")
                errors.append("document_close")
        self._documents.clear()
        presentation = None
        unidentified = self._app is not None and self._pid is None
        if unidentified:
            errors.append("ownership_unknown")
        if self._app is not None and self._pid is not None:
            try:
                self._app.Quit()
            except Exception:
                LOGGER.exception("앱 소유 PowerPoint 종료 실패")
                errors.append("application_quit")
        self._app = None
        gc.collect()
        self._com.CoUninitialize()
        self._com = None
        self._thread_id = None
        exited = self._pid is None and not unidentified
        if self._pid is not None:
            deadline = time.monotonic() + 8
            try:
                while self._pid in process_pids("POWERPNT.EXE") and time.monotonic() < deadline:
                    time.sleep(0.2)
                exited = self._pid not in process_pids("POWERPNT.EXE")
            except Exception:
                LOGGER.exception("PowerPoint 종료 상태 확인 실패")
                errors.append("process_check")
        self.cleanup = {"owned_pid": self._pid, "owned_process_exited": exited, "errors": errors}
        self._pid = None
        LOGGER.info("PowerPoint 작업 정리 %s", self.cleanup)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self._close()
        if exc_type is None and (self.cleanup["errors"] or not self.cleanup["owned_process_exited"]):
            raise PowerPointError("PowerPoint 작업 정리를 완료하지 못했습니다. 로그를 확인하세요.")
