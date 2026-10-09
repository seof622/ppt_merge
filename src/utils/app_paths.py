"""소스 실행과 EXE 실행의 쓰기 가능한 데이터 경로."""
import os
from pathlib import Path
import sys


def app_data_root() -> Path:
    if getattr(sys, "frozen", False):
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else Path.home() / "AppData" / "Local"
        return base / "PPTMerge"
    return Path(__file__).resolve().parents[2]
