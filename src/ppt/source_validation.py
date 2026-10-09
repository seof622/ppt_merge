"""썸네일과 PPT 생성에서 공유하는 원본 검증·변경 감지."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

from src.ppt.errors import CancelCallback, PresentationOpenError, SourceChangedError, check_cancel


def file_hash(path: Path, cancel: CancelCallback | None = None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            check_cancel(cancel)
            digest.update(block)
    return digest.hexdigest()


def fingerprint(path: Path, cancel: CancelCallback | None = None) -> dict[str, Any]:
    before = path.stat()
    digest = file_hash(path, cancel)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise SourceChangedError("작업 중 파일이 변경되었습니다. 저장을 마친 뒤 다시 시도하세요.")
    return {"path": os.path.normcase(str(path)), "size": after.st_size,
            "mtime_ns": after.st_mtime_ns, "sha256": digest}


def revision(identity: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()


def validate_source(path: Path) -> None:
    if path.suffix.lower() not in (".pptx", ".pptm"):
        raise PresentationOpenError("PPTX 또는 PPTM 파일을 선택하세요.")
    if not path.is_file():
        raise PresentationOpenError(f"PowerPoint 파일을 찾을 수 없습니다: {path}")
    try:
        with path.open("rb") as stream:
            if stream.read(8) == bytes.fromhex("D0CF11E0A1B11AE1"):
                raise PresentationOpenError("암호 보호 등으로 자동으로 열 수 없는 PowerPoint 파일입니다.")
        with ZipFile(path) as archive:
            ET.fromstring(archive.read("ppt/presentation.xml"))
            archive.getinfo("ppt/_rels/presentation.xml.rels")
    except (BadZipFile, KeyError, ET.ParseError, RuntimeError) as error:
        if isinstance(error, PresentationOpenError):
            raise
        raise PresentationOpenError("PowerPoint 파일이 손상되었거나 지원되지 않는 형식입니다.") from error
