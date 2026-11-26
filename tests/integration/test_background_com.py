"""실제 PowerPoint의 그림 채우기 누락 재현과 배경 복원 회귀 검증."""
import hashlib
import json
import os
from pathlib import Path
import posixpath
import tempfile
import unittest
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from PIL import Image, ImageChops, ImageDraw

from src.models.slide_model import SlideBackground, SlideItem
from src.ppt.background_preservation import P, R, _slide_parts, _rels_part
from src.ppt.powerpoint_service import PowerPointService
from src.ppt.presentation_manager import PresentationManager
from src.ppt.slide_background import import_background_image
from src.ppt.source_validation import fingerprint, revision
from src.ppt.thumbnail_service import ThumbnailService
from src.utils.process_utils import process_pids
from dataclasses import replace

ROOT = Path(__file__).resolve().parents[2]


def background_signature(path, index):
    with ZipFile(path) as archive:
        part = _slide_parts(archive)[index - 1][1]
        background = ET.fromstring(archive.read(part)).find(f"{{{P}}}cSld/{{{P}}}bg")
        if background is None:
            return None
        rels = ET.fromstring(archive.read(_rels_part(part)))
        targets = {r.get("Id"): r.get("Target") for r in rels}
        for node in background.iter():
            for key, rid in list(node.attrib.items()):
                if key.startswith("{" + R + "}"):
                    image = posixpath.normpath(posixpath.join(posixpath.dirname(part), targets[rid]))
                    node.set(key, hashlib.sha256(archive.read(image)).hexdigest())
        return ET.tostring(background)


