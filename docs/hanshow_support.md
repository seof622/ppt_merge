# 한쇼 SHOW 지원 로드맵과 1단계 검증

브랜치: `codex/show-support`. 목표는 한쇼에서 SHOW를 PPTX로 변환하고 기존 PowerPoint 미리보기·병합 엔진을 재사용하는 것이다. 1단계에서는 앱 UI와 배포 EXE의 지원 형식을 변경하지 않는다.

## 확정한 로드맵

| 단계 | 작업 | 완료 조건 |
| --- | --- | --- |
| 1 | 실제 한쇼 자동화·변환·품질 검증 | SHOW 열기 → PPTX 저장 → PowerPoint 열기·미리보기·병합과 종료를 검증하고 호환성 한계를 기록 |
| 2 | 임시 변환 서비스 | 원본을 수정하지 않고 앱 전용 임시 폴더에 변환; 최종 저장·검증 성공 후 변환본 삭제; 재생성 시 원본에서 다시 변환 |
| 3 | 검색·로딩·미리보기 | 폴더·검색·드래그 앤 드롭에서 SHOW 인식; 변환 상태·오류 안내; 원래 파일명을 표시 |
| 4 | 혼합 병합·안정성 | 원본 SHOW와 변환본의 경로·변경 정보 연결; 혼합 병합, 취소·실패 처리, 기존 사용자 문서 보호 |
| 5 | 통합 검증·EXE | 실제 Office와 여러 형식·원본 변경·재생성·종료를 검증하고 단일 최종 EXE 빌드 |
| 6 | SHOW 결과 자동 저장 | 병합 PPTX를 한쇼로 열어 SHOW 저장·검증; 성공 후 중간 파일 정리; 왕복 변환 품질 확인 |

최종 형식이 SHOW이면 6단계 저장·검증까지 성공한 뒤 중간 파일을 삭제한다. 원본 SHOW와 사용자 지정 최종 결과물은 삭제하지 않는다. 취소·실패·앱 종료 때에도 앱 소유 임시 파일만 정리한다. 변환본 삭제 후에도 출력 목록을 유지하려면 원본 경로와 선택한 슬라이드 정보를 보존하고 다음 생성 때 다시 변환·검증해야 한다.

## 2026-10-10 검증 환경

- Windows, 프로젝트 Python 3.12 가상 환경, pywin32.
- 한쇼 2022 실행 파일 버전 `12.0.0.535`, 32비트 등록.
- ProgID `HShow.Application`, 클래스 `{11D90292-3D2E-49A5-BB3F-611E9C67F3A3}`.
- 설치된 `HShowObject.tlb`에서 `Presentations.Open`, `Presentation.SaveAs`, `Slide.Export`, `Application.Quit`, `IsExistReadPassword`를 확인했다.
- `ppSaveAsOpenXMLPresentation` 실제 값은 `24`이다. 레지스트리와 Office 설정을 수정하지 않았다.
- PowerPoint 버전 `16.0`. 다른 한쇼·PowerPoint 버전의 호환성은 미검증이다.

