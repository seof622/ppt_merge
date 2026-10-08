"""PPT 썸네일과 캐시를 생성하고 확인용 이미지·JSON을 저장한다."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import json
import logging
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFont

from src.ppt.errors import PowerPointError
from src.ppt.thumbnail_service import ThumbnailProgress, ThumbnailResult, ThumbnailService
from src.utils.logger import configure_logging

LOGGER = logging.getLogger("ppt_merge.export_thumbnails")


def write_preview(results: list[ThumbnailResult], target: Path) -> None:
    """실제 앱 화면과 별개인 정적 썸네일 확인 이미지."""
    # 대용량 입력에서도 확인 이미지가 과도하게 커지지 않도록 첫 36장만 보여 준다.
    slides = [slide for result in results for slide in result.presentation.slides][:36]
    if not slides:
        return
    columns = 3
    tile_width, tile_height = 480, 400
    image = Image.new("RGB", (columns * tile_width, ((len(slides) + columns - 1) // columns) * tile_height), "#e5e7eb")
    draw = ImageDraw.Draw(image)
    font_path = Path("C:/Windows/Fonts/malgun.ttf")
    font = ImageFont.truetype(str(font_path), 18) if font_path.exists() else ImageFont.load_default()
    for position, slide in enumerate(slides):
        left, top = (position % columns) * tile_width, (position // columns) * tile_height
        with Image.open(slide.thumbnail_path) as source:
            thumbnail = source.convert("RGB")
            thumbnail.thumbnail((460, 345))
            image.paste(thumbnail, (left + (tile_width - thumbnail.width) // 2, top + 10))
        draw.text((left + 10, top + 365), f"{slide.source_file_name} / {slide.slide_index}", font=font, fill="#111827")
    image.save(target, "PNG")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", nargs="+", type=Path)
    parser.add_argument("--width", type=int, default=480)
    parser.add_argument("--cache-root", type=Path, default=ROOT / "cache")
    args = parser.parse_args()
    configure_logging(ROOT / "logs")
    service = ThumbnailService(args.cache_root, args.width)

    def progress(event: ThumbnailProgress) -> None:
        LOGGER.info("%s %s %s/%s", Path(event.source_file).name, event.stage, event.completed, event.total)

    results = []
    failures = []
    # 추후 QThread에서도 동일하게 워커 안에서 생성·종료한다. COM 참조는 반환하지 않는다.
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="ppt-thumbnails") as worker:
        for source in args.sources:
            try:
                results.append(worker.submit(service.load, source, progress).result())
            except PowerPointError as error:
                LOGGER.error("썸네일 생성 실패 %s: %s", source, error)
                failures.append({"source": str(source.resolve()), "error": str(error)})
    (ROOT / "output").mkdir(exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="thumbnails_", dir=ROOT / "output"))
    (directory / "report.json").write_text(
        json.dumps({"results": [asdict(result) for result in results], "failures": failures},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    write_preview(results, directory / "preview.png")
    LOGGER.info("확인 자료 저장 %s", directory)
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
