"""프로젝트 루트와 무관하게 Windows 단일 EXE를 빌드한다."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if sys.platform != "win32":
        raise SystemExit("Windows Python 환경에서 빌드하세요.")
    parser = argparse.ArgumentParser(description="Windows 단일 EXE 빌드")
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist",
                        help="EXE 출력 폴더 (기본: dist)")
    args = parser.parse_args()
    destination = args.dist_dir.resolve()
    # 외부 도구의 같은 이름 DLL(ICU 등)이 번들에 섞이지 않도록 제한한다.
    env = os.environ.copy()
    windows = Path(env.get("SystemRoot", "C:/Windows"))
    env["PATH"] = os.pathsep.join([str(windows / "System32"), str(windows),
                                    str(Path(sys.base_prefix)), str(ROOT / ".venv/Scripts")])
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm",
         "--distpath", str(destination), "--workpath", str(ROOT / "build/windows"),
         str(ROOT / "packaging/PPTMerge.spec")],
        cwd=ROOT, env=env, check=True,
    )
    print(f"EXE: {destination / 'PPTMerge.exe'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
