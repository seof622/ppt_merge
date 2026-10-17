"""마지막으로 선택한 폴더와 생성에 성공한 PPT 경로를 보관한다."""

import logging
from pathlib import Path

from PySide6.QtCore import QSettings


class PathPreferences:
    def __init__(self, filename: Path) -> None:
        self._settings = QSettings(str(filename), QSettings.Format.IniFormat)

    @property
    def root_path(self) -> str:
        return self._settings.value("paths/root", "", type=str)

    def output_path(self, fallback_directory: Path) -> str:
        saved = self._settings.value("paths/output", "", type=str)
        if not saved:
            return "result.pptx"
        path = Path(saved)
        # 이동식 드라이브나 삭제된 폴더는 열지 않고 파일명만 유지한다.
        if not path.parent.is_dir():
            path = fallback_directory / path.name
        return str(path)

    def remember_root(self, path: str) -> None:
        self._save("paths/root", path)

    def remember_output(self, path: str) -> None:
        self._save("paths/output", str(Path(path).resolve()))

    def _save(self, key: str, value: str) -> None:
        self._settings.setValue(key, value)
        self._settings.sync()
        if self._settings.status() != QSettings.Status.NoError:
            logging.getLogger("ppt_merge.settings").warning(
                "경로 설정을 저장하지 못했습니다: %s", self._settings.fileName())
