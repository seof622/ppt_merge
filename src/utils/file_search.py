"""선택한 폴더 아래의 PPT 파일명 검색. COM과 Qt에 의존하지 않는다."""

from collections.abc import Callable
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import time


LOGGER = logging.getLogger("ppt_merge.file_search")


def is_presentation(path: str | Path) -> bool:
    value = Path(path)
    return value.suffix.casefold() in (".pptx", ".pptm") and not value.name.startswith("~$")


@dataclass(frozen=True)
class SearchSummary:
    matches: int = 0
    skipped: int = 0
    limited: bool = False
    cancelled: bool = False


def search_presentations(root: Path, query: str, on_batch: Callable[[tuple[str, ...]], None],
                         cancel: Callable[[], bool], *, limit: int = 2000) -> SearchSummary:
    """하위 폴더를 순회하되 연결 폴더를 따라가지 않고 결과를 묶어 전달한다."""
    needle = query.strip().casefold()
    if not needle:
        return SearchSummary()
    pending = [root]
    batch: list[str] = []
    matches = skipped = 0
    last_emit = time.monotonic()
    while pending:
        if cancel():
            return SearchSummary(matches, skipped, cancelled=True)
        directory = pending.pop()
        try:
            with os.scandir(directory) as entries:
                for entry in entries:
                    if cancel():
                        return SearchSummary(matches, skipped, cancelled=True)
                    try:
                        if entry.is_symlink() or Path(entry.path).is_junction():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(Path(entry.path))
                        elif (entry.is_file(follow_symlinks=False) and is_presentation(entry.name)
                              and needle in entry.name.casefold()):
                            batch.append(entry.path)
                            matches += 1
                            if matches >= limit:
                                on_batch(tuple(batch))
                                return SearchSummary(matches, skipped, limited=True)
                    except OSError:
                        skipped += 1
                        LOGGER.debug("검색 항목 접근 실패: %s", entry.path, exc_info=True)
                    if batch and (len(batch) >= 50 or time.monotonic() - last_emit >= 0.1):
                        on_batch(tuple(batch))
                        batch.clear()
                        last_emit = time.monotonic()
        except OSError:
            skipped += 1
            LOGGER.debug("검색 폴더 접근 실패: %s", directory, exc_info=True)
    if batch and not cancel():
        on_batch(tuple(batch))
    return SearchSummary(matches, skipped, cancelled=cancel())
