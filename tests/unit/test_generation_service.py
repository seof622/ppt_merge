"""생성 중 원본·출력 충돌, 취소, 실패 시 데이터 보존을 검증한다."""

from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile, ZipInfo

from src.models.slide_model import SlideItem
from src.ppt.errors import GenerationError, OperationCancelled, SourceChangedError, check_cancel
from src.ppt.powerpoint_service import PowerPointService
from src.ppt.source_validation import fingerprint, revision


def write_deck(path, ids=(256, 257, 258), size=(12192000, 6858000), marker=""):
    p = "http://schemas.openxmlformats.org/presentationml/2006/main"
    r = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    rel = "http://schemas.openxmlformats.org/package/2006/relationships"
    parts = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        "_rels/.rels": f'<Relationships xmlns="{rel}"><Relationship Id="root" Type="{r}/officeDocument" Target="ppt/presentation.xml"/></Relationships>',
        "ppt/presentation.xml": f'<p:presentation xmlns:p="{p}" xmlns:r="{r}">'
            + '<p:sldIdLst>' + ''.join(f'<p:sldId id="{id}" r:id="rId{i}"/>' for i, id in enumerate(ids, 1))
            + '</p:sldIdLst>' + f'<p:sldSz cx="{size[0]}" cy="{size[1]}"/><!--{marker}--></p:presentation>',
        "ppt/_rels/presentation.xml.rels": f'<Relationships xmlns="{rel}">'
            + ''.join(f'<Relationship Id="rId{i}" Type="{r}/slide" Target="slides/slide{i}.xml"/>'
                      for i in range(1, len(ids) + 1)) + '</Relationships>',
    }
    parts.update({f"ppt/slides/slide{i}.xml": f'<p:sld xmlns:p="{p}"/>' for i in range(1, len(ids) + 1)})
    with ZipFile(path, "w") as archive:
        for name, content in parts.items():
            archive.writestr(ZipInfo(name, (2020, 1, 1, 0, 0, 0)), content)


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.a, self.b, self.output = [self.root / n for n in ("한글 A.pptx", "B.pptm", "결과.pptx")]
        write_deck(self.a)
        write_deck(self.b)
        self.started = self.closed = 0
        self.copied = []
        self.saved_targets = []
        self.work = self.root / "local_work"
        self.work.mkdir()
        self.action = None
        self.service = PowerPointService(self.backend, work_root=self.work)
        self.selection = (self.item(self.a, 2), self.item(self.b, 3), self.item(self.a, 1), self.item(self.a, 2))

    def tearDown(self):
        self.temp.cleanup()

    def item(self, path, number):
        return SlideItem(str(path), path.name, number, 255 + number,
                         source_revision=revision(fingerprint(path)))

    def backend(self):
        owner = self

        class Backend:
            def __enter__(self):
                owner.started += 1
                return self

            def __exit__(self, *args):
                owner.closed += 1

            def compose(self, slides, target, width, height, progress, cancel):
                owner.saved_targets.append(target)
                for number, item in enumerate(slides, 1):
                    check_cancel(cancel)
                    owner.copied.append(item)
                    progress("copying", number, item.source_file)
                if owner.action:
                    owner.action()
                write_deck(target, ids=range(256, 256 + len(slides)))

        return Backend()

    def assert_no_partial(self):
        self.assertFalse(list(self.root.glob(".ppt_merge-*")))
        self.assertEqual(list(self.work.iterdir()), [])

    def test_exact_order_duplicates_and_result_after_cleanup(self):
        plan = self.service.prepare(self.selection, self.output)
        result = self.service.generate(plan)
        self.assertEqual(self.copied, list(self.selection))
        self.assertEqual(result.slide_count, 4)
        self.assertTrue(self.output.exists())
        self.assertEqual((self.started, self.closed), (1, 1))
        self.assert_no_partial()

    def test_source_same_size_and_mtime_changed_after_selection_refused_before_com(self):
        before = self.a.stat()
        write_deck(self.a, ids=(256, 259, 258))
        os.utime(self.a, ns=(before.st_atime_ns, before.st_mtime_ns))
        with self.assertRaises(SourceChangedError):
            self.service.prepare(self.selection, self.output)
        self.assertEqual(self.started, 0)

    def test_missing_source_and_missing_revision_refused(self):
        with self.assertRaises(SourceChangedError):
            self.service.prepare((replace(self.selection[0], source_revision=None),), self.output)
        self.a.unlink()
        with self.assertRaisesRegex(Exception, "찾을 수"):
            self.service.prepare(self.selection, self.output)
        self.assertEqual(self.started, 0)

    def test_invalid_slide_id_and_output_source_alias_refused(self):
        with self.assertRaises(SourceChangedError):
            self.service.prepare((replace(self.selection[0], slide_id=900),), self.output)
        with self.assertRaisesRegex(GenerationError, "원본"):
            self.service.prepare(self.selection, self.a, overwrite=True)
        self.assertEqual(self.started, 0)

    def test_changed_source_between_prepare_and_generate_refused(self):
        plan = self.service.prepare(self.selection, self.output)
        write_deck(self.b, marker="changed")
        with self.assertRaises(SourceChangedError):
            self.service.generate(plan)
        self.assertEqual(self.started, 0)
        self.assertFalse(self.output.exists())

    def test_changed_source_during_generate_never_published(self):
        plan = self.service.prepare(self.selection, self.output)
        self.action = lambda: write_deck(self.a, marker="changed")
        with self.assertRaises(SourceChangedError):
            self.service.generate(plan)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.closed, 1)
        self.assert_no_partial()

    def test_mixed_sizes_requires_explicit_confirmation(self):
        write_deck(self.b, size=(9144000, 6858000))
        selection = (self.item(self.a, 2), self.item(self.b, 3))
        plan = self.service.prepare(selection, self.output)
        self.assertTrue(plan.mixed_sizes)
        with self.assertRaises(GenerationError):
            self.service.generate(plan)
        self.assertEqual(self.started, 0)
        self.service.generate(plan, allow_mixed_sizes=True)
        self.assertTrue(self.output.exists())

    def test_cancellation_preserves_existing_output_and_closes_backend(self):
        self.output.write_bytes(b"existing")
        plan = self.service.prepare(self.selection, self.output, overwrite=True)
        cancelled = False

        def progress(event):
            nonlocal cancelled
            if event.stage == "copying" and event.completed == 1:
                cancelled = True

        with self.assertRaises(OperationCancelled):
            self.service.generate(plan, progress=progress, cancel=lambda: cancelled)
        self.assertEqual(self.output.read_bytes(), b"existing")
        self.assertEqual(self.closed, 1)
        self.assert_no_partial()

    def test_exception_preserves_existing_output_and_cleans_temporary(self):
        self.output.write_bytes(b"existing")
        plan = self.service.prepare(self.selection, self.output, overwrite=True)

        def fail():
            raise RuntimeError("PRIVATE HRESULT")

        self.action = fail
        with self.assertLogs("ppt_merge.generation", level="ERROR"):
            with self.assertRaises(GenerationError) as caught:
                self.service.generate(plan)
        self.assertNotIn("PRIVATE", str(caught.exception))
        self.assertEqual(self.output.read_bytes(), b"existing")
        self.assertEqual(self.closed, 1)
        self.assert_no_partial()

    def test_new_output_created_during_work_is_preserved(self):
        plan = self.service.prepare(self.selection, self.output)
        self.action = lambda: self.output.write_bytes(b"created by user")
        with self.assertRaises(GenerationError):
            self.service.generate(plan)
        self.assertEqual(self.output.read_bytes(), b"created by user")
        self.assert_no_partial()

    def test_existing_output_changed_during_work_is_preserved(self):
        self.output.write_bytes(b"existing")
        plan = self.service.prepare(self.selection, self.output, overwrite=True)
        self.action = lambda: self.output.write_bytes(b"edited by user")
        with self.assertRaises(GenerationError):
            self.service.generate(plan)
        self.assertEqual(self.output.read_bytes(), b"edited by user")
        self.assert_no_partial()

    def test_overwrite_only_when_authorized(self):
        self.output.write_bytes(b"existing")
        with self.assertRaises(GenerationError):
            self.service.prepare(self.selection, self.output)
        self.service.generate(self.service.prepare(self.selection, self.output, overwrite=True))
        self.assertNotEqual(self.output.read_bytes(), b"existing")
        self.assert_no_partial()


    def test_office_saves_outside_final_output_folder(self):
        folder = self.root / "OneDrive" / "바탕 화면"
        folder.mkdir(parents=True)
        output = folder / "생성 결과.pptx"
        self.service.generate(self.service.prepare(self.selection, output))
        self.assertTrue(output.is_file())
        self.assertTrue(all(self.work in target.parents for target in self.saved_targets))
        self.assertFalse(any(folder in target.parents for target in self.saved_targets))
        self.assertEqual(list(folder.iterdir()), [output])
        self.assert_no_partial()

    def test_partial_copy_failure_keeps_existing_output_and_cleans_both_stages(self):
        self.output.write_bytes(b"existing")
        plan = self.service.prepare(self.selection, self.output, overwrite=True)

        def fail_copy(source, target, cancel):
            target.write_bytes(b"partial copy")
            raise OSError("intentional copy failure")

        self.service._copy_result = fail_copy
        with self.assertLogs("ppt_merge.generation", level="ERROR"):
            with self.assertRaises(GenerationError):
                self.service.generate(plan)
        self.assertEqual(self.output.read_bytes(), b"existing")
        self.assert_no_partial()

    def test_cancel_before_publication_keeps_existing_output(self):
        self.output.write_bytes(b"existing")
        plan = self.service.prepare(self.selection, self.output, overwrite=True)
        cancelled = False

        def progress(event):
            nonlocal cancelled
            if event.stage == "publishing":
                cancelled = True

        with self.assertRaises(OperationCancelled):
            self.service.generate(plan, progress=progress, cancel=lambda: cancelled)
        self.assertEqual(self.output.read_bytes(), b"existing")
        self.assert_no_partial()
