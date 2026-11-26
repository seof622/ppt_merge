# 차분한 블루 팔레트

2026-11-24, 기존 블루 화면의 채도를 낮추고 넓은 배경을 옅은 회색 계열로 조정했다. Radix의 [중립색과 강조색 조합](https://www.radix-ui.com/themes/docs/theme/color)을 참고하되, 색상은 이 앱에 맞춰 조정했다.

| 용도 | 색상 |
| --- | --- |
| 전체 배경 | `#F3F5F7` |
| 원본 영역 | `#FAFBFC` |
| 자료 목록 | `#EEF1F4` |
| 결과 영역 | `#EDF1F5` |
| 저장 버튼·선택 테두리·아이콘 | `#526F93` |
| 선택 배경 | `#E5EBF1` |
| 본문 | `#293440` |
| 보조 글자 | `#5C6978` |

강조색의 HSL 채도는 기존 약 80%에서 약 28%로 낮췄다. 저장 버튼의 흰 글자 대비는 약 5.18:1이며, 보조 글자는 드래그 자리 배경에서도 약 4.58:1이다. 카드 배지·스크롤바·검색·보기 전환·툴팁과 Qt 기본 팔레트도 함께 조정했다. 드래그 미리보기와 일반 결과 영역은 같은 배경 상수를 사용한다. 슬라이드 이미지 자체의 색상은 변경하지 않는다.

## 검증

- 화면 배치·보기 전환·출력 편집·종료 관련 기존 검사 21개 통과.
- 예시 썸네일과 가짜 읽기 데이터를 이용해 Qt offscreen에서 1600×900, 1000×640 화면과 격자·가로 목록·빈 결과·드래그 미리보기를 렌더링했다.
- 화면: `output/slate_workspace_1600.png`, `output/slate_workspace_1000_source.png`, `output/slate_workspace_1000_result.png`, `output/slate_drop_1000.png`.
- 검사 로그: `output/slate_blue_tests.log`.
- 새 EXE: `dist/slate-blue/PPTMerge.exe`. 기존 `dist/PPTMerge.exe`가 실행 중이라 별도 폴더에 빌드했다. 설정·캐시·작업 복원 경로는 기존과 같다.
- EXE 빌드 성공, 포함된 앱 모듈 37개가 현재 소스와 일치함을 확인했다. 보고서와 체크섬은 `output/slate_blue_build_verification.json`, `output/slate_blue_SHA256SUMS.txt`에 기록했다. 빌드 로그는 `output/slate_blue_build.log`이다.

색상 변경으로 실제 Office COM 병합·취소 검사는 재실행하지 않았다.
