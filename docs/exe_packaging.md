# Windows 단일 EXE

2026-10-09, PyInstaller 6.22.3 · hooks 2026.8로 Windows x64 EXE를 생성했다.

최신 파일: dist/search-clear/PPTMerge.exe, 54633802 bytes (약 52.1 MiB). SHA-256: d602c01bfe29b42a6692167112695d452554e1f6687cd917908486c15214d75f

## 사용

검색 해제 시 다른 PPT가 자동 추가되는 수정이 반영된 최신 화면은 dist/search-clear/PPTMerge.exe를 더블클릭한다. 기존 실행 파일과 겹치지 않게 별도 폴더에 빌드했다. EXE 파일 하나를 다른 폴더에 복사해도 실행할 수 있도록 Python 3.12·PySide6·Pillow·pywin32 런타임을 포함했다. Microsoft PowerPoint는 실행 PC에 별도로 설치되어 있어야 한다. 설치 프로그램이나 관리자 권한은 요구하지 않는다.

EXE 실행 시 데이터는 다음 경로에 쓴다.

- 캐시: %LOCALAPPDATA%/PPTMerge/cache
- 앱 로그: %LOCALAPPDATA%/PPTMerge/logs/app.log
- 시작 오류: %LOCALAPPDATA%/PPTMerge/logs/launcher.log
- 생성 PPTX: 사용자가 저장 대화상자에서 선택한 경로

소스 실행(run_app.bat 또는 python -m src.main)은 기존 프로젝트의 cache·logs를 계속 사용한다. EXE를 업데이트해도 사용자 데이터 경로는 유지한다. [PyInstaller 런타임 문서](https://pyinstaller.org/en/stable/runtime-information.html)의 단일 EXE 압축 해제 경로와 사용자 데이터를 분리해 종료 시 캐시가 사라지는 문제를 방지했다.

## 빌드

프로젝트 루트에서 실행한다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -X utf8 scripts\build_exe.py
```

실행 중인 EXE와 별도로 빌드하려면 `scripts/build_exe.py --dist-dir dist/search-clear`를 사용한다. 다른 경로의 EXE 검증은 `scripts/validate_exe.py --exe dist/search-clear/PPTMerge.exe`로 수행한다.

빌드 설정은 packaging/PPTMerge.spec이며 결과는 dist/PPTMerge.exe, 중간 파일은 build/windows에 생성한다. 콘솔 없는 onefile 형태이며 Python·Qt·COM 모듈만 분석해서 포함한다. 기존 개인 파일·캐시·로그·테스트 PPT는 묶지 않는다. 배포 바이너리는 Git에서 제외한다.

빌드용 PATH를 Windows·빌드 Python 경로로 제한한다. 처음 빌드에서는 외부 Poppler 경로의 icuuc.dll이 수집되어 QtCore 시작이 실패했다. 의존 DLL의 실제 함수 목록 비교로 혼입을 확인했고, 제한된 빌드 환경에서 Windows 시스템 DLL을 사용하도록 수정했다. 수정 후 EXE 실행 검증을 통과했다.

## 검증

- 단위 테스트 128개 통과 (기존 98개와 파일 검색·메인 UI 탐색 검증 30개), 22.064초.
- EXE를 ‘한글 배포 폴더’에 단독 복사하고 별도의 작업 폴더에서 실행.
- PATH를 Windows/System32·Windows만 남기고 PYTHONPATH·PYTHONHOME·VIRTUAL_ENV를 제거한 환경에서 실행.
- 실제 frozen EXE에서 Qt 워커로 A·B PPT 8장 썸네일을 새로 생성하고 사용자 데이터 경로에 캐시 저장.
- A2 → B4 → A1 → A2의 4장 PPTX 생성, 패키지 장수 및 출력 순서 확인.
- 저장 결과의 파일·폴더 열기 버튼 표시와 화면 캡처 확인.
- 40장 생성 중 창 닫기: 취소 안내 유지, 미완성 결과 없음, 남은 POWERPNT.EXE 없음.
- EXE 종료 코드 0, 19개 진단 조건 통과.

2026-10-09 메인 UI 검색 결과의 PPT 아이콘·읽기 상태 표시와 검색 해제 시 다른 PPT가 자동 추가되는 수정을 반영해 dist/search-clear/PPTMerge.exe를 빌드했다. 최상위 폴더 지정 단계에서만 폴더 선택 창을 열고 이후 폴더 펼치기·PPT 선택·검색은 메인 화면에서 처리한다. 실제 Windows 실행 검증은 output/package_validation_pvloujlv/report.json에서 19개 조건 통과, 종료 코드 0, 21.77초로 확인했다. 남은 PowerPoint 프로세스는 없었다. 새 메인 UI 기능·화면 검증은 [UI·파일 탐색 변경](compact_ui_file_browser.md)을 참고한다. 아래 두 보고서는 이전 빌드의 검증 기록이다.

화면 없는 Qt 검증 결과: output/package_validation_ug_jrtd5/report.json (21.019초).
실제 Windows 창 검증 결과: output/package_validation_g1cn_2x8/report.json (21.033초, qt_platform=windows, 19개 조건 통과, 종료 코드 0).

이 환경의 Windows 11 x64와 설치된 PowerPoint 16.0에서 확인했다. Python이 설치되지 않은 별도 PC의 실물 검증은 수행하지 않았다. EXE는 필요한 Python 런타임을 자체 포함하며, 위 PATH 분리 검증으로 개발 가상환경을 찾지 않아도 실행됨을 확인했다.

재검증은 PowerPoint 작업을 저장하고 닫은 상태에서 실행한다.

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\validate_exe.py
```

이 스크립트는 배포 EXE만 별도 한글 폴더로 복사하고, 개발용 --package-check 진단으로 실제 창·썸네일·생성·취소를 검증한다. 개인 사용자 데이터에 영향을 주지 않도록 해당 실행의 LOCALAPPDATA를 검증 산출물 폴더로 지정한다. 매 실행마다 별도 output/package_validation_* 폴더에 report.json·packaged_ui.png·package_result.pptx·검증 캐시와 로그를 남긴다. 검증에서 파일·폴더 열기 버튼을 실제 클릭해 외부 앱을 여는 동작은 수행하지 않는다.
