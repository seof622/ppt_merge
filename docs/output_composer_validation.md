# 출력 슬라이드 순서 편집 사용·검증

개발 순서 Phase 4를 구현했습니다. 원본 슬라이드 담기, 중복 추가, 출력 다중 선택, 드래그 재정렬, 삭제·복제·위치 이동을 사용할 수 있습니다. 새 PPT 생성 연결은 Phase 5에서 진행합니다.

현재 **단위 테스트 42개**, **실제 PPT 캐시 기반 UI 통합 테스트 1개**가 통과했습니다. 마우스로 실제 Windows 창에서 끌어 놓는 수동 검증은 대기 중입니다. 이번 통합 검증은 기존 캐시를 사용했으며 Office 실행 횟수는 0회입니다.

## 실행과 테스트 자료의 정확한 경로

- 실행: [run_app.bat](</C:/Work/Side Project/ppt_merge/run_app.bat>) — `C:\Work\Side Project\ppt_merge\run_app.bat`
- 기본 A: [A.pptx](</C:/Work/Side Project/ppt_merge/tests/fixtures/basic/A.pptx>) — `C:\Work\Side Project\ppt_merge\tests\fixtures\basic\A.pptx`
- 기본 B: [B.pptx](</C:/Work/Side Project/ppt_merge/tests/fixtures/basic/B.pptx>) — `C:\Work\Side Project\ppt_merge\tests\fixtures\basic\B.pptx`
- 고급 자료: [advanced.pptx](</C:/Work/Side Project/ppt_merge/tests/fixtures/advanced/advanced.pptx>) — `C:\Work\Side Project\ppt_merge\tests\fixtures\advanced\advanced.pptx`

실행 파일을 탐색기에서 더블클릭합니다. 현재 환경에는 실행 의존성이 설치되어 있습니다. A·B·고급 자료의 기존 캐시도 검증되어 바로 사용할 수 있습니다. 캐시가 없는 자료를 읽으려면 기존 PowerPoint 자료를 저장하고 PowerPoint를 닫은 상태에서 추가합니다.

## 사용자가 확인할 사항

1. **담기**: A와 B를 함께 추가합니다. 왼쪽 A를 선택하고 2번 슬라이드를 클릭한 뒤 ‘선택 슬라이드 담기’를 누릅니다. B의 4번은 더블클릭해서 담고, A의 1번은 우클릭 → ‘선택 슬라이드 담기’로 담습니다. 아래 출력 목록이 왼쪽부터 **A-2 → B-4 → A-1**, 총 3장이면 정상입니다.
2. **원본에서 드래그**: 위 원본 썸네일을 아래 출력 카드 사이로 끌어 놓습니다. 파란 삽입 표시가 보여야 하고 해당 위치에 항목이 추가되어야 합니다. 원본 그리드의 슬라이드는 유지되어야 합니다. 추가한 항목을 선택하고 ‘선택 삭제’로 다시 3장으로 만듭니다.
3. **출력 드래그**: 첫 출력 카드 A-2를 마지막 카드 A-1 뒤로 끌어 놓습니다. **B-4 → A-1 → A-2**로 바뀌고 장수는 3장으로 유지되어야 합니다. 카드의 출력 번호도 1·2·3으로 다시 표시되어야 합니다.
4. **다중 선택·복제·삭제**: 출력 목록에서 Ctrl로 두 항목을 선택하고 ‘복제’를 누릅니다. 각각 원본 바로 뒤에 복사본이 생겨 총 5장이 되고 복사본 2개가 선택되어야 합니다. 출력 카드 영역을 클릭해 포커스를 둔 뒤 Delete를 누르면 선택한 항목만 빠져 총 3장이 되어야 합니다. Shift 범위 선택도 확인합니다.
5. **이동 버튼**: 출력 항목을 선택하고 ‘앞으로’, ‘뒤로’, ‘맨 앞으로’, ‘맨 뒤로’를 눌러 표시 순서와 선택이 함께 이동하는지 확인합니다. 첫 위치에서 앞으로 이동할 수 없으면 버튼이 비활성화되는 것이 정상입니다.
6. **목록 구분·중복**: 같은 원본 슬라이드를 다시 담아 중복이 유지되는지 확인합니다. 상단 ‘파일 목록 비우기’를 눌러도 출력 목록은 유지되어야 합니다. 아래 ‘출력 비우기’는 출력 항목만 모두 제거해야 합니다. 원본 PPT 파일은 그대로 남습니다.
7. **작은 창·종료**: 창을 줄이면 원본 썸네일이 작아지고 출력 목록은 가로 스크롤할 수 있어야 합니다. 위아래 영역의 경계선을 끌어 높이도 조정할 수 있습니다. 현재 편집 내용은 앱 종료 시 초기화됩니다.

문제가 없으면 ‘이상 없음’, 문제가 있으면 ‘누른 버튼 또는 드래그 위치 / 파일과 슬라이드 번호 / 보이는 현상’을 알려주세요. 예: `출력 A-2를 맨 뒤로 드래그 / 장수가 4장으로 늘어남`.

## 편집 동작과 단축키

