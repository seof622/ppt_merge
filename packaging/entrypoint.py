"""콘솔 없는 EXE의 시작 오류를 로그와 Windows 안내로 남긴다."""
import ctypes
import sys
import traceback

from src.utils.app_paths import app_data_root


def launch() -> int:
    try:
        from src.main import main
        return main()
    except Exception:
        directory = app_data_root() / "logs"
        try:
            directory.mkdir(parents=True, exist_ok=True)
            with (directory / "launcher.log").open("a", encoding="utf-8") as stream:
                traceback.print_exc(file=stream)
            detail = f"로그: {directory / 'launcher.log'}"
        except OSError:
            detail = "로그 파일을 저장하지 못했습니다."
        if "--package-check" in sys.argv:
            return 1
        ctypes.windll.user32.MessageBoxW(
            None, f"PPT Merge를 시작하지 못했습니다.\n{detail}", "PPT Merge", 0x10)
        return 1


if __name__ == "__main__":
    raise SystemExit(launch())
