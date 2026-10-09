"""원본 검증, COM 결합, 안전한 결과 저장을 담당한다."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import hashlib
import logging
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Protocol
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from src.models.slide_model import SlideItem
from src.ppt.errors import (CancelCallback, GenerationError, PowerPointError,
                            SourceChangedError, check_cancel, file_error_message)
from src.ppt.presentation_manager import PresentationManager
from src.ppt.source_validation import file_hash, fingerprint, revision, validate_source

LOGGER = logging.getLogger("ppt_merge.generation")
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"


@dataclass(frozen=True)
class GenerationSource:
    path: str
    revision: str
    width_points: float
    height_points: float


@dataclass(frozen=True)
class GenerationPlan:
    slides: tuple[SlideItem, ...]
    sources: tuple[GenerationSource, ...]
    output_path: str
    output_revision: str | None
    overwrite: bool

    @property
    def mixed_sizes(self) -> bool:
        return len({(round(s.width_points, 3), round(s.height_points, 3)) for s in self.sources}) > 1


@dataclass(frozen=True)
class GenerationProgress:
    stage: str
    completed: int
    total: int
    source_file: str = ""


@dataclass(frozen=True)
class GenerationResult:
    output_path: str
    slide_count: int


ProgressCallback = Callable[[GenerationProgress], None]


class GenerationBackend(Protocol):
    def __enter__(self) -> GenerationBackend: ...
    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None: ...
    def compose(self, slides: tuple[SlideItem, ...], target: Path, width: float, height: float,
                progress: Callable[[str, int, str], None], cancel: CancelCallback | None) -> None: ...


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left)) == os.path.normcase(str(right)) or (
        left.exists() and right.exists() and left.samefile(right))


class PowerPointService:
    """호출한 작업 스레드 안에서만 COM을 사용한다."""

    def __init__(self, backend_factory: Callable[[], GenerationBackend] = PresentationManager,
                 work_root: Path | None = None) -> None:
        self._backend_factory = backend_factory
        self._work_root = work_root

    def prepare(self, slides: Iterable[SlideItem], output: Path, *, overwrite: bool = False,
                progress: ProgressCallback | None = None,
                cancel: CancelCallback | None = None) -> GenerationPlan:
        selection = tuple(slides)
        if not selection:
            raise GenerationError("출력 목록에 슬라이드를 먼저 담아 주세요.")
        path = output.resolve()
        if path.suffix.lower() != ".pptx" or not path.parent.is_dir() or path.is_dir():
            raise GenerationError("존재하는 폴더에 PPTX 저장 경로를 선택하세요.")
        if path.exists() and not overwrite:
            raise GenerationError("같은 이름의 파일이 있습니다. 다른 이름을 선택하거나 덮어쓰기를 확인하세요.")
        try:
            output_revision = revision(fingerprint(path, cancel)) if path.exists() else None
            groups: dict[Path, list[SlideItem]] = {}
            for slide in selection:
                source = Path(slide.source_file).resolve()
                if _same_path(source, path):
                    raise GenerationError("원본 PowerPoint 파일에는 저장할 수 없습니다. 다른 경로를 선택하세요.")
                groups.setdefault(source, []).append(slide)
            sources = []
            for completed, (source, items) in enumerate(groups.items(), 1):
                check_cancel(cancel)
                if progress:
                    progress(GenerationProgress("checking", completed - 1, len(groups), str(source)))
                validate_source(source, cancel)
                identity = revision(fingerprint(source, cancel))
                if any(item.source_revision is None or item.source_revision != identity for item in items):
                    raise SourceChangedError(
                        f"원본 확인 정보가 없거나 파일이 변경되었습니다: {source.name}\n"
                        "‘다시 읽기’ 후 기존 출력 항목을 삭제하고 슬라이드를 다시 담아 주세요.")
                with ZipFile(source) as archive:
                    xml = ET.fromstring(archive.read("ppt/presentation.xml"))
                size = xml.find(P + "sldSz")
                ids = xml.find(P + "sldIdLst")
                if size is None or ids is None:
                    raise GenerationError(f"슬라이드 정보를 읽지 못했습니다: {source.name}")
                width, height = int(size.attrib["cx"]) / 12700, int(size.attrib["cy"]) / 12700
                if not all(math.isfinite(v) and v > 0 for v in (width, height)):
                    raise GenerationError("슬라이드 크기가 올바르지 않습니다.")
                slide_ids = [int(element.attrib["id"]) for element in ids]
                for item in items:
                    if (type(item.slide_index) is not int or not 1 <= item.slide_index <= len(slide_ids)
                            or slide_ids[item.slide_index - 1] != item.slide_id):
                        raise SourceChangedError(f"슬라이드 번호 또는 ID가 달라졌습니다: {source.name}. 다시 읽고 담아 주세요.")
                if revision(fingerprint(source, cancel)) != identity:
                    raise SourceChangedError("확인 중 원본이 변경되었습니다. 다시 읽고 담아 주세요.")
                sources.append(GenerationSource(str(source), identity, width, height))
            return GenerationPlan(selection, tuple(sources), str(path), output_revision, overwrite)
        except PowerPointError:
            raise
        except OSError as error:
            LOGGER.exception("PPT 생성 준비 파일 접근 실패")
            raise GenerationError(file_error_message(error)) from error
        except Exception as error:
            LOGGER.exception("PPT 생성 준비 실패")
            raise GenerationError("원본이나 저장 경로를 확인하지 못했습니다. 경로·권한과 로그를 확인하세요.") from error

    def generate(self, plan: GenerationPlan, *, allow_mixed_sizes: bool = False,
                 progress: ProgressCallback | None = None,
                 cancel: CancelCallback | None = None) -> GenerationResult:
        def report(stage: str, count: int = 0, source: str = "") -> None:
            if progress:
                progress(GenerationProgress(stage, count, len(plan.slides), source))

        if plan.mixed_sizes and not allow_mixed_sizes:
            raise GenerationError("슬라이드 크기가 다릅니다. 첫 출력 슬라이드 크기 사용을 확인해야 합니다.")
        path = Path(plan.output_path)
        started = time.perf_counter()
        LOGGER.info("PPT 생성 시작 원본=%s 출력=%s장 경로=%s", len(plan.sources), len(plan.slides), path)
        try:
            check_cancel(cancel)
            self._check_sources(plan, cancel)
            self._check_output(plan, cancel)
            # Office가 OneDrive 경로를 클라우드 URL로 바꾸지 않도록 로컬 임시 폴더에 저장한다.
            with tempfile.TemporaryDirectory(prefix="ppt_merge-", dir=self._work_root) as folder:
                temporary = Path(folder) / "result.pptx"
                first = plan.sources[0]
                report("opening")
                with self._backend_factory() as backend:
                    backend.compose(plan.slides, temporary, first.width_points, first.height_points,
                                    lambda stage, count, source: report(stage, count, source), cancel)
                    report("saved", len(plan.slides))
                check_cancel(cancel)
                report("verifying", len(plan.slides))
                self._check_sources(plan, cancel)
                self._verify_result(temporary, len(plan.slides))
                self._check_output(plan, cancel)
                # 최종 교체는 출력과 같은 볼륨에서 수행하므로 다른 드라이브에도 안전하게 저장한다.
                with tempfile.TemporaryDirectory(prefix=".ppt_merge-", dir=path.parent) as publish_folder:
                    staged = Path(publish_folder) / "result.pptx"
                    report("publishing", len(plan.slides))
                    self._copy_result(temporary, staged, cancel)
                    self._check_sources(plan, cancel)
                    self._check_output(plan, cancel)
                    check_cancel(cancel)
                    if plan.output_revision is None:
                        # Windows rename는 뒤늦게 생긴 기존 파일을 덮어쓰지 않는다.
                        staged.rename(path)
                    else:
                        os.replace(staged, path)
            report("completed", len(plan.slides))
            LOGGER.info("PPT 생성 완료 %s %s장 %.3f초", path, len(plan.slides), time.perf_counter() - started)
            return GenerationResult(str(path), len(plan.slides))
        except PowerPointError as error:
            LOGGER.info("PPT 생성 중단 %s %.3f초: %s", type(error).__name__, time.perf_counter() - started, error)
            raise
        except OSError as error:
            LOGGER.exception("PPT 생성·저장 파일 접근 실패")
            raise GenerationError(file_error_message(error)) from error
        except Exception as error:
            LOGGER.exception("PPT 생성·저장 실패")
            raise GenerationError("PPT를 생성하거나 저장하지 못했습니다. 파일 사용 상태·권한과 로그를 확인하세요.") from error

    @staticmethod
    def _copy_result(source: Path, target: Path, cancel: CancelCallback | None) -> None:
        digest = hashlib.sha256()
        with source.open("rb") as original, target.open("xb") as output:
            while block := original.read(1024 * 1024):
                check_cancel(cancel)
                output.write(block)
                digest.update(block)
            output.flush()
            os.fsync(output.fileno())
        check_cancel(cancel)
        if file_hash(target, cancel) != digest.hexdigest():
            raise GenerationError("완성된 PPT를 저장 경로로 복사하는 중 오류가 발생했습니다.")

    def _check_sources(self, plan: GenerationPlan, cancel: CancelCallback | None) -> None:
        for source in plan.sources:
            check_cancel(cancel)
            path = Path(source.path)
            if not path.is_file() or revision(fingerprint(path, cancel)) != source.revision:
                raise SourceChangedError(f"원본이 없어졌거나 변경되었습니다: {path.name}. 다시 읽고 담아 주세요.")

    def _check_output(self, plan: GenerationPlan, cancel: CancelCallback | None) -> None:
        path = Path(plan.output_path)
        current = revision(fingerprint(path, cancel)) if path.exists() else None
        if current != plan.output_revision or (current is not None and not plan.overwrite):
            raise GenerationError("저장할 파일이 작업 중 변경되었습니다. 경로를 다시 선택해 주세요.")

    @staticmethod
    def _verify_result(path: Path, count: int) -> None:
        with ZipFile(path) as archive:
            xml = ET.fromstring(archive.read("ppt/presentation.xml"))
            slides = xml.find(P + "sldIdLst")
            if slides is None or len(slides) != count or archive.testzip() is not None:
                raise GenerationError("생성된 PPT의 슬라이드 수 또는 파일 무결성이 올바르지 않습니다.")