원본의 ‘선택 슬라이드 담기’는 선택한 슬라이드를 원본 번호 순으로 출력 끝에 추가합니다. 더블클릭은 클릭한 한 장을 담습니다. 원본에서 출력으로 드래그하면 삽입 위치에 복사하고, 출력 안에서 드래그하면 이동합니다. 비연속 다중 선택을 이동해도 선택 항목의 상대 순서를 유지합니다.

| 출력 목록 기능 | 단축키 | 동작 |
| --- | --- | --- |
| 선택 삭제 | Delete | 선택한 출력 항목만 제거 |
| 복제 | Ctrl+D | 각 선택 항목 바로 뒤에 복사본 추가 |
| 앞으로·뒤로 | Alt+↑ / Alt+↓ | 이동 가능한 선택 묶음을 한 위치씩 이동 |
| 맨 앞으로·맨 뒤로 | Alt+Home / Alt+End | 선택 순서를 유지해 처음·끝으로 이동 |

단축키는 출력 목록이나 출력 편집 버튼에 포커스가 있을 때 적용됩니다. 원본 파일 목록과 미리보기에서 Delete를 눌러 출력 항목이 지워지지 않습니다. 우클릭 메뉴로도 편집할 수 있습니다.

파일 제거와 파일 목록 비우기는 출력 항목을 유지합니다. 출력 항목은 파일 경로·슬라이드 ID·번호·썸네일을 담은 추가 당시 데이터입니다. 원본 파일 자체를 이동·수정하면 출력 항목이 자동 갱신되지는 않습니다. 후속 생성 단계에서 원본 존재와 변경 여부를 검증하도록 연결할 예정입니다. 프로젝트 저장·복원도 아직 지원하지 않습니다.

## 자동 검증과 화면

이번 단위 테스트는 기존 캐시 15개·기본 UI 9개·출력 순서 모델 8개·출력 UI 10개, 총 42개입니다. 중복 항목의 독립 삭제, 비연속 이동, 경계 이동, 잘못된 위치, 선택 복구, Ctrl/Shift, 단축키 범위, 우클릭, 실제 Qt 드래그 진입·이동·드롭 이벤트를 검증했습니다. 오래된 출력 드래그 데이터와 다른 창의 드래그 데이터는 거절합니다.

통합 검증은 실제 A 4장·B 4장·고급 9장의 캐시를 QThread로 읽고 **A-2 → B-4 → A-1 → A-2**를 편집했습니다. 고급 슬라이드 3장을 추가해 출력 7장을 렌더했으며 원본 슬라이드 ID·번호·썸네일이 일치하는지 확인했습니다. 1000×640에서 원본 첫 카드가 완전히 보이고 출력 가로 스크롤이 생기는 것도 검사했습니다. 실제 PPT 파일을 생성한 검증은 아닙니다.

- [1920×1080 화면](</C:/Work/Side Project/ppt_merge/output/composer_validation_brwvogpu/loaded.png>) — `C:\Work\Side Project\ppt_merge\output\composer_validation_brwvogpu\loaded.png`
- [1000×640 화면](</C:/Work/Side Project/ppt_merge/output/composer_validation_brwvogpu/compact.png>) — `C:\Work\Side Project\ppt_merge\output\composer_validation_brwvogpu\compact.png`
- [초기 화면](</C:/Work/Side Project/ppt_merge/output/composer_validation_brwvogpu/empty.png>) — `C:\Work\Side Project\ppt_merge\output\composer_validation_brwvogpu\empty.png`
- [검증 보고서](</C:/Work/Side Project/ppt_merge/output/composer_validation_brwvogpu/report.json>) — `C:\Work\Side Project\ppt_merge\output\composer_validation_brwvogpu\report.json`

검증 이미지는 실제 Qt 위젯을 화면 없는 환경에서 렌더하고 직접 확인했습니다. Windows 창 테두리·DPI·물리적인 마우스 드래그는 위 수동 확인이 필요합니다. 이미지·보고서·로그는 Git에서 제외됩니다.

## 코드와 재검증

- [project_model.py](</C:/Work/Side Project/ppt_merge/src/models/project_model.py>): Qt·COM과 분리된 `OutputSequence`, 최종 순서는 `list[SlideItem]`
- [output_panel.py](</C:/Work/Side Project/ppt_merge/src/ui/output_panel.py>): 출력 Qt 모델·가로 목록·편집 버튼·우클릭·드래그 처리
- [slide_mime.py](</C:/Work/Side Project/ppt_merge/src/ui/slide_mime.py>): 같은 창의 원본·출력 사이에서 공유하는 일반 슬라이드 데이터
- [slide_grid.py](</C:/Work/Side Project/ppt_merge/src/ui/slide_grid.py>): 원본 담기 입력·드래그 복사·작은 창의 카드 크기 조정

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests/unit -v

# A·B·advanced의 기존 cache가 필요하며 Office를 실행하지 않음
$env:PPT_MERGE_OUTPUT_UI_TESTS = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests/integration -p test_output_cached.py -v
```

Qt의 [모델과 드래그·드롭 문서](https://doc.qt.io/qtforpython-6/overviews/qtwidgets-model-view-programming.html), [QDrag 문서](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QDrag.html)를 참고했습니다.
