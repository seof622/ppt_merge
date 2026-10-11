"""원본 배경의 그림·서식·관계 복원과 실패 시 파일 보호."""
from pathlib import Path
import tempfile
import unittest
from xml.dom import minidom
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from src.models.slide_model import SlideItem
from src.ppt.background_preservation import P, R, REL, CT, restore_slide_backgrounds
from src.ppt.errors import GenerationError, OperationCancelled

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"


def write_deck(path, backgrounds, image=b"original image", broken=False):
    parts = {
        "[Content_Types].xml": f'<Types xmlns="{CT}"><Default Extension="png" ContentType="image/png"/></Types>',
        "ppt/presentation.xml": f'<p:presentation xmlns:p="{P}" xmlns:r="{R}"><p:sldIdLst>'
            + ''.join(f'<p:sldId id="{256+i}" r:id="s{i}"/>' for i in range(len(backgrounds)))
            + '</p:sldIdLst></p:presentation>',
        "ppt/_rels/presentation.xml.rels": f'<Relationships xmlns="{REL}">'
            + ''.join(f'<Relationship Id="s{i}" Type="{R}/slide" Target="slides/slide{10+i}.xml"/>'
                      for i in range(len(backgrounds))) + '</Relationships>',
        "ppt/media/image1.png": image,
    }
    for i, background in enumerate(backgrounds):
        parts[f"ppt/slides/slide{10+i}.xml"] = (
            f'<p:sld xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}" xmlns:mc="{MC}" '
            'xmlns:p14="http://schemas.microsoft.com/office/powerpoint/2010/main" mc:Ignorable="p14">'
            f'<p:cSld>{background}<p:spTree/><p:extLst/></p:cSld><p:clrMapOvr/></p:sld>')
        parts[f"ppt/slides/_rels/slide{10+i}.xml.rels"] = (
            f'<Relationships xmlns="{REL}"><Relationship Id="rIdBackground1" Type="{R}/slideLayout" '
            'Target="../slideLayouts/layout.xml"/>'
            + ('' if broken else f'<Relationship Id="picture" Type="{R}/image" Target="../media/image1.png"/>')
            + '</Relationships>')
    with ZipFile(path, "w") as archive:
        for name, content in parts.items():
            archive.writestr(name, content)


PICTURE = ('<p:bg><p:bgPr><a:blipFill><a:blip r:embed="picture"><a:alphaModFix amt="65000"/>'
           '</a:blip><a:srcRect l="1200" r="3400"/><a:tile tx="1234" ty="5678" sx="80000" '
           'sy="90000" flip="xy" algn="ctr"/></a:blipFill><a:effectLst/></p:bgPr></p:bg>')


class BackgroundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source, self.other, self.output = [self.root / p for p in ("A.pptx", "B.pptm", "out.pptx")]

    def tearDown(self):
        self.temp.cleanup()

    def item(self, path, index=1):
        return SlideItem(str(path), path.name, index, 255 + index)

    def assert_picture(self, archive, number, expected):
        part = f"ppt/slides/slide{10+number}.xml"
        root = ET.fromstring(archive.read(part))
        bg = root.find(f"{{{P}}}cSld/{{{P}}}bg")
        blip = bg.find(f".//{{{A}}}blip")
        rid = blip.get(f"{{{R}}}embed")
        rels = ET.fromstring(archive.read(f"ppt/slides/_rels/slide{10+number}.xml.rels"))
        rel = next(r for r in rels if r.get("Id") == rid)
        self.assertEqual(archive.read("ppt/" + rel.get("Target")[3:]), expected)
        # 관계 ID를 제외한 투명도·자르기·타일 설정을 통째로 비교한다.
        blip.set(f"{{{R}}}embed", "picture")
        baseline = ET.fromstring(f'<root xmlns:p="{P}" xmlns:a="{A}" xmlns:r="{R}">{PICTURE}</root>')[0]
        self.assertEqual(ET.tostring(bg), ET.tostring(baseline))
        self.assertNotEqual(rid, "rIdBackground1")
        self.assertEqual(root.get(f"{{{MC}}}Ignorable"), "p14")
        document = minidom.parseString(archive.read(part))
        self.assertEqual(document.documentElement.getAttribute("xmlns:p14"),
                         "http://schemas.microsoft.com/office/powerpoint/2010/main")
        types = ET.fromstring(archive.read("[Content_Types].xml"))
        self.assertTrue(any(t.get("ContentType") == "image/png" and "background_" in t.get("PartName", "")
                            for t in types))

    def test_package_namespace_spelling_preserves_image_lookup_in_other_office(self):
        # Polaris는 새 ns0 접두사가 붙은 관계·형식 요소의 그림 참조를 놓친다.
        write_deck(self.source, [PICTURE])
        for prefix in ("", "pkg"):
            with self.subTest(prefix=prefix):
                write_deck(self.output, [""])
                if prefix:
                    with ZipFile(self.output) as archive:
                        parts = {name: archive.read(name) for name in archive.namelist()}
                    for name in ("[Content_Types].xml", "ppt/slides/_rels/slide10.xml.rels"):
                        document = minidom.parseString(parts[name])
                        namespace = CT if name == "[Content_Types].xml" else REL
                        for node in list(document.getElementsByTagNameNS(namespace, "*")):
                            document.renameNode(node, namespace, f"{prefix}:{node.localName}")
                        document.documentElement.removeAttribute("xmlns")
                        document.documentElement.setAttributeNS("http://www.w3.org/2000/xmlns/",
                                                              f"xmlns:{prefix}", namespace)
                        parts[name] = document.toxml(encoding="utf-8")
                    with ZipFile(self.output, "w") as archive:
                        for name, data in parts.items():
                            archive.writestr(name, data)
                restore_slide_backgrounds((self.item(self.source),), self.output)
                with ZipFile(self.output) as archive:
                    for name, namespace, root_name, child_name in (
                            ("[Content_Types].xml", CT, "Types", "Override"),
                            ("ppt/slides/_rels/slide10.xml.rels", REL, "Relationships", "Relationship")):
                        document = minidom.parseString(archive.read(name))
                        expected = f"{prefix}:" if prefix else ""
                        self.assertEqual(document.documentElement.tagName, expected + root_name)
                        self.assertTrue(document.getElementsByTagName(expected + child_name))
                        self.assertTrue(all(node.prefix == (prefix or None)
                            for node in document.getElementsByTagNameNS(namespace, child_name)))
                    self.assert_picture(archive, 0, b"original image")

    def test_picture_metadata_media_and_cross_source_duplicates(self):
        write_deck(self.source, [PICTURE], b"A image")
        write_deck(self.other, [PICTURE], b"B image")
        write_deck(self.output, ["", "", ""], b"destination image")
        before = self.source.read_bytes()
        slides = (self.item(self.source), self.item(self.other), self.item(self.source))
        self.assertEqual(restore_slide_backgrounds(slides, self.output), 3)
        with ZipFile(self.output) as archive:
            for i, expected in enumerate((b"A image", b"B image", b"A image")):
                self.assert_picture(archive, i, expected)
            self.assertEqual(len([n for n in archive.namelist() if "/background_" in n]), 2)
            self.assertEqual(archive.read("ppt/media/image1.png"), b"destination image")
            self.assertIsNone(archive.testzip())
        self.assertEqual(self.source.read_bytes(), before)

    def test_inherited_background_leaves_com_output_unchanged(self):
        write_deck(self.source, [""])
        write_deck(self.output, [""])
        before = self.output.read_bytes()
        self.assertEqual(restore_slide_backgrounds((self.item(self.source),), self.output), 0)
        self.assertEqual(self.output.read_bytes(), before)

    def test_missing_picture_relationship_does_not_publish_broken_background(self):
        write_deck(self.source, [PICTURE], broken=True)
        write_deck(self.output, [""])
        before = self.output.read_bytes()
        with self.assertRaises(GenerationError):
            restore_slide_backgrounds((self.item(self.source),), self.output)
        self.assertEqual(self.output.read_bytes(), before)

    def test_cancel_during_rewrite_keeps_original_and_cleans_temporary_file(self):
        write_deck(self.source, [PICTURE])
        write_deck(self.output, [""])
        before = self.output.read_bytes()
        with self.assertRaises(OperationCancelled):
            restore_slide_backgrounds((self.item(self.source),), self.output,
                                      lambda: bool(list(self.root.glob("background-*.pptx"))))
        self.assertEqual(self.output.read_bytes(), before)
        self.assertFalse(list(self.root.glob("background-*.pptx")))

    def test_explicit_solid_background_replaces_inserted_background(self):
        solid = '<p:bg><p:bgPr><a:solidFill><a:srgbClr val="123456"/></a:solidFill></p:bgPr></p:bg>'
        write_deck(self.source, [solid])
        write_deck(self.output, [PICTURE])
        restore_slide_backgrounds((self.item(self.source),), self.output)
        with ZipFile(self.output) as archive:
            root = ET.fromstring(archive.read("ppt/slides/slide10.xml"))
            self.assertEqual(root.find(f".//{{{A}}}srgbClr").get("val"), "123456")
