# PPT 생성 사용·검증

2026-10-09 개발 순서 Phase 5를 구현했습니다. 출력 목록을 새 PPTX로 저장할 수 있습니다. 기본·고급 보존 PoC에서 검증한 방식을 앱 서비스로 옮겨 UI와 연결했습니다. 이전 출력 편집의 실제 마우스 드래그는 같은 날 사용자 확인으로 통과 기록했습니다.

## 사용 방법

1. `run_app.bat`을 실행하고 A·B 또는 자신의 PPTX·PPTM 파일을 추가합니다.
2. 원본 슬라이드를 출력 목록에 담고 원하는 순서로 편집합니다.
3. 오른쪽 아래 **PPT 생성…**을 누르고 PPTX 저장 경로를 선택합니다.
4. 기존 파일은 덮어쓰기 여부를 확인합니다. 원본 PowerPoint 파일에는 저장할 수 없습니다.
5. 크기가 서로 다르면 파일별 크기를 표시하고 첫 출력 슬라이드 크기로 진행할지 확인합니다. 취소가 기본 선택입니다. 크기 혼합에서는 모양·배치가 달라질 수 있습니다.
6. 하단 상태 표시줄의 저장 완료·장수·경로를 확인하고 결과를 PowerPoint로 엽니다. 긴 경로는 상태 표시줄의 툴팁에서도 볼 수 있습니다.

출력 목록은 생성 뒤에도 유지됩니다. 작업 중에는 편집·중복 생성이 비활성화됩니다. 취소나 창 닫기는 현재 COM 호출을 마친 안전한 지점에서 처리하고, 정리가 끝난 뒤 종료합니다. 파일 저장 중 강제 중단은 지원하지 않습니다.

## 원본 보존 및 데이터 안전

- `Slides.InsertFromFile` + `Designs.Clone` + 원본 디자인·레이아웃·배경 적용을 사용합니다. 슬라이드 도형을 재구성하지 않습니다.
- 출력은 선택 목록의 순서를 따르며 같은 원본 슬라이드의 중복도 유지합니다.
- 내부 링크를 원본 파일 경로와 SlideID로 구분해 새 출력 위치로 연결합니다. 같은 대상이 중복되면 첫 출력 항목으로 연결합니다. 링크 대상이 선택되지 않았거나 형식을 해석할 수 없으면 생성하지 않습니다.
- 썸네일을 읽을 때의 파일 경로·수정 시각·크기·SHA-256 정보를 슬라이드 데이터에 기록합니다. 생성 준비·실행 전·완성 후 원본 변경을 확인합니다. 같은 파일 크기와 수정 시각이어도 내용이 달라지면 감지합니다.
- 원본을 이동·수정했으면 다시 추가하거나 ‘다시 읽기’ 후 기존 출력 항목을 삭제하고 다시 담아야 합니다. 출력 항목을 자동으로 다른 슬라이드로 교체하지 않습니다.
- PowerPoint는 Windows 로컬 임시 폴더에 PPT를 저장합니다. COM 정리·파일 무결성·원본·출력 충돌을 확인한 뒤 완성된 파일을 출력 폴더의 고유한 임시 경로로 복사하고 최종 이름으로 교체합니다. 복사한 파일의 SHA-256도 확인하며 취소·실패 시 두 임시 경로를 정리하고 기존 결과를 유지합니다.
- 이미 있는 결과를 덮어쓸 때도 준비 이후 변경된 파일은 교체하지 않습니다. 작업 중 새로 생긴 결과 파일도 보호합니다.
- 기존 사용자 PowerPoint가 열려 있으면 COM 생성은 거부하고 사용자 세션은 유지합니다. 썸네일 캐시는 계속 사용할 수 있습니다.

## 자동 검증

- 단위 테스트 **84개**: 기존 42개 + 생성 서비스 15개 + 생성 UI 7개 + Phase 6 원본 검증·캐시 재시도·COM 시작 보호 20개.
- 실제 Office 생성 통합 검증 **9개 사례**: 기본 UI 생성, 고급 보존, PPTM·서로 다른 소스의 같은 SlideID·중복 링크, 내부 링크 대상 누락, 취소·예외, 크기 혼합, 기존 사용자 세션 보호, 생성 중 창 닫기, 10개 원본 처리.
- 기존 실제 PPT 캐시 출력 UI 회귀 검증 **1개**: 캐시 재사용, 원본·출력 순서, 중복, 작은 창의 원본 카드와 가로 스크롤.

