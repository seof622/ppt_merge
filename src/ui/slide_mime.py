"""동일 창의 슬라이드 보기와 출력 목록 사이에서 사용할 드래그 데이터."""

from dataclasses import asdict
import json

from PySide6.QtCore import QMimeData

from src.models.slide_model import SlideItem

SLIDE_MIME = "application/x-ppt-merge-slides"


def make_slide_mime(token: str, slides: tuple[SlideItem, ...], *,
                    origin: str = "source", revision: int = 0, rows: tuple[int, ...] = ()) -> QMimeData:
    mime = QMimeData()
    payload = {"token": token, "origin": origin, "revision": revision, "rows": rows,
               "slides": [asdict(slide) for slide in slides]}
    mime.setData(SLIDE_MIME, json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    return mime


def read_slide_mime(mime: QMimeData, token: str) -> dict | None:
    if not mime.hasFormat(SLIDE_MIME):
        return None
    try:
        payload = json.loads(bytes(mime.data(SLIDE_MIME)).decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("token") != token:
            return None
        slides = tuple(SlideItem(**item) for item in payload["slides"])
        if not slides or any(not isinstance(slide.slide_index, int) or slide.slide_index < 1
                             for slide in slides):
            return None
        payload["slides"] = slides
        if not isinstance(payload["origin"], str) or not isinstance(payload["revision"], int):
            return None
        rows = payload["rows"]
        if not isinstance(rows, list) or any(type(row) is not int or row < 0 for row in rows):
            return None
        return payload
    except (ValueError, TypeError, KeyError, UnicodeDecodeError):
        return None
