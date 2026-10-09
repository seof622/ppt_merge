"""10~20개 원본·100~500장 실제 Office 부하 및 Windows 실패 상황 검증."""
import json
import os
from pathlib import Path
import shutil
import struct
import tempfile
import time
import unittest
from zipfile import ZipFile
import xml.etree.ElementTree as ET

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QModelIndex, QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from src.main import configure_application
from src.models.slide_model import SlideItem
from src.ppt.errors import GenerationError, PresentationOpenError, SourceChangedError
from src.ppt.powerpoint_service import PowerPointService
from src.ppt.presentation_manager import PresentationManager
from src.ppt.source_validation import fingerprint, revision, validate_source
from src.ppt.thumbnail_service import ThumbnailService
from src.ui.main_window import MainWindow
from src.utils.logger import configure_logging
from src.utils.process_utils import process_pids
from tests.integration import test_generation_com as helpers

ROOT = Path(__file__).resolve().parents[2]
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"


def selection(path, count=None):
    with ZipFile(path) as archive:
        ids = ET.fromstring(archive.read("ppt/presentation.xml")).find(P + "sldIdLst")
    stamp = revision(fingerprint(path))
    return tuple(SlideItem(str(path), path.name, i + 1, int(node.attrib["id"]), source_revision=stamp)
                 for i, node in enumerate(ids) if count is None or i < count)


def content_signatures(path):
    """모든 슬라이드의 본문·노트를 출력 순서대로 검사한다."""
    import posixpath
    a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    r = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    result = []
    with ZipFile(path) as archive:
        pres = ET.fromstring(archive.read("ppt/presentation.xml"))
        targets = {rel.attrib["Id"]: rel.attrib["Target"]
                   for rel in ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))}
        for node in pres.find(P + "sldIdLst"):
            part = posixpath.normpath(posixpath.join("ppt", targets[node.attrib[r + "id"]]))
            directory, name = posixpath.split(part)
            xml = ET.fromstring(archive.read(part))
            notes = []
            for rel in ET.fromstring(archive.read(f"{directory}/_rels/{name}.rels")):
                if rel.attrib["Type"].endswith("/notesSlide"):
                    note_part = posixpath.normpath(posixpath.join(directory, rel.attrib["Target"]))
                    note_xml = ET.fromstring(archive.read(note_part))
                    for shape in note_xml.findall(".//" + P + "sp"):
                        placeholder = shape.find(".//" + P + "ph")
                        if placeholder is not None and placeholder.attrib.get("type") == "body":
                            notes.extend(text.text for text in shape.iter(a + "t"))
            result.append({"text": [text.text for text in xml.iter(a + "t")], "notes": notes})
    return result


