"""COM 삽입에서 누락되는 개별 배경을 원본 OOXML 그대로 복원한다."""

from __future__ import annotations

from contextlib import ExitStack
import hashlib
import os
from pathlib import Path, PurePosixPath
import posixpath
import tempfile
from xml.dom import minidom
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from src.models.slide_model import SlideItem
from src.ppt.errors import CancelCallback, GenerationError, check_cancel

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
XMLNS = "http://www.w3.org/2000/xmlns/"


def _part(owner: str, target: str) -> str:
    name = posixpath.normpath(posixpath.join(posixpath.dirname(owner), target))
    if target.startswith("/"):
        name = target.lstrip("/")
    if name.startswith("../") or name == "..":
        raise GenerationError("배경 이미지의 파일 참조가 올바르지 않습니다.")
    return name


def _rels_part(owner: str) -> str:
    path = PurePosixPath(owner)
    return str(path.parent / "_rels" / (path.name + ".rels"))


def _slide_parts(archive: ZipFile) -> list[tuple[int, str]]:
    presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
    relationships = ET.fromstring(archive.read("ppt/_rels/presentation.xml.rels"))
    targets = {rel.get("Id"): rel.get("Target") for rel in relationships}
    return [(int(slide.attrib["id"]), _part("ppt/presentation.xml", targets[slide.get(f"{{{R}}}id")]))
            for slide in presentation.find(f"{{{P}}}sldIdLst")]


def _child(node, namespace: str, name: str):
    return next((child for child in node.childNodes
                 if child.nodeType == child.ELEMENT_NODE
                 and child.namespaceURI == namespace and child.localName == name), None)


def _background(archive: ZipFile, part: str):
    document = minidom.parseString(archive.read(part))
    common = _child(document.documentElement, P, "cSld")
    return _child(common, P, "bg") if common is not None else None


def _content_type(types: ET.Element, part: str) -> str:
    overrides = {element.get("PartName"): element.get("ContentType")
                 for element in types.findall(f"{{{CT}}}Override")}
    defaults = {element.get("Extension"): element.get("ContentType")
                for element in types.findall(f"{{{CT}}}Default")}
    value = overrides.get("/" + part) or defaults.get(PurePosixPath(part).suffix.lstrip("."))
    if not value:
        raise GenerationError("배경 이미지의 파일 형식을 확인하지 못했습니다.")
    return value


def _package_element(document, namespace: str, name: str, attributes: dict[str, str]):
    """관계·형식 파일의 기존 접두사 표기를 유지해 다른 Office에서도 읽게 한다."""
    prefix = document.documentElement.prefix
    element = document.createElementNS(namespace, f"{prefix}:{name}" if prefix else name)
    for key, value in attributes.items():
        element.setAttribute(key, value)
    return element


