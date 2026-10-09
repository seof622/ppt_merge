"""앱 생성 서비스와 QThread UI의 실제 Office 보존·정리를 검증한다."""

from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from zipfile import ZipFile
import xml.etree.ElementTree as ET

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.main import configure_application
from src.models.slide_model import SlideItem
from src.ppt.errors import GenerationError, OperationCancelled, PowerPointBusyError
from src.ppt.powerpoint_service import PowerPointService
from src.ppt.presentation_manager import PresentationManager
from src.ppt.source_validation import fingerprint, revision
from src.ppt.thumbnail_service import ThumbnailService
from src.ui.main_window import MainWindow
from src.utils.logger import configure_logging
from src.utils.process_utils import process_pids

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/poc"))
from verify_slides import slide_signature, advanced_package_signatures, compare_images


def wait_until(predicate, timeout=120):
    if predicate():
        return
    loop = QEventLoop()
    timer = QTimer(loop)
    timer.setInterval(20)
    timer.timeout.connect(lambda: loop.quit() if predicate() else None)
    limit = QTimer(loop)
    limit.setSingleShot(True)
    limit.timeout.connect(loop.quit)
    timer.start()
    limit.start(timeout * 1000)
    loop.exec()
    if not predicate():
        raise AssertionError("실제 PPT 생성 작업 시간 초과")


