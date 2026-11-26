"""작업에 쓸 배경 이미지를 저장하고 PowerPoint 슬라이드에 채우기를 적용한다."""

from pathlib import Path
import shutil
import tempfile
from typing import Any

from PIL import Image

from src.models.slide_model import SlideBackground
from src.ppt.errors import CancelCallback, PowerPointError
from src.ppt.source_validation import file_hash


def import_background_image(source: Path, directory: Path) -> SlideBackground:
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".import-", dir=directory) as folder:
            staged = Path(folder) / "image"
            shutil.copyfile(source, staged)
            try:
                with Image.open(staged) as image:
                    extension = {"PNG": ".png", "JPEG": ".jpg"}.get(image.format)
                    if extension is None:
                        raise ValueError("지원되지 않는 이미지 형식")
                    image.verify()
            except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as error:
                raise PowerPointError("읽을 수 있는 PNG 또는 JPEG 이미지를 선택해 주세요.") from error
            digest = file_hash(staged)
            target = directory.resolve() / (digest + extension)
            if not target.is_file() or file_hash(target) != digest:
                staged.replace(target)
            return SlideBackground(image_path=str(target))
    except OSError as error:
        raise PowerPointError("배경 이미지 파일을 읽거나 작업 폴더에 저장하지 못했습니다.") from error


def validate_background_image(image_path: str, cancel: CancelCallback | None = None) -> None:
    path = Path(image_path)
    try:
        if path.suffix in (".png", ".jpg") and file_hash(path, cancel) == path.stem:
            return
    except OSError as error:
        raise PowerPointError("작업에 저장한 배경 이미지를 읽을 수 없습니다. 배경 이미지를 다시 선택해 주세요.") from error
    raise PowerPointError("작업에 저장한 배경 이미지가 변경되었습니다. 배경 이미지를 다시 선택해 주세요.")


def set_slide_background(slide: Any, background: SlideBackground) -> None:
    slide.FollowMasterBackground = False
    fill = slide.Background.Fill
    if background.color is not None:
        fill.Solid()
        fill.ForeColor.RGB = int.from_bytes(bytes.fromhex(background.color[1:]), "little")
        fill.Transparency = 0
    else:
        fill.UserPicture(background.image_path)