기본 4장·고급 10장·PPTM 혼합 6장, 총 20장의 원본 대비 COM 정보·내부 자료·PNG 렌더 비교를 통과했습니다. 내부 링크 목적지도 검증했습니다. 차트·SmartArt·SVG·오디오·비디오·Excel OLE·애니메이션·전환·노트·테마·배경·레이아웃을 포함한 제공 테스트 자료의 결과입니다. 모든 앱 소유 PowerPoint는 검증 후 종료되었으며 잔존 프로세스가 없습니다.

대표 자료:

- [기본 결과 4장](../output/generation_validation_vht17hiu/basic.pptx): A-2 → B-4 → A-1 → A-2
- [고급 결과 10장](../output/generation_validation_6lr89g4t/advanced.pptx): 내부 링크 재정렬·SVG 중복 포함
- [PPTM 혼합 결과 6장](../output/generation_validation_6lr89g4t/cross_source.pptx): 서로 다른 소스와 중복 링크 대상
- [보존·신뢰성 보고서](../output/generation_validation_6lr89g4t/report.json)
- [최종 UI·종료·10개 소스 보고서](../output/generation_validation_vht17hiu/report.json)
- [생성 완료 화면](../output/generation_validation_vht17hiu/generated.png)
- [1000×640 화면](../output/generation_validation_vht17hiu/compact.png)

2026-10-09 사용자가 OneDrive 저장 수정 후 앱에서 정상 동작한다고 확인했습니다. 실제 저장 동작의 사용자 확인도 통과했습니다. 새 앱에서 생성한 고급 자료의 재생·클릭·편집 전체 수동 비교는 별도 확인 대상이며, 앞선 PoC의 수동 검증과 출력 드래그 확인은 통과했습니다. 새 앱에서도 위 결과를 열어 외관·슬라이드 쇼·미디어 재생·링크 클릭을 확인할 수 있습니다. 자료의 VBA 매크로는 없으며 실제 매크로 보존을 검증한 것은 아닙니다. Phase 6에서 실제 암호·손상 자료 차단, 잠금·읽기 전용 결과 보존과 100~500장 처리를 검증했습니다. 결과는 [신뢰성 검증](reliability_validation.md)에 있습니다. 기존 사용자 PowerPoint와의 동시 COM 작업은 지원하지 않으며, 해당 세션은 보호합니다. 프로젝트 저장은 아직 지원하지 않습니다.

## OneDrive 저장 오류 수정

2026-10-09 사용자 오류를 재현했습니다. OneDrive 바탕 화면을 PowerPoint의 SaveAs에 직접 전달하면 PowerPoint가 클라우드 주소로 저장했고, 로컬 임시 경로에는 PPT가 없었습니다. 수정 후 PowerPoint 저장은 로컬 임시 폴더에서 수행하고 앱이 결과를 선택한 폴더로 복사합니다.

실제 OneDrive 바탕 화면에 사용자 선택 A-1 → A-2 → B-2 → C-1 → B-3의 5장 결과 생성과 기존 파일 덮어쓰기 2개를 통과했습니다. 테스트가 만든 파일만 정리했고 결과 사본과 보고서는 onedrive_validation_o43dhwtm에 보관했습니다. 앱 소유 PowerPoint 잔존 프로세스는 없습니다.

- [OneDrive 저장 검증 보고서](../output/onedrive_validation_o43dhwtm/report.json)
- [5장 결과 사본](../output/onedrive_validation_o43dhwtm/user_selection.pptx)

OneDrive 실환경 회귀 테스트는 `PPT_MERGE_ONEDRIVE_DIRECTORY`에 검증할 폴더를 지정한 뒤 `test_generation_onedrive.py`를 실행합니다. 이 검증은 지정한 폴더에 고유한 테스트 파일만 생성·정리합니다.

## 재검증

PowerPoint를 닫은 상태에서 다음을 실행합니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests/unit -v

$env:PPT_MERGE_GENERATION_COM_TESTS = '1'
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests/integration -p test_generation_com.py -v

# A·B·advanced의 기존 cache 필요, Office 실행 없음
$env:PPT_MERGE_OUTPUT_UI_TESTS = '1'
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests/integration -p test_output_cached.py -v
```

보고서·PNG·생성된 PPT·로그는 Git에서 제외되는 `output/`·`logs/`에 보관합니다. Qt 화면 이미지는 화면 없는 환경에서 렌더한 것으로 실제 Windows 창 테두리는 포함하지 않습니다.
