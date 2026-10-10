"""원본 코드·가상환경과 분리한 경로에서 완성 EXE를 검증한다."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="지정한 EXE의 실제 Windows 실행 검증")
    parser.add_argument("--exe", type=Path, default=ROOT / "dist/PPTMerge.exe",
                        help="검증할 EXE (기본: dist/PPTMerge.exe)")
    executable = parser.parse_args().exe.resolve()
    if not executable.is_file():
        raise SystemExit("먼저 scripts/build_exe.py를 실행하세요.")
    directory = Path(tempfile.mkdtemp(prefix="package_validation_", dir=ROOT / "output"))
    deployment = directory / "한글 배포 폴더"
    deployment.mkdir()
    copied = deployment / executable.name
    shutil.copy2(executable, copied)
    working = directory / "작업 폴더"
    working.mkdir()
    env = os.environ.copy()
    for name in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
        env.pop(name, None)
    env["LOCALAPPDATA"] = str(directory / "user_data")
    env["QT_QPA_PLATFORM"] = "windows"
    windows = Path(env.get("SystemRoot", "C:/Windows"))
    env["PATH"] = os.pathsep.join([str(windows / "System32"), str(windows)])
    started = time.perf_counter()
    command = [str(copied), "--package-check", str(directory),
               str(ROOT / "tests/fixtures/basic/A.pptx"), str(ROOT / "tests/fixtures/basic/B.pptx")]
    process = subprocess.Popen(command, cwd=working, env=env)
    print(f"진단 폴더: {directory}", flush=True)
    code = process.wait()
    report_path = directory / "report.json"
    if not report_path.is_file():
        raise SystemExit(f"EXE 진단 보고서 없음, 종료 코드={code}, 로그={env['LOCALAPPDATA']}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["exe_bytes"] = executable.stat().st_size
    with executable.open("rb") as stream:
        report["exe_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    report["process_exit_code"] = code
    report["total_seconds"] = round(time.perf_counter() - started, 3)
    report["isolated_path"] = env["PATH"]
    report["qt_platform"] = env["QT_QPA_PLATFORM"]
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"완료: passed={report['passed']} code={code}, 보고서={report_path}")
    return 0 if code == 0 and report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
