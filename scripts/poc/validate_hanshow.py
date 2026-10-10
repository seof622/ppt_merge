"""SHOW→PPTX 변환·원본 보존·기존 엔진 재사용을 실제 Office로 검증한다."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import datetime
import json
import logging
from pathlib import Path
import posixpath
import shutil
import sys
import tempfile
from typing import Any
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from com_session import ROOT, PowerPointSession, configure_logging, process_pids
from hanshow_session import HanShowSession, installed_environment
from verify_slides import compare_images, advanced_package_signatures, slide_signature

sys.path.insert(0, str(ROOT))
from src.ppt.errors import OperationCancelled
from src.ppt.powerpoint_service import PowerPointService
from src.ppt.source_validation import file_hash, validate_source
from src.ppt.thumbnail_service import ThumbnailService

LOGGER = logging.getLogger("ppt_merge.hanshow_poc")
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def package_inventory(path: Path) -> dict[str, Any]:
    """이번 샘플의 OOXML 데이터를 읽는다. SHOW 일반 파서는 구현하지 않는다."""
    with ZipFile(path) as archive:
        presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
        targets = {node.attrib["Id"]: node.attrib["Target"] for node in
                   ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))}
        size = presentation.find(P + "sldSz")
        slides = []
        for node in presentation.find(P + "sldIdLst"):
            part = posixpath.normpath(posixpath.join("ppt", targets[node.attrib[R + "id"]]))
            xml = ET.fromstring(archive.read(part))
            slides.append({
                "id": int(node.attrib["id"]),
                "text": [item.text for item in xml.iter(A + "t")],
                "fonts": sorted({item.attrib.get("typeface", "") for item in xml.iter()
                                 if item.tag in (A + "latin", A + "ea", A + "cs")}),
                "shapes": len(xml.findall(".//" + P + "sp")),
                "pictures": len(xml.findall(".//" + P + "pic")),
                "groups": len(xml.findall(".//" + P + "grpSp")),
                "tables": len(xml.findall(".//" + A + "tbl")),
                "timing_present": xml.find(P + "timing") is not None,
                "transition_present": xml.find(P + "transition") is not None,
            })
        return {"size": dict(size.attrib), "slides": slides,
                "assets": advanced_package_signatures(path)}


def render_hanshow(document: Any, folder: Path) -> int:
    folder.mkdir(parents=True)
    count = int(document.Slides.Count)
    width = 1280
    height = round(width * float(document.PageSetup.SlideHeight) /
                   float(document.PageSetup.SlideWidth))
    slide = None
    try:
        for index in range(1, count + 1):
            slide = document.Slides.Item(index)
            slide.Export(str(folder / f"slide_{index}.png"), "PNG", width, height)
            if not (folder / f"slide_{index}.png").is_file():
                raise RuntimeError(f"한쇼 렌더링 실패: 슬라이드 {index}")
    finally:
        slide = None
    return count


def inspect_powerpoint(path: Path, folder: Path, sessions: list[dict]) -> list[dict]:
    folder.mkdir(parents=True)
    session = PowerPointSession()
    document = slide = None
    result = []
    try:
        with session:
            try:
                document = session.open(path)
                width = 1280
                height = round(width * float(document.PageSetup.SlideHeight) /
                               float(document.PageSetup.SlideWidth))
                for index in range(1, int(document.Slides.Count) + 1):
                    slide = document.Slides.Item(index)
                    result.append(slide_signature(slide))
                    slide.Export(str(folder / f"slide_{index}.png"), "PNG", width, height)
            finally:
                slide = document = None
    finally:
        sessions.append({"app": "PowerPoint", **session.cleanup})
    return result


def differences(left: dict, right: dict) -> list[str]:
    return [field for field in left if field not in ("name", "id") and left[field] != right[field]]


def run_case(label: str, seed: Path, actual_show: bool, directory: Path,
             temporary: Path, report: dict, *,
             session_factory: Callable[[], HanShowSession] = HanShowSession) -> tuple[Path, dict]:
    folder = directory / label
    folder.mkdir()
    source = folder / "source.show"
    original_hash = file_hash(seed)
    native = folder / "hanshow"
    converted = temporary / f"{label}.pptx"
    session = session_factory()
    document = None
    try:
        with session:
            try:
                if actual_show:
                    shutil.copy2(seed, source)
                else:
                    document = session.open(seed)
                    session.save_sample_show(document, source)
                    session.close(document)
                    document = None
                show_hash = file_hash(source)
                document = session.open(source)
                count = render_hanshow(document, native)
                session.save_pptx(document, converted)
                session.close(document)
                document = None
                # 재변환 시 슬라이드 ID 안정성을 후속 단계 설계에 활용한다.
                document = session.open(source)
                second = temporary / f"{label}_repeat.pptx"
                session.save_pptx(document, second)
            finally:
                document = None
    finally:
        report["sessions"].append({"app": "HanShow", **session.cleanup})
    validate_source(converted)
    validate_source(second)
    before = package_inventory(source)
    after = package_inventory(converted)
    repeated = package_inventory(second)
    signatures = inspect_powerpoint(converted, folder / "powerpoint", report["sessions"])
    rows = []
    for index, (left, right) in enumerate(zip(before["slides"], after["slides"], strict=True), 1):
        rows.append({"slide": index, "changed_content_fields": differences(left, right),
                     "changed_asset_fields": differences(before["assets"][index - 1], after["assets"][index - 1]),
                     "native_vs_powerpoint_render": compare_images(native / f"slide_{index}.png",
                                                                   folder / f"powerpoint/slide_{index}.png")})
    result = {"label": label, "sample_kind": "actual_show" if actual_show else "pptx_imported_into_hanshow",
              "source": str(seed), "sample_show": str(source), "slide_count": count,
              "source_unchanged": original_hash == file_hash(seed) and show_hash == file_hash(source),
              "valid_pptx": True, "powerpoint_opened": len(signatures) == count,
              "size_preserved": before["size"] == after["size"],
              "reconversion_content_stable": after == repeated,
              "show_to_pptx": rows, "seed_to_show": None,
              "powerpoint_signatures": signatures, "show_inventory": before,
              "pptx_inventory": after}
    if not actual_show:
        original = inspect_powerpoint(seed, folder / "seed_powerpoint", report["sessions"])
        original_package = package_inventory(seed)
        result["seed_to_show"] = [
            {"slide": index, "changed_content_fields": differences(left, right),
             "changed_asset_fields": differences(original_package["assets"][index-1], before["assets"][index-1]),
             "seed_vs_hanshow_render": compare_images(folder / f"seed_powerpoint/slide_{index}.png",
                                                      native / f"slide_{index}.png"),
             "seed_vs_converted_com_changes": differences(original[index-1], signatures[index-1])}
            for index, (left, right) in enumerate(zip(original_package["slides"], before["slides"], strict=True), 1)]
    result["pipeline_passed"] = all((result["source_unchanged"], result["valid_pptx"],
                                      result["powerpoint_opened"], result["size_preserved"],
                                      result["reconversion_content_stable"]))
    report["cases"].append(result)
    return converted, result


def reliability(source: Path, report: dict) -> None:
    for label in ("failure_after_open", "cancel_after_open", "preexisting_session"):
        session = HanShowSession()
        document = None
        outcome = False
        try:
            with session:
                try:
                    document = session.open(source)
                    if label == "failure_after_open":
                        raise RuntimeError("검증용 의도적 오류")
                    if label == "cancel_after_open":
                        raise OperationCancelled("검증용 안전한 지점 취소")
                    blocked = HanShowSession()
                    try:
                        with blocked:
                            raise AssertionError("기존 한쇼 실행을 차단하지 못했습니다.")
                    except RuntimeError:
                        outcome = session.pid in process_pids("HShow.exe") and int(document.Slides.Count) > 0
                finally:
                    document = None
        except (RuntimeError, OperationCancelled) as error:
            outcome = str(error).startswith("검증용")
        report["sessions"].append({"app": "HanShow", **session.cleanup})
        report["reliability"].append({"case": label, "passed": outcome and
                                      session.cleanup.get("owned_process_exited", False) and
                                      not session.cleanup.get("errors")})


def run(directory: Path, sources: list[Path]) -> dict:
    report = {"environment": installed_environment(), "cases": [], "sessions": [],
              "reliability": [], "merge": None, "error": None,
              "limitations": ["실제 사용자 SHOW 문서 미검증" if not sources else "입력된 SHOW 문서만 검증",
                              "오디오·영상·애니메이션 재생과 외부 연결 갱신은 수동 확인 필요",
                              "강제 취소·시간 제한·암호/손상 문서의 실파일 검증은 후속 단계"]}
    seeds = [(f"show_{index}", path, True) for index, path in enumerate(sources, 1)] if sources else [
        ("A", ROOT / "tests/fixtures/basic/A.pptx", False),
        ("B", ROOT / "tests/fixtures/basic/B.pptx", False),
        ("C", ROOT / "tests/fixtures/basic/C_4x3.pptx", False),
        ("advanced", ROOT / "tests/fixtures/advanced/advanced.pptx", False)]
    try:
        with tempfile.TemporaryDirectory(prefix="conversion_", dir=directory) as work:
            temporary = Path(work)
            results = {}
            for label, seed, actual in seeds:
                LOGGER.info("한쇼 변환 검증 시작 %s", label)
                results[label] = run_case(label, seed, actual, directory, temporary, report)
                (directory / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            reliability(Path(report["cases"][0]["sample_show"]), report)
            # 변환된 SHOW와 원래 PPTX를 함께 기존 생성 서비스로 처리한다.
            first = next(iter(results))
            converted, data = results[first]
            thumbs = ThumbnailService(temporary / "thumbnails").load(converted)
            if not sources:
                other = ThumbnailService(temporary / "thumbnails").load(ROOT / "tests/fixtures/basic/B.pptx")
                selection = (thumbs.presentation.slides[1], other.presentation.slides[3], thumbs.presentation.slides[0])
                expected = (data["powerpoint_signatures"][1], None, data["powerpoint_signatures"][0])
            else:
                selection = tuple(reversed(thumbs.presentation.slides))
                expected = tuple(reversed(data["powerpoint_signatures"]))
            service = PowerPointService(work_root=temporary)
            target = directory / "merged_result.pptx"
            result = service.generate(service.prepare(selection, target))
            merged = inspect_powerpoint(target, directory / "merged_powerpoint", report["sessions"])
            actual_changes = [differences(left, right) if left is not None else []
                              for left, right in zip(expected, merged, strict=True)]
            expected_renders = ([directory / first / "powerpoint/slide_2.png", None,
                                 directory / first / "powerpoint/slide_1.png"] if not sources else
                                [directory / first / f"powerpoint/slide_{item.slide_index}.png"
                                 for item in selection])
            # 미검증 원래 PPTX 한 장도 실제 원본과 비교한다.
            if not sources:
                # B 원본 COM은 앞에서 읽은 결과와 별도로 다시 확인한다.
                baseline = inspect_powerpoint(ROOT / "tests/fixtures/basic/B.pptx",
                                              directory / "merge_original_B", report["sessions"])
                actual_changes[1] = differences(baseline[3], merged[1])
                expected_renders[1] = directory / "merge_original_B/slide_4.png"
            render_comparisons = [compare_images(path, directory / f"merged_powerpoint/slide_{index}.png")
                                  for index, path in enumerate(expected_renders, 1)]
            report["merge"] = {"output": result.output_path, "slide_count": result.slide_count,
                               "changed_com_fields": actual_changes,
                               "render_comparisons": render_comparisons,
                               "passed": result.slide_count == len(selection) and not any(actual_changes)
                                         and all(row["equal"] for row in render_comparisons)}
        report["intermediate_directory_deleted"] = not temporary.exists()
    except Exception as error:
        LOGGER.exception("한쇼 PoC 검증 중 오류")
        report["error"] = repr(error)
    report["live_hanshow_pids"] = sorted(process_pids("HShow.exe"))
    report["live_powerpoint_pids"] = sorted(process_pids("POWERPNT.EXE"))
    report["pipeline_passed"] = (report["error"] is None and len(report["cases"]) == len(seeds)
                                 and all(case["pipeline_passed"] for case in report["cases"])
                                 and all(case["passed"] for case in report["reliability"])
                                 and bool(report["merge"] and report["merge"]["passed"])
                                 and all(session["owned_process_exited"] and not session["errors"]
                                         for session in report["sessions"])
                                 and report.get("intermediate_directory_deleted", False)
                                 and not report["live_hanshow_pids"] and not report["live_powerpoint_pids"])
    report["fidelity_exact"] = bool(report["cases"]) and all(
        not row["changed_content_fields"] and not row["changed_asset_fields"] and
        row["native_vs_powerpoint_render"]["equal"]
        for case in report["cases"] for row in case["show_to_pptx"])
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", type=Path, default=[], help="실제 SHOW 전체 경로(읽기 전용)")
    parser.add_argument("--output", type=Path, default=ROOT / "output" /
                        ("hanshow_poc_" + datetime.now().strftime("%Y%m%d_%H%M%S")))
    args = parser.parse_args()
    directory = args.output.resolve()
    if not directory.is_relative_to((ROOT / "output").resolve()) or directory.exists():
        parser.error("새로운 프로젝트 output 하위 폴더를 지정하세요.")
    for source in args.source:
        if source.suffix.lower() != ".show" or not source.is_file():
            parser.error("존재하는 SHOW 파일을 지정하세요.")
    if process_pids("HShow.exe") or process_pids("POWERPNT.EXE"):
        parser.error("한쇼와 PowerPoint를 먼저 저장하고 닫아 주세요.")
    directory.mkdir(parents=True)
    configure_logging()
    report = run(directory, args.source)
    (directory / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    LOGGER.info("검증 완료 pipeline=%s fidelity_exact=%s report=%s",
                report["pipeline_passed"], report["fidelity_exact"], directory / "report.json")
    return 0 if report["pipeline_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
