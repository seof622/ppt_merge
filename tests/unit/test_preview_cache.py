"""확대할 한 장의 캐시 재사용·손상 복구·실패 정리를 검증한다."""
from pathlib import Path
import unittest
from PIL import Image
from src.models.slide_model import SlideItem
from src.ppt.thumbnail_service import ThumbnailService
from src.ppt.source_validation import fingerprint, revision
from src.ppt.errors import OperationCancelled, SourceChangedError, ThumbnailError
import test_thumbnail_service as thumbnail_fixture


class PreviewCacheTests(unittest.TestCase):
    setUp = thumbnail_fixture.ThumbnailServiceTests.setUp
    tearDown = thumbnail_fixture.ThumbnailServiceTests.tearDown
    write_source = thumbnail_fixture.ThumbnailServiceTests.write_source

    def preview_service(self):
        return ThumbnailService(self.cache, width=1600, backend_factory=self.recorder.backend)

    def slide(self, index=2):
        return SlideItem(str(self.source), self.source.name, index, 255 + index,
                         source_revision=revision(fingerprint(self.source)))

    def test_only_requested_slide_is_exported_and_hit_does_not_open_office(self):
        slide = self.slide()
        image = Path(self.preview_service().load_preview(slide))
        with Image.open(image) as value:
            self.assertEqual(value.size, (1600, 900))
        self.assertEqual(self.recorder.exported, [2])
        self.assertEqual(self.preview_service().load_preview(slide), str(image))
        self.assertEqual((self.recorder.started, self.recorder.closed), (1, 1))

    def test_corrupt_high_resolution_cache_is_repaired(self):
        slide = self.slide()
        image = Path(self.preview_service().load_preview(slide))
        image.write_bytes(b'broken')
        self.preview_service().load_preview(slide)
        with Image.open(image) as value:
            value.verify()
        self.assertEqual(self.recorder.exported, [2, 2])
        self.assertEqual(self.recorder.started, self.recorder.closed)

    def test_changed_source_is_rejected_before_opening_office(self):
        slide = self.slide()
        self.write_source('changed')
        with self.assertRaises(SourceChangedError):
            self.preview_service().load_preview(slide)
        self.assertEqual(self.recorder.started, 0)

    def test_failure_preserves_other_cache_and_removes_temporary_files(self):
        good = Path(self.preview_service().load_preview(self.slide(1)))
        original = good.read_bytes()
        self.recorder.fail_at = 2
        with self.assertRaises(ThumbnailError):
            self.preview_service().load_preview(self.slide())
        self.assertEqual(good.read_bytes(), original)
        self.assertEqual(self.recorder.started, self.recorder.closed)
        self.assertFalse(any(p.name.startswith('.preview-') or p.suffix == '.lock'
                             for p in (self.cache / 'previews').iterdir()))

    def test_cancel_after_export_closes_backend_and_does_not_publish(self):
        cancel = {'requested': False}
        backend = self.recorder.backend()
        export = backend.export_slide
        def cancelling_export(*args):
            export(*args)
            cancel['requested'] = True
        backend.export_slide = cancelling_export
        service = ThumbnailService(self.cache, width=1600, backend_factory=lambda: backend)
        with self.assertRaises(OperationCancelled):
            service.load_preview(self.slide(), cancel=lambda: cancel['requested'])
        self.assertEqual(self.recorder.started, self.recorder.closed)
        self.assertEqual(list((self.cache / 'previews').iterdir()), [])


if __name__ == '__main__':
    unittest.main()
