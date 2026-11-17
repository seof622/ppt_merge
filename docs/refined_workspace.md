# 화면 다듬기와 종료 안정성

2026-11-17, 기존 자료·원본·결과 배치를 유지하며 썸네일 비중과 시각적 위계를 조정했다.

## 화면

- 상단을 64px로 정리하고 저장 버튼을 코발트 블루로 강조한다. 나머지 도구는 가벼운 선 아이콘과 배경으로 표현한다.
- 배경(`#F3F7FF`)·자료 영역·결과 영역(`#EDF3FF`)을 밝은 블루 계열로 통일하고 명도 차이로 구분한다. PPT 아이콘과 사용 횟수 배지도 같은 블루 계열로 표시한다. 본문은 짙은 중립색으로 유지한다.
- 기본 글자는 13px, 영역 제목은 18px, 보조 정보는 11~12px로 구분한다. Segoe UI와 맑은 고딕을 사용한다. 실제 Windows 실행은 시스템 글꼴을 사용하고 offscreen 검증용 글꼴은 QApplication마다 한 번만 등록한다.
- 보기 전환은 하나의 묶음으로 표시한다. 검색창·확대 보기·크기 슬라이더의 색과 테두리를 줄인다.
- 원본 카드는 썸네일 아래 번호·제목 한 줄을 표시한다. 사용 횟수는 작은 배지로 표시하고 반복 사용 안내는 영역에 한 번만 둔다.
- 결과 카드에는 번호·제목과 출처를 유지한다. 선택한 썸네일은 파란 테두리·체크로 구분하며 이미지 자체를 착색하거나 자르지 않는다.
- 작은 창에서는 원본 카드 크기를 실제 남은 높이에 맞춰 줄여 제목까지 표시한다. 결과의 격자·가로 목록 전환과 드래그 편집은 유지한다.

## 드래그할 때 놓을 자리 표시

결과 목록의 세로 삽입선을 슬라이드 크기의 옅은 블루 빈 카드로 변경했다. 빈 카드에 놓을 위치와 추가·이동할 장수를 표시하고 주변 카드는 150ms 동안 부드럽게 자리를 내준다. 여러 장은 장수를 표시한 하나의 묶음으로 미리 보여 준다.

드래그 중에는 표시 위치만 바꾸며 실제 모델과 실행 취소 기록은 드롭 시 한 번 변경한다. 취소·이탈·허용되지 않은 드롭은 미리보기를 제거한다. 격자와 가로 목록에서 마지막 빈 자리까지 스크롤할 수 있고, 결과가 비어 있어도 첫 자리부터 표시한다. 내부 이동에서는 옮기는 원본 카드를 미리보기에서 빼서 중복 표시하지 않는다.

드래그 추가·내부 이동·취소 시 순서·선택·실행 취소 보존·마지막 슬롯 접근·보기 전환·드래그 미리보기 중 앱 종료를 포함한 관련 32개 검사가 7.693초에 통과했고 프로세스 종료 코드도 0이었다. Qt의 drag enter/move/drop/leave 이벤트로 검증했다. 로그는 `output/drag_preview_tests.log`, 화면은 `output/drag_preview_1600.png`, `output/drag_move_1600.png`, `output/drag_preview_1000.png`, `output/drag_preview_filmstrip.png`, `output/drag_preview_empty.png`이다.

## 종료 메모리 접근 오류

일부 Qt 검사는 검증 항목이 통과한 뒤 QApplication 해제 중 `0xC0000005`로 종료됐다. 창의 `close()`는 창을 숨길 뿐 위젯과 자식 모델의 즉시 삭제를 보장하지 않아, 해제가 Python GC 시점까지 남는 상태였다.

`shutdown_application()`은 창의 지연 삭제를 요청하고 DeferredDelete 이벤트를 처리한 뒤 Python 순환 참조를 수거하고 QApplication을 해제한다. 실제 앱 진입점과 검사 실행기에 같은 순서를 적용했다. Qt가 권장하는 QApplication을 마지막에 해제하는 원칙에 따른다. [Qt 공식 객체 수명 지침](https://doc.qt.io/qt-6/threads-qobject.html).

테스트의 대기 루프는 완료 후 타이머를 정지하고 신호 연결을 해제한다. UI 테스트는 각 창의 지연 삭제도 처리한다. 검사 실행기는 Windows 오류창을 띄우지 않고 로그와 실제 종료 코드로 실패를 보고한다. 비정상 종료를 성공 코드로 바꾸는 처리는 없다.

## 검증과 산출물

`python -X utf8 -X faulthandler scripts/run_tests.py`로 전체 163개 검사가 30.422초에 통과했고 프로세스 종료 코드도 0이었다. `test_shutdown`은 실제 앱 진입점을 별도 프로세스에서 실행하여 빈 화면 종료와 가짜 읽기 서비스를 통한 파일 로드·출력 추가·미리보기 표시 후 종료를 검증한다. 두 경우 모두 정상 반환과 QApplication 해제를 확인했다.

마지막 화면 검토에서 보기 전환 후 확대 아이콘이 사라지는 문제도 수정했다. 관련 보기 전환·배치 검사 7개를 다시 실행해 정상 종료 코드 0을 확인했다.

최종 블루 계열 통일 후 종료·원본 선택·결과 편집·배치·보기 전환 검사 27개를 6.024초에 통과했고 종료 코드도 0이었다. 로그는 `output/blue_workspace_tests.log`이다. 1600×900과 1000×640 화면을 다시 렌더링했으며 렌더링 프로세스도 정상 종료했다. `output/refined_workspace_*.png`에 최종 색상을 반영했다.

- 전체 검사 로그: `output/refined_workspace_all_tests.log`
- 실행 파일: `dist/PPTMerge.exe` 재빌드 성공
- 빌드 로그: `output/refined_workspace_build.log`, 색상 반영 `output/blue_workspace_build.log`, 최종 드래그 개선 `output/drag_preview_build.log`
- 화면: `output/refined_workspace_1600.png`, `output/refined_workspace_1000_source.png`, `output/refined_workspace_1000_result.png`
- 추가 화면: `output/refined_workspace_filmstrip.png`, `output/refined_workspace_browser.png`, `output/refined_workspace_empty.png`

화면은 기존 예시 이미지와 가짜 읽기 서비스를 이용해 Qt offscreen에서 확인했다. 이번 변경에서 실제 Office COM 병합이나 Windows 보안 정책 아래의 배포 EXE 실행은 재검증하지 않았다.