def restore_slide_backgrounds(slides: tuple[SlideItem, ...], target: Path,
                              cancel: CancelCallback | None = None) -> int:
    """배경 XML과 이미지 바이트를 복사한다. 도형·마스터·애니메이션은 COM 결과를 유지한다."""
    updates: dict[str, bytes] = {}
    with ExitStack() as stack:
        sources = {}
        backgrounds = []
        for number, item in enumerate(slides):
            check_cancel(cancel)
            key = str(Path(item.source_file).resolve())
            if key not in sources:
                archive = stack.enter_context(ZipFile(key))
                sources[key] = (archive, dict(_slide_parts(archive)))
            archive, parts = sources[key]
            part = parts[item.slide_id]
            background = _background(archive, part)
            if background is not None:
                backgrounds.append((number, archive, part, background))
        if not backgrounds:
            return 0

        output = stack.enter_context(ZipFile(target))
        output_parts = _slide_parts(output)
        types = minidom.parseString(output.read("[Content_Types].xml"))
        known_types = {element.getAttribute("PartName"): element
                       for element in types.getElementsByTagNameNS(CT, "Override")}
        for number, source, source_part, background in backgrounds:
            check_cancel(cancel)
            destination_part = output_parts[number][1]
            document = minidom.parseString(output.read(destination_part))
            common = _child(document.documentElement, P, "cSld")
            if common is None:
                raise GenerationError("출력 슬라이드의 배경을 복원하지 못했습니다.")
            copied = document.importNode(background, True)
            # mc:Ignorable 등의 접두사 문자열도 유효하도록 원본 네임스페이스를 보존한다.
            ancestors = []
            ancestor = background
            while ancestor.nodeType == ancestor.ELEMENT_NODE:
                ancestors.append(ancestor)
                ancestor = ancestor.parentNode
            for ancestor in reversed(ancestors):
                for attribute in ancestor.attributes.values():
                    if attribute.namespaceURI == XMLNS:
                        copied.setAttributeNS(XMLNS, attribute.name, attribute.value)

            rels_part = _rels_part(destination_part)
            rels = minidom.parseString(output.read(rels_part) if rels_part in output.namelist()
                                      else f'<Relationships xmlns="{REL}"/>')
            source_rels_part = _rels_part(source_part)
            source_rels = (ET.fromstring(source.read(source_rels_part))
                           if source_rels_part in source.namelist() else [])
            originals = {rel.get("Id"): rel for rel in source_rels}
            used_ids = {rel.getAttribute("Id") for rel in rels.getElementsByTagNameNS(REL, "Relationship")}
            mapped = {}
            for element in [copied, *copied.getElementsByTagName("*")]:
                for attribute in list(element.attributes.values()):
                    if attribute.namespaceURI != R:
                        continue
                    old_id = attribute.value
                    if old_id not in mapped:
                        original = originals.get(old_id)
                        if original is None or original.get("Type") != R + "/image":
                            raise GenerationError("배경 이미지의 연결 정보를 확인하지 못했습니다.")
                        relationship = dict(original.attrib)
                        index = 1
                        while f"rIdBackground{index}" in used_ids:
                            index += 1
                        new_id = f"rIdBackground{index}"
                        used_ids.add(new_id)
                        relationship["Id"] = new_id
                        if original.get("TargetMode") != "External":
                            image_part = _part(source_part, original.attrib["Target"])
                            data = source.read(image_part)
                            digest = hashlib.sha256(data).hexdigest()
                            name = f"ppt/media/background_{digest}{PurePosixPath(image_part).suffix}"
                            if name in output.namelist() and output.read(name) != data:
                                raise GenerationError("배경 이미지의 저장 경로가 충돌했습니다.")
                            updates[name] = data
                            relationship["Target"] = posixpath.relpath(name, posixpath.dirname(destination_part))
                            content_type = _content_type(ET.fromstring(source.read("[Content_Types].xml")), image_part)
                            if "/" + name not in known_types:
                                override = _package_element(types, CT, "Override",
                                    {"PartName": "/" + name, "ContentType": content_type})
                                types.documentElement.appendChild(override)
                                known_types["/" + name] = override
                        rels.documentElement.appendChild(_package_element(rels, REL, "Relationship", relationship))
                        mapped[old_id] = new_id
                    element.setAttributeNS(R, attribute.name, mapped[old_id])
            old_background = _child(common, P, "bg")
            if old_background is not None:
                common.replaceChild(copied, old_background)
            else:
                common.insertBefore(copied, common.firstChild)
            updates[destination_part] = document.toxml(encoding="utf-8")
            updates[rels_part] = rels.toxml(encoding="utf-8")
        updates["[Content_Types].xml"] = types.toxml(encoding="utf-8")

        # 원본과 최종 출력에는 쓰지 않고, COM이 닫은 로컬 임시 결과만 교체한다.
        with tempfile.NamedTemporaryFile(prefix="background-", suffix=".pptx", dir=target.parent,
                                         delete=False) as file:
            repaired = Path(file.name)
        try:
            with ZipFile(repaired, "w") as archive:
                archive.comment = output.comment
                for info in output.infolist():
                    check_cancel(cancel)
                    archive.writestr(info, updates.pop(info.filename, None) or output.read(info.filename))
                for name, data in updates.items():
                    check_cancel(cancel)
                    archive.writestr(name, data)
            check_cancel(cancel)
        except BaseException:
            repaired.unlink(missing_ok=True)
            raise
    try:
        os.replace(repaired, target)
    finally:
        repaired.unlink(missing_ok=True)
    return len(backgrounds)