@unittest.skipUnless(os.environ.get("PPT_MERGE_RELIABILITY_COM_TESTS") == "1", "신뢰성 Office 검증 활성화 필요")
class ReliabilityComTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if process_pids("POWERPNT.EXE"):
            raise unittest.SkipTest("사용자 PowerPoint를 먼저 저장하고 닫아 주세요.")
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        configure_application(cls.app)
        configure_logging(ROOT / "logs")
        cls.directory = Path(tempfile.mkdtemp(prefix="reliability_validation_", dir=ROOT / "output"))
        cls.cleanups, cls.cases, cls.test_results = [], [], []
        cls.templates = {}
        service = PowerPointService(cls.backend)
        for count in (10, 25):
            for key in ("A", "B"):
                original = selection(ROOT / f"tests/fixtures/basic/{key}.pptx")
                path = cls.directory / f"{key}_{count}.pptx"
                slides = tuple(original[i % len(original)] for i in range(count))
                service.generate(service.prepare(slides, path))
                cls.templates[key, count] = path
        print("검증 자료:", cls.directory, flush=True)

    @classmethod
    def backend(cls):
        class RecordingManager(PresentationManager):
            def __exit__(self, *args):
                try:
                    super().__exit__(*args)
                finally:
                    cls.cleanups.append(dict(self.cleanup))
        return RecordingManager()

    @classmethod
    def tearDownClass(cls):
        report = {"directory": str(cls.directory), "cases": cls.cases, "sessions": cls.cleanups,
                  "live_powerpoint_pids": sorted(process_pids("POWERPNT.EXE")), "test_results": cls.test_results,
                  "dataset": "A/B 기본 자료를 반복한 합성 자료. 무거운 미디어 500장 부하는 포함하지 않음."}
        (cls.directory / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    def tearDown(self):
        result = self._outcome.result
        failed = any(test is self for test, _ in (*result.failures, *result.errors))
        self.test_results.append({"case": self._testMethodName, "passed": not failed})

    def assert_clean(self):
        self.assertFalse(process_pids("POWERPNT.EXE"))
        self.assertTrue(all(c["owned_process_exited"] and not c["errors"] for c in self.cleanups))
        self.assertFalse(list(self.directory.rglob(".ppt_merge-*")))

    def bulk(self, files, per_file):
        folder = self.directory / f"bulk_{files * per_file}"
        folder.mkdir()
        paths = []
        for i in range(files):
            path = folder / f"원본 {i + 1:02d}.pptx"
            shutil.copyfile(self.templates["AB"[i % 2], per_file], path)
            paths.append(path)
        cache = folder / "cache"
        window = MainWindow(cache, generation_service_factory=lambda: PowerPointService(self.backend),
                            service_factory=lambda: ThumbnailService(cache, backend_factory=self.backend))
        window.resize(1920, 1080)
        window.show()
        metrics = {"files": files, "slides": files * per_file}
        ticks = []
        timer = QTimer()
        timer.setInterval(20)
        timer.timeout.connect(lambda: ticks.append(time.perf_counter()))
        timer.start()
        def measure(name, operation):
            ticks.clear()
            start = time.perf_counter()
            operation()
            end = time.perf_counter()
            metrics[name + "_seconds"] = round(end - start, 3)
            samples = [start, *ticks, end]
            gap = max(b - a for a, b in zip(samples, samples[1:]))
            metrics[name + "_max_gui_gap_seconds"] = round(gap, 3)
            self.assertGreater(len(ticks), 0)
            self.assertLess(gap, 2, metrics)
            print(name, json.dumps(metrics, ensure_ascii=False), flush=True)
        def load():
            window.add_sources(paths)
            helpers.wait_until(lambda: not window.is_loading, timeout=600)
        try:
            measure("cold_load", load)
            self.assertEqual(len(window._sources), files)
            self.assertTrue(all(s.result for s in window._sources.values()), window.notice.text())
            results = [window._sources[os.path.normcase(str(p))].result for p in paths]
            self.assertEqual(sum(r.presentation.slide_count for r in results), files * per_file)
            chosen = [r.presentation.slides[n] for n in reversed(range(per_file)) for r in results]
            window.output_panel.add_slides(chosen)
            model = window.output_panel.model
            mime = model.mimeData([model.index(i, 0) for i in range(0, len(chosen), 3)])
            self.assertTrue(model.dropMimeData(mime, Qt.DropAction.MoveAction, len(chosen), 0, QModelIndex()))
            expected = window.output_panel.output_slides
            self.assertEqual(len(expected), files * per_file)
            # 순서 이동·전체 선택과 모든 썸네일의 지연 로딩, 아이콘 캐시 상한 확인.
            window.output_panel.view.selectAll()
            self.assertEqual(len(window.output_panel.view.selectionModel().selectedIndexes()), len(expected))
            for i in range(len(expected)):
                model.data(model.index(i, 0), Qt.ItemDataRole.DecorationRole)
            self.assertLessEqual(len(model._icons), 128)
            window.output_panel.view.scrollTo(model.index(len(expected) - 1, 0))
            QTest.qWait(100)
            window.grab().save(str(folder / "500_or_100_slides.png"))
            output = folder / "결과.pptx"
            def generate():
                self.assertTrue(window.start_generation(output))
                helpers.wait_until(lambda: not window.is_generating, timeout=600)
            measure("generation", generate)
            self.assertIsNotNone(window.last_generation_result, window.notice.text())
            self.assertEqual(window.last_generation_result.slide_count, len(expected))
            with self.backend() as manager:
                actual = manager.read_presentation(output)
            self.assertEqual([s.title for s in actual.slides], [s.title for s in expected])
            package = helpers.advanced_package_signatures(output)
            baseline = {str(p): helpers.advanced_package_signatures(p) for p in paths}
            content = content_signatures(output)
            baseline_content = {str(p): content_signatures(p) for p in paths}
            for i, item in enumerate(expected):
                self.assertEqual(package[i], baseline[item.source_file][item.slide_index - 1])
                self.assertEqual(content[i], baseline_content[item.source_file][item.slide_index - 1])
            renders = folder / "renders"
            renders.mkdir()
            with self.backend() as manager:
                for number in sorted({1, len(expected) // 4, len(expected) // 2, len(expected) * 3 // 4, len(expected)}):
                    rendered = renders / f"slide_{number}.png"
                    manager.export_slide(output, number, rendered, 480, 270)
                    self.assertTrue(helpers.compare_images(Path(expected[number - 1].thumbnail_path), rendered)["equal"])
                    source_doc = output_doc = source_slide = output_slide = None
                    try:
                        item = expected[number - 1]
                        source_doc = manager._open(Path(item.source_file))
                        output_doc = manager._open(output)
                        source_slide = source_doc.Slides.Item(item.slide_index)
                        output_slide = output_doc.Slides.Item(number)
                        source_signature = helpers.slide_signature(source_slide)
                        output_signature = helpers.slide_signature(output_slide)
                        for signature in (source_signature, output_signature):
                            signature.pop("name")
                        self.assertEqual(source_signature, output_signature)
                    finally:
                        source_doc = output_doc = source_slide = output_slide = None
            self.assert_clean()
            window.clear_sources()
            sessions_before = len(self.cleanups)
            measure("cache_load", load)
            self.assertTrue(all(s.result.cache_hit for s in window._sources.values()))
            self.assertEqual(len(self.cleanups), sessions_before)
            metrics["output_bytes"] = output.stat().st_size
            self.cases.append({"case": f"bulk_{len(expected)}", "passed": True, **metrics})
        finally:
            timer.stop()
            if window.is_busy:
                window.cancel_loading()
                helpers.wait_until(lambda: not window.is_busy, timeout=120)
            window.close()
            self.app.processEvents()
        self.assert_clean()

    def test_01_100_slides(self):
        self.bulk(10, 10)

    def test_02_500_slides(self):
        self.bulk(20, 25)

    def test_03_real_encrypted_and_damaged_sources_isolated(self):
        original = self.templates["A", 10]
        encrypted = self.directory / "암호 보호.pptx"
        with self.backend() as manager:
            doc = manager._open(original)
            try:
                doc.Password = "ppt-merge-reliability-fixture"
                doc.SaveAs(str(encrypted), 24)
                doc.Saved = True
            finally:
                doc = None
        self.assertEqual(encrypted.read_bytes()[:8], bytes.fromhex("D0CF11E0A1B11AE1"))
        truncated = self.directory / "잘린 파일.pptx"
        truncated.write_bytes(original.read_bytes()[:100])
        missing = self.directory / "슬라이드 누락.pptx"
        malformed = self.directory / "XML 손상.pptx"
        with ZipFile(original) as src:
            for path in (missing, malformed):
                with ZipFile(path, "w") as dst:
                    for info in src.infolist():
                        if path == missing and info.filename == "ppt/slides/slide1.xml":
                            continue
                        data = b"<p:broken" if path == malformed and info.filename == "ppt/slides/slide1.xml" else src.read(info)
                        dst.writestr(info.filename, data, compress_type=info.compress_type)
        crc = self.directory / "미디어 CRC 손상.pptx"
        shutil.copyfile(original, crc)
        with ZipFile(crc) as archive:
            media = next(info for info in archive.infolist() if info.filename.startswith("ppt/media/") and info.file_size > 0)
            offset = media.header_offset
        payload = bytearray(crc.read_bytes())
        name_size, extra_size = struct.unpack_from("<HH", payload, offset + 26)
        payload[offset + 30 + name_size + extra_size] ^= 1
        crc.write_bytes(payload)
        for path in (encrypted, truncated, missing, malformed, crc):
            with self.assertRaises(PresentationOpenError):
                validate_source(path)
        window = MainWindow(self.directory / "failure_cache",
                            service_factory=lambda: ThumbnailService(self.directory / "failure_cache", backend_factory=self.backend))
        window.show()
        try:
            window.add_sources([encrypted, truncated, missing, malformed, crc, original])
            helpers.wait_until(lambda: not window.is_loading, timeout=120)
            values = list(window._sources.values())
            self.assertTrue(all(s.result is None and s.error for s in values[:5]))
            self.assertIsNotNone(values[5].result)
            window.output_panel.add_slides(values[5].result.presentation.slides[:2])
            result = self.directory / "정상 원본만 생성.pptx"
            self.assertTrue(window.start_generation(result))
            helpers.wait_until(lambda: not window.is_generating)
            self.assertIsNotNone(window.last_generation_result)
        finally:
            window.close()
            self.app.processEvents()
        self.assert_clean()
        self.cases.append({"case": "encrypted_corrupt_isolation", "passed": True})

    def test_04_windows_locked_output_and_readonly_keep_existing(self):
        import win32con
        import win32file
        source = self.templates["A", 10]
        output = self.directory / "잠긴 결과.pptx"
        shutil.copyfile(source, output)
        before = output.read_bytes()
        slides = selection(source, 2)
        service = PowerPointService(self.backend)
        for locked in (source, output):
            handle = win32file.CreateFile(str(locked), win32con.GENERIC_READ, 0, None, win32con.OPEN_EXISTING, 0, None)
            try:
                with self.assertRaisesRegex((GenerationError, PresentationOpenError), "사용 중"):
                    service.prepare(selection(source, 2) if locked == output else slides, output, overwrite=True)
            finally:
                handle.Close()
        service = PowerPointService(self.backend)
        plan = service.prepare(selection(source, 2), output, overwrite=True)
        handle = None
        def progress(event):
            nonlocal handle
            if event.stage == "publishing":
                handle = win32file.CreateFile(str(output), win32con.GENERIC_READ, 0, None,
                                             win32con.OPEN_EXISTING, 0, None)
        try:
            with self.assertRaisesRegex(GenerationError, "사용 중"):
                service.generate(plan, progress=progress)
        finally:
            if handle is not None:
                handle.Close()
        self.assertEqual(output.read_bytes(), before)
        self.assert_clean()
        win32file.SetFileAttributes(str(output), win32con.FILE_ATTRIBUTE_READONLY)
        try:
            with self.assertRaisesRegex(GenerationError, "권한"):
                service.generate(service.prepare(selection(source, 2), output, overwrite=True))
        finally:
            win32file.SetFileAttributes(str(output), win32con.FILE_ATTRIBUTE_NORMAL)
        self.assertEqual(output.read_bytes(), before)
        self.assert_clean()
        self.cases.append({"case": "locked_readonly_output", "passed": True})

    def test_05_source_changed_or_removed_after_selection(self):
        source = self.directory / "변경 원본.pptx"
        shutil.copyfile(self.templates["A", 10], source)
        slides = selection(source, 2)
        service = PowerPointService(self.backend)
        output = self.directory / "원본 변경 결과.pptx"
        plan = service.prepare(slides, output)
        shutil.copyfile(self.templates["B", 10], source)
        with self.assertRaises(SourceChangedError):
            service.generate(plan)
        source.unlink()
        with self.assertRaises(SourceChangedError):
            service.generate(plan)
        self.assertFalse(output.exists())
        self.assert_clean()
        self.cases.append({"case": "changed_removed_source", "passed": True})
