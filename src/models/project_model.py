"""Qt나 COM에 의존하지 않는 출력 순서 편집 데이터."""

from dataclasses import dataclass, field
from collections.abc import Iterable

from src.models.slide_model import SlideItem


@dataclass
class OutputSequence:
    """같은 원본 슬라이드도 목록의 각 위치에서 독립적으로 편집한다."""

    slides: list[SlideItem] = field(default_factory=list)

    def _rows(self, rows: Iterable[int]) -> list[int]:
        result = sorted(set(rows))
        if any(not isinstance(row, int) or not 0 <= row < len(self.slides) for row in result):
            raise ValueError("출력 목록의 범위를 벗어난 선택입니다.")
        return result

    def insert(self, slides: Iterable[SlideItem], target: int | None = None) -> list[int]:
        target = len(self.slides) if target is None else target
        if not 0 <= target <= len(self.slides):
            raise ValueError("삽입 위치가 잘못되었습니다.")
        additions = list(slides)
        self.slides[target:target] = additions
        return list(range(target, target + len(additions)))

    def remove(self, rows: Iterable[int]) -> list[int]:
        rows = self._rows(rows)
        if not rows:
            return []
        for row in reversed(rows):
            del self.slides[row]
        return [min(rows[0], len(self.slides) - 1)] if self.slides else []

    def duplicate(self, rows: Iterable[int]) -> list[int]:
        copies = []
        for offset, row in enumerate(self._rows(rows)):
            position = row + offset + 1
            self.slides.insert(position, self.slides[position - 1])
            copies.append(position)
        return copies

    def move(self, rows: Iterable[int], target: int) -> list[int]:
        """삭제 전 목록의 경계 위치로 선택 항목을 순서대로 이동한다."""
        rows = self._rows(rows)
        if not 0 <= target <= len(self.slides):
            raise ValueError("이동 위치가 잘못되었습니다.")
        if not rows:
            return []
        moved = [self.slides[row] for row in rows]
        destination = target - sum(row < target for row in rows)
        for row in reversed(rows):
            del self.slides[row]
        return self.insert(moved, destination)

    def step(self, rows: Iterable[int], direction: int) -> list[int]:
        if direction not in (-1, 1):
            raise ValueError("이동 방향이 잘못되었습니다.")
        selected = set(self._rows(rows))
        order = sorted(selected, reverse=direction == 1)
        for row in order:
            neighbor = row + direction
            if 0 <= neighbor < len(self.slides) and neighbor not in selected:
                self.slides[row], self.slides[neighbor] = self.slides[neighbor], self.slides[row]
                selected.remove(row)
                selected.add(neighbor)
        return sorted(selected)
