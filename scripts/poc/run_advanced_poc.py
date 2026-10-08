"""고급 요소 보존과 내부 슬라이드 링크의 재연결을 실제 PowerPoint로 검증한다."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from com_session import ROOT, PowerPointSession, configure_logging
from internal_links import InternalLinkError
from run_poc import inspect_deck, merge
from verify_slides import advanced_package_signatures, compare_images

LOGGER = logging.getLogger("ppt_merge.poc")


def run(fixtures: Path, directory: Path, selected_cases: list[str] | None = None) -> dict[str, Any]:
    paths = {"G": fixtures / "advanced.pptx", "M": fixtures / "advanced_container.pptm",
             "A": ROOT / "tests/fixtures/basic/A.pptx"}
    baseline = {}
    session = PowerPointSession()
    with session:
        for key, path in paths.items():
            baseline[key] = {"com": inspect_deck(session, path, directory / "renders" / key),
                             "package": advanced_package_signatures(path)}
    source_cleanup = session.cleanup
    with ZipFile(paths["G"]) as archive:
        names = archive.namelist()
        presence = {"svg": any(name.endswith(".svg") for name in names),
                    "audio": any(name.endswith(".wav") for name in names),
                    "video": any(name.endswith(".mp4") for name in names),
                    "smartart": any(name.startswith("ppt/diagrams/data") for name in names)}
    presence.update({"embedded_ole": any("ole_progid" in shape and shape["type"] == 7
                                         for slide in baseline["G"]["com"] for shape in slide["shapes"]),
                     "linked_ole_chart": any(shape["name"] == "linked_excel_chart"
                                             and shape.get("ole_progid", "").startswith("Excel.")
                                             and shape["type"] == 10 and "source_data.xlsx!TestData!" in shape["linked_source"]
                                             for slide in baseline["G"]["com"] for shape in slide["shapes"]),
                     "motion_path": bool(baseline["G"]["package"][8]["motion_paths"]),
                     "internal_link": baseline["G"]["package"][4]["internal_link_target_indices"] == [6]})
    if not all(presence.values()):
        raise RuntimeError(f"검증 자료에 필요한 요소가 없습니다: {presence}")

    reorder = [("G", i) for i in (5, 1, 6, 2, 3, 4, 7, 8, 9, 1)]
    selections = [
        ("original_method", reorder, False),
        ("result", reorder, True),
        ("duplicates", [("G", i) for i in (6, 5, 6, 5, 2, 3, 4, 7, 8, 9, 1)] + [("A", 2)], True),
        ("pptm", [("M", i) for i in (5, 1, 6, 2, 3, 4, 7, 8, 9)], True),
        ("cross_source", [("G", 5), ("M", 6), ("G", 6), ("M", 5), ("G", 2), ("M", 2)], True),
    ]
    if selected_cases is not None:
        selections = [case for case in selections if case[0] in selected_cases]
    cases = []
    for label, selection, remap in selections:
        sources = {}
        output = directory / f"{label}.pptx"
        session = PowerPointSession()
        error = None
        actual = []
        try:
            with session:
                try:
                    sources = {key: session.open(paths[key]) for key in {key for key, _ in selection}}
                    merge(session, sources, selection, "insert_file_design", output, remap_links=remap)
                    sources.clear()
                    actual = inspect_deck(session, output, directory / "renders" / label)
                finally:
                    sources.clear()
        except Exception as exception:
            error = str(exception)
            LOGGER.exception("고급 검증 실패 %s", label)
        rows = []
        if actual:
            parts = advanced_package_signatures(output)
            for index, (key, number) in enumerate(selection):
                expected = baseline[key]["com"][number - 1]
                expected_package = baseline[key]["package"][number - 1]
                changed = [field for field in expected if field not in ("name", "hyperlinks")
                           and expected[field] != actual[index][field]]
                changed_parts = [field for field in expected_package if field != "internal_link_target_indices"
                                 and expected_package[field] != parts[index][field]]
                expected_targets = [next((position + 1 for position, candidate in enumerate(selection)
                                         if candidate == (key, target)), None)
                                    for target in expected_package["internal_link_target_indices"]]
                link_ok = parts[index]["internal_link_target_indices"] == expected_targets
                image = compare_images(directory / "renders" / key / f"slide_{number}.png",
                                       directory / "renders" / label / f"slide_{index + 1}.png")
                rows.append({"output_slide": index + 1, "source": f"{key}-{number}",
                             "changed_fields": changed, "changed_package_fields": changed_parts,
                             "render": image, "links_correct": link_ok,
                             "expected_internal_targets": expected_targets,
                             "actual_internal_targets": parts[index]["internal_link_target_indices"]})
        passed = (bool(rows) and error is None and len(actual) == len(selection)
                  and all(not row["changed_fields"] and not row["changed_package_fields"]
                          and row["render"]["equal"] and row["links_correct"] for row in rows)
                  and session.cleanup.get("owned_process_exited", False)
                  and not session.cleanup.get("errors"))
        cases.append({"case": label, "passed": passed, "remap_links": remap,
                      "output": str(output), "comparisons": rows, "error": error, "cleanup": session.cleanup})
        LOGGER.info("고급 검증 %s passed=%s", label, passed)

    session = PowerPointSession()
    sources = {}
    rejected = False
    missing_path = directory / "missing_link_target.pptx"
    with session:
        try:
            sources["G"] = session.open(paths["G"])
            try:
                merge(session, sources, [("G", 5), ("G", 1)], "insert_file_design", missing_path, remap_links=True)
            except InternalLinkError:
                rejected = True
        finally:
            sources.clear()
    missing = {"passed": rejected and not missing_path.exists()
               and not missing_path.with_suffix(".partial.pptx").exists()
               and session.cleanup["owned_process_exited"], "cleanup": session.cleanup}
    return {"directory": str(directory), "fixtures": str(fixtures), "feature_presence": presence,
            "source_cleanup": source_cleanup, "cases": cases, "missing_link_target": missing,
            "duplicate_target_policy": "first occurrence in output sequence",
            "pptm_contains_vba": False, "manual_review_required": True,
            "linked_chart_kind": "Excel.Sheet.12 linked OLE chart"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=ROOT / "tests/fixtures/advanced")
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--cases", nargs="+", choices=("original_method", "result", "duplicates", "pptm", "cross_source"))
    args = parser.parse_args()
    configure_logging()
    directory = (args.output_directory or ROOT / "output" / f"advanced_{datetime.now():%Y%m%d_%H%M%S}").resolve()
    directory.mkdir(parents=True, exist_ok=False)
    report = run(args.fixtures.resolve(), directory, args.cases)
    (directory / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    LOGGER.info("고급 검증 보고서 %s", directory / "report.json")
    if not report["missing_link_target"]["passed"] or not all(case["passed"] for case in report["cases"] if case["remap_links"]):
        raise SystemExit("고급 보존 검증에서 차이가 발견되었습니다. report.json을 확인하세요.")


if __name__ == "__main__":
    main()
