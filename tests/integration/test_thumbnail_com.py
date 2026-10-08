"""명시적으로 활성화한 경우에만 실제 설치된 PowerPoint에서 검증한다."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import pickle
import shutil
import tempfile
import threading
import unittest
from zipfile import ZipFile

from PIL import Image

from src.ppt.errors import OperationCancelled, PowerPointBusyError, PowerPointError, ThumbnailError
from src.ppt.presentation_manager import PresentationManager
from src.ppt.thumbnail_service import ThumbnailService
from src.utils.logger import configure_logging
from src.utils.process_utils import process_pids

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(os.environ.get("PPT_MERGE_COM_TESTS") == "1", "PowerPoint 통합 검증 활성화 필요")
class ThumbnailComTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if process_pids("POWERPNT.EXE"):
            raise unittest.SkipTest("사용자 PowerPoint를 먼저 저장하고 닫아 주세요.")
        configure_logging(ROOT / "logs")
        cls.workspace = Path(tempfile.mkdtemp(prefix="thumbnail_validation_", dir=ROOT / "output"))
        cls.cache = cls.workspace / "cache"
        cls.sessions = []
        cls.report = {"directory": str(cls.workspace), "cases": []}

    @classmethod
    def tearDownClass(cls):
        cls.report["live_powerpoint_pids"] = sorted(process_pids("POWERPNT.EXE"))
        cls.report["sessions"] = [session.cleanup for session in cls.sessions]
        (cls.workspace / "validation_report.json").write_text(
            json.dumps(cls.report, ensure_ascii=False, indent=2), encoding="utf-8")

    def backend(self):
        session = PresentationManager()
        self.sessions.append(session)
        return session

    def assert_clean(self):
        self.assertEqual(process_pids("POWERPNT.EXE"), set())
        for session in self.sessions:
            if session.cleanup:
                self.assertTrue(session.cleanup["owned_process_exited"])
                self.assertEqual(session.cleanup["errors"], [])

    def record(self, case, **details):
        self.report["cases"].append({"case": case, "passed": True, **details})

    def test_01_native_exports_and_cache_hit(self):
        service = ThumbnailService(self.cache, backend_factory=self.backend)
        results = []
        for relative, count, size in (("basic/A.pptx", 4, (480, 270)),
                                      ("basic/B.pptx", 4, (480, 270)),
                                      ("basic/C_4x3.pptx", 1, (480, 360)),
                                      ("advanced/advanced.pptx", 9, (480, 270)),
                                      ("advanced/advanced_container.pptm", 9, (480, 270))):
            path = ROOT / "tests/fixtures" / relative
            before = digest(path)
            result = service.load(path)
            self.assertEqual(result.generated_slides, count)
            self.assertEqual(result.presentation.slide_count, count)
            self.assertTrue(result.presentation.slides[0].title)
            timestamps = []
            for slide in result.presentation.slides:
                thumbnail = Path(slide.thumbnail_path)
                timestamps.append(thumbnail.stat().st_mtime_ns)
                with Image.open(thumbnail) as image:
                    self.assertEqual(image.size, size)
            session_count = len(self.sessions)
            hit = service.load(path)
            self.assertTrue(hit.cache_hit)
            self.assertEqual(len(self.sessions), session_count)
            self.assertEqual([Path(s.thumbnail_path).stat().st_mtime_ns for s in hit.presentation.slides], timestamps)
            self.assertEqual(digest(path), before)
            results.append(asdict(result))
        self.assert_clean()
        self.report["exports"] = results
        self.record("native_exports_and_cache_hit", compared_slides=27)

    def test_02_repair_missing_and_corrupt_png(self):
        service = ThumbnailService(self.cache, backend_factory=self.backend)
        path = ROOT / "tests/fixtures/advanced/advanced.pptx"
        result = service.load(path)
        originals = [digest(Path(slide.thumbnail_path)) for slide in result.presentation.slides]
        Path(result.presentation.slides[0].thumbnail_path).unlink()
        Path(result.presentation.slides[2].thumbnail_path).write_bytes(b"corrupt PNG")
        repaired = service.load(path)
        self.assertEqual(repaired.generated_slides, 2)
        self.assertEqual([digest(Path(s.thumbnail_path)) for s in repaired.presentation.slides], originals)
        self.assert_clean()
        self.record("repair_missing_and_corrupt_png", regenerated_slides=2)

    def test_03_cancel_releases_com(self):
        cancelled = threading.Event()
        cache = self.workspace / "cancel_cache"

        def progress(event):
            if event.stage == "exporting" and event.completed == 1:
                cancelled.set()

        with self.assertRaises(OperationCancelled):
            ThumbnailService(cache, backend_factory=self.backend).load(
                ROOT / "tests/fixtures/basic/A.pptx", progress, cancelled.is_set)
        self.assertEqual(list(cache.iterdir()), [])
        self.assert_clean()
        self.record("cancel_releases_com")

    def test_04_error_releases_com(self):
        sessions = self.sessions

        class FailedExporter(PresentationManager):
            def export_slide(self, path, index, target, width, height):
                if index == 2:
                    raise ThumbnailError("의도적 COM 작업 오류")
                super().export_slide(path, index, target, width, height)

        def factory():
            session = FailedExporter()
            sessions.append(session)
            return session

        cache = self.workspace / "error_cache"
        with self.assertRaises(ThumbnailError):
            ThumbnailService(cache, backend_factory=factory).load(ROOT / "tests/fixtures/basic/A.pptx")
        self.assertEqual(list(cache.iterdir()), [])
        self.assert_clean()
        self.record("error_releases_com")

    def test_05_existing_session_preserved_and_hit_available(self):
        path = ROOT / "tests/fixtures/basic/A.pptx"
        with self.backend() as owner:
            info = owner.read_presentation(path)
            existing = process_pids("POWERPNT.EXE")
            with self.assertRaises(PowerPointBusyError):
                ThumbnailService(self.workspace / "busy_cache", backend_factory=self.backend).load(path)
            hit = ThumbnailService(self.cache, backend_factory=self.backend).load(path)
            self.assertTrue(hit.cache_hit)
            self.assertEqual(owner.read_presentation(path), info)
            self.assertEqual(process_pids("POWERPNT.EXE"), existing)
        self.assert_clean()
        self.record("existing_session_preserved_and_hit_available")

    def test_06_actual_source_change_invalidates(self):
        source = self.workspace / "변경 확인.pptx"
        shutil.copyfile(ROOT / "tests/fixtures/basic/A.pptx", source)
        service = ThumbnailService(self.cache, backend_factory=self.backend)
        first = service.load(source)
        with ZipFile(source) as archive:
            parts = [(item, archive.read(item.filename)) for item in archive.infolist()]
        with ZipFile(source, "w") as archive:
            for item, data in parts:
                if item.filename == "ppt/slides/slide1.xml":
                    self.assertIn(b"A-1", data)
                    data = data.replace(b"A-1", b"N-1")
                archive.writestr(item, data)
        changed = service.load(source)
        self.assertFalse(changed.cache_hit)
        self.assertNotEqual(changed.cache_directory, first.cache_directory)
        self.assertIn("N-1", changed.presentation.slides[0].title)
        self.assertNotEqual(digest(Path(first.presentation.slides[0].thumbnail_path)),
                            digest(Path(changed.presentation.slides[0].thumbnail_path)))
        self.assert_clean()
        self.record("actual_source_change_invalidates")

    def test_07_worker_thread_and_plain_data(self):
        main_thread = threading.get_ident()
        threads = []

        def factory():
            threads.append(threading.get_ident())
            return self.backend()

        service = ThumbnailService(self.workspace / "worker_cache", backend_factory=factory)
        with ThreadPoolExecutor(max_workers=1) as worker:
            result = worker.submit(service.load, ROOT / "tests/fixtures/basic/A.pptx").result()
        self.assertEqual(len(threads), 1)
        self.assertNotEqual(threads[0], main_thread)
        self.assertEqual(pickle.loads(pickle.dumps(result)), result)
        self.assert_clean()
        self.record("worker_thread_and_plain_data")

    def test_08_cross_thread_com_access_rejected(self):
        with self.backend() as owner:
            with ThreadPoolExecutor(max_workers=1) as worker:
                with self.assertRaisesRegex(PowerPointError, "스레드"):
                    worker.submit(owner.read_presentation, ROOT / "tests/fixtures/basic/A.pptx").result()
        self.assert_clean()
        self.record("cross_thread_com_access_rejected")


if __name__ == "__main__":
    unittest.main()
