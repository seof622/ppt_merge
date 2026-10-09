"""캐시 오판·부분 저장·원본 변경·취소를 COM 없이 검증한다."""

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from src.models.presentation_model import PresentationInfo
from src.models.slide_model import SlideItem
from src.ppt.errors import OperationCancelled, PresentationOpenError, SourceChangedError, ThumbnailError
from src.ppt.thumbnail_service import ThumbnailService
from tests.unit.test_generation_service import write_deck


@dataclass
class Recorder:
    started: int = 0
    closed: int = 0
    exported: list[int] = field(default_factory=list)
    fail_at: int | None = None
    size: tuple[float, float] = (960, 540)

    def backend(self):
        recorder = self

        class Backend:
            def __enter__(self):
                recorder.started += 1
                return self

            def __exit__(self, *args):
                recorder.closed += 1

            def read_presentation(self, path, cancel=None):
                slides = tuple(SlideItem(str(path), path.name, i, 255 + i, title=f"제목 {i}")
                               for i in range(1, 4))
                return PresentationInfo(str(path), path.name, *recorder.size, slides)

            def export_slide(self, path, index, target, width, height):
                if recorder.fail_at == index:
                    raise ThumbnailError("의도적 내보내기 오류")
                Image.new("RGB", (width, height), (index * 50, 20, 100)).save(target, "PNG")
                recorder.exported.append(index)

        return Backend()


class ThumbnailServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "한글 자료.pptx"
        self.cache = self.root / "cache"
        self.write_source("AAA")
        self.recorder = Recorder()
        self.service = ThumbnailService(self.cache, backend_factory=self.recorder.backend)

    def tearDown(self):
        self.temporary.cleanup()

    def write_source(self, marker):
        write_deck(self.source, marker=marker)

    def assert_no_partial(self):
        self.assertFalse(any(p.name.startswith((".staging-", ".retired-")) or p.suffix == ".lock"
                             for p in self.cache.iterdir()))

    def test_hit_does_not_start_backend_or_rewrite_images(self):
        result = self.service.load(self.source)
        image = Path(result.presentation.slides[0].thumbnail_path)
        timestamp = image.stat().st_mtime_ns
        hit = self.service.load(self.source)
        self.assertTrue(hit.cache_hit)
        self.assertEqual(hit.generated_slides, 0)
        self.assertEqual(self.recorder.started, 1)
        self.assertEqual(self.recorder.closed, 1)
        self.assertEqual(image.stat().st_mtime_ns, timestamp)
        self.assertEqual(hit.presentation, result.presentation)
        self.assert_no_partial()

    def test_content_change_with_same_size_and_mtime_invalidates(self):
        first = self.service.load(self.source)
        stat = self.source.stat()
        self.write_source("BBB")
        os.utime(self.source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertEqual(self.source.stat().st_size, stat.st_size)
        changed = self.service.load(self.source)
        self.assertFalse(changed.cache_hit)
        self.assertNotEqual(first.cache_directory, changed.cache_directory)
        self.assertEqual(changed.generated_slides, 3)

    def test_modified_time_alone_invalidates(self):
        first = self.service.load(self.source)
        stat = self.source.stat()
        os.utime(self.source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1000000000))
        self.assertNotEqual(first.cache_directory, self.service.load(self.source).cache_directory)

    def test_missing_and_corrupt_images_repair_only_affected_slides(self):
        result = self.service.load(self.source)
        Path(result.presentation.slides[0].thumbnail_path).unlink()
        Path(result.presentation.slides[2].thumbnail_path).write_bytes(b"broken PNG")
        self.recorder.exported.clear()
        repaired = self.service.load(self.source)
        self.assertEqual(self.recorder.exported, [1, 3])
        self.assertEqual(repaired.generated_slides, 2)
        self.assertTrue(self.service.load(self.source).cache_hit)
        self.assert_no_partial()

    def test_valid_png_replacement_is_detected_by_hash(self):
        result = self.service.load(self.source)
        Image.new("RGB", (480, 270), "black").save(result.presentation.slides[1].thumbnail_path)
        self.recorder.exported.clear()
        self.service.load(self.source)
        self.assertEqual(self.recorder.exported, [2])

    def test_corrupt_manifest_never_yields_empty_cache_hit(self):
        result = self.service.load(self.source)
        path = Path(result.cache_directory) / "manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["slides"] = []
        path.write_text(json.dumps(data), encoding="utf-8")
        regenerated = self.service.load(self.source)
        self.assertEqual(regenerated.presentation.slide_count, 3)
        self.assertEqual(regenerated.generated_slides, 3)

    def test_cancel_between_slides_closes_backend_and_publishes_nothing(self):
        def cancelled():
            return len(self.recorder.exported) == 1

        with self.assertRaises(OperationCancelled):
            self.service.load(self.source, cancel=cancelled)
        self.assertEqual(self.recorder.closed, 1)
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_export_failure_preserves_existing_cache(self):
        result = self.service.load(self.source)
        manifest = Path(result.cache_directory) / "manifest.json"
        before = manifest.read_bytes()
        Path(result.presentation.slides[1].thumbnail_path).unlink()
        self.recorder.fail_at = 2
        with self.assertRaises(ThumbnailError):
            self.service.load(self.source)
        self.assertEqual(manifest.read_bytes(), before)
        self.assertEqual(self.recorder.closed, 2)
        self.assert_no_partial()

    def test_source_change_during_export_publishes_nothing(self):
        def progress(event):
            if event.stage == "exporting" and event.completed == 1:
                self.write_source("BBB")

        with self.assertRaises(SourceChangedError):
            self.service.load(self.source, progress=progress)
        self.assertEqual(list(self.cache.iterdir()), [])
        self.assertEqual(self.recorder.closed, 1)

    def test_publish_failure_restores_previous_directory(self):
        result = self.service.load(self.source)
        manifest = Path(result.cache_directory) / "manifest.json"
        before = manifest.read_bytes()
        Path(result.presentation.slides[1].thumbnail_path).unlink()
        rename = Path.rename

        def fail_staging(path, target):
            if path.name.startswith(".staging-"):
                raise OSError("의도적 게시 오류")
            return rename(path, target)

        with patch.object(Path, "rename", fail_staging):
            with self.assertLogs("ppt_merge.thumbnails", level="ERROR"):
                with self.assertRaises(ThumbnailError):
                    self.service.load(self.source)
        self.assertEqual(manifest.read_bytes(), before)
        self.assert_no_partial()

    def test_transient_windows_publish_denial_retries_without_regenerating(self):
        rename = Path.rename
        attempts = 0
        def transient(path, target):
            nonlocal attempts
            if path.name.startswith(".staging-"):
                attempts += 1
                if attempts <= 2:
                    error = PermissionError("일시적 Windows 공유 오류")
                    error.winerror = 5
                    raise error
            return rename(path, target)
        with patch.object(Path, "rename", transient), patch("src.ppt.thumbnail_service.time.sleep"):
            result = self.service.load(self.source)
        self.assertEqual(attempts, 3)
        self.assertEqual(self.recorder.exported, [1, 2, 3])
        self.assertTrue(self.service.load(self.source).cache_hit)
        self.assert_no_partial()

    def test_persistent_windows_denial_has_bounded_retries_and_preserves_old_cache(self):
        result = self.service.load(self.source)
        manifest = Path(result.cache_directory) / "manifest.json"
        before = manifest.read_bytes()
        Path(result.presentation.slides[1].thumbnail_path).unlink()
        rename = Path.rename
        attempts = 0
        def denied(path, target):
            nonlocal attempts
            if path.name.startswith(".staging-"):
                attempts += 1
                error = PermissionError("지속적 Windows 권한 오류")
                error.winerror = 5
                raise error
            return rename(path, target)
        with patch.object(Path, "rename", denied), patch("src.ppt.thumbnail_service.time.sleep"):
            with self.assertLogs("ppt_merge.thumbnails", level="WARNING"):
                with self.assertRaisesRegex(ThumbnailError, "권한"):
                    self.service.load(self.source)
        self.assertEqual(attempts, 5)
        self.assertEqual(manifest.read_bytes(), before)
        self.assert_no_partial()

    def test_cancel_during_windows_publish_retry_restores_old_cache(self):
        result = self.service.load(self.source)
        manifest = Path(result.cache_directory) / "manifest.json"
        before = manifest.read_bytes()
        Path(result.presentation.slides[1].thumbnail_path).unlink()
        rename = Path.rename
        cancelled = False
        def denied(path, target):
            nonlocal cancelled
            if path.name.startswith(".staging-"):
                cancelled = True
                error = PermissionError("일시적 Windows 공유 오류")
                error.winerror = 32
                raise error
            return rename(path, target)
        with patch.object(Path, "rename", denied), patch("src.ppt.thumbnail_service.time.sleep"):
            with self.assertRaises(OperationCancelled):
                self.service.load(self.source, cancel=lambda: cancelled)
        self.assertEqual(manifest.read_bytes(), before)
        self.assert_no_partial()

    def test_failed_rollback_keeps_backup_for_recovery(self):
        result = self.service.load(self.source)
        before = (Path(result.cache_directory) / "manifest.json").read_bytes()
        Path(result.presentation.slides[1].thumbnail_path).unlink()
        rename = Path.rename

        def fail_publication_and_restore(path, target):
            if path.name.startswith(".staging-") or path.name == "previous":
                raise OSError("의도적 복원 오류")
            return rename(path, target)

        with patch.object(Path, "rename", fail_publication_and_restore):
            with self.assertLogs("ppt_merge.thumbnails", level="ERROR"):
                with self.assertRaisesRegex(ThumbnailError, "보관"):
                    self.service.load(self.source)
        backups = list(self.cache.glob(".retired-*/previous/manifest.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), before)
        self.assertFalse(list(self.cache.glob("*.lock")))

    def test_size_and_source_path_are_part_of_cache_identity(self):
        first = self.service.load(self.source)
        wide = ThumbnailService(self.cache, 640, self.recorder.backend).load(self.source)
        self.assertNotEqual(first.cache_directory, wide.cache_directory)
        second = self.root / "다른 자료.pptm"
        second.write_bytes(self.source.read_bytes())
        copied = self.service.load(second)
        self.assertNotEqual(first.cache_directory, copied.cache_directory)
        self.assertEqual(copied.presentation.source_file, str(second))

    def test_four_by_three_preserves_aspect_ratio(self):
        self.recorder.size = (720, 540)
        result = self.service.load(self.source)
        with Image.open(result.presentation.slides[0].thumbnail_path) as image:
            self.assertEqual(image.size, (480, 360))

    def test_cache_hit_works_with_backend_unavailable(self):
        self.service.load(self.source)

        def unavailable():
            raise AssertionError("캐시 적중 시 PowerPoint를 실행하면 안 됩니다.")

        cached = ThumbnailService(self.cache, backend_factory=unavailable).load(self.source)
        self.assertTrue(cached.cache_hit)

    def test_invalid_source_rejected_before_backend_start(self):
        self.source.write_bytes(b"not a pptx")
        with self.assertRaises(PresentationOpenError):
            self.service.load(self.source)
        self.source.write_bytes(bytes.fromhex("D0CF11E0A1B11AE1") + b"encrypted")
        with self.assertRaisesRegex(PresentationOpenError, "암호 보호"):
            self.service.load(self.source)
        self.assertEqual(self.recorder.started, 0)


if __name__ == "__main__":
    unittest.main()
