# PPT Merge

여러 PowerPoint 파일에서 선택한 슬라이드를 원하는 순서로 결합하는 Windows 데스크톱 앱입니다. 개발 기준은 [AGENT.md](AGENT.md)를 따릅니다.

## 개발 환경

- Windows 10 / 11
- Python 3.12 이상
- PySide6
- pywin32 (`pythoncom` 포함)
- 설치된 Microsoft PowerPoint

현재는 폴더와 모듈 골격만 구성되어 있으며 앱 실행과 슬라이드 결합 기능은 아직 구현하지 않았습니다.

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
│   └── poc/                    # 첫 단계: 슬라이드 보존 검증
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

UI에서 COM 객체를 직접 조작하지 않습니다. 작업 스레드는 `pythoncom.CoInitialize()` / `CoUninitialize()`를 호출하고, 스레드 간에는 일반 Python 데이터만 전달합니다. 각 모듈의 docstring은 향후 구현할 책임을 설명합니다.
