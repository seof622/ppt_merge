"""PPTX에 저장된 슬라이드 본문을 읽는다. 워커 스레드에서만 호출한다."""

import logging
import posixpath
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree as ET


def read_slide_texts(path, cancel=lambda: False) -> dict[int, str]:
    texts = {}
    try:
        with ZipFile(path) as archive:
            def xml(name):
                if archive.getinfo(name).file_size > 8 * 1024 * 1024:
                    raise ValueError("슬라이드 검색용 XML이 너무 큽니다.")
                return ET.fromstring(archive.read(name))
            rels = {r.attrib['Id']: r.attrib['Target']
                    for r in xml('ppt/_rels/presentation.xml.rels')
                    if r.attrib.get('TargetMode') != 'External'}
            presentation = xml('ppt/presentation.xml')
            ns = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}
            rid = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
            for number, slide in enumerate(presentation.findall('p:sldIdLst/p:sldId', ns), 1):
                if cancel():
                    break
                target = rels[slide.attrib[rid]]
                name = posixpath.normpath(target.lstrip('/') if target.startswith('/')
                                         else posixpath.join('ppt', target))
                root = xml(name)
                texts[number] = ' '.join(node.text or '' for node in root.iter()
                                         if node.tag.endswith('}t')).casefold()
    except (OSError, BadZipFile, KeyError, ValueError, ET.ParseError):
        logging.getLogger('ppt_merge.search').debug('본문 검색 자료를 읽지 못했습니다: %s', path)
    return texts
