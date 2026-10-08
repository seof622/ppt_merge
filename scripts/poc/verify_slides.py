"""COM 메타데이터, PPTX 내부 자료, PowerPoint 렌더링으로 슬라이드를 비교한다."""

from __future__ import annotations

import hashlib
from pathlib import Path
import posixpath
from typing import Any
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from PIL import Image, ImageChops, ImageStat

NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
      "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "c": "http://schemas.openxmlformats.org/drawingml/2006/chart"}


def text_signature(shape: Any) -> list[dict[str, Any]]:
    if not shape.HasTextFrame or not shape.TextFrame.HasText:
        return []
    result = []
    for run in shape.TextFrame.TextRange.Runs():
        result.append({"text": run.Text, "font": run.Font.Name,
                       "size": round(float(run.Font.Size), 3), "bold": int(run.Font.Bold),
                       "color": int(run.Font.Color.RGB)})
    return result


def shape_signature(shape: Any) -> dict[str, Any]:
    result = {"name": shape.Name, "type": int(shape.Type),
              "geometry": [round(float(getattr(shape, attr)), 3)
                           for attr in ("Left", "Top", "Width", "Height", "Rotation")],
              "text": text_signature(shape)}
    if shape.Type == 6:
        result["children"] = [shape_signature(child) for child in shape.GroupItems]
    if shape.Type == 1:
        result["fill"] = int(shape.Fill.ForeColor.RGB)
    if shape.HasTable:
        table = shape.Table
        result["table"] = [[text_signature(table.Cell(row, col).Shape)
                            for col in range(1, table.Columns.Count + 1)]
                           for row in range(1, table.Rows.Count + 1)]
    if shape.HasChart:
        result["chart_type"] = int(shape.Chart.ChartType)
    if shape.HasSmartArt:
        result["smartart"] = {
            "layout": shape.SmartArt.Layout.Id,
            "nodes": [(node.TextFrame2.TextRange.Text, int(node.Level))
                      for node in shape.SmartArt.AllNodes],
        }
    if shape.Type == 16:
        result["media"] = {"type": int(shape.MediaType), "length_ms": int(shape.MediaFormat.Length)}
    if shape.Type in (7, 10):
        result["ole_progid"] = shape.OLEFormat.ProgID
    if shape.Type == 10:
        result["linked_source"] = shape.LinkFormat.SourceFullName
    return result


def slide_signature(slide: Any) -> dict[str, Any]:
    notes = []
    for shape in slide.NotesPage.Shapes:
        if shape.Type == 14 and shape.PlaceholderFormat.Type == 2:
            notes.append(shape.TextFrame.TextRange.Text)
    effects = [{"type": int(effect.EffectType), "shape": effect.Shape.Name,
                "duration": round(float(effect.Timing.Duration), 3),
                "trigger": int(effect.Timing.TriggerType)}
               for effect in slide.TimeLine.MainSequence]
    background = slide.Master.Background if slide.FollowMasterBackground else slide.Background
    return {
        "name": slide.Name,
        "shapes": [shape_signature(shape) for shape in slide.Shapes],
        "notes": notes,
        "effects": effects,
        "transition": int(slide.SlideShowTransition.EntryEffect),
        "background": int(background.Fill.ForeColor.RGB),
        "theme_colors": [int(slide.Design.SlideMaster.Theme.ThemeColorScheme.Colors(i).RGB)
                         for i in range(1, 13)],
        "layout": slide.CustomLayout.Name,
        "hyperlinks": sorted((link.Address or "", link.SubAddress or "") for link in slide.Hyperlinks),
    }


