# 기본 PySide6 UI 사용·검증

2026-10-08 기본 UI를 구현했습니다. 현재 파일 목록·썸네일 보기·다중 선택·파일 제거·다시 읽기·작업 취소까지 사용할 수 있습니다. 출력 목록에 슬라이드를 담고 순서를 편집하거나 새 PPT를 생성하는 UI는 다음 단계입니다.

자동 검증은 **UI 9개 + 캐시 15개 = 단위 테스트 24개**, **실제 PowerPoint UI 통합 테스트 2개**가 통과했습니다. 사용자의 실제 데스크톱 수동 확인은 **대기 중**입니다.

## 실행할 파일과 정확한 경로

탐색기에서 아래 파일을 더블클릭합니다. 현재 환경에는 의존성이 설치되어 있어 코드 실행이나 추가 설치가 필요 없습니다.

- [run_app.bat](</C:/Work/Side Project/ppt_merge/run_app.bat>) — `C:\Work\Side Project\ppt_merge\run_app.bat`

탐색기의 주소창에 `C:\Work\Side Project\ppt_merge`를 입력하면 실행 파일이 있는 폴더를 열 수 있습니다. 처음 썸네일을 만들어야 하는 파일은 PowerPoint를 저장하고 닫은 뒤 추가합니다. 이미 캐시가 있는 파일은 PowerPoint를 열어 둔 상태에서도 볼 수 있습니다.

## 사용자가 확인할 사항

1. **창 실행**: 위 배치 파일을 더블클릭했을 때 ‘PPT Merge · 슬라이드 미리보기’ 창이 뜨는지 확인합니다.
2. **PPT 여러 개 추가**: ‘PPT 추가’를 누르고 `C:\Work\Side Project\ppt_merge\tests\fixtures\basic` 폴더에서 `A.pptx`, `B.pptx`를 함께 선택합니다. 파일 목록에 각각 **4장**으로 표시되어야 합니다.
3. **파일 전환**: 왼쪽 A와 B를 번갈아 선택합니다. 오른쪽에 각 4장과 해당 파일의 파란색·초록색 슬라이드가 표시되어야 합니다.
4. **슬라이드 선택**: 오른쪽 첫 슬라이드를 클릭한 뒤 Ctrl을 누르고 다른 슬라이드를 클릭해 2장을 선택합니다. 첫 장을 다시 클릭하고 Shift를 누른 채 4장을 클릭하면 1~4장 범위가 선택되어야 합니다. 오른쪽 위 선택 장수가 맞는지 확인합니다.
5. **끌어 놓기**: `C:\Work\Side Project\ppt_merge\tests\fixtures\advanced\advanced.pptx`를 탐색기에서 앱 창으로 끌어 놓습니다. **9장**으로 표시되어야 합니다. 같은 파일을 다시 추가하면 중복 소스가 생기지 않아야 합니다.
6. **파일 제거·비우기**: 왼쪽에서 파일을 선택하고 ‘선택 파일 제거’를 누르면 목록에서만 빠져야 합니다. ‘전체 비우기’는 빈 화면으로 돌아가야 합니다. 원본 파일과 썸네일 캐시는 삭제하지 않습니다.
7. **창 크기·종료**: 창을 줄여도 파일 목록과 카드·스크롤이 보이는지 확인하고 창을 닫습니다. 로딩 중 닫으면 정리를 마친 뒤 종료합니다. 빠른 캐시 로딩에서는 취소 버튼이 매우 짧게 보일 수 있습니다. 취소를 확인하기 위해 캐시를 지울 필요는 없습니다.

문제가 없으면 ‘이상 없음’, 문제가 있으면 ‘누른 버튼 / 파일명 / 보이는 현상’을 알려주세요. 예: `B.pptx 선택 / 썸네일이 A 그대로 보임`.

## 화면과 자동 보고서

