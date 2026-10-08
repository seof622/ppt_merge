# 고급 PowerPoint COM 보존 검증

2026-10-07, PowerPoint 16.0에서 자동 검증을 완료했습니다. SVG·SmartArt·오디오·비디오·Excel OLE·모션 경로와 내부 링크의 자동 비교는 통과했습니다. 2026-10-08 사용자가 위 결과의 외관·재생·클릭·편집 동작을 확인한 뒤 ‘이상 없음’으로 응답했습니다. 주 확인 결과의 자동·수동 검증 모두 **통과**입니다. 아래 절차는 재검증에 사용할 수 있습니다.

## 확인할 파일과 정확한 경로

- [주 확인 결과 result.pptx](</C:/Work/Side Project/ppt_merge/output/advanced_20261007_161845/result.pptx>) — `C:\Work\Side Project\ppt_merge\output\advanced_20261007_161845\result.pptx`, 10장
- [비교용 원본 advanced.pptx](</C:/Work/Side Project/ppt_merge/tests/fixtures/advanced/advanced.pptx>) — `C:\Work\Side Project\ppt_merge\tests\fixtures\advanced\advanced.pptx`, 9장
- [연결된 Excel source_data.xlsx](</C:/Work/Side Project/ppt_merge/tests/fixtures/advanced/source_data.xlsx>) — `C:\Work\Side Project\ppt_merge\tests\fixtures\advanced\source_data.xlsx`

PowerPoint에서 결과와 원본을 열어 아래 번호를 비교합니다. 코드 실행이나 패키지 설치는 필요 없습니다. 결과는 복구 경고 없이 열려야 합니다. 편집 동작을 시험한 뒤에는 저장하지 않고 닫으면 됩니다.

| 결과 슬라이드 | 원본 슬라이드 | 직접 확인할 동작 |
| --- | --- | --- |
| 1 | 5 | 현재 슬라이드에서 `Shift+F5` → ‘링크 대상 G-6으로 이동’ 클릭 → **결과 3장**으로 이동 |
| 2·10 | 1 | SVG의 원·삼각형·그라데이션이 원본과 같고, 이미지를 선택하면 그래픽 형식 메뉴가 표시됨 |
| 3 | 6 | ‘G-6에 도착했습니다.’가 표시되는 링크 도착 지점 |
| 4 | 2 | SmartArt를 선택하면 SmartArt 메뉴와 텍스트 창이 표시되고 ‘단계 1·2·3’을 편집할 수 있음 |
| 5 | 3 | `Shift+F5` → 오디오 아이콘의 재생 버튼으로 **2초 테스트음**이 들림 |
| 6 | 4 | `Shift+F5` → 영상의 재생 버튼으로 **3초 동안 패턴이 움직임**. 영상에는 소리가 없음 |
| 7 | 7 | Excel 객체를 더블클릭하면 통합문서를 편집할 수 있고 `TestData`의 값은 `10, 20, 15` |
| 8 | 8 | 막대 값이 `10, 20, 15`이며 연결 원본이 위의 `source_data.xlsx`로 유지됨 |
| 9 | 9 | `Shift+F5` → 슬라이드 클릭 시 보라색 원이 약 **1.5초 원형 경로**를 따라 이동 |

슬라이드 쇼에서 `Esc`를 누르면 편집 화면으로 돌아옵니다. 8장의 외부 연결은 PowerPoint의 **파일 → 정보 → 파일 연결 편집**에서 원본 경로를 확인할 수 있습니다. 표시되는 연결에 `source_data.xlsx`와 `TestData`가 포함되어야 합니다. 외부 연결을 확인할 때 원본 Excel 값을 바꾸거나 연결을 끊을 필요는 없습니다.

결과 노트의 순서는 `NOTES_G-5, NOTES_G-1, NOTES_G-6, NOTES_G-2, NOTES_G-3, NOTES_G-4, NOTES_G-7, NOTES_G-8, NOTES_G-9, NOTES_G-1`입니다. 전체 배경·테마·하단 띠·페이드 전환도 원본과 같아야 합니다.

확인 후 ‘이상 없음’ 또는 ‘결과 슬라이드 번호 / 다른 점’을 알려주세요. 예: `6번 / 재생을 눌러도 영상이 움직이지 않음`.

## 자동 검증 결과

| 사례 | 출력 장수 | 결과 |
| --- | --- | --- |
| 원래 디자인 보존 방식, 명시적 링크 재연결 없이 실행 | 10 | 통과 |
| 재정렬·SVG 중복, 링크 재연결 적용 (`result`) | 10 | 통과 |
| 링크 출발·대상 중복 및 기본 A 테마 혼합 (`duplicates`) | 12 | 통과 |
| 매크로 없는 PPTM 입력 → PPTX (`pptm`) | 9 | 통과 |
| 두 소스의 같은 SlideID를 구분하여 링크 재연결 (`cross_source`) | 6 | 통과 |
| 내부 링크 대상이 출력 선택 목록에 없는 경우 | 생성 중단 | 통과, 완성·부분 출력 파일 모두 미생성 |

