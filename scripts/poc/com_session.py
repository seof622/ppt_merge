"""PoC 전용 PowerPoint 세션. 사용자의 기존 인스턴스는 건드리지 않는다."""

from __future__ import annotations

import csv
import gc
import io
import logging
from pathlib import Path
import subprocess
import time
from typing import Any

import pythoncom
import win32com.client

ROOT = Path(__file__).resolve().parents[2]
LOGGER = logging.getLogger("ppt_merge.poc")


def configure_logging() -> None:
    (ROOT / "logs").mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(ROOT / "logs/poc.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def powerpoint_pids() -> set[int]:
    result = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq POWERPNT.EXE", "/FO", "CSV", "/NH"],
        capture_output=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    rows = csv.reader(io.StringIO(result.stdout.decode("mbcs", errors="replace")))
    return {int(row[1]) for row in rows if len(row) > 1 and row[0].upper() == "POWERPNT.EXE"}


class PowerPointSession:
    def __init__(self) -> None:
        self.app: Any = None
        self.presentations: list[Any] = []
        self.pid: int | None = None
        self.before: set[int] = set()
        self.cleanup: dict[str, Any] = {}

    def __enter__(self) -> "PowerPointSession":
        self.before = powerpoint_pids()
        if self.before:
            self.cleanup = {
                "owned_pid": None, "owned_process_exited": True,
                "preexisting_pids": sorted(self.before),
                "preexisting_processes_preserved": True, "errors": [],
            }
            raise RuntimeError("안전한 PoC 실행을 위해 열려 있는 PowerPoint를 먼저 닫아 주세요.")
        pythoncom.CoInitialize()
        try:
            self.app = win32com.client.DispatchEx("PowerPoint.Application")
            created_pids = powerpoint_pids() - self.before
            if len(created_pids) != 1:
                raise RuntimeError("앱 소유 PowerPoint 프로세스를 확실히 식별하지 못했습니다.")
            self.pid = created_pids.pop()
            self.app.DisplayAlerts = 1  # ppAlertsNone
            self.app.AutomationSecurity = 3  # msoAutomationSecurityForceDisable
            LOGGER.info("PowerPoint 시작 pid=%s version=%s", self.pid, self.app.Version)
            return self
        except BaseException:
            self._close()
            raise

    def open(self, path: Path) -> Any:
        path = path.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"PowerPoint 파일을 찾을 수 없습니다: {path}")
        presentation = self.app.Presentations.Open(str(path), True, False, False)
        self.presentations.append(presentation)
        LOGGER.info("소스 열기 %s", path)
        return presentation

    def new(self, with_window: bool = False) -> Any:
        presentation = self.app.Presentations.Add(with_window)
        self.presentations.append(presentation)
        return presentation

    def close_presentation(self, presentation: Any) -> None:
        presentation.Saved = True
        presentation.Close()
        self.presentations.remove(presentation)
        LOGGER.info("프레젠테이션 닫기")

    def _close(self) -> None:
        errors: list[str] = []
        for presentation in reversed(self.presentations):
            try:
                presentation.Saved = True
                presentation.Close()
                LOGGER.info("프레젠테이션 닫기")
            except Exception as error:
                LOGGER.exception("프레젠테이션 종료 실패")
                errors.append(str(error))
        self.presentations.clear()
        presentation = None
        if self.app is not None and self.pid is not None and self.pid not in self.before:
            try:
                self.app.Quit()
            except Exception as error:
                LOGGER.exception("PowerPoint 종료 실패")
                errors.append(str(error))
        self.app = None
        gc.collect()
        pythoncom.CoUninitialize()
        remaining = powerpoint_pids()
        deadline = time.monotonic() + 8
        while self.pid not in self.before and self.pid in remaining and time.monotonic() < deadline:
            time.sleep(0.2)
            remaining = powerpoint_pids()
        self.cleanup = {
            "owned_pid": self.pid,
            "owned_process_exited": self.pid is None or self.pid in self.before or self.pid not in remaining,
            "preexisting_pids": sorted(self.before),
            "preexisting_processes_preserved": self.before.issubset(remaining),
            "errors": errors,
        }
        LOGGER.info("COM 정리 결과 %s", self.cleanup)

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self._close()
