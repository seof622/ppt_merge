"""썸네일과 PPT 생성에서 공유하는 원본 검증·변경 감지."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
import posixpath
from typing import Any
from urllib.parse import unquote, urlsplit
from zipfile import BadZipFile, ZipFile
import zlib
import xml.etree.ElementTree as ET

from src.ppt.errors import (CancelCallback, PresentationOpenError, SourceChangedError,
                            check_cancel, file_error_message, PowerPointError)

LOGGER = logging.getLogger("ppt_merge.validation")
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


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


def validate_source(path: Path, cancel: CancelCallback | None = None) -> None:
    """Office 복구·암호 창이 뜨기 전에 패키지 CRC·XML·내부 참조를 확인한다."""
    check_cancel(cancel)
    if path.suffix.lower() not in (".pptx", ".pptm"):
        raise PresentationOpenError("PPTX 또는 PPTM 파일을 선택하세요.")
    if not path.is_file():
        raise PresentationOpenError(f"PowerPoint 파일을 찾을 수 없습니다: {path}")
    try:
        with path.open("rb") as stream:
            if stream.read(8) == bytes.fromhex("D0CF11E0A1B11AE1"):
                raise PresentationOpenError("암호 보호 등으로 자동으로 열 수 없는 PowerPoint 파일입니다.")
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            if len(names) != len(archive.infolist()):
                raise BadZipFile("중복 패키지 항목")
            for required in ("[Content_Types].xml", "_rels/.rels", "ppt/presentation.xml",
                             "ppt/_rels/presentation.xml.rels"):
                archive.getinfo(required)
            relationships = {}
            presentation = None
            for entry in archive.infolist():
                check_cancel(cancel)
                if entry.is_dir():
                    continue
                # 전체 미디어를 메모리에 올리지 않고 EOF까지 읽어 CRC를 검사한다.
                with archive.open(entry) as stream:
                    while stream.read(1024 * 1024):
                        check_cancel(cancel)
                if entry.filename.endswith((".xml", ".rels")):
                    with archive.open(entry) as stream:
                        xml = ET.parse(stream).getroot()
                    if entry.filename == "ppt/presentation.xml":
                        presentation = xml
                    if entry.filename.endswith(".rels"):
                        directory = posixpath.dirname(posixpath.dirname(entry.filename))
                        targets = {}
                        for rel in xml:
                            key = rel.attrib["Id"]
                            if key in targets:
                                raise BadZipFile("중복 관계 ID")
                            if rel.attrib.get("TargetMode") == "External":
                                targets[key] = None
                                continue
                            target = unquote(urlsplit(rel.attrib["Target"]).path)
                            part = posixpath.normpath(posixpath.join(directory, target)).lstrip("/")
                            if part not in names:
                                raise BadZipFile(f"누락된 내부 참조: {part}")
                            targets[key] = (part, rel.attrib["Type"].rsplit("/", 1)[-1])
                        relationships[entry.filename] = targets
            if presentation is None or presentation.tag != P + "presentation":
                raise BadZipFile("프레젠테이션 정보 없음")
            if ("ppt/presentation.xml", "officeDocument") not in relationships["_rels/.rels"].values():
                raise BadZipFile("루트 프레젠테이션 참조 없음")
            targets = relationships["ppt/_rels/presentation.xml.rels"]
            seen = set()
            for slide in presentation.findall(P + "sldIdLst/" + P + "sldId"):
                target = targets[slide.attrib[R + "id"]]
                slide_id = int(slide.attrib["id"])
                if target is None or target[1] != "slide" or slide_id in seen:
                    raise BadZipFile("슬라이드 참조 정보 오류")
                seen.add(slide_id)
    except PowerPointError:
        raise
    except OSError as error:
        LOGGER.exception("원본 파일 접근 실패 %s", path)
        raise PresentationOpenError(file_error_message(error)) from error
    except (BadZipFile, KeyError, ValueError, ET.ParseError, RuntimeError, zlib.error, EOFError) as error:
        LOGGER.exception("원본 패키지 검증 실패 %s", path)
        raise PresentationOpenError("PowerPoint 파일이 손상되었거나 지원되지 않는 형식입니다.") from error