총 47장 비교에서 원본과 출력의 1280×720 PNG 픽셀이 일치했습니다. COM 도형·SmartArt 노드·미디어 길이·OLE 종류·외부 경로·노트·애니메이션·전환 정보를 비교했습니다. SVG·미디어·OLE 내장 파일은 바이트 해시를, SmartArt 편집 XML은 렌더 캐시 확장을 제외한 정규화 해시를 비교했습니다. 내부 링크는 출력 순서에서 실제 도착 슬라이드를 검사했습니다. 모든 소유 PowerPoint 세션이 정상 종료했습니다.

명시적 링크 재연결이 없는 기존 방식도 이 자료에서는 성공했습니다. 추가된 재연결은 대상 누락·중복·서로 다른 소스의 동일 SlideID를 명시적으로 처리합니다. 대상이 중복 선택되면 **출력 순서에서 첫 번째 대상**으로 연결하고 로그에 기록합니다. 대상을 선택하지 않으면 저장 전에 오류로 중단합니다.

보고서 및 추가 확인 파일:

- [주 자동 보고서](</C:/Work/Side Project/ppt_merge/output/advanced_20261007_161845/report.json>) — `C:\Work\Side Project\ppt_merge\output\advanced_20261007_161845\report.json`
- [Office 파일 무결성·관계 검사 보고서](</C:/Work/Side Project/ppt_merge/output/advanced_20261007_161845/package_audit.json>) — `C:\Work\Side Project\ppt_merge\output\advanced_20261007_161845\package_audit.json`, PPTX·PPTM·XLSX 8개 검사 통과
- [소스 간 링크 자동 보고서](</C:/Work/Side Project/ppt_merge/output/advanced_20261007_162204/report.json>) — `C:\Work\Side Project\ppt_merge\output\advanced_20261007_162204\report.json`
- [중복 링크 결과 duplicates.pptx](</C:/Work/Side Project/ppt_merge/output/advanced_20261007_161845/duplicates.pptx>) — `C:\Work\Side Project\ppt_merge\output\advanced_20261007_161845\duplicates.pptx`, 2·4장의 링크가 첫 대상인 1장으로 이동
- [소스 간 링크 결과 cross_source.pptx](</C:/Work/Side Project/ppt_merge/output/advanced_20261007_162204/cross_source.pptx>) — `C:\Work\Side Project\ppt_merge\output\advanced_20261007_162204\cross_source.pptx`, 1장 링크 → 3장, 4장 링크 → 2장
- [PPTM 입력 결합 결과 pptm.pptx](</C:/Work/Side Project/ppt_merge/output/advanced_20261007_161845/pptm.pptx>) — `C:\Work\Side Project\ppt_merge\output\advanced_20261007_161845\pptm.pptx`

결과와 보고서는 Git에서 제외되는 로컬 `output/`에 있습니다. 기본 자료 회귀 검증도 디자인 보존 방식의 12장 비교 및 신뢰성 6개 사례가 통과했습니다.

## 검증 범위와 남은 항목

- `.pptm`은 VBA가 없는 컨테이너 입력만 검증했습니다. 실제 매크로 보존이나 실행을 검증하지 않았습니다.
- 외부 연결은 `Excel.Sheet.12` OLE 차트입니다. 경로와 차트 캐시 외관을 비교했으며, 원본 Excel 값 변경 후 실제 갱신은 자동 시험하지 않았습니다. PowerPoint 기본 차트의 외부 `ChartData` 연결은 별도 자료가 필요합니다.
- 미디어 재생, SmartArt·OLE의 실제 편집, 링크 클릭과 모션 재생은 위 주 확인 결과에서 사용자 확인을 통과했습니다. PNG와 파일 바이트 비교만으로 동작을 모두 판단하지 않으며, 다른 입력 자료는 별도 확인이 필요합니다.
- 암호화·손상 파일, 기존 사용자 PowerPoint와 동시 작업, 저장 중 강제 종료는 후속 검증 대상입니다.

## 재실행과 코드

PowerPoint를 닫고 아래 명령을 실행합니다. 결과는 새 `output/advanced_<날짜_시간>/`에 저장됩니다.

```powershell
.\.venv\Scripts\python.exe scripts/poc/run_advanced_poc.py
```

자료 생성에는 Excel도 필요합니다. 외부 Excel 경로가 현재 컴퓨터의 절대 경로이므로 다른 경로에서는 PowerPoint·Excel을 닫고 새 폴더에 재생성합니다.

```powershell
.\.venv\Scripts\python.exe scripts/poc/create_advanced_fixtures.py --directory temp/advanced_fixture
.\.venv\Scripts\python.exe scripts/poc/run_advanced_poc.py --fixtures temp/advanced_fixture
```

- `scripts/poc/create_advanced_fixtures.py`: 합성 미디어와 네이티브 PowerPoint·Excel 검증 자료 생성
- `scripts/poc/internal_links.py`: 소스 파일·SlideID별 내부 링크 재연결, 누락 감지·중복 정책
- `scripts/poc/run_advanced_poc.py`: 재정렬·중복·PPTM·소스 간 링크 비교 및 보고서 생성
- `scripts/poc/verify_slides.py`: COM 서명·자료 해시·렌더 비교
- `scripts/poc/com_session.py`: Win32 프로세스 스냅샷으로 실행 중인 Office 세션만 감지, 종료 후 남은 기록 제외
