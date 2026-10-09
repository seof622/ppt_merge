# PPT Merge

여러 PowerPoint 파일에서 선택한 슬라이드를 원하는 순서로 결합하는 Windows 데스크톱 앱입니다. 개발 기준은 [AGENT.md](AGENT.md)를 따릅니다.

## 개발 환경

- Windows 10 / 11
- Python 3.12 이상
- PySide6
- pywin32 (`pythoncom` 포함)
- 설치된 Microsoft PowerPoint

현재 PPT 파일 목록·썸네일 보기·출력 순서 편집과 **새 PPTX 생성**이 구현되어 있습니다. 원본 서식·마스터·레이아웃을 보존하는 PowerPoint COM 방식으로 결합하고 내부 슬라이드 링크를 재연결합니다. Phase 7 UX 다듬기까지 구현했고 단위 테스트 98개를 통과했습니다. Phase 6에서 실제 Office 통합 테스트 22개(신뢰성 5개·생성 9개·썸네일 8개)를 통과했으며, 이번 단계에서도 실제 생성·생성 중 종료 2개와 캐시 출력 UI 1개를 재검증했습니다. UX 변경과 검증 범위는 [UX 검증](docs/ux_validation.md)에 정리했습니다. 합성 자료 20개 파일·500장의 생성은 약 54초, 캐시 재로딩은 약 2.1초였습니다. 측정 범위와 재검증 방법은 [신뢰성 검증](docs/reliability_validation.md)에 정리했습니다. OneDrive 저장·덮어쓰기 검증 2개와 실제 PPT 캐시 UI 회귀 검증 1개도 앞서 통과했습니다. 생성과 검증 결과는 [PPT 생성 안내](docs/generation_validation.md), 기존 단계는 [기본 보존](docs/poc_validation.md), [고급 보존](docs/advanced_validation.md), [썸네일](docs/thumbnail_validation.md), [기본 UI](docs/ui_validation.md), [출력 편집](docs/output_composer_validation.md)을 참고하세요.

## 앱 실행

Windows 단일 실행 파일은 `dist/PPTMerge.exe`입니다. 더블클릭하면 실행되며 Python 설치와 `run_app.bat`은 필요하지 않습니다. 실행 PC에는 Microsoft PowerPoint가 설치되어 있어야 합니다. EXE의 캐시와 로그는 `%LOCALAPPDATA%/PPTMerge`에 저장합니다. 빌드와 검증 방법은 [EXE 패키징](docs/exe_packaging.md)을 참고하세요.

소스로 개발할 때는 이 작업 환경의 `run_app.bat`을 탐색기에서 더블클릭하면 됩니다. PPT 추가 버튼 또는 파일 끌어 놓기로 PPTX·PPTM 파일을 추가합니다. 소스를 선택하면 슬라이드 번호·제목·썸네일이 표시되고 Ctrl·Shift로 여러 슬라이드를 선택할 수 있습니다. 파일 제거·파일 목록 비우기·다시 읽기·로딩 취소를 지원합니다.

‘선택 슬라이드 담기’, 더블클릭, 우클릭 메뉴 또는 출력 영역에 드래그해서 슬라이드를 담습니다. 출력 목록은 왼쪽부터 최종 순서이며 중복을 허용합니다. Ctrl·Shift 선택, 드래그 순서 변경, Delete 삭제, 복제(Ctrl+D), 앞으로·뒤로·맨 앞으로·맨 뒤로 이동, 출력 비우기를 지원합니다. 복제는 선택한 슬라이드를 한 번 더 담는 기능입니다. 담은 직후 출력 목록으로 포커스가 이동해 복제·삭제 단축키를 이어서 쓸 수 있고, 편집 결과는 아래 상태 표시줄에 표시됩니다. 파일 목록을 비워도 출력 목록은 유지됩니다. 오른쪽 아래 ‘PPT 생성’을 눌러 저장 경로를 선택하면 출력 목록 순서대로 새 PPTX를 만듭니다. 같은 이름의 기존 파일은 확인 후 덮어쓰며, 원본 파일에는 저장할 수 없습니다. 저장 완료 후 상태 표시줄의 ‘PPT 파일 열기’로 결과 파일을 바로 열거나 ‘저장 폴더 열기’로 결과 폴더를 확인할 수 있습니다. 파일은 Windows에 연결된 앱으로 열며, PowerPoint로 열었다면 다음 생성 전에 PowerPoint를 닫아 주세요. 현재 편집 목록은 앱 종료 시 초기화되고 프로젝트 저장은 아직 지원하지 않습니다.

새 환경에서는 의존성을 설치하고 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.main
```

처음 생성해야 하는 자료는 PowerPoint를 닫은 상태에서 읽습니다. 기존 캐시가 있으면 PowerPoint가 실행 중이어도 미리보기를 사용할 수 있습니다. 크기가 다른 슬라이드를 섞으면 첫 출력 슬라이드의 크기 사용을 확인합니다. 원본이 변경되면 ‘다시 읽기’ 후 기존 출력 항목을 삭제하고 다시 담아야 합니다. 취소를 요청하면 ‘취소 중…’ 안내를 유지하고 현재 작업과 정리가 끝난 뒤 편집이 복원됩니다. 생성 중에도 취소할 수 있으며, 임시 PPT와 PowerPoint 정리가 끝난 뒤에만 결과 파일을 게시합니다. 내부 링크 대상이 출력 목록에 없으면 생성을 중단하고, 대상이 중복되면 처음 등장하는 항목으로 연결합니다. 작업은 QThread에서 순서대로 처리하며, 창을 닫으면 취소 요청 후 COM·스레드 정리를 마친 뒤 종료합니다. 로그는 `logs/app.log`이고 시작 단계 오류는 `logs/launcher.log`에서 확인합니다.

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
│   │   ├── slide_mime.py         # 같은 창의 슬라이드 드래그 데이터
│   │   ├── output_panel.py
│   │   └── slide_item_widget.py
│   ├── ppt/                    # PowerPoint COM 서비스
│   │   ├── __init__.py
│   │   ├── source_validation.py    # 원본 검증·변경 감지
│   │   ├── internal_links.py       # 내부 링크 재연결
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

UI에서 COM 객체를 직접 조작하지 않습니다. 작업 스레드는 `pythoncom.CoInitialize()` / `CoUninitialize()`를 호출하고, 스레드 간에는 일반 Python 데이터만 전달합니다. 생성 준비와 실행은 각 워커에서 수행하며 UI에는 생성 계획·진행률·결과 데이터만 전달합니다.

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
