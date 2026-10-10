"""한쇼 변환 PoC 전용 세션. 기존 사용자 인스턴스에는 연결하지 않는다."""

from __future__ import annotations

import gc
import logging
from pathlib import Path
import time
from typing import Any
import winreg

import pythoncom
import win32api
import win32com.client

from com_session import process_pids

LOGGER = logging.getLogger("ppt_merge.hanshow_poc")


def installed_environment() -> dict[str, Any]:
    """32/64비트 등록을 읽기만 한다. Office 설정은 수정하지 않는다."""
    with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"HShow.Application\CLSID") as key:
        clsid = winreg.QueryValueEx(key, None)[0]
    server = None
    for view in (winreg.KEY_WOW64_32KEY, winreg.KEY_WOW64_64KEY):
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"CLSID\{clsid}\LocalServer32",
                                0, winreg.KEY_READ | view) as key:
                server = winreg.QueryValueEx(key, None)[0]
                break
        except FileNotFoundError:
            continue
    if server is None:
        raise RuntimeError("한쇼 COM 실행 경로를 찾지 못했습니다.")
    executable = server.rsplit(" -Automation", 1)[0].strip('"')
    version = win32api.GetFileVersionInfo(executable, "\\")
    high, low = version["FileVersionMS"], version["FileVersionLS"]
    return {"progid": "HShow.Application", "clsid": clsid, "server": server,
            "file_version": f"{high >> 16}.{high & 65535}.{low >> 16}.{low & 65535}"}


class HanShowSession:
    """동일 스레드에서 생성·열기·저장·종료하는 실험용 COM 세션."""

    def __init__(self, *, allow_preexisting: bool = False) -> None:
        # 별도 인스턴스 식별 실험에서만 허용한다. 기본 검증은 기존 실행을 차단한다.
        self.allow_preexisting = allow_preexisting
        self.app: Any = None
        self.documents: list[Any] = []
        self.pid: int | None = None
        self.before: set[int] = set()
        self.cleanup: dict[str, Any] = {}

    def __enter__(self) -> HanShowSession:
        self.before = process_pids("HShow.exe")
        if self.before and not self.allow_preexisting:
            raise RuntimeError("안전한 검증을 위해 열려 있는 한쇼를 저장하고 닫아 주세요.")
        pythoncom.CoInitialize()
        try:
            self.app = win32com.client.DispatchEx("HShow.Application")
            created = process_pids("HShow.exe") - self.before
            if len(created) != 1:
                raise RuntimeError("앱 소유 한쇼 프로세스를 식별하지 못했습니다.")
            self.pid = created.pop()
            LOGGER.info("한쇼 시작 pid=%s", self.pid)
            return self
        except BaseException:
            self._close()
            raise

    def open(self, source: Path, *, read_only: bool = True, with_window: bool = False) -> Any:
        source = source.resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        # 실제 보호 파일은 후속 검증 대상이다. 암호 창을 띄우기 전에 차단한다.
        if self.app.IsExistReadPassword(str(source)):
            raise ValueError("암호 보호 파일은 이 PoC에서 열지 않습니다.")
        document = self.app.Presentations.Open(str(source), -1 if read_only else 0, 0,
                                               -1 if with_window else 0)
        if document is None:
            raise RuntimeError(f"한쇼 문서를 열지 못했습니다: {source.name}")
        self.documents.append(document)
        return document

    def close(self, document: Any) -> None:
        document.Close()
        self.documents.remove(document)

    def save_sample_show(self, document: Any, target: Path) -> None:
        if len(self.documents) != 1 or self.documents[0] is not document:
            raise RuntimeError("한쇼 시험 자료 저장은 문서가 하나인 세션에서만 가능합니다.")
        if target.exists() or target.suffix.lower() != ".show":
            raise ValueError("새 SHOW 샘플 경로를 지정하세요.")
        # 한쇼 자체 SaveAs는 확장자로 형식을 선택한다. 파일명 변경이 아니다.
        if not self.app.SaveAs(str(target.resolve())) or not target.is_file():
            raise RuntimeError("한쇼가 SHOW 시험 자료를 저장하지 못했습니다.")

    def save_pptx(self, document: Any, target: Path) -> None:
        if target.exists() or target.suffix.lower() != ".pptx":
            raise ValueError("새 PPTX 변환 경로를 지정하세요.")
        document.SaveAs(str(target.resolve()), self.app.ppSaveAsOpenXMLPresentation, 0)
        if not target.is_file():
            raise RuntimeError("한쇼가 PPTX 변환본을 저장하지 못했습니다.")

    def _close(self) -> None:
        errors = []
        document = None
        for document in reversed(self.documents):
            try:
                document.Close()
            except Exception as error:
                errors.append(repr(error))
        self.documents.clear()
        document = None
        if self.app is not None:
            if self.pid is None:
                errors.append("ownership_unknown")
            else:
                try:
                    self.app.Quit()
                except Exception as error:
                    errors.append(repr(error))
        self.app = None
        gc.collect()
        pythoncom.CoUninitialize()
        deadline = time.monotonic() + 8
        remaining = process_pids("HShow.exe")
        while self.pid in remaining and time.monotonic() < deadline:
            time.sleep(.1)
            remaining = process_pids("HShow.exe")
        self.cleanup = {"owned_pid": self.pid,
                        "owned_process_exited": self.pid is not None and self.pid not in remaining,
                        "preexisting_processes_preserved": self.before.issubset(remaining),
                        "errors": errors}
        LOGGER.info("한쇼 정리 %s", self.cleanup)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self._close()
        if exc_type is None and (self.cleanup["errors"] or not self.cleanup["owned_process_exited"]):
            raise RuntimeError("한쇼 정리 검증에 실패했습니다.")
