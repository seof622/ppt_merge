"""Python logging으로 앱 로그와 COM 예외 및 HRESULT를 기록한다."""

import logging
from pathlib import Path


def configure_logging(log_directory: Path) -> None:
    log_directory.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.FileHandler(log_directory / "app.log", encoding="utf-8"),
                  logging.StreamHandler()],
    )
