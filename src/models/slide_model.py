"""스레드 사이에서 전달할 슬라이드 데이터. COM 참조를 담지 않는다."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SlideItem:
    source_file: str
    source_file_name: str
    slide_index: int
    slide_id: int
    thumbnail_path: str | None = None
    title: str | None = None