공식 문서는 [PPTX 저장](https://help.hancom.com/hoffice/multi/ko_kr/show/file/save_as/save_as.htm)과 [PPTX 불러오기](https://help.hancom.com/hoffice120/ko-KR/HShow/file/open/open%28other%29.htm)를 안내한다. COM 호출 가능 여부는 공개 한글(HWP) API를 한쇼 API로 추정하지 않고, 설치된 한쇼 타입 라이브러리와 실제 실행으로 확인했다.

## 검증 코드와 실행

- `scripts/poc/hanshow_session.py`: 기존 한쇼 실행 시 검증을 시작하지 않고, 앱 소유 프로세스를 확인한 뒤 종료한다.
- `scripts/poc/validate_hanshow.py`: 한쇼 저장·렌더링, PowerPoint 파일 검증·렌더링, 기존 썸네일·생성 서비스 재사용, 원본 해시·임시 폴더 정리를 검사한다.

한쇼와 PowerPoint에서 작업 중인 자료를 저장하고 두 프로그램을 닫은 뒤 프로젝트 루트에서 실행한다.

```powershell
.venv\Scripts\python.exe -u scripts\poc\validate_hanshow.py
```

기본 모드는 기존 PPTX 테스트 자료를 한쇼 자체 저장 기능으로 SHOW 샘플로 만든 뒤 검증한다. 실제 SHOW를 시험하려면 `--source`를 반복 지정한다. 입력 파일은 수정하지 않으며 결과는 새 `output` 하위 폴더에 저장한다.

```powershell
.venv\Scripts\python.exe -u scripts\poc\validate_hanshow.py --source "C:\자료\sample.show"
```

스크립트는 원본·샘플 SHOW, 결과 PPTX, 비교 PNG와 JSON 보고서를 보존한다. 앱 전용 임시 폴더의 변환 PPTX와 썸네일은 검증 완료·실패 시 제거한다. 검증용 SHOW·결과 PPTX는 변환 캐시가 아니라 재현·품질 비교용 산출물이다. 기존 결과를 덮어쓰지 않으며, COM 호출 중 강제 취소·시간 제한은 아직 구현하지 않았다.

## 기본·고급 샘플 실행 결과

실행 보고서: `output/hanshow_poc_stage1/report.json`.

| 샘플 | 슬라이드 | 내용 |
| --- | ---: | --- |
| A | 4 | 한글·영문 글꼴, 이미지, 그룹, 표, 기본 차트, 애니메이션·전환, 마스터·노트·외부 링크 |
| B | 4 | 다른 테마와 배경, A와 같은 객체 범위 |
| C | 1 | 4:3 슬라이드 |
| advanced | 9 | SVG, SmartArt, 오디오·영상, 내부 링크, Excel OLE·외부 연결, 모션 경로 |

총 18장 모두 다음 검사를 통과했다.

1. 한쇼에서 SHOW 저장·재열기·PNG 내보내기·PPTX 저장.
2. 변환 PPTX의 패키지·CRC·XML·관계 검증 및 PowerPoint 열기.
3. 원본 PPTX와 시험 SHOW의 파일 해시가 작업 전후 동일.
4. SHOW와 PPTX의 슬라이드 수·크기·검사한 텍스트·폰트·객체 개수·자산 정보 보존.
5. 같은 SHOW의 재변환 시 검사한 내용·자산·슬라이드 ID 동일.
6. 변환 PPTX와 최초 테스트 PPTX의 PowerPoint COM 서명에 차이가 없음. 검사 범위는 글꼴·배치·그룹·표·차트·SmartArt·미디어·OLE·애니메이션·전환·배경·테마·레이아웃·노트·링크이다.

변환 A의 2장째 → 원래 B의 4장째 → 변환 A의 1장째 순서로 기존 앱 서비스를 통해 3장 결과물을 생성했다. 출력 순서·COM 서명을 확인했고, 비교 PNG 3장도 모두 픽셀 단위로 같았다. 변환 임시 폴더는 삭제되었다.

문서 열기 후 의도적 오류, 안전한 지점에서 취소, 기존 한쇼 세션이 있을 때 시작 거부를 각각 검증했다. 기록된 17개 세션은 정상 종료했고, 썸네일·생성 서비스의 PowerPoint 정리도 로그에서 확인했다. 실행 종료 시 한쇼·PowerPoint 프로세스가 남지 않았다.

### 한쇼 기본 SHOW 샘플 추가 검증

한쇼에 포함된 `Bin/Resource/HShow/Style/ko-KR/Afterimage.show` 15장도 별도로 검증했다. 이 샘플은 PowerPoint 테스트 자료에서 새로 만든 파일이 아니라 설치된 한쇼 기본 SHOW 테마다. 원본을 수정하지 않았으며 앱 UI의 추가 샘플 창과 별도인 COM 프로세스를 유일하게 식별해 사용했다. 기존 창을 보존한 상태에서 새 자동화 프로세스만 정상 종료되었다.

보고서는 `output/hanshow_native_template/report.json`이다. 15장 모두 SHOW→PPTX 후 검사한 내용·자산·크기가 보존되었고 재변환 결과도 안정적이었다. PowerPoint에서 15장을 열고 내보냈으며 임시 변환 폴더도 삭제되었다. 한쇼와 PowerPoint PNG는 서로 달랐다. 기본·고급 합성 18장과 기본 SHOW 15장을 합쳐 **총 33장**을 검증했다.

두 보고서와 혼합 병합 PNG 비교를 합친 최종 요약은 `output/hanshow_poc_stage1/summary.json`이다. `passed=true`, `total_slides=33`, `temporary_folders_deleted=true`를 확인했다. `fidelity_exact=false`는 화면 차이가 남아 있다는 뜻이며 자동 변환 실패를 뜻하지 않는다.

같은 자료는 설치 경로를 확인한 뒤 기본 실행 모드로 재검증할 수 있다.

```powershell
.venv\Scripts\python.exe -u scripts\poc\validate_hanshow.py --source "C:\Program Files (x86)\HNC\Office 2022\HOffice120\Bin\Resource\HShow\Style\ko-KR\Afterimage.show"
```

기존 인스턴스가 있을 때 별도 프로세스를 식별하는 추가 실험에서는 `HanShowSession(allow_preexisting=True)`를 사용했다. 기본값과 CLI는 계속 기존 한쇼 실행을 차단한다. 이는 앱에서 여러 한쇼 인스턴스를 함께 사용할 수 있다는 보장이 아니다.

## 품질 판단과 한계

**자동 변환과 기존 엔진 재사용은 가능하다. 한쇼 화면과 PowerPoint 화면의 완전한 일치는 확인되지 않았다.**

18장 모두 한쇼 PNG와 PowerPoint PNG가 픽셀 단위로 달랐다. 채널 RMS 범위는 `8.011202~76.425436`이며 이는 품질 점수가 아니라 이미지 차이 지표다. 육안으로 글자 위치·차트 표현 차이를 확인했고, SVG 샘플은 한쇼 내보내기 PNG에서 본문 그림이 표시되지 않지만 PowerPoint에서는 표시되었다. 자산 파일과 변환 후 PowerPoint COM 정보는 보존되었으므로 이 현상을 변환 중 SVG 데이터 손실로 단정하지 않는다.

이 결과는 PPTX를 한쇼에서 불러와 SHOW로 저장한 합성 샘플과 한쇼 기본 SHOW 테마의 검사 결과다. 한쇼에서 직접 작성한 복잡한 사용자 SHOW, 구버전 SHOW, 암호·손상 문서는 별도 검증이 필요하다. 오디오·동영상·애니메이션 재생, 외부 Excel 연결 갱신은 자동 메타데이터 검사만으로 정상 동작을 보장하지 않는다.

추가 샘플 작성 과정에서 한쇼 텍스트 편집 COM 호출이 `0x8000FFFF`를 반환했다. 창 없는 모드의 `Shapes.AddTextbox`, 창 있는 모드의 `TextRange.Text` 설정이 실패했다. 이 문제는 파일 열기·저장·내보내기 성공 여부와 별개이며, 지원 기능에서는 해당 편집 API에 의존하지 않는다.

한쇼 UI에서 새 합성 문서의 제목·본문·도형도 작성했으나 표 만들기 대화상자에서 computer-use 도구가 `failed to activate captured window`를 반환했다. 이 문서는 저장하지 못했으므로 33장 검증 수에 포함하지 않는다. 기본 SHOW 샘플로 추가 변환 검증을 완료한 뒤, 시작 시각·경로·PID·새 문서 제목이 모두 일치하는 시험 프로세스만 종료했다. 이후 한쇼와 PowerPoint의 실행 프로세스가 없는 것을 확인했다.

2단계에서는 파일 변환 서비스와 임시 파일 관리부터 구현하되, 화면 차이를 자동으로 수정하거나 모든 한쇼 문서의 원본 보존을 보장하지 않는다. 5단계 배포 검증과 6단계 SHOW 저장에는 추가 품질 확인이 필요하다.