@unittest.skipUnless(os.environ.get("PPT_MERGE_GENERATION_COM_TESTS") == "1", "Office 검증 활성화 필요")
class BackgroundComTests(unittest.TestCase):
    def test_output_background_overrides_and_previews_keep_the_source(self):
        if process_pids("POWERPNT.EXE"):
            self.skipTest("사용자 PowerPoint를 저장하고 닫은 뒤 실행하세요.")
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / "source.pptx"
            original_image = folder / "original.png"
            Image.new("RGB", (320, 180), "#166981").save(original_image)
            replacement_image = folder / "replacement.png"
            Image.new("RGB", (320, 180), "#346854").save(replacement_image)
            with PresentationManager() as manager:
                deck = manager._app.Presentations.Add(False)
                slide = None
                try:
                    deck.PageSetup.SlideWidth, deck.PageSetup.SlideHeight = 960, 540
                    slide = deck.Slides.Add(1, 12)
                    slide.FollowMasterBackground = False
                    slide.Background.Fill.UserPicture(str(original_image))
                    slide_id = int(slide.SlideID)
                    deck.SaveAs(str(source), 24)
                finally:
                    slide = None
                    deck.Saved = True
                    deck.Close()
                    deck = None
            before = fingerprint(source)
            item = SlideItem(str(source), source.name, 1, slide_id, source_revision=revision(before))
            color = replace(item, background=SlideBackground(color="#D25A24"))
            picture = replace(item, background=import_background_image(replacement_image, folder / "assets"))
            replacement_image.rename(folder / "moved.png")
            output = folder / "result.pptx"
            service = PowerPointService(work_root=folder)
            service.generate(service.prepare((item, color, picture), output))

            expected = ((22, 105, 129), (210, 90, 36), (52, 104, 84))
            with PresentationManager() as manager:
                for index, pixel in enumerate(expected, 1):
                    path = folder / f"out-{index}.png"
                    manager.export_slide(output, index, path, 320, 180)
                    with Image.open(path) as image:
                        self.assertEqual(image.convert("RGB").getpixel((20, 20)), pixel)
            self.assertEqual(background_signature(output, 1), background_signature(source, 1))

            previews = ThumbnailService(folder / "cache", width=320)
            (_, color_path), (_, picture_path) = previews.load_background_previews((color, picture))
            self.assertNotEqual(color_path, picture_path)
            for path, pixel in zip((color_path, picture_path), expected[1:]):
                with Image.open(path) as image:
                    self.assertEqual(image.convert("RGB").getpixel((20, 20)), pixel)
            preview = ThumbnailService(folder / "cache", width=1600).load_preview(picture)
            with Image.open(preview) as image:
                self.assertEqual(image.convert("RGB").getpixel((20, 20)), expected[2])
            self.assertEqual(fingerprint(source), before)
        self.assertFalse(process_pids("POWERPNT.EXE"))

    def test_picture_transparency_texture_master_solid_gradient_and_duplicates(self):
        if process_pids("POWERPNT.EXE"):
            self.skipTest("사용자 PowerPoint를 저장하고 닫은 뒤 실행하세요.")
        folder = Path(tempfile.mkdtemp(prefix="background_validation_", dir=ROOT / "output"))
        paths = {key: folder / f"source_{key}.pptx" for key in ("A", "B")}
        images = {}
        for key, color in (("A", "#eb8434"), ("B", "#438cdf")):
            picture = Image.new("RGB", (960, 540), color)
            draw = ImageDraw.Draw(picture)
            draw.rectangle((80, 90, 270, 300), fill="#3daa65")
            draw.ellipse((500, 210, 870, 500), fill="#ffe584")
            images[key] = folder / f"image_{key}.png"
            picture.save(images[key])
        with PresentationManager() as manager:
            deck = slide = shape = None
            try:
                for key in ("A", "B"):
                    deck = manager._app.Presentations.Add(False)
                    deck.PageSetup.SlideWidth = 960
                    deck.PageSetup.SlideHeight = 540
                    if key == "B":
                        deck.SlideMaster.Background.Fill.UserPicture(str(images[key]))
                    kinds = ("picture", "transparent", "texture", "solid", "gradient") if key == "A" else ("master", "picture")
                    for number, kind in enumerate(kinds, 1):
                        slide = deck.Slides.Add(number, 12)
                        if kind != "master":
                            slide.FollowMasterBackground = False
                            if kind == "texture":
                                slide.Background.Fill.UserTextured(str(images[key]))
                                slide.Background.Fill.TextureHorizontalScale = 0.4
                                slide.Background.Fill.TextureVerticalScale = 0.6
                                slide.Background.Fill.TextureOffsetX = 17
                                slide.Background.Fill.TextureOffsetY = 29
                            elif kind == "solid":
                                slide.Background.Fill.Solid()
                                slide.Background.Fill.ForeColor.RGB = 0x884422
                            elif kind == "gradient":
                                slide.Background.Fill.PresetGradient(1, 1, 2)
                            else:
                                slide.Background.Fill.UserPicture(str(images[key]))
                                if kind == "transparent":
                                    slide.Background.Fill.Transparency = 0.35
                        shape = slide.Shapes.AddShape(1, 340, 50, 90, 60)
                        shape.Fill.ForeColor.RGB = 0x223344
                        shape = None
                    deck.SaveAs(str(paths[key]), 24)
                    for number in range(1, int(deck.Slides.Count) + 1):
                        slide = deck.Slides.Item(number)
                        slide.Export(str(folder / f"{key}_{number}.png"), "PNG", 960, 540)
                    slide = None
                    deck.Saved = True
                    deck.Close()
                    deck = None
            finally:
                shape = slide = None
                if deck is not None:
                    deck.Saved = True
                    deck.Close()
                deck = None
        before = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in paths.items()}
        with PresentationManager() as manager:
            selections = {key: manager.read_presentation(path).slides for key, path in paths.items()}
        pairs = [("A", 1), ("B", 1), ("A", 2), ("A", 3), ("B", 2), ("A", 4), ("A", 5), ("A", 1)]
        slides = tuple(replace(selections[key][number - 1], source_revision=revision(fingerprint(paths[key])))
                       for key, number in pairs)
        uncorrected = folder / "before_fix.pptx"
        with PresentationManager() as manager:
            manager.compose(slides, uncorrected, 960, 540, lambda *args: None)
        output = folder / "after_fix.pptx"
        service = PowerPointService(work_root=folder)
        service.generate(service.prepare(slides, output))
        comparisons = []
        with PresentationManager() as manager:
            deck = slide = None
            try:
                for label, path in (("before", uncorrected), ("after", output)):
                    deck = manager._open(path)
                    for index, (key, number) in enumerate(pairs, 1):
                        slide = deck.Slides.Item(index)
                        render = folder / f"{label}_{index}.png"
                        slide.Export(str(render), "PNG", 960, 540)
                        with Image.open(folder / f"{key}_{number}.png") as original, Image.open(render) as actual:
                            equal = ImageChops.difference(original.convert("RGB"), actual.convert("RGB")).getbbox() is None
                        comparisons.append({"stage": label, "source": f"{key}-{number}", "equal": equal})
                    slide = deck = None
            finally:
                slide = deck = None
        for index, (key, number) in enumerate(pairs, 1):
            self.assertEqual(background_signature(paths[key], number), background_signature(output, index))
        report = {"directory": str(folder), "comparisons": comparisons,
                  "remaining_powerpoint": sorted(process_pids("POWERPNT.EXE"))}
        (folder / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        self.assertTrue(any(not row["equal"] for row in comparisons if row["stage"] == "before"))
        self.assertTrue(all(row["equal"] for row in comparisons if row["stage"] == "after"), report)
        self.assertEqual(before, {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in paths.items()})
        self.assertFalse(process_pids("POWERPNT.EXE"))
        print(json.dumps(report, ensure_ascii=False))
