"""기본 PPT의 결합 방식, 원본 보존, 중복, 오류와 취소 정리를 검증한다."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any

from com_session import ROOT, PowerPointSession, configure_logging
from verify_slides import compare_images, package_signatures, slide_signature

LOGGER = logging.getLogger("ppt_merge.poc")
METHODS = ("copy_paste", "insert_file", "insert_file_design")


class GenerationCancelled(Exception):
    """다음 슬라이드 작업 전에 취소된 생성."""


def merge(session: PowerPointSession, sources: dict[str, Any],
          selection: list[tuple[str, int]], method: str, path: Path,
          cancel_after: int | None = None, fail_after: int | None = None) -> None:
    if path.exists():
        raise FileExistsError(f"기존 결과를 덮어쓰지 않습니다: {path}")
    sizes = {(round(float(sources[key].PageSetup.SlideWidth), 3),
              round(float(sources[key].PageSetup.SlideHeight), 3)) for key, _ in selection}
    if len(sizes) != 1:
        raise ValueError("소스 슬라이드 크기가 다릅니다. 출력 크기를 선택한 뒤 명시적으로 승인해야 합니다.")
    destination = session.new()
    design_cache: dict[tuple[str, int], Any] = {}
    pasted = source = target = design = None
    temporary = path.with_suffix(".partial.pptx")
    if temporary.exists():
        session.close_presentation(destination)
        raise FileExistsError(f"기존 임시 파일을 덮어쓰지 않습니다: {temporary}")
    saved = False
    try:
        width, height = sizes.pop()
        destination.PageSetup.SlideWidth = width
        destination.PageSetup.SlideHeight = height
        for completed, (key, number) in enumerate(selection):
            if cancel_after is not None and completed >= cancel_after:
                raise GenerationCancelled("슬라이드 사이의 안전한 지점에서 취소했습니다.")
            if fail_after is not None and completed >= fail_after:
                raise RuntimeError("정리 검증을 위한 의도적 생성 오류")
            source = sources[key].Slides.Item(number)
            LOGGER.info("슬라이드 복사 method=%s %s #%s %s/%s", method, key, number, completed + 1, len(selection))
            if method == "copy_paste":
                source.Copy()
                pasted = destination.Slides.Paste()
                target = pasted.Item(1)
            else:
                inserted = destination.Slides.InsertFromFile(str(Path(sources[key].FullName)),
                                                            destination.Slides.Count, number, number)
                if inserted != 1:
                    raise RuntimeError("슬라이드 삽입 수가 예상과 다릅니다.")
                target = destination.Slides.Item(destination.Slides.Count)
            if method == "insert_file_design":
                design_key = (key, int(source.Design.Index))
                if design_key not in design_cache:
                    design_cache[design_key] = destination.Designs.Clone(source.Design)
                design = design_cache[design_key]
                target.Design = design
                target.CustomLayout = design.SlideMaster.CustomLayouts.Item(source.CustomLayout.Index)
                target.FollowMasterBackground = source.FollowMasterBackground
            pasted = source = target = design = None
        if destination.Slides.Count != len(selection):
            raise RuntimeError("출력 슬라이드 수가 예상과 다릅니다.")
        destination.SaveAs(str(temporary), 24)
        saved = True
        LOGGER.info("출력 저장 %s", path)
    finally:
        pasted = source = target = design = None
        design_cache.clear()
        try:
            session.close_presentation(destination)
        finally:
            destination = None
            if not saved:
                temporary.unlink(missing_ok=True)
    temporary.rename(path)


def inspect_deck(session: PowerPointSession, path: Path, render_dir: Path) -> list[dict[str, Any]]:
    render_dir.mkdir(parents=True, exist_ok=True)
    presentation = session.open(path)
    result = []
    try:
        for number in range(1, presentation.Slides.Count + 1):
            slide = presentation.Slides.Item(number)
            result.append(slide_signature(slide))
            slide.Export(str(render_dir / f"slide_{number}.png"), "PNG", 1280, 720)
            slide = None
    finally:
        session.close_presentation(presentation)
        presentation = None
    return result


def run(fixtures: Path, directory: Path) -> dict[str, Any]:
    baseline = {}
    with PowerPointSession() as session:
        for key in ("A", "B"):
            path = fixtures / f"{key}.pptx"
            baseline[key] = {"com": inspect_deck(session, path, directory / "renders" / key),
                             "package": package_signatures(path)}
    source_cleanup = session.cleanup
    selections = {
        "demo": [("A", 2), ("B", 4), ("A", 1)],
        "coverage": [(key, i) for key in ("A", "B") for i in range(1, 5)] + [("A", 2)],
    }
    cases = []
    for method in METHODS:
        for label, selection in selections.items():
            session = PowerPointSession()
            output = directory / f"{label}_{method}.pptx"
            sources = {}
            error = None
            actual = []
            try:
                with session:
                    try:
                        sources = {key: session.open(fixtures / f"{key}.pptx") for key in ("A", "B")}
                        merge(session, sources, selection, method, output)
                        sources.clear()
                        actual = inspect_deck(session, output, directory / "renders" / f"{label}_{method}")
                    finally:
                        sources.clear()
            except Exception as exception:
                LOGGER.exception("결합 방식 검증 실패 %s %s", method, label)
                error = str(exception)
            comparisons = []
            if actual:
                parts = package_signatures(output)
                for i, (key, number) in enumerate(selection):
                    expected = baseline[key]["com"][number - 1]
                    # 새 프레젠테이션은 내부 Slide.Name을 재할당한다.
                    # 실제 순서는 제목을 포함한 전체 도형 내용으로 검증한다.
                    changed = [field for field in expected
                               if field != "name" and actual[i][field] != expected[field]]
                    image = compare_images(directory / "renders" / key / f"slide_{number}.png",
                                           directory / "renders" / f"{label}_{method}" / f"slide_{i + 1}.png")
                    comparisons.append({"output_slide": i + 1, "source": f"{key}-{number}",
                                        "source_slide_name": expected["name"],
                                        "output_slide_name": actual[i]["name"],
                                        "changed_fields": changed,
                                        "package_equal": parts[i] == baseline[key]["package"][number - 1],
                                        "render": image})
            passed = (bool(comparisons) and error is None and len(actual) == len(selection)
                      and all(not row["changed_fields"] and row["package_equal"] and row["render"]["equal"]
                              for row in comparisons)
                      and session.cleanup.get("owned_process_exited", False)
                      and not session.cleanup.get("errors"))
            cases.append({"method": method, "case": label, "passed": passed,
                          "output": str(output), "error": error,
                          "comparisons": comparisons, "cleanup": session.cleanup})
            LOGGER.info("비교 결과 %s %s passed=%s", method, label, passed)

    reliability = []
    for label in ("cancel", "exception", "missing_file", "mixed_size", "ten_sources"):
        session = PowerPointSession()
        sources = {}
        expected_error = None
        outcome = "unexpected_success"
        target = directory / f"reliability_{label}.pptx"
        try:
            with session:
                try:
                    sources = {key: session.open(fixtures / f"{key}.pptx") for key in ("A", "B")}
                    if label == "missing_file":
                        try:
                            session.open(fixtures / "does_not_exist.pptx")
                        except FileNotFoundError as exception:
                            expected_error = str(exception)
                        merge(session, sources, selections["demo"], "insert_file_design", target)
                        outcome = "other_sources_usable" if expected_error else "missing_error_not_detected"
                    elif label == "mixed_size":
                        sources["C"] = session.open(fixtures / "C_4x3.pptx")
                        merge(session, sources, [("A", 1), ("C", 1)], "insert_file_design", target)
                    elif label == "ten_sources":
                        import shutil
                        local_sources = directory / "ten_sources"
                        local_sources.mkdir()
                        for i in range(10):
                            copy = local_sources / f"source_{i + 1}.pptx"
                            shutil.copyfile(fixtures / "A.pptx", copy)
                            session.open(copy)
                        outcome = "opened_ten_sources"
                    else:
                        merge(session, sources, selections["coverage"], "insert_file_design", target,
                              cancel_after=1 if label == "cancel" else None,
                              fail_after=1 if label == "exception" else None)
                finally:
                    sources.clear()
        except (GenerationCancelled, RuntimeError, ValueError) as exception:
            expected_error = str(exception)
            outcome = "expected_error" if (
                (label == "cancel" and isinstance(exception, GenerationCancelled))
                or (label == "exception" and str(exception) == "정리 검증을 위한 의도적 생성 오류")
                or (label == "mixed_size" and isinstance(exception, ValueError))) else "unexpected_error"
        cleanup_ok = session.cleanup.get("owned_process_exited", False) and not session.cleanup.get("errors")
        file_ok = label == "missing_file" or (not target.exists() and not target.with_suffix(".partial.pptx").exists())
        passed = outcome in ("expected_error", "other_sources_usable", "opened_ten_sources") and cleanup_ok and file_ok
        reliability.append({"case": label, "passed": passed, "outcome": outcome,
                            "error": expected_error, "cleanup": session.cleanup})
    # 사용자의 세션을 대신할 별도 소유 세션을 만든 후, PoC가 접근을 거부하는지 검증한다.
    owner = PowerPointSession()
    blocked = PowerPointSession()
    protected = False
    with owner:
        sentinel = owner.new()
        slide = sentinel.Slides.Add(1, 12)
        slide.Name = "USER_SESSION_SENTINEL"
        slide = None
        try:
            with blocked:
                raise AssertionError("기존 PowerPoint 세션을 보호하지 못했습니다.")
        except RuntimeError as exception:
            protected = (blocked.before == {owner.pid}
                         and sentinel.Slides.Count == 1
                         and sentinel.Slides.Item(1).Name == "USER_SESSION_SENTINEL")
            LOGGER.info("기존 세션 보호: %s", exception)
        sentinel = None
    reliability.append({"case": "existing_session_protected", "passed": protected and owner.cleanup["owned_process_exited"],
                        "outcome": "safely_refused_existing_session", "cleanup": owner.cleanup,
                        "limitation": "현재 PoC는 기존 PowerPoint가 열려 있으면 실행을 거부한다. 동시 실행 지원은 후속 과제다."})
    return {"fixtures": str(fixtures), "directory": str(directory), "source_cleanup": source_cleanup,
            "cases": cases, "reliability": reliability,
            "not_tested": ["SVG", "SmartArt", "Excel-linked charts", "embedded OLE objects", "audio", "video",
                           "internal slide links", "pptm", "motion animation", "password protected or corrupted files"],
            "manual_review_required": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=ROOT / "tests/fixtures/basic")
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args()
    configure_logging()
    directory = args.output_directory or ROOT / "output" / f"poc_{datetime.now():%Y%m%d_%H%M%S}"
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    report = run(args.fixtures.resolve(), directory)
    path = directory / "report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    LOGGER.info("검증 보고서 %s", path)
    if not all(case["passed"] for case in report["reliability"]):
        raise SystemExit("신뢰성 검증 실패: report.json을 확인하세요.")
    if not any(all(case["passed"] for case in report["cases"] if case["method"] == method) for method in METHODS):
        raise SystemExit("모든 결합 방식에서 차이가 발견되었습니다. report.json을 확인하세요.")


if __name__ == "__main__":
    main()
