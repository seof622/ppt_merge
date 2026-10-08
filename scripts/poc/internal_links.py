"""슬라이드 선택·재정렬 후에도 내부 링크가 같은 소스 슬라이드를 가리키도록 연결한다."""

from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger("ppt_merge.poc")


class InternalLinkError(ValueError):
    """대상이 선택되지 않았거나 해석할 수 없는 내부 링크."""


def read_internal_links(presentation: Any, slide: Any) -> list[tuple[int, int]]:
    result = []
    for position, link in enumerate(slide.Hyperlinks, 1):
        if link.Address or not link.SubAddress:
            continue
        subaddress = str(link.SubAddress)
        first = subaddress.split(",", 1)[0]
        target = None
        if "," in subaddress and first.isdecimal():
            try:
                target = presentation.Slides.FindBySlideID(int(first))
            except Exception as error:
                raise InternalLinkError(f"내부 링크 대상 SlideID를 찾지 못했습니다: {subaddress}") from error
        else:
            for candidate in presentation.Slides:
                if candidate.Name == subaddress:
                    target = candidate
                    break
            candidate = None
        if target is None:
            raise InternalLinkError(f"지원되지 않는 내부 링크 형식입니다: {subaddress}")
        result.append((position, int(target.SlideID)))
        target = None
    return result


def reconnect_internal_links(destination: Any,
                             slide_map: dict[tuple[str, int], list[int]],
                             links: list[tuple[int, str, list[tuple[int, int]]]]) -> None:
    slide = target = link = None
    try:
        for output_number, source_key, source_links in links:
            slide = destination.Slides.Item(output_number)
            for link_number, source_target_id in source_links:
                candidates = slide_map.get((source_key, source_target_id), [])
                if not candidates:
                    raise InternalLinkError("내부 링크 대상 슬라이드가 출력 목록에 없습니다. 대상을 함께 선택해 주세요.")
                if len(candidates) > 1:
                    LOGGER.warning("중복 내부 링크 대상: %s #%s, 첫 출력 항목 #%s 사용",
                                   source_key, source_target_id, candidates[0])
                target = destination.Slides.Item(candidates[0])
                link = slide.Hyperlinks.Item(link_number)
                link.Address = ""
                link.SubAddress = f"{target.SlideID},{target.SlideIndex},{target.Name}"
                LOGGER.info("내부 링크 재연결 출력 #%s -> #%s", output_number, target.SlideIndex)
                link = target = None
            slide = None
    finally:
        slide = target = link = None