def package_signatures(path: Path) -> list[dict[str, Any]]:
    """이미지 바이트와 차트 캐시를 비교한다. 복사 엔진은 사용하지 않는다."""
    signatures = []
    with ZipFile(path) as archive:
        pres = ET.fromstring(archive.read("ppt/presentation.xml"))
        rels = ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))
        targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        for slide_id in pres.findall("p:sldIdLst/p:sldId", NS):
            target = targets[slide_id.attrib[f"{{{NS['r']}}}id"]]
            slide_path = posixpath.normpath(posixpath.join("ppt", target))
            directory, filename = posixpath.split(slide_path)
            relationships = ET.fromstring(archive.read(f"{directory}/_rels/{filename}.rels"))
            images, charts = [], []
            for rel in relationships:
                if rel.attrib.get("TargetMode") == "External":
                    continue
                kind = rel.attrib["Type"].rsplit("/", 1)[-1]
                part = posixpath.normpath(posixpath.join(directory, rel.attrib["Target"]))
                if kind == "image":
                    images.append(hashlib.sha256(archive.read(part)).hexdigest())
                elif kind == "chart":
                    root = ET.fromstring(archive.read(part))
                    chart_dir, chart_file = posixpath.split(part)
                    chart_rels_path = f"{chart_dir}/_rels/{chart_file}.rels"
                    workbooks = []
                    if chart_rels_path in archive.namelist():
                        for chart_rel in ET.fromstring(archive.read(chart_rels_path)):
                            if chart_rel.attrib["Type"].endswith("/package") and chart_rel.attrib.get("TargetMode") != "External":
                                workbook = posixpath.normpath(posixpath.join(chart_dir, chart_rel.attrib["Target"]))
                                workbooks.append(hashlib.sha256(archive.read(workbook)).hexdigest())
                    charts.append({"values": [node.text for node in root.findall(".//c:v", NS)],
                                   "text": [node.text for node in root.findall(".//a:t", NS)],
                                   "embedded_workbook_hashes": sorted(workbooks)})
            signatures.append({"image_hashes": sorted(images), "charts": charts})
    return signatures


def compare_images(source: Path, output: Path) -> dict[str, Any]:
    with Image.open(source) as original, Image.open(output) as generated:
        if original.size != generated.size:
            return {"equal": False, "error": "렌더 크기 불일치"}
        difference = ImageChops.difference(original.convert("RGB"), generated.convert("RGB"))
        rms = sum(ImageStat.Stat(difference).rms) / 3
        return {"equal": difference.getbbox() is None, "mean_channel_rms": round(rms, 6)}


def advanced_package_signatures(path: Path) -> list[dict[str, Any]]:
    """미디어·SVG·SmartArt·OLE·외부 링크·모션 경로의 원본 자료를 검사한다."""
    signatures = package_signatures(path)
    with ZipFile(path) as archive:
        pres = ET.fromstring(archive.read("ppt/presentation.xml"))
        targets = {r.attrib["Id"]: r.attrib["Target"]
                   for r in ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))}
        slide_paths = [posixpath.normpath(posixpath.join("ppt", targets[s.attrib[f"{{{NS['r']}}}id"]]))
                       for s in pres.findall("p:sldIdLst/p:sldId", NS)]
        for index, slide_path in enumerate(slide_paths):
            directory, filename = posixpath.split(slide_path)
            relationships = ET.fromstring(archive.read(f"{directory}/_rels/{filename}.rels"))
            assets, external, internal = [], [], []
            for rel in relationships:
                kind = rel.attrib["Type"].rsplit("/", 1)[-1]
                target = rel.attrib["Target"]
                if rel.attrib.get("TargetMode") == "External":
                    external.append((kind, target))
                    continue
                part = posixpath.normpath(posixpath.join(directory, target))
                if kind in ("audio", "video", "media", "oleObject", "package", "diagramData",
                            "diagramLayout", "diagramColors", "diagramQuickStyle"):
                    data = archive.read(part)
                    if kind.startswith("diagram"):
                        root = ET.fromstring(data)
                        # PowerPoint가 갱신하는 렌더 캐시 확장은 제외하고 편집용 데이터를 비교한다.
                        for parent in root.iter():
                            for child in list(parent):
                                if child.tag.rsplit("}", 1)[-1] == "extLst":
                                    parent.remove(child)
                        data = ET.canonicalize(ET.tostring(root, encoding="unicode")).encode("utf-8")
                    assets.append((kind, hashlib.sha256(data).hexdigest()))
                elif kind == "slide":
                    internal.append(slide_paths.index(part) + 1 if part in slide_paths else None)
            slide = ET.fromstring(archive.read(slide_path))
            motion_paths = [node.attrib.get("path") for node in slide.iter()
                            if node.tag.rsplit("}", 1)[-1] == "animMotion"]
            signatures[index].update({"advanced_assets": sorted(assets), "external_links": sorted(external),
                                      "internal_link_target_indices": internal, "motion_paths": motion_paths})
    return signatures
