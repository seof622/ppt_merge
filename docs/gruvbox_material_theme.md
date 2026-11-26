# Gruvbox Material 버전

2026-11-24, [sainnhe/gruvbox-material의 공식 팔레트](https://github.com/sainnhe/gruvbox-material/blob/master/autoload/gruvbox_material.vim)의 Dark Soft 배경과 Material 전경을 바탕으로 다크 테마를 추가했다. 작은 글자의 대비와 앱의 영역 구분에 맞춰 일부 중간색을 조정했다.

| 용도 | 색상 |
| --- | --- |
| 전체 배경 | `#252423` |
| 원본 영역 | `#32302F` |
| 결과 영역 | `#3C3836` |
| 본문 | `#F2E5BC` |
| 보조 글자 | `#D5C4A1` |
| 저장 버튼·선택 표시 | `#A9B665` |
| 배지·강조 제목 | `#E5BD76` |
| 선택 배경 | `#424A3E` |

검색·탭·메뉴·툴팁·진행 표시와 직접 그리는 썸네일 카드·체크 표시·드래그 이미지도 같은 테마를 사용한다. 초록색 버튼과 체크에는 어두운 글자를 사용한다. 슬라이드 이미지의 원래 색은 유지한다.

## 글자 가독성 보완

같은 날 사용자 피드백에 따라 본문은 밝은 크림색, 보조 글자는 밝은 베이지색으로 변경했다. 기본 글자와 카드 제목은 14px, 카드 출처와 번호·보조 안내는 13px, 사용 횟수 배지는 12px로 키웠다. 파일 목록과 버튼의 글자 굵기를 보완하고 검색창 안내문에도 명시적인 불투명 글자색을 지정했다. 기본 블루 테마의 글자 크기는 유지한다.

본문/원본 배경의 대비는 약 10.45:1, 출처/결과 배경의 대비는 기존 약 4.55:1에서 약 6.76:1로 높아졌다. 드래그 안내도 약 6.82:1로 조정했다.

구현한 검색창 안내문 색상 속성은 [Qt 스타일시트 문서](https://doc.qt.io/qt-6/stylesheet-reference.html#placeholder-text-color)를 따른다.

## 얇은 글꼴 보완

추가 사용자 피드백에 따라 글꼴을 Segoe UI 우선에서 `Malgun Gothic` 우선으로 변경했다. 이 환경의 맑은 고딕에는 Regular와 Bold만 있으며, Qt의 굵기 500은 실제 Regular로 표시되는 것을 glyph run 정보로 확인했다. Gruvbox의 기본·보조 글자와 카드·번호·배지·드래그 안내에 굵기 600을 사용해 실제 Bold 글꼴로 표시한다. 크기와 색상은 위 가독성 보완 상태를 유지한다. 블루 테마는 기존 굵기를 유지한다.

이 단계의 실행 파일은 `dist/gruvbox-material-bold/PPTMerge.exe`다. 기존 Gruvbox EXE가 실행 중이라 덮어쓰지 않고 새 폴더에 빌드했다. 설정과 자동 복원 경로는 같다. 최신 글꼴은 아래 Pretendard 적용 단계다.

- 실제 파일 목록·검색창·상태·저장 버튼과 카드 제목·출처의 한글·영문이 모두 `Malgun Gothic / Bold`로 표시되는지 검사했다. 보고서: `output/gruvbox_bold_font_verification.json`.
- 블루와 Gruvbox의 화면·편집·복원·종료 검사 32개씩 통과. 로그: `output/slate-blue_bold_tests.log`, `output/gruvbox-material_bold_tests.log`.
- 최신 화면: `output/gruvbox_bold_1600.png`, `output/gruvbox_bold_1000_source.png`, `output/gruvbox_bold_1000_result.png`, `output/gruvbox_bold_drop_1000.png`.
- 해당 단계 빌드 로그: `output/gruvbox_bold_build.log`.
- 단일 EXE 빌드 성공. 포함된 앱 모듈 38개와 현재 소스의 일치, 런타임 테마 훅과 굵기 600 설정을 확인했다. 기존 실행 파일들은 변경하지 않았다. 보고서: `output/gruvbox_bold_build_verification.json`, 체크섬: `output/gruvbox_bold_SHA256SUMS.txt`.

## Pretendard 적용

사용자가 다운로드한 Pretendard GOV 1.3.9 배포본에서 Medium·SemiBold·Bold 원본 OTF와 `LICENSE.txt`를 `assets/fonts`에 복사했다. 본문·파일명·보조 안내는 Medium(500), 카드 제목·영역 제목·주요 버튼은 SemiBold(600), 앱 브랜드는 Bold(700)를 사용한다. 앞선 강제 굵기 600 처리는 제거했다. 글자 크기와 테마 색상은 유지한다.

Qt의 `addApplicationFont()`로 앱 안에서만 등록하며 Windows에 설치하지 않는다. 소스는 프로젝트의 `assets/fonts`, EXE는 PyInstaller 번들 안의 같은 경로에서 읽는다. QApplication마다 한 번만 등록하고 PyInstaller에 원본 글꼴과 라이선스를 함께 포함한다. 기본 블루 테마에는 해당 글꼴을 적용하지 않는다.

- 최신 EXE: `dist/gruvbox-pretendard/PPTMerge.exe`.
- 화면: `output/gruvbox_pretendard_1600.png`, `output/gruvbox_pretendard_1000_source.png`, `output/gruvbox_pretendard_1000_result.png`, `output/gruvbox_pretendard_drop_1000.png`.
- 블루와 Gruvbox의 화면·편집·복원·종료 검사 각각 32개 통과. 로그: `output/slate-blue_pretendard_tests.log`, `output/gruvbox-material_pretendard_tests.log`.
- 빌드 로그: `output/gruvbox_pretendard_build.log`.
- 단일 EXE 빌드 성공. 앱 모듈 38개의 소스 일치, 글꼴 3개와 라이선스 원본 포함을 확인했다. EXE에서 추출한 앱 코드와 글꼴을 번들 디렉터리 구조에서 읽어 파일명·검색·안내는 Medium, 제목·저장 버튼은 SemiBold, 브랜드는 Bold로 표시되는 것을 확인했다.
- 보고서: `output/gruvbox_pretendard_build_verification.json`. 체크섬: `output/gruvbox_pretendard_SHA256SUMS.txt`.

## 실행과 빌드

- 최신 Gruvbox EXE: `dist/gruvbox-pretendard-ui/PPTMerge.exe`. 최초 Pretendard 적용 버전은 `dist/gruvbox-pretendard/PPTMerge.exe`, 맑은 고딕 Bold 버전은 `dist/gruvbox-material-bold/PPTMerge.exe`다.
- 기존 블루 EXE: `dist/slate-blue/PPTMerge.exe`.
- 두 EXE 모두 기존 `%LOCALAPPDATA%/PPTMerge` 설정·작업 복원 경로를 사용하므로 기존 앱을 종료한 뒤 다른 테마를 실행한다.
- 기본 소스 테마는 계속 `slate-blue`이며 `PPT_MERGE_THEME=gruvbox-material` 환경 변수로 다크 테마를 선택할 수 있다.
- Gruvbox EXE에는 앱 모듈을 읽기 전에 테마를 선택하는 PyInstaller 런타임 훅을 포함한다. EXE 하나만 복사해도 해당 테마를 적용한다.

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts/build_exe.py --theme gruvbox-material --dist-dir dist/gruvbox-pretendard-ui
```

기본 빌드 명령은 계속 블루 테마를 생성한다.

## 검증

- 기존 화면 배치·보기 전환·편집·자동 복원·종료 검사: 블루와 Gruvbox에서 각각 32개 통과, 프로세스 종료 코드 0.
- 가독성 보완 후 두 테마의 같은 검사 32개씩 다시 통과했다. 로그: `output/slate-blue_readable_tests.log`, `output/gruvbox-material_readable_tests.log`.
- 예시 썸네일과 가짜 읽기 데이터를 이용한 Qt offscreen 화면 검토: 1600×900·1000×640, 원본·결과 전환, 격자·가로 목록, 빈 결과와 드래그 미리보기.
- 앞선 색상·크기 보완 화면: `output/gruvbox_readable_1600.png`, `output/gruvbox_readable_1000_source.png`, `output/gruvbox_readable_1000_result.png`, `output/gruvbox_readable_drop_1000.png`.
- 앞선 색상·크기 보완 빌드 로그: `output/gruvbox_readable_build.log`.
- 단일 EXE 빌드 성공. 포함된 앱 모듈 38개가 현재 소스와 일치하며 런타임 테마 훅도 확인했다. 기존 블루 EXE의 해시는 변경되지 않았다.
- 빌드 검증 보고서: `output/gruvbox_material_build_verification.json`. 체크섬: `output/gruvbox_material_SHA256SUMS.txt`.

실제 Office COM 병합·취소와 배포 EXE의 Windows 실행은 위 테마 변경에서 재검증하지 않았다. 아래 UI 보완에서는 한 장의 실제 고해상도 내보내기를 추가로 확인했다.

## UI 점검 반영

같은 날 UI 점검 결과 6개 항목과 좌하단 상태 문구 여백을 수정했다.

1. 작업 목록은 `작업 목록 저장됨`, PPT는 `PPT 생성 전/완료/변경 사항 있음`으로 구분한다. 생성 이후 편집하면 저장 버튼은 `PPT 다시 생성`, 파일 열기는 `이전 생성본 열기`로 바뀐다. 실행 취소로 생성 당시 순서로 돌아오면 변경 표시도 해제한다.
2. 창 너비 1320px 고정 기준을 제거했다. 사용자가 지정한 썸네일 크기와 사이드바 너비를 기준으로 두 패널에 각각 두 열이 들어갈 공간을 계산해 나란히 보기를 제공한다.
3. 높이가 낮은 창에서는 원본 안내문과 도구 줄을 압축한다. 1000×640 예시에서 원본 썸네일 표시 높이는 기존 179px에서 279px로 늘고 세 장이 한 줄에 온전히 표시된다. 결과의 장수·선택 안내도 제목 줄로 합친다.
4. 파일 목록·검색·탐색기의 긴 이름은 가운데 말줄임으로 앞뒤를 보존한다. 선택한 파일의 전체 이름은 사이드바 위에서 줄바꿈해 표시·복사할 수 있고 원본 경로는 툴팁으로 확인한다. 사이드바 최대 너비도 480px로 늘렸다.
5. 확대 창은 기존 썸네일을 즉시 표시한 뒤 선택한 한 장만 1600px로 내보내 `cache/previews`에 저장한다. 파일 리비전·슬라이드 ID·해상도와 PNG 해시를 검증하며 유효한 캐시는 Office 실행 없이 재사용한다. 작업은 QThread에서 수행하고 이동·Esc·앱 종료 시 안전한 지점에서 취소하고 정리한다. PowerPoint 시작 실패 시 기본 이미지와 안내를 유지한다.
6. 자료가 없는 화면에는 중앙 `PPT 추가` 버튼과 파일 드롭 안내를 보여 주고 검색·확대·크기·담기 및 결과 편집 도구를 숨긴다.
7. 좌하단 상태 문구를 전용 컨테이너에 넣어 왼쪽 20px, 위 6px, 아래 8px 여백을 확보했다. QStatusBar의 표시 높이도 확보해 문구가 창 가장자리에 붙지 않게 했다.

### 검증

- Gruvbox 전체 단위·Qt 검사 **179개 통과**, 종료 코드 0: `output/ui_refinements_all_tests.log`.
- 기본 블루 화면·생성·편집·복원·종료 회귀 검사 **47개 통과**, 종료 코드 0: `output/ui_refinements_blue_tests.log`.
- 새 검사 13개는 생성 이후 편집·자동 저장·실행 취소, 두 열 기준 배치, 작은 창의 전체 카드와 상태 여백, 빈 화면 추가, 긴 파일명, 확대 창의 취소·이동·실패·부모 종료, 단일 슬라이드 캐시·손상 복구·원본 변경·실패 정리를 다룬다.
- 실제 PowerPoint에서 기본 A의 2번 슬라이드를 1600×900 PNG로 내보냈다. 같은 요청의 캐시 재사용, 원본 해시 유지와 잔여 PowerPoint 프로세스 0개를 확인했다. 보고서: `output/ui_preview_com/report.json`.
- Qt offscreen 화면: `output/ui_refinements_1600.png`, `output/ui_refinements_1000_source.png`, `output/ui_refinements_1000_result.png`, `output/ui_refinements_empty.png`, 격자·가로 목록·드래그 미리보기 화면.
- 빌드 로그: `output/ui_refinements_build.log`.
- 단일 EXE 빌드 성공. 앱 모듈 38개가 현재 소스와 일치하며 글꼴 3개·라이선스 포함을 확인했다. 번들에서 추출한 앱 코드와 글꼴로 빈 화면·실제 글꼴 굵기·상태 여백·생성 후 편집/되돌리기·1320px 보기 전환을 검증했다. 보고서: `output/ui_refinements_build_verification.json`, 체크섬: `output/ui_refinements_SHA256SUMS.txt`.