@unittest.skipUnless(os.environ.get("PPT_MERGE_GENERATION_COM_TESTS") == "1", "PPT 생성 Office 검증 활성화 필요")
class GenerationComTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if process_pids("POWERPNT.EXE"):
            raise unittest.SkipTest("사용자 PowerPoint를 먼저 저장하고 닫아 주세요.")
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        configure_application(cls.app)
        configure_logging(ROOT / "logs")
        cls.directory = Path(tempfile.mkdtemp(prefix="generation_validation_", dir=ROOT / "output"))
        cls.cleanups, cls.cases = [], []
        cls.paths = {"A": ROOT / "tests/fixtures/basic/A.pptx", "B": ROOT / "tests/fixtures/basic/B.pptx",
                     "G": ROOT / "tests/fixtures/advanced/advanced.pptx",
                     "M": ROOT / "tests/fixtures/advanced/advanced_container.pptm",
                     "C": ROOT / "tests/fixtures/basic/C_4x3.pptx"}
        cls.baselines = {}

    @classmethod
    def tearDownClass(cls):
        report = {"directory": str(cls.directory), "cases": cls.cases, "sessions": cls.cleanups,
                  "live_powerpoint_pids": sorted(process_pids("POWERPNT.EXE")),
                  "manual_new_output_validation": "pending"}
        (cls.directory / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def backend(self):
        cleanups = self.cleanups

        class RecordingManager(PresentationManager):
            def __exit__(self, *args):
                try:
                    super().__exit__(*args)
                finally:
                    cleanups.append(dict(self.cleanup))

        return RecordingManager()

    def service(self):
        return PowerPointService(self.backend)

    def selection(self, pairs):
        items = []
        for key, number in pairs:
            path = self.paths[key]
            with ZipFile(path) as archive:
                xml = ET.fromstring(archive.read("ppt/presentation.xml"))
            ids = xml.find("{http://schemas.openxmlformats.org/presentationml/2006/main}sldIdLst")
            items.append(SlideItem(str(path), path.name, number, int(ids[number - 1].attrib["id"]),
                                   source_revision=revision(fingerprint(path))))
        return tuple(items)

    def inspect(self, path, name):
        folder = self.directory / "renders" / name
        folder.mkdir(parents=True, exist_ok=True)
        data = []
        with self.backend() as manager:
            presentation = slide = None
            try:
                presentation = manager._open(path)
                for number in range(1, int(presentation.Slides.Count) + 1):
                    slide = presentation.Slides.Item(number)
                    data.append(slide_signature(slide))
                    slide.Export(str(folder / f"slide_{number}.png"), "PNG", 1280, 720)
                    slide = None
            finally:
                slide = presentation = None
        return {"com": data, "package": advanced_package_signatures(path), "renders": folder}

    def compare(self, output, pairs, name):
        for key in dict.fromkeys(key for key, _ in pairs):
            if key not in self.baselines:
                self.baselines[key] = self.inspect(self.paths[key], key)
        actual = self.inspect(output, name)
        rows = []
        for index, (key, number) in enumerate(pairs):
            baseline = self.baselines[key]
            original, generated = baseline["com"][number - 1], actual["com"][index]
            original_part, generated_part = baseline["package"][number - 1], actual["package"][index]
            changed = [field for field in original if field not in ("name", "hyperlinks")
                       and original[field] != generated[field]]
            changed_parts = [field for field in original_part if field != "internal_link_target_indices"
                             and original_part[field] != generated_part[field]]
            targets = [next((i + 1 for i, pair in enumerate(pairs) if pair == (key, target)), None)
                       for target in original_part["internal_link_target_indices"]]
            image = compare_images(baseline["renders"] / f"slide_{number}.png",
                                   actual["renders"] / f"slide_{index + 1}.png")
            row = {"source": f"{key}-{number}", "changed_fields": changed,
                   "changed_package_fields": changed_parts, "render": image,
                   "links_correct": generated_part["internal_link_target_indices"] == targets}
            rows.append(row)
        self.cases.append({"case": name, "passed": all(not r["changed_fields"] and not r["changed_package_fields"]
                                                         and r["render"]["equal"] and r["links_correct"] for r in rows),
                           "output": str(output), "comparisons": rows})
        self.assertTrue(self.cases[-1]["passed"], rows)
        self.assert_clean()

    def assert_clean(self):
        self.assertFalse(process_pids("POWERPNT.EXE"))
        self.assertTrue(all(s["owned_process_exited"] and not s["errors"] for s in self.cleanups))
        self.assertFalse(list(self.directory.glob(".ppt_merge-*")))

    def test_01_basic_ui_generation(self):
        window = MainWindow(ROOT / "cache", generation_service_factory=self.service)
        window.resize(1920, 1080)
        window.show()
        try:
            window.add_sources([self.paths["A"], self.paths["B"]])
            wait_until(lambda: not window.is_loading)
            self.assertTrue(all(s.result is not None for s in window._sources.values()))
            data = {key: window._sources[os.path.normcase(str(self.paths[key]))].result.presentation.slides
                    for key in ("A", "B")}
            pairs = [("A", 2), ("B", 4), ("A", 1), ("A", 2)]
            window.output_panel.add_slides([data[key][number - 1] for key, number in pairs])
            QTest.qWait(50)
            window.grab().save(str(self.directory / "before_generation.png"))
            output = self.directory / "basic.pptx"
            ticks = []
            timer = QTimer()
            timer.setInterval(20)
            timer.timeout.connect(lambda: ticks.append(1))
            timer.start()
            self.assertTrue(window.start_generation(output))
            wait_until(lambda: not window.is_generating)
            timer.stop()
            self.assertIsNotNone(window.last_generation_result, window.notice.text())
            self.assertGreater(len(ticks), 0)
            self.assertEqual(window.last_generation_result.slide_count, 4)
            self.assertTrue(window.open_output_button.isVisible())
            self.assertIn(str(output), window.status_text.toolTip())
            self.assertEqual(window.output_panel.output_slides, [data[key][n - 1] for key, n in pairs])
            window.grab().save(str(self.directory / "generated.png"))
            window.resize(1000, 640)
            QTest.qWait(100)
            window.grab().save(str(self.directory / "compact.png"))
        finally:
            if window.is_busy:
                window.cancel_loading()
                wait_until(lambda: not window.is_busy)
            window.close()
            self.app.processEvents()
        self.compare(output, pairs, "basic")

    def test_02_advanced_reorder_and_duplicate(self):
        pairs = [("G", n) for n in (5, 1, 6, 2, 3, 4, 7, 8, 9, 1)]
        output = self.directory / "advanced.pptx"
        service = self.service()
        service.generate(service.prepare(self.selection(pairs), output))
        self.compare(output, pairs, "advanced")

    def test_03_pptm_and_cross_source_duplicate_links(self):
        pairs = [("G", 5), ("M", 6), ("G", 6), ("M", 5), ("G", 6), ("G", 1)]
        output = self.directory / "cross_source.pptx"
        service = self.service()
        service.generate(service.prepare(self.selection(pairs), output))
        self.compare(output, pairs, "cross_source")

    def test_04_missing_internal_link_target(self):
        output = self.directory / "missing_target.pptx"
        service = self.service()
        with self.assertRaisesRegex(GenerationError, "링크 대상"):
            service.generate(service.prepare(self.selection([("G", 5), ("G", 1)]), output))
        self.assertFalse(output.exists())
        self.assert_clean()
        self.cases.append({"case": "missing_link_target", "passed": True})

    def test_05_cancel_and_exception_keep_existing_result(self):
        service = self.service()
        items = self.selection([("A", 2), ("B", 4), ("A", 1)])
        for mode in ("cancel", "exception"):
            output = self.directory / f"{mode}.pptx"
            output.write_bytes(b"existing output")
            cancelled = False

            def progress(event):
                nonlocal cancelled
                if event.stage == "copying" and event.completed == 1:
                    if mode == "exception":
                        raise RuntimeError("intentional generation failure")
                    cancelled = True

            with self.assertRaises(OperationCancelled if mode == "cancel" else GenerationError):
                service.generate(service.prepare(items, output, overwrite=True), progress=progress,
                                 cancel=lambda: cancelled)
            self.assertEqual(output.read_bytes(), b"existing output")
            self.assert_clean()
            self.cases.append({"case": mode + "_cleanup", "passed": True})

    def test_06_mixed_size_confirmation(self):
        service = self.service()
        output = self.directory / "mixed_size.pptx"
        plan = service.prepare(self.selection([("A", 2), ("C", 1)]), output)
        self.assertTrue(plan.mixed_sizes)
        with self.assertRaises(GenerationError):
            service.generate(plan)
        service.generate(plan, allow_mixed_sizes=True)
        with self.backend() as manager:
            presentation = manager._open(output)
            try:
                self.assertEqual(int(presentation.Slides.Count), 2)
                self.assertAlmostEqual(float(presentation.PageSetup.SlideWidth), plan.sources[0].width_points)
                self.assertAlmostEqual(float(presentation.PageSetup.SlideHeight), plan.sources[0].height_points)
            finally:
                presentation = None
        self.assert_clean()
        self.cases.append({"case": "mixed_size_confirmation", "passed": True})

    def test_07_existing_powerpoint_session_protected(self):
        service = self.service()
        output = self.directory / "existing_session.pptx"
        plan = service.prepare(self.selection([("A", 2)]), output)
        with self.backend() as owner:
            presentation = owner._open(self.paths["A"])
            try:
                with self.assertRaises(PowerPointBusyError):
                    service.generate(plan)
                self.assertEqual(int(presentation.Slides.Count), 4)
            finally:
                presentation = None
        self.assertFalse(output.exists())
        self.assert_clean()
        self.cases.append({"case": "existing_session_protected", "passed": True})


    def test_08_close_during_real_generation(self):
        window = MainWindow(ROOT / "cache", generation_service_factory=self.service)
        window.show()
        output = self.directory / "close_during_generation.pptx"
        try:
            data = ThumbnailService(ROOT / "cache").load(self.paths["A"]).presentation.slides
            window.output_panel.add_slides([data[1]] * 40)
            timer = QTimer(window)
            timer.setInterval(20)

            def close_after_first_slide():
                if window.progress_bar.maximum() == 40 and window.progress_bar.value() > 0:
                    timer.stop()
                    window.close()
                    self.assertEqual(window.cancel_button.text(), "취소 중…")
                    self.assertIn("정리한 뒤 창을 닫", window.status_text.toolTip())

            timer.timeout.connect(close_after_first_slide)
            timer.start()
            window.start_generation(output)
            wait_until(lambda: not window.is_generating and not window.isVisible())
            self.assertTrue(window._closing)
            self.assertFalse(output.exists())
        finally:
            if window.is_busy:
                window.cancel_loading()
                wait_until(lambda: not window.is_busy)
            window.close()
            self.app.processEvents()
        self.assert_clean()
        self.cases.append({"case": "close_during_real_generation", "passed": True})

    def test_09_ten_sources_and_cleanup(self):
        folder = self.directory / "ten_sources"
        folder.mkdir()
        slides = []
        for i in range(10):
            path = folder / f"source_{i + 1}.pptx"
            path.write_bytes(self.paths["A"].read_bytes())
            slides.append(SlideItem(str(path), path.name, 2, 257,
                                    source_revision=revision(fingerprint(path))))
        output = self.directory / "ten_sources.pptx"
        service = self.service()
        result = service.generate(service.prepare(slides, output))
        self.assertEqual(result.slide_count, 10)
        self.assert_clean()
        self.cases.append({"case": "ten_sources", "passed": True, "output": str(output)})
