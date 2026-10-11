"""지정한 실제 원본과 서비스 또는 frozen EXE의 전체 병합 결과를 비교한다."""
import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import posixpath
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from PIL import Image, ImageChops

from src.ppt.background_preservation import P, R, _slide_parts, _rels_part
from src.ppt.presentation_manager import PresentationManager
from src.ppt.powerpoint_service import PowerPointService
from src.ppt.source_validation import fingerprint, revision
from src.utils.process_utils import process_pids

ROOT = Path(__file__).resolve().parents[1]


def background_signature(path: Path, number: int) -> bytes | None:
    with ZipFile(path) as archive:
        part = _slide_parts(archive)[number - 1][1]
        bg = ET.fromstring(archive.read(part)).find(f"{{{P}}}cSld/{{{P}}}bg")
        if bg is None:
            return None
        rels = ET.fromstring(archive.read(_rels_part(part)))
        targets = {rel.get("Id"): rel for rel in rels}
        for node in bg.iter():
            for key, rid in list(node.attrib.items()):
                if key.startswith("{" + R + "}"):
                    rel = targets[rid]
                    if rel.get("TargetMode") == "External":
                        node.set(key, rel.attrib["Target"])
                    else:
                        image = posixpath.normpath(posixpath.join(posixpath.dirname(part), rel.attrib["Target"]))
                        node.set(key, hashlib.sha256(archive.read(image)).hexdigest())
        return ET.tostring(bg)


def shapes_signature(slide) -> list[dict]:
    return [{"name": str(shape.Name), "type": int(shape.Type),
             "bounds": [round(float(value), 3) for value in
                        (shape.Left, shape.Top, shape.Width, shape.Height)],
             "text": str(shape.TextFrame.TextRange.Text) if shape.HasTextFrame else None,
             "placeholder": int(shape.PlaceholderFormat.Type) if int(shape.Type) == 14 else None}
            for shape in slide.Shapes]


def main() -> int:
    parser = argparse.ArgumentParser(description="실제 PPT 전체 병합의 원본 일치 검증")
    parser.add_argument("sources", nargs="+", type=Path)
    parser.add_argument("--exe", type=Path)
    args = parser.parse_args()
    sources = [path.resolve() for path in args.sources]
    if args.exe and len(sources) != 2:
        parser.error("EXE 진단에는 원본 2개를 지정하세요.")
    folder = Path(tempfile.mkdtemp(prefix="merge_fidelity_", dir=ROOT / "output"))
    print(f"검증 폴더: {folder}", flush=True)
    before = {str(path): fingerprint(path) for path in sources}
    backgrounds = {}
    for path in sources:
        with ZipFile(path) as archive:
            count = len(_slide_parts(archive))
        backgrounds[str(path)] = [background_signature(path, number) for number in range(1, count + 1)]
    selection, baselines = [], []
    with PresentationManager() as manager:
        deck = slide = None
        try:
            for source_number, path in enumerate(sources, 1):
                info = manager.read_presentation(path)
                deck = manager._open(path)
                for item in info.slides:
                    slide = deck.Slides.Item(item.slide_index)
                    render = folder / f"source_{source_number}_{item.slide_index}.png"
                    slide.Export(str(render), "PNG", 960, 720)
                    baselines.append({"source": str(path), "number": item.slide_index,
                                      "render": render, "shapes": shapes_signature(slide),
                                      "background": backgrounds[str(path)][item.slide_index - 1]})
                    selection.append(replace(item, source_revision=revision(before[str(path)])))
                    slide = None
                deck = None
        finally:
            slide = deck = None
    output = folder / "merged.pptx"
    package_report = None
    if args.exe:
        env = os.environ.copy()
        for name in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
            env.pop(name, None)
        env["LOCALAPPDATA"] = str(folder / "user_data")
        env["QT_QPA_PLATFORM"] = "offscreen"
        windows = Path(env.get("SystemRoot", "C:/Windows"))
        env["PATH"] = os.pathsep.join((str(windows / "System32"), str(windows)))
        process = subprocess.run([str(args.exe.resolve()), "--package-check", str(folder),
                                  "--package-check-all-slides", *(str(path) for path in sources)],
                                 cwd=folder, env=env, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
        package_report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
        if process.returncode or not package_report["passed"]:
            raise AssertionError(package_report)
        (folder / "package_result.pptx").rename(output)
    else:
        service = PowerPointService(work_root=folder)
        service.generate(service.prepare(tuple(selection), output))
    rows = []
    with PresentationManager() as manager:
        deck = slide = None
        try:
            deck = manager._open(output)
            if int(deck.Slides.Count) != len(baselines):
                raise AssertionError("슬라이드 수 불일치")
            for index, baseline in enumerate(baselines, 1):
                slide = deck.Slides.Item(index)
                render = folder / f"result_{index}.png"
                slide.Export(str(render), "PNG", 960, 720)
                with Image.open(baseline["render"]) as original, Image.open(render) as actual:
                    box = ImageChops.difference(original.convert("RGB"), actual.convert("RGB")).getbbox()
                shapes = shapes_signature(slide)
                rows.append({"index": index, "source": baseline["source"], "slide": baseline["number"],
                             "render_equal": box is None, "difference_bounds": box,
                             "shapes_equal": shapes == baseline["shapes"],
                             "source_shape_count": len(baseline["shapes"]), "output_shape_count": len(shapes)})
                slide = None
        finally:
            slide = deck = None
    unchanged = all(fingerprint(path) == before[str(path)] for path in sources)
    for row, baseline in zip(rows, baselines):
        row["background_equal"] = background_signature(output, row["index"]) == baseline["background"]
    passed = all(row["render_equal"] and row["shapes_equal"] and row["background_equal"] for row in rows)
    report = {"passed": passed and unchanged and not process_pids("POWERPNT.EXE"),
              "output": str(output), "rows": rows, "sources_unchanged": unchanged,
              "remaining_powerpoint": sorted(process_pids("POWERPNT.EXE")), "package": package_report}
    (folder / "fidelity_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
