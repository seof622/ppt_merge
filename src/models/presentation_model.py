"""소스 프레젠테이션의 일반 Python 데이터."""

from dataclasses import dataclass

from src.models.slide_model import SlideItem


@dataclass(frozen=True)
class PresentationInfo:
    source_file: str
    source_file_name: str
    width_points: float
    height_points: float
    slides: tuple[SlideItem, ...]

    @property
    def slide_count(self) -> int:
        return len(self.slides)
