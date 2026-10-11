"""원본에서 삭제한 자리 표시자가 레이아웃 적용 후 다시 생기지 않는지 검증한다."""
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageChops

from src.ppt.presentation_manager import PresentationManager
from src.ppt.powerpoint_service import PowerPointService
from src.ppt.source_validation import fingerprint, revision
from src.utils.process_utils import process_pids

ROOT = Path(__file__).resolve().parents[2]


def shapes_signature(slide):
    return [{"name": str(shape.Name), "type": int(shape.Type),
             "bounds": [round(float(value), 3) for value in
                        (shape.Left, shape.Top, shape.Width, shape.Height)],
             "text": str(shape.TextFrame.TextRange.Text) if shape.HasTextFrame else None,
             "placeholder": int(shape.PlaceholderFormat.Type) if int(shape.Type) == 14 else None}
            for shape in slide.Shapes]


@unittest.skipUnless(os.environ.get("PPT_MERGE_GENERATION_COM_TESTS") == "1", "Office 검증 활성화 필요")
class LayoutComTests(unittest.TestCase):
    def test_deleted_placeholders_stay_deleted_and_original_placeholders_survive(self):
        if process_pids("POWERPNT.EXE"):
            self.skipTest("사용자 PowerPoint를 먼저 저장하고 닫아 주세요.")
        folder = Path(tempfile.mkdtemp(prefix="layout_validation_", dir=ROOT / "output"))
        source = folder / "source.pptx"
        original = []
        with PresentationManager() as manager:
            deck = slide = shape = None
            try:
                deck = manager._app.Presentations.Add(False)
                deck.PageSetup.SlideWidth = 960
                deck.PageSetup.SlideHeight = 540
                for number in range(1, 5):
                    slide = deck.Slides.Add(number, 1)
                    for index in range(int(slide.Shapes.Count), 0, -1):
                        shape = slide.Shapes.Item(index)
                        if number in (2, 4) or (number == 1 and int(shape.PlaceholderFormat.Type) == 4):
                            shape.Delete()
                        else:
                            shape.TextFrame.TextRange.Text = f"원본 자리 표시자 {number}-{index}"
                        shape = None
                    if number != 4:
                        shape = slide.Shapes.AddPicture(str(ROOT / "tests/fixtures/basic/sample.jpg"),
                                                        False, True, 50, 40, 180, 120)
                        shape = None
                    original.append(shapes_signature(slide))
                    slide.Export(str(folder / f"source_{number}.png"), "PNG", 960, 540)
                slide = None
                deck.SaveAs(str(source), 24)
            finally:
                shape = slide = None
                if deck is not None:
                    deck.Saved = True
                    deck.Close()
                deck = None
        with PresentationManager() as manager:
            items = manager.read_presentation(source).slides
        order = (2, 1, 3, 4, 2)
        slides = tuple(replace(items[number - 1], source_revision=revision(fingerprint(source))) for number in order)
        output = folder / "result.pptx"
        service = PowerPointService(work_root=folder)
        service.generate(service.prepare(slides, output))
        rows = []
        with PresentationManager() as manager:
            deck = slide = None
            try:
                deck = manager._open(output)
                for index, number in enumerate(order, 1):
                    slide = deck.Slides.Item(index)
                    actual = shapes_signature(slide)
                    slide.Export(str(folder / f"result_{index}.png"), "PNG", 960, 540)
                    with Image.open(folder / f"source_{number}.png") as before, Image.open(folder / f"result_{index}.png") as after:
                        equal = ImageChops.difference(before.convert("RGB"), after.convert("RGB")).getbbox() is None
                    rows.append({"number": index, "source": number, "shapes_equal": actual == original[number - 1],
                                 "render_equal": equal, "actual": actual, "expected": original[number - 1]})
                    slide = None
            finally:
                slide = deck = None
        report = {"rows": rows, "powerpoint": sorted(process_pids("POWERPNT.EXE"))}
        (folder / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        self.assertTrue(all(row["shapes_equal"] and row["render_equal"] for row in rows), report)
        self.assertFalse(process_pids("POWERPNT.EXE"))
