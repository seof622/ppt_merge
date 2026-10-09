"""PowerPoint PNG 내보내기, 원본 변경 감지 및 취소 가능한 썸네일 캐시."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
import hashlib
import json
import logging
import math
import os
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any, Protocol

from PIL import Image

from src.models.presentation_model import PresentationInfo
from src.models.slide_model import SlideItem
from src.ppt.errors import (CancelCallback, OperationCancelled, PresentationOpenError,
                            SourceChangedError, ThumbnailError, check_cancel, file_error_message)
from src.ppt.source_validation import (file_hash as _file_hash, fingerprint as _fingerprint,
                                       validate_source as _validate_source, revision)
from src.ppt.presentation_manager import PresentationManager

LOGGER = logging.getLogger("ppt_merge.thumbnails")
CACHE_VERSION = 1


class ThumbnailBackend(Protocol):
    def __enter__(self) -> ThumbnailBackend: ...
    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None: ...
    def read_presentation(self, path: Path, cancel: CancelCallback | None = None) -> PresentationInfo: ...
    def export_slide(self, path: Path, index: int, target: Path, width: int, height: int) -> None: ...


@dataclass(frozen=True)
class ThumbnailProgress:
    source_file: str
    stage: str
    completed: int
    total: int


@dataclass(frozen=True)
class ThumbnailResult:
    presentation: PresentationInfo
    cache_directory: str
    cache_hit: bool
    generated_slides: int


ProgressCallback = Callable[[ThumbnailProgress], None]


def _dimensions(info: PresentationInfo, width: int) -> tuple[int, int]:
    if not (math.isfinite(info.width_points) and math.isfinite(info.height_points)
            and info.width_points > 0 and info.height_points > 0):
        raise ThumbnailError("슬라이드 크기를 읽지 못했습니다.")
    return width, max(1, round(width * info.height_points / info.width_points))


def _valid_image(path: Path, width: int, height: int, digest: str | None = None) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    try:
        with Image.open(path) as image:
            if image.format != "PNG" or image.size != (width, height):
                return False
            image.verify()
        return digest is None or _file_hash(path) == digest
    except (OSError, SyntaxError, ValueError):
        return False


def _manifest_hash(manifest: dict[str, Any]) -> str:
    payload = {key: value for key, value in manifest.items() if key != "metadata_sha256"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def _rename_cache(source: Path, target: Path, cancel: CancelCallback | None = None) -> None:
    """Windows의 일시적인 공유·접근 거부만 최대 0.75초 재시도한다."""
    delays = (0.05, 0.1, 0.2, 0.4)
    for attempt in range(len(delays) + 1):
        check_cancel(cancel)
        try:
            source.rename(target)
            return
        except OSError as error:
            if getattr(error, "winerror", None) not in (5, 32, 33) or attempt == len(delays):
                raise
            LOGGER.warning("캐시 폴더 교체 재시도 %s/%s winerror=%s",
                           attempt + 1, len(delays), error.winerror)
            time.sleep(delays[attempt])


class ThumbnailService:
    """호출 스레드에서 동작한다. UI는 추후 워커에서 호출하고 데이터만 받는다."""

    def __init__(self, cache_root: Path, width: int = 480,
                 backend_factory: Callable[[], ThumbnailBackend] = PresentationManager) -> None:
        if type(width) is not int or not 64 <= width <= 4096:
            raise ValueError("썸네일 너비는 64~4096 픽셀의 정수여야 합니다.")
        self.cache_root = cache_root.resolve()
        self.width = width
        self._backend_factory = backend_factory

    def _read_cache(self, directory: Path, identity: dict[str, Any], path: Path,
                    cancel: CancelCallback | None) -> tuple[PresentationInfo | None, set[int]]:
        if directory.is_symlink():
            raise ThumbnailError("캐시 폴더의 심볼릭 링크는 사용할 수 없습니다.")
        try:
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            if not isinstance(manifest, dict) or manifest.get("metadata_sha256") != _manifest_hash(manifest):
                return None, set()
            if manifest["identity"] != identity:
                return None, set()
            records = manifest["slides"]
            if not isinstance(records, list):
                return None, set()
            items = []
            for index, record in enumerate(records, 1):
                if (record["index"] != index or type(record["id"]) is not int
                        or record["id"] <= 0 or not isinstance(record["image_sha256"], str)
                        or (record["title"] is not None and not isinstance(record["title"], str))):
                    return None, set()
                items.append(SlideItem(str(path), path.name, index, record["id"],
                                       str(directory / f"slide_{index}.png"), record["title"],
                                       revision(identity["source"])))
            info = PresentationInfo(str(path), path.name, float(manifest["width_points"]),
                                    float(manifest["height_points"]), tuple(items))
            width, height = _dimensions(info, self.width)
            valid = set()
            for index, record in enumerate(records, 1):
                check_cancel(cancel)
                if _valid_image(directory / f"slide_{index}.png", width, height, record["image_sha256"]):
                    valid.add(index)
            return info, valid
        except (OSError, ValueError, KeyError, TypeError, ThumbnailError):
            LOGGER.info("캐시 메타데이터 없음 또는 무효 %s", directory.name)
            return None, set()

    def load(self, source: Path, progress: ProgressCallback | None = None,
             cancel: CancelCallback | None = None) -> ThumbnailResult:
        path = source.resolve()
        check_cancel(cancel)
        try:
            return self._load(path, progress, cancel)
        except (OperationCancelled, ThumbnailError, PresentationOpenError):
            raise
        except OSError as error:
            LOGGER.exception("썸네일 파일 작업 실패 %s", path)
            raise ThumbnailError(file_error_message(error)) from error

    def _load(self, path: Path, progress: ProgressCallback | None,
              cancel: CancelCallback | None) -> ThumbnailResult:
        def report(stage: str, completed: int, total: int) -> None:
            if progress:
                progress(ThumbnailProgress(str(path), stage, completed, total))

        _validate_source(path, cancel)
        report("checking", 0, 0)
        identity = {"version": CACHE_VERSION, "source": _fingerprint(path, cancel), "width": self.width}
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()
        directory = self.cache_root / key
        cached, valid = self._read_cache(directory, identity, path, cancel)
        if cached is not None and len(valid) == cached.slide_count:
            check_cancel(cancel)
            if _fingerprint(path, cancel) != identity["source"]:
                raise SourceChangedError("캐시 확인 중 PPT 파일이 변경되었습니다. 다시 시도하세요.")
            report("cached", cached.slide_count, cached.slide_count)
            LOGGER.info("썸네일 캐시 재사용 %s %s장", path, cached.slide_count)
            return ThumbnailResult(cached, str(directory), True, 0)

        self.cache_root.mkdir(parents=True, exist_ok=True)
        lock = self.cache_root / f".{key}.lock"
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as error:
            raise ThumbnailError("이 PPT의 썸네일을 이미 생성 중입니다. 작업이 끝난 뒤 다시 시도하세요.") from error
        os.close(descriptor)
        try:
            with tempfile.TemporaryDirectory(prefix=".staging-", dir=self.cache_root) as temporary:
                staging = Path(temporary)
                report("loading", 0, 0)
                generated = 0
                with self._backend_factory() as backend:
                    info = backend.read_presentation(path, cancel)
                    # 같은 원본의 손상 이미지 복구라도 메타데이터가 달라졌으면 모두 재생성한다.
                    if cached is None or replace(cached, slides=tuple(replace(s, thumbnail_path=None, source_revision=None)
                                                                        for s in cached.slides)) != info:
                        valid = set()
                    width, height = _dimensions(info, self.width)
                    for slide in info.slides:
                        check_cancel(cancel)
                        target = staging / f"slide_{slide.slide_index}.png"
                        if slide.slide_index in valid:
                            shutil.copyfile(directory / target.name, target)
                        else:
                            backend.export_slide(path, slide.slide_index, target, width, height)
                            generated += 1
                        if not _valid_image(target, width, height):
                            raise ThumbnailError("생성된 슬라이드 미리보기 이미지가 올바르지 않습니다.")
                        report("exporting", slide.slide_index, info.slide_count)
                check_cancel(cancel)
                if _fingerprint(path, cancel) != identity["source"]:
                    raise SourceChangedError("작업 중 PPT 파일이 변경되었습니다. 저장을 마친 뒤 다시 시도하세요.")
                records = [{"index": slide.slide_index, "id": slide.slide_id, "title": slide.title,
                            "image_sha256": _file_hash(staging / f"slide_{slide.slide_index}.png")}
                           for slide in info.slides]
                manifest = {"identity": identity, "width_points": info.width_points,
                            "height_points": info.height_points, "slides": records}
                manifest["metadata_sha256"] = _manifest_hash(manifest)
                (staging / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                                      encoding="utf-8")
                check_cancel(cancel)
                self._publish(staging, directory, cancel)
                result_info = replace(info, slides=tuple(replace(slide, thumbnail_path=str(
                    directory / f"slide_{slide.slide_index}.png"),
                    source_revision=revision(identity["source"])) for slide in info.slides))
                report("completed", info.slide_count, info.slide_count)
                LOGGER.info("썸네일 캐시 저장 %s 생성=%s 재사용=%s", path, generated, info.slide_count - generated)
                return ThumbnailResult(result_info, str(directory), False, generated)
        finally:
            lock.unlink(missing_ok=True)

    def _publish(self, staging: Path, directory: Path, cancel: CancelCallback | None = None) -> None:
        """기존 캐시는 새 이미지·메타데이터가 모두 완성된 뒤 교체한다."""
        if not directory.exists():
            _rename_cache(staging, directory, cancel)
            return
        if directory.is_symlink() or not directory.is_dir():
            raise ThumbnailError("캐시 저장 위치가 올바른 폴더가 아닙니다.")
        retired = Path(tempfile.mkdtemp(prefix=".retired-", dir=self.cache_root))
        backup = retired / "previous"
        removable = True
        try:
            _rename_cache(directory, backup, cancel)
            try:
                _rename_cache(staging, directory, cancel)
            except BaseException:
                try:
                    _rename_cache(backup, directory)
                except OSError as error:
                    removable = False
                    LOGGER.exception("기존 캐시 복원 실패. 복구 자료 보관 %s", backup)
                    raise ThumbnailError(f"캐시 교체에 실패했습니다. 기존 자료는 {backup}에 보관했습니다.") from error
                raise
        finally:
            if removable:
                shutil.rmtree(retired)
