"""스레드 사이에서 전달할 슬라이드 데이터. COM 참조를 담지 않는다."""

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class SlideBackground:
    color: str | None = None
    image_path: str | None = None

    def __post_init__(self) -> None:
        if self.image_path is None:
            if not isinstance(self.color, str) or re.fullmatch(r"#[0-9a-fA-F]{6}", self.color) is None:
                raise ValueError("배경색은 RGB 색상이어야 합니다.")
            object.__setattr__(self, "color", self.color.upper())
        elif self.color is not None or not isinstance(self.image_path, str) or not self.image_path:
            raise ValueError("배경은 단색 또는 이미지 중 하나여야 합니다.")


@dataclass(frozen=True)
class SlideItem:
    source_file: str
    source_file_name: str
    slide_index: int
    slide_id: int
    thumbnail_path: str | None = None
    title: str | None = None
    source_revision: str | None = None
    background: SlideBackground | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "SlideItem":
        background = data.get("background")
        if background is not None:
            data = {**data, "background": SlideBackground(**background)}
        return cls(**data)
