"""CRC, XML, 관계 누락과 취소를 Office 실행 전에 검증한다."""
from pathlib import Path
import struct
import tempfile
import unittest
from zipfile import ZipFile

from src.ppt.errors import OperationCancelled, PresentationOpenError
from src.ppt.source_validation import validate_source
from tests.unit.test_generation_service import write_deck


class SourceValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / "원본.pptx"
        write_deck(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def rewrite(self, transform):
        with ZipFile(self.path) as archive:
            parts = [(info, archive.read(info)) for info in archive.infolist()]
        with ZipFile(self.path, "w") as archive:
            for info, data in parts:
                replacement = transform(info.filename, data)
                if replacement is not None:
                    archive.writestr(info, replacement)

    def test_valid_deck_and_external_targets(self):
        self.rewrite(lambda name, data: data.replace(b'</Relationships>',
            b'<Relationship Id="external" Type="hyperlink" Target="https://example.com/no-part" TargetMode="External"/></Relationships>')
            if name.endswith(".rels") else data)
        validate_source(self.path)

    def test_missing_slide_part_rejected(self):
        self.rewrite(lambda name, data: None if name == "ppt/slides/slide1.xml" else data)
        with self.assertRaisesRegex(PresentationOpenError, "손상"):
            validate_source(self.path)

    def test_missing_package_root_rejected(self):
        self.rewrite(lambda name, data: None if name == "[Content_Types].xml" else data)
        with self.assertRaises(PresentationOpenError):
            validate_source(self.path)

    def test_wrong_root_presentation_rejected(self):
        self.rewrite(lambda name, data: data.replace(b"officeDocument", b"image") if name == "_rels/.rels" else data)
        with self.assertRaises(PresentationOpenError):
            validate_source(self.path)

    def test_slide_id_missing_relationship_rejected(self):
        self.rewrite(lambda name, data: data.replace(b'r:id="rId1"', b'r:id="gone"') if name.endswith("presentation.xml") else data)
        with self.assertRaises(PresentationOpenError):
            validate_source(self.path)

    def test_malformed_slide_xml_rejected(self):
        self.rewrite(lambda name, data: b"<p:broken" if name == "ppt/slides/slide2.xml" else data)
        with self.assertRaises(PresentationOpenError):
            validate_source(self.path)

    def test_media_crc_damage_rejected(self):
        with ZipFile(self.path, "a") as archive:
            archive.writestr("ppt/media/image.png", b"image-byte-fixture")
        with ZipFile(self.path) as archive:
            offset = archive.getinfo("ppt/media/image.png").header_offset
        payload = bytearray(self.path.read_bytes())
        name_size, extra_size = struct.unpack_from("<HH", payload, offset + 26)
        payload[offset + 30 + name_size + extra_size] ^= 1
        self.path.write_bytes(payload)
        with self.assertRaises(PresentationOpenError):
            validate_source(self.path)

    def test_encoded_absolute_and_parent_targets_accepted(self):
        with ZipFile(self.path, "a") as archive:
            archive.writestr("ppt/media/한 글.png", b"fixture")
            archive.writestr("ppt/slides/_rels/slide1.xml.rels",
                '<Relationships><Relationship Id="image" Type="image" Target="../media/%ED%95%9C%20%EA%B8%80.png"/>'
                '<Relationship Id="absolute" Type="image" Target="/ppt/media/%ED%95%9C%20%EA%B8%80.png"/></Relationships>')
        validate_source(self.path)

    def test_duplicate_zip_entry_rejected(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with ZipFile(self.path, "a") as archive:
                archive.writestr("ppt/slides/slide1.xml", "<slide/>")
        with self.assertRaises(PresentationOpenError):
            validate_source(self.path)

    def test_encrypted_container_rejected(self):
        self.path.write_bytes(bytes.fromhex("D0CF11E0A1B11AE1") + b"fixture")
        with self.assertRaisesRegex(PresentationOpenError, "암호"):
            validate_source(self.path)

    @unittest.skipUnless(__import__("os").name == "nt", "실제 Windows 공유 잠금 검증")
    def test_native_windows_stream_lock_is_reported_and_handles_released(self):
        import win32con
        import win32file
        handle = win32file.CreateFile(str(self.path), win32con.GENERIC_READ, 0, None,
                                     win32con.OPEN_EXISTING, 0, None)
        try:
            with self.assertLogs("ppt_merge.validation", level="ERROR"):
                with self.assertRaisesRegex(PresentationOpenError, "사용 중"):
                    validate_source(self.path)
        finally:
            handle.Close()
        validate_source(self.path)
        # 오류 분류의 확인 핸들도 닫혔으므로 파일을 삭제할 수 있다.
        self.path.unlink()

    def test_validation_cancels_between_parts(self):
        calls = 0
        def cancel():
            nonlocal calls
            calls += 1
            return calls > 4
        with self.assertRaises(OperationCancelled):
            validate_source(self.path, cancel)
