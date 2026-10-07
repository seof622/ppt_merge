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
