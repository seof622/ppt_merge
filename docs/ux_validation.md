# Phase 7 · UX 다듬기

2026-10-09 구현 및 자동 검증 완료. Phase 6의 실제 Windows 사용자 테스트 1~3번 정상 확인을 바탕으로 진행했다.

## 변경 사항

- 읽기·생성 취소 요청 뒤 버튼이 ‘취소 중…’으로 바뀌고 비활성화된다. 늦게 도착하는 진행 신호가 취소·창 닫기 안내를 덮지 않는다. 다음 작업에서는 ‘취소’로 복원된다.
- PPT 저장과 PowerPoint 정리가 끝나면 상태 표시줄에 ‘PPT 파일 열기’와 ‘저장 폴더 열기’가 나타난다. 파일 열기는 저장한 PPTX를 Windows에 연결된 앱으로 열도록 요청한다. PowerPoint로 연 경우 다음 생성 전에 닫도록 상태 표시줄과 툴팁으로 안내한다. 파일 이동·삭제 또는 열기 요청 실패는 화면에 안내한다. 이후 생성이 실패해도 마지막 성공 결과의 폴더를 열 수 있다. 작업 중에는 버튼을 숨긴다. 폴더가 없어지거나 Windows가 열기 요청을 거부하면 화면에 안내한다.
- 슬라이드를 담거나 편집하면 출력 목록에서 선택·포커스를 유지한다. 담은 직후 Ctrl+D 복제·Delete 삭제를 이어서 쓸 수 있다. 추가·복제·삭제·순서 변경 결과와 총 장수를 상태 표시줄에 표시한다.
- 복제 툴팁과 완료 안내에 ‘같은 슬라이드를 한 번 더 담기’라는 의미를 설명한다.
- 소스 목록의 읽기 대기·불러오는 중·완료·실패·취소를 아이콘과 글자로 구분한다. 로딩 안내에 파일 순번을 표시하고, 최종 요약에 실패·취소 수를 유지한다.
- 줄여 표시하는 상태 문장의 툴팁을 새 문장으로 갱신해 전체 안내를 확인할 수 있다.

## 검증 결과

| 검증 | 결과 |
|---|---|
| 전체 단위 테스트 | 95개 통과, 10.212초 |
| 이번 단계에서 추가한 UX 회귀 테스트 | 11개, 위 95개에 포함 |
| 실제 PowerPoint UI 생성 | 통과: A2 → B4 → A1 → A2, 중복 포함 4장 |
| 실제 PowerPoint 생성 중 창 닫기 | 통과: 취소 안내 및 정리, 결과 파일 없음 |
| 실제 PPT 캐시 출력 편집 | 통과: 17장 캐시, 출력 7장, Office 호출 0회 |
| PowerPoint 정리 | 5개 기록 모두 정상, 남은 POWERPNT.EXE 없음 |
| 화면 렌더 확인 | 1920×1080, 1000×640의 저장 완료·출력 편집 화면 확인 |

생성한 4장은 COM 속성·PPTX 패키지 비교에서 차이가 없고 PNG 렌더도 원본과 동일했다. 이번 변경은 UI와 테스트에 한정되며 PPT 결합·서식 보존 엔진은 변경하지 않았다. Phase 6의 100·500장 성능 및 전체 Office 테스트 결과는 [신뢰성 검증](reliability_validation.md)을 참고한다.

Qt 이벤트 루프 테스트는 취소 직후 늦게 도착하는 진행 신호, 재시도 버튼 복원, 포커스와 실제 키 입력, 로딩 중 편집 안내 충돌, 한글·공백 폴더의 URL, 마지막 성공 결과 유지, 폴더 열기 실패, 실패 요약 유지, 긴 상태 문장 툴팁을 검증한다. 파일·폴더를 여는 호출은 단위 테스트에서 대체했으므로 실제 PowerPoint·탐색기 창이 열리는 동작은 사용자 확인 대상이다. 파일 열기의 한글·공백 경로, 마지막 성공 결과 유지, 파일 이동·삭제, 실행 요청 실패, 작업 중·종료 중 실행 방지를 추가 검증했다. 기존 Windows 드래그·실제 PPT 사용 확인은 Phase 6 기록을 유지하며 이번 단계에서 사용자에게 재확인받은 것으로 기록하지 않는다.

## 로컬 산출물

Git에서 제외하는 output 폴더에 보관한다.

- 파일 열기 버튼 추가 후 화면: output/ux_file_open/saved_1920.png, saved_1000.png (기존 실제 PPT 캐시와 이전 저장 결과를 사용한 UI 렌더, 파일 열기 요청은 실행하지 않음)
- 요약: output/ux_native_report.json (3개 통합 검증, 실패·오류·건너뜀 0)
- 실제 생성: output/generation_validation_h3xjf3c6/report.json
- 실제 캐시 편집: output/composer_validation_1_wzp610/report.json
- 생성 화면: 위 생성 폴더의 before_generation.png, generated.png, compact.png
- 캐시 편집 화면: 위 편집 폴더의 empty.png, loaded.png, compact.png

## 재검증

저장한 PowerPoint 작업을 닫고 프로젝트 루트의 PowerShell에서 실행한다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests\unit -q

$env:PYTHONPATH = "$PWD;$PWD\tests\integration"
$env:PPT_MERGE_GENERATION_COM_TESTS = "1"
$env:PPT_MERGE_OUTPUT_UI_TESTS = "1"
.\.venv\Scripts\python.exe -X utf8 -m unittest -v test_generation_com.GenerationComTests.test_01_basic_ui_generation test_generation_com.GenerationComTests.test_08_close_during_real_generation test_output_cached.OutputCachedTests.test_real_cached_slides_preserve_requested_order_and_render
```

캐시 검증은 tests/fixtures/basic/A.pptx·B.pptx와 tests/fixtures/advanced/advanced.pptx의 기존 cache가 필요하다. 생성 UI 검증은 A·B의 캐시가 없으면 실제 PowerPoint로 생성한다. 통합 검증을 실행할 때마다 별도의 산출물 폴더가 생성된다.

사용자가 확인할 새 흐름은 ‘슬라이드 담기 → Ctrl+D → Delete’, ‘PPT 생성 → PPT 파일 열기 / 저장 폴더 열기’, ‘작업 중 취소 → 취소 중 안내 → 편집 복원’이다.
