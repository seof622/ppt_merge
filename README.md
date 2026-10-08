# PPT Merge

여러 PowerPoint 파일에서 선택한 슬라이드를 원하는 순서로 결합하는 Windows 데스크톱 앱입니다. 개발 기준은 [AGENT.md](AGENT.md)를 따릅니다.

## 개발 환경

- Windows 10 / 11
- Python 3.12 이상
- PySide6
- pywin32 (`pythoncom` 포함)
- 설치된 Microsoft PowerPoint

현재는 PPT 파일 목록과 슬라이드 썸네일을 보여 주는 기본 PySide6 UI, 썸네일 캐시 서비스 및 PowerPoint COM 결합 PoC가 구현되어 있습니다. UI의 출력 순서 편집·PPT 생성 연결은 다음 단계입니다. 기본·고급 PPT 보존 검증, UI·캐시 단위 테스트 24개와 실제 Office UI 통합 테스트 2개를 통과했습니다. 실행 방법과 검증 결과는 [기본 검증 안내](docs/poc_validation.md), [고급 검증 안내](docs/advanced_validation.md), [썸네일 검증 안내](docs/thumbnail_validation.md), [UI 사용·검증 안내](docs/ui_validation.md)를 참고하세요.

## 앱 실행

이 작업 환경에서는 `run_app.bat`을 탐색기에서 더블클릭하면 됩니다. PPT 추가 버튼 또는 파일 끌어 놓기로 PPTX·PPTM 파일을 추가합니다. 소스를 선택하면 슬라이드 번호·제목·썸네일이 표시되고 Ctrl·Shift로 여러 슬라이드를 선택할 수 있습니다. 파일 제거·전체 비우기·다시 읽기·로딩 취소를 지원합니다.

새 환경에서는 의존성을 설치하고 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.main
```

처음 생성해야 하는 자료는 PowerPoint를 닫은 상태에서 읽습니다. 기존 캐시가 있으면 PowerPoint가 실행 중이어도 미리보기를 사용할 수 있습니다. 작업은 QThread에서 순서대로 처리하며, 창을 닫으면 취소 요청 후 COM·스레드 정리를 마친 뒤 종료합니다. 로그는 `logs/app.log`이고 시작 단계 오류는 `logs/launcher.log`에서 확인합니다.

## 폴더 구조

```text
ppt_merge/
├── AGENT.md                    # 프로젝트 요구사항 및 개발 지침
├── README.md
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── main.py                 # 앱 진입점
│   ├── ui/                     # PySide6 화면 및 사용자 입력
│   │   ├── __init__.py
│   │   ├── main_window.py
│   │   ├── source_panel.py
│   │   ├── slide_grid.py
│   │   ├── output_panel.py
│   │   └── slide_item_widget.py
│   ├── ppt/                    # PowerPoint COM 서비스
│   │   ├── __init__.py
│   │   ├── powerpoint_service.py
│   │   ├── presentation_manager.py
│   │   └── thumbnail_service.py
│   ├── models/                 # dataclass 기반 데이터 및 출력 순서
│   │   ├── __init__.py
│   │   ├── slide_model.py
│   │   ├── presentation_model.py
│   │   └── project_model.py
│   ├── workers/                # QThread 작업 및 진행률 전달
│   │   ├── __init__.py
│   │   └── ppt_worker.py
│   └── utils/                  # 로깅 및 파일 처리
│       ├── __init__.py
│       ├── logger.py
│       └── file_utils.py
├── scripts/
│   └── poc/                    # 테스트 PPT 생성, 결합 방식 비교 및 보존 검증
├── tests/
│   ├── unit/                   # COM 없이 검증하는 모델 및 유틸리티 테스트
│   ├── integration/            # PowerPoint 설치가 필요한 통합 테스트
│   └── fixtures/               # 의도적으로 추적하는 테스트 PPT 및 관련 미디어
├── docs/                       # 설계 및 검증 기록
├── cache/                      # 썸네일: <presentation_hash>/slide_1.png
├── logs/                       # 실행 로그: app.log
├── output/                     # 생성된 PPTX 및 검증 결과
└── temp/                       # 임시 작업 파일
```

빈 폴더는 `.gitkeep`으로 유지합니다. `cache/`, `logs/`, `output/`, `temp/`의 생성 파일, Python 캐시, 가상 환경, 빌드 산출물, 로컬 환경 설정은 Git에서 제외합니다. 테스트용 `.pptx` / `.pptm`과 관련 미디어는 일괄 제외하지 않아 `tests/fixtures/`에 추가하면 추적할 수 있습니다. 개인 입력 파일과 생성 결과는 위 로컬 작업 폴더에 보관합니다.

## 개발 순서 및 책임

1. `scripts/poc/`에서 `A.pptx` 2번 → `B.pptx` 4번 → `A.pptx` 1번 결합을 검증합니다. PowerPoint COM의 `Copy` / `Paste`와 `InsertFromFile`을 비교하고 서식·마스터·애니메이션·미디어·노트 보존 결과를 `docs/`에 기록합니다.
2. `src/ppt/`에서 검증된 결합 방식과 `Slide.Export()` 기반 썸네일 캐시를 구현합니다.
3. 보존 검증이 통과하면 `src/ui/`에서 파일 목록·슬라이드 그리드·출력 순서 화면을 구현합니다.
4. `src/workers/`를 통해 서비스 호출, 진행률, 취소 및 COM 정리를 연결합니다.

UI에서 COM 객체를 직접 조작하지 않습니다. 작업 스레드는 `pythoncom.CoInitialize()` / `CoUninitialize()`를 호출하고, 스레드 간에는 일반 Python 데이터만 전달합니다. 아직 구현하지 않은 모듈의 docstring은 향후 구현할 책임을 설명합니다.

## PoC 실행

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-poc.txt
.\.venv\Scripts\python.exe scripts/poc/run_poc.py
```

