"""원본 경로와 편집 순서를 원자적으로 저장한다. 원본 PPT는 변경하지 않는다."""

from dataclasses import asdict
import json
import logging
from pathlib import Path
from PySide6.QtCore import QSaveFile, QIODevice
from src.models.slide_model import SlideItem


class WorkspaceStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self):
        try:
            if self.path.stat().st_size > 16 * 1024 * 1024:
                return [], []
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if data.get('version') != 1:
                return [], []
            sources = data['sources']
            slides = [SlideItem(**item) for item in data['slides']]
            if (not isinstance(sources, list) or any(not isinstance(p, str) for p in sources)
                    or any(type(s.slide_index) is not int or s.slide_index < 1
                           or type(s.slide_id) is not int or not isinstance(s.source_file, str)
                           for s in slides)):
                return [], []
            return sources, slides
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return [], []

    def save(self, sources, slides) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = json.dumps({'version': 1, 'sources': list(sources),
                               'slides': [asdict(s) for s in slides]}, ensure_ascii=False).encode('utf-8')
            output = QSaveFile(str(self.path))
            if not output.open(QIODevice.OpenModeFlag.WriteOnly):
                return False
            if output.write(data) != len(data):
                output.cancelWriting()
                return False
            return output.commit()
        except (OSError, ValueError, TypeError):
            logging.getLogger('ppt_merge.workspace').warning('작업 목록 저장 실패', exc_info=True)
            return False