- [1920×1080 화면](</C:/Work/Side Project/ppt_merge/output/ui_validation_wmev5ska/loaded.png>) — `C:\Work\Side Project\ppt_merge\output\ui_validation_wmev5ska\loaded.png`
- [1000×640 화면](</C:/Work/Side Project/ppt_merge/output/ui_validation_wmev5ska/compact.png>) — `C:\Work\Side Project\ppt_merge\output\ui_validation_wmev5ska\compact.png`
- [초기 빈 화면](</C:/Work/Side Project/ppt_merge/output/ui_validation_wmev5ska/empty.png>) — `C:\Work\Side Project\ppt_merge\output\ui_validation_wmev5ska\empty.png`
- [실제 Office UI 검증 보고서](</C:/Work/Side Project/ppt_merge/output/ui_validation_wmev5ska/report.json>) — `C:\Work\Side Project\ppt_merge\output\ui_validation_wmev5ska\report.json`

위 화면은 실제 Qt 위젯을 화면 없는 환경에서 렌더한 검증 이미지입니다. 실제 Windows 창 테두리·DPI 배율·탐색기의 파일 선택 창은 사용자 환경에서 확인해야 합니다.

| 자동 검증 | 결과 |
| --- | --- |
| 여러 소스 추가·중복 제거·잘못된 경로 안내 | 통과 |
| 소스 전환·슬라이드 Ctrl/Shift 선택 | 통과 |
| Qt 파일 드래그 입력 이벤트 | 통과 |
| 읽기 중 추가한 파일의 대기열 처리 | 통과 |
| 한 파일의 오류 격리·친화적인 오류 메시지 | 통과, 다음 소스 계속 읽기 |
| 취소 후 다시 읽기·파일 제거·전체 비우기 | 통과 |
| 로딩 중 창 닫기와 GUI 이벤트 처리 | 통과 |
| 워커 신호의 GUI 스레드 전달 | 통과 |
| 실제 A 4장 + advanced 9장, QThread COM 생성 | 통과, 13장 표시 |
| 실제 파일 ‘다시 읽기’ | 통과, 추가 COM 실행 없이 캐시 사용 |
| 실제 B 생성 중 창 닫기 | 통과, 2장 내보낸 뒤 취소·COM 정상 종료 |

실제 생성 동안 GUI 타이머가 **577회** 실행되어 이벤트 처리가 계속되는 것을 확인했습니다. 앱 소유 PowerPoint가 남지 않았고, 1920×1080·1000×640·빈 화면 이미지를 직접 확인했습니다.

## 코드와 재검증

- `src/main.py`: QApplication 설정·앱 진입점
- `src/ui/main_window.py`: 파일 작업·대기열·화면 상태·작업 중 종료
- `src/ui/source_panel.py`: 소스 이름·장수·상태·전체 경로 툴팁
- `src/ui/slide_grid.py`: 모델 기반 썸네일 그리드·다중 선택·최대 128개 아이콘 메모리 캐시
- `src/workers/ppt_worker.py`: QThread 서비스 호출·진행률·취소·오류 격리
- `requirements.txt`: 앱 실행 의존성
- `run_app.bat`: 현재 환경의 더블클릭 실행 도구

작업 스레드에서 COM을 초기화·종료하며 일반 dataclass 데이터만 전달합니다. GUI 신호는 명시적인 queued connection으로 전달합니다. 스레드 종료 신호 후에도 실제 정리가 끝날 때까지 참조를 유지하며, 강제 종료나 GUI를 막는 무제한 `wait()`를 사용하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.main
.\.venv\Scripts\python.exe -m unittest discover -s tests/unit -v

# PowerPoint를 저장하고 닫은 상태에서만 실행
$env:PPT_MERGE_UI_COM_TESTS = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests/integration -p test_ui_com.py -v
```

앱 로그: `C:\Work\Side Project\ppt_merge\logs\app.log`. 시작 오류 로그: `C:\Work\Side Project\ppt_merge\logs\launcher.log`. 생성 이미지·로그·임시 검사 자료는 Git에서 제외됩니다. 배포용 EXE 패키징과 수백 장 자료의 UI 성능 측정은 후속 과제입니다.

Qt의 [QThread](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html), [QListView](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QListView.html) 문서를 참고했습니다. 보존 검증을 통과한 기존 PowerPoint 서비스의 생성 방식을 유지합니다.