PowerPoint를 닫은 상태에서 실행합니다. 기본 PPT는 `tests/fixtures/basic/`에 있습니다. 새 자료를 만들려면 `create_fixtures.py --directory <새 폴더> --image <이미지 경로>`를 사용합니다. 결과는 매 실행마다 별도의 `output/poc_<날짜_시간>/`에 저장되며 기존 출력 파일을 덮어쓰지 않습니다.

고급 자료의 검증은 다음과 같이 실행합니다.

```powershell
.\.venv\Scripts\python.exe scripts/poc/run_advanced_poc.py
```

고급 자료는 `tests/fixtures/advanced/`에 있습니다. 새 자료를 만들려면 PowerPoint와 Excel을 닫고 `create_advanced_fixtures.py --directory <새 폴더>`를 실행합니다. 기존 자료를 덮어쓰지 않습니다. 외부 Excel 연결에 절대 경로가 저장되므로 다른 컴퓨터에서는 자료를 새 폴더에 생성한 뒤 `run_advanced_poc.py --fixtures <새 폴더>`로 검증합니다. `.pptm` 자료는 실제 VBA 매크로가 없는 형식 검증용입니다.

## 썸네일 생성·캐시

기존 `requirements-poc.txt`의 의존성으로 실행할 수 있습니다. 최초 생성 시 PowerPoint를 닫고 실행합니다.

```powershell
.\.venv\Scripts\python.exe scripts/export_thumbnails.py tests/fixtures/basic/A.pptx tests/fixtures/basic/B.pptx
```

썸네일은 `cache/<캐시 키>/slide_<번호>.png`, 슬라이드 제목·ID와 캐시 정보는 같은 폴더의 `manifest.json`에 저장합니다. 기본 너비는 480px이며 원본 비율을 유지합니다. `--width 640` 등으로 바꿀 수 있습니다.

같은 파일은 PowerPoint 실행 없이 캐시를 재사용합니다. 원본 내용·수정 시각·경로 또는 썸네일 너비가 달라지면 새 캐시를 만들고, 누락·손상된 이미지가 있으면 해당 이미지만 복구합니다. 실행 보고서와 첫 36장 이내의 정적 확인 이미지는 매번 새 `output/thumbnails_<임의값>/`에 저장합니다. 로그는 `logs/app.log`입니다.

앱 서비스는 `src/ppt/thumbnail_service.py`, COM 세션 관리는 `src/ppt/presentation_manager.py`에 있습니다. CLI와 UI는 워커에서 서비스를 실행하며 결과에는 일반 dataclass 데이터만 담습니다. UI의 QThread 연결은 `src/workers/ppt_worker.py`에 있습니다.

```powershell
# PowerPoint 설치 없이 캐시 로직 검증
.\.venv\Scripts\python.exe -m unittest discover -s tests/unit -v

# PowerPoint를 닫은 상태에서 실제 Office 통합 검증
$env:PPT_MERGE_COM_TESTS = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests/integration -p test_thumbnail_com.py -v
```
