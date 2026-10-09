"""단일 EXE의 임시 압축 해제 위치와 사용자 데이터 경로를 분리한다."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from src.utils.app_paths import app_data_root


class AppPathTests(unittest.TestCase):
    def test_source_execution_keeps_project_data_directory(self):
        with patch.object(sys, "frozen", False, create=True):
            self.assertEqual(app_data_root(), Path(__file__).resolve().parents[2])

    def test_frozen_execution_uses_local_app_data_not_bundle_or_current_directory(self):
        local = str(Path("C:/사용자 데이터/Local"))
        with patch.object(sys, "frozen", True, create=True), patch.dict(os.environ, {"LOCALAPPDATA": local}):
            self.assertEqual(app_data_root(), Path(local) / "PPTMerge")

    def test_frozen_execution_without_environment_has_user_profile_fallback(self):
        with patch.object(sys, "frozen", True, create=True), patch.dict(os.environ, {key: value for key, value in os.environ.items() if key != "LOCALAPPDATA"}, clear=True):
            self.assertEqual(app_data_root(), Path.home() / "AppData/Local/PPTMerge")
