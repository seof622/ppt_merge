"""완성된 EXE에서 Qt·COM·캐시·생성·종료를 검증하는 개발용 진단."""
import json
from pathlib import Path
import platform
import sys
import time
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from PySide6.QtCore import QObject, QTimer
from src.utils.process_utils import process_pids


def start_package_check(app, window, directory: Path, sources: list[Path], data_root: Path) -> None:
    app.setQuitOnLastWindowClosed(False)
    window._package_check = _PackageCheck(app, window, directory, sources, data_root)


class _PackageCheck(QObject):
    def __init__(self, app, window, directory, sources, data_root):
        super().__init__(window)
        self.app, self.window = app, window
        self.directory = directory.resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.sources = [path.resolve() for path in sources]
        self.report = {
            "frozen": bool(getattr(sys, "frozen", False)),
            "executable": sys.executable, "architecture": platform.machine(),
            "python": sys.version, "data_root": str(data_root),
            "bundle_root": getattr(sys, "_MEIPASS", ""),
            "checks": [], "passed": False,
        }
        self.started = time.monotonic()
        self.phase = "starting"
        self.error = ""
        self.output = self.directory / "package_result.pptx"
        self.cancelled_output = self.directory / "cancelled_result.pptx"
        self.timer = QTimer(self)
        self.timer.setInterval(20)
        self.timer.timeout.connect(self.step)
        self.timer.start()

    def check(self, condition, message):
        if not condition:
            raise AssertionError(message)
        self.report["checks"].append(message)

    def step(self):
        try:
            self._step()
        except Exception as error:
            self.error = f"{type(error).__name__}: {error}"
            self.phase = "cleanup"
            self.window.close()

    def _step(self):
        window = self.window
        if self.phase == "cleanup":
            if not window.is_busy:
                self.finish()
            return
        if time.monotonic() - self.started > 180:
            raise TimeoutError("패키지 검증 시간 초과")
        if self.phase == "starting":
            self.check(self.report["frozen"], "실제 frozen EXE 실행")
            self.check(len(self.sources) == 2, "검증용 원본 2개")
            self.check(not process_pids("POWERPNT.EXE"), "기존 PowerPoint 세션 없음")
            self.check(not self.output.exists() and not self.cancelled_output.exists(), "검증 결과 경로가 비어 있음")
            window.add_sources(self.sources)
            self.phase = "loading"
        elif self.phase == "loading" and not window.is_loading:
            states = list(window._sources.values())
            self.check(len(states) == 2 and all(state.status == "ready" for state in states),
                       "Qt 워커에서 두 원본 썸네일 로드")
            self.check(all(state.result.presentation.slide_count >= 4 for state in states), "원본마다 4장 이상")
            self.report["source_counts"] = [state.result.presentation.slide_count for state in states]
            self.report["cache_hits"] = [state.result.cache_hit for state in states]
            self.report["cache_directories"] = [state.result.cache_directory for state in states]
            self.check(all(Path(state.result.cache_directory).is_relative_to(Path(self.report["data_root"]))
                           for state in states), "캐시를 사용자 데이터 폴더에 저장")
            self.check(not Path(self.report["data_root"]).is_relative_to(Path(self.report["bundle_root"])),
                       "사용자 데이터가 EXE 임시 압축 해제 경로 밖에 있음")
            a, b = [state.result.presentation.slides for state in states]
            self.slides = (a[1], b[3], a[0], a[1])
            window.output_panel.add_slides(self.slides)
            self.check(window.start_generation(self.output), "GUI에서 실제 PPT 생성 시작")
            self.phase = "generating"
        elif self.phase == "generating" and not window.is_generating:
            result = window.last_generation_result
            self.check(result is not None and result.slide_count == 4, "중복 포함 4장 생성 완료")
            with ZipFile(self.output) as archive:
                xml = ET.fromstring(archive.read("ppt/presentation.xml"))
            ids = xml.find("{http://schemas.openxmlformats.org/presentationml/2006/main}sldIdLst")
            self.check(len(ids) == 4, "생성 PPTX 패키지에서 4장 확인")
            self.check(tuple(window.output_panel.output_slides) == self.slides, "출력 순서 유지")
            self.check(window.open_file_button.isVisible() and window.open_output_button.isVisible(),
                       "저장 결과 열기 버튼 표시")
            self.check(not process_pids("POWERPNT.EXE"), "생성 후 PowerPoint 정상 종료")
            window.resize(1000, 640)
            self.phase = "capture"
        elif self.phase == "capture":
            self.check(window.grab().save(str(self.directory / "packaged_ui.png")), "EXE 화면 캡처")
            window.output_panel.model.clear()
            window.output_panel.add_slides([self.slides[0]] * 40)
            self.check(window.start_generation(self.cancelled_output), "종료 검증용 40장 생성 시작")
            self.phase = "cancelling"
        elif self.phase == "cancelling":
            if window.progress_bar.maximum() == 40 and window.progress_bar.value() > 0:
                window.close()
                self.check("취소 중" in window.cancel_button.text(), "창 닫기 시 취소 안내 유지")
                self.phase = "closing"
            elif not window.is_generating:
                raise AssertionError("취소 전에 생성이 종료됨")
        elif self.phase == "closing" and not window.is_busy and not window.isVisible():
            self.check(not self.cancelled_output.exists(), "취소된 결과 파일 없음")
            self.check(not process_pids("POWERPNT.EXE"), "취소 후 PowerPoint 정상 종료")
            self.finish()

    def finish(self):
        self.timer.stop()
        self.report["passed"] = not bool(self.error)
        self.report["error"] = self.error
        self.report["elapsed_seconds"] = round(time.monotonic() - self.started, 3)
        self.report["live_powerpoint_pids"] = sorted(process_pids("POWERPNT.EXE"))
        (self.directory / "report.json").write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2), encoding="utf-8")
        self.window.close()
        self.app.exit(1 if self.error else 0)
