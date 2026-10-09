"""OneDrive 경로 저장·덮어쓰기와 로컬 임시 저장을 실제 Office에서 검증한다."""

import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from uuid import uuid4
from zipfile import ZipFile

import test_generation_com as com_fixture
from src.ppt.powerpoint_service import PowerPointService
from src.ppt.presentation_manager import PresentationManager
from src.utils.process_utils import process_pids

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(os.environ.get("PPT_MERGE_ONEDRIVE_DIRECTORY"), "OneDrive 저장 검증 경로 지정 필요")
class OneDriveGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if process_pids("POWERPNT.EXE"):
            raise unittest.SkipTest("기존 사용자 PowerPoint가 열려 있습니다.")
        cls.destination = Path(os.environ["PPT_MERGE_ONEDRIVE_DIRECTORY"]).resolve()
        if not cls.destination.is_dir():
            raise unittest.SkipTest("OneDrive 검증 폴더가 없습니다.")
        cls.directory = Path(tempfile.mkdtemp(prefix="onedrive_validation_", dir=ROOT / "output"))
        cls.cases = []

    @classmethod
    def tearDownClass(cls):
        (cls.directory / "report.json").write_text(json.dumps(
            {"cases": cls.cases, "live_powerpoint_pids": sorted(process_pids("POWERPNT.EXE"))},
            ensure_ascii=False, indent=2), encoding="utf-8")

    def exercise(self, name, pairs, overwrite):
        filename = "ppt_merge_저장검증_" + uuid4().hex + ".pptx"
        target = self.destination / filename
        self.assertFalse(target.exists())
        fixture = com_fixture.GenerationComTests()
        fixture.paths = {"A": ROOT / "tests/fixtures/basic/A.pptx",
                         "B": ROOT / "tests/fixtures/basic/B.pptx",
                         "C": ROOT / "tests/fixtures/basic/C_4x3.pptx"}
        selection = fixture.selection(pairs)
        cleanups, work_targets = [], []

        class RecordingManager(PresentationManager):
            def compose(self, slides, path, *args):
                work_targets.append(path)
                return super().compose(slides, path, *args)

            def __exit__(self, *args):
                try:
                    super().__exit__(*args)
                finally:
                    cleanups.append(dict(self.cleanup))

        service = PowerPointService(RecordingManager)
        try:
            if overwrite:
                target.write_bytes(b"previous test output")
            result = service.generate(service.prepare(selection, target, overwrite=overwrite),
                                      allow_mixed_sizes=True)
            self.assertEqual(result.slide_count, len(pairs))
            self.assertTrue(target.is_file())
            self.assertTrue(work_targets)
            self.assertTrue(all(self.destination not in path.parents for path in work_targets))
            with ZipFile(target) as archive:
                self.assertIsNone(archive.testzip())
            self.assertTrue(all(c["owned_process_exited"] and not c["errors"] for c in cleanups))
            self.assertFalse(process_pids("POWERPNT.EXE"))
            copied = self.directory / (name + ".pptx")
            shutil.copyfile(target, copied)
            self.cases.append({"case": name, "passed": True, "requested_path": str(target),
                               "copied_result": str(copied), "office_work_paths": [str(p) for p in work_targets],
                               "cleanup": cleanups})
        finally:
            # UUID로 이번 테스트가 직접 만든 정확한 파일만 제거한다.
            if target.parent.resolve() == self.destination and target.name == filename:
                target.unlink(missing_ok=True)

    def test_new_result_in_onedrive_with_user_selection(self):
        self.exercise("user_selection", [("A", 1), ("A", 2), ("B", 2), ("C", 1), ("B", 3)], False)

    def test_overwrite_result_in_onedrive(self):
        self.exercise("overwrite", [("A", 2), ("B", 4), ("A", 1)], True)
