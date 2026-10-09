# 신뢰성 검증 — Phase 6

2026-10-09. Phase 6은 COM 정리·스레드·취소·오류 안내·로그와 10~20개 파일, 100~500장 처리 검증을 대상으로 합니다.

## 변경 사항

- PowerPoint를 실행하기 전에 PPT 패키지의 필수 항목, 전체 CRC, XML, 내부 관계 대상과 슬라이드 ID 참조를 검사합니다. 누락·손상 자료를 복구 창에 넘기지 않고 오류로 처리합니다.
- 큰 미디어는 1MB 단위로 검사하고 검사 도중 취소를 확인합니다. 썸네일과 생성 준비가 같은 검증을 사용합니다.
- 대량 재검증에서 캐시 폴더 교체의 간헐적인 Windows 접근 거부를 발견했습니다. 공유/접근 거부에만 최대 0.75초, 4회 재시도하고 계속 실패하면 기존 캐시를 복원합니다. 재시도 중에도 취소를 확인합니다.
- Windows 공유 잠금과 권한/읽기 전용 오류를 구분해서 안내합니다. Python 스트림이 두 오류를 같은 errno로 전달하면 읽기 전용 OPEN_EXISTING으로 공유 상태를 확인하고 핸들을 즉시 닫습니다. [Microsoft CreateFileW 문서](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)를 기준으로 구현했습니다. 자세한 예외와 원인은 로그에 기록합니다.
- 반복 COM 실행에서 PowerPoint 서버 실행 실패(0x80080005)도 관찰했습니다. 실패 후와 1초 대기 후 모두 PowerPoint 프로세스가 없을 때만 한 번 재시도합니다. 다른 오류·실행 중인 프로세스에는 재시도하지 않습니다.
- PPT 생성 로그에 원본 수·출력 장수·소요 시간·중단 종류를 기록합니다.
- 원본 서식 보존 방식, 사용자 PowerPoint 세션 보호, OneDrive를 위한 로컬 임시 저장 후 게시 방식을 유지합니다.

## 대량 검증

실제 설치된 PowerPoint 16.0과 화면 없는 Qt 창에서 수행했습니다. A/B 기본 자료를 PowerPoint로 10장·25장으로 늘린 뒤 서로 다른 실제 파일로 복제했습니다. 텍스트·이미지·도형·그룹·표·차트·원본 테마·애니메이션·노트를 반복한 합성 자료입니다.

최종 코드 재검증 결과:

| 자료 | 최초 썸네일 로딩 | 캐시 재로딩 | PPT 생성 | 생성 중 최대 GUI 타이머 간격 |
| --- | ---: | ---: | ---: | ---: |
| 10개 파일 / 100장 | 47.531초 | 0.773초 | 19.091초 | 0.050초 |
| 20개 파일 / 500장 | 126.694초 | 2.084초 | 54.373초 | 0.041초 |

생성 시간에는 준비·원본 확인·복사·저장·COM 종료·무결성 검사·최종 게시를 포함합니다. GUI 타이머는 20ms 주기이며 이 값은 해당 환경의 이벤트 루프 지연 측정입니다. 모든 하드웨어에서 같은 속도를 보장하는 값은 아닙니다. 최초 로딩은 각 원본의 PowerPoint 실행·종료 비용을 포함하며 캐시 로딩은 PowerPoint를 실행하지 않습니다.

100장·500장 전체의 장수·출력 순서·본문·발표자 노트·이미지/차트 자료와 5개 표본의 PNG 및 COM 정보 비교를 통과했습니다. 전체 선택·다중 항목 순서 이동·마지막 항목 스크롤·모든 썸네일 요청도 확인했고 메모리 내 아이콘 캐시는 128개 이내였습니다. 모든 앱 소유 PowerPoint 세션이 종료되었고 잔존 프로세스·부분 게시 파일이 없었습니다.

표본 COM 비교에는 도형·서식·테마·레이아웃·애니메이션·전환을 포함합니다.

- [최종 신뢰성 보고서](../output/reliability_validation_cdo3sxjy/report.json)
- [100장 결과](../output/reliability_validation_cdo3sxjy/bulk_100/결과.pptx)
- [500장 결과](../output/reliability_validation_cdo3sxjy/bulk_500/결과.pptx)
- [500장 화면](../output/reliability_validation_cdo3sxjy/bulk_500/500_or_100_slides.png)

## 오류·취소 검증

최종 단위 테스트 **84개**, 실제 Office 통합 테스트 **22개**를 모두 통과했습니다. Office 테스트는 신뢰성 5개 + 생성 9개 + 썸네일 8개이며 한 번의 최종 실행에서 모두 성공했습니다.

| 검증 | 결과 |
| --- | --- |
| 10개 원본을 추가한 뒤 창 종료 | 앱 소유 PowerPoint 잔존 없음 |
| 생성 중 취소·창 닫기 | COM·스레드 정리, 미완성 출력 게시 안 함 |
| 한 원본이 열리지 않음 | 실패 격리, 정상 원본 로딩·생성 가능 |
| 생성 도중 예외 주입 | 기존 결과의 바이트 유지, COM·임시 출력 정리 |
| 기존 사용자 PowerPoint가 열려 있음 | 새 COM 작업 거부, 사용자 세션 보존, 캐시 사용 가능 |
| 실제 암호 보호 PPTX | Office 실행 전 거부, 암호 입력 창 없음 |
| 잘린 ZIP·슬라이드 누락·XML 손상·미디어 CRC 손상 | Office 실행 전 거부, 정상 원본은 계속 사용 가능 |
| 원본/결과 파일 공유 잠금·게시 중 잠금 | 사용 중 안내, 기존 결과 보존 |
| 읽기 전용 결과 파일 | 권한 안내, 기존 결과 보존 |
| 선택 후 원본 변경·삭제 | 생성 거부, 출력 게시 안 함 |
| 캐시 폴더 교체의 일시/지속 실패 및 재시도 중 취소 | 제한된 재시도, 기존 캐시 복원·보존 |
| COM 서버 시작 실패 후 사용자 프로세스가 나타남 | 재시도 안 함, 사용자 프로세스에 연결 안 함 |

정상 완료·취소·예외의 종료 상태를 확인했고 최종 보고서의 잔존 PowerPoint PID 목록은 모두 비어 있습니다. 의도적으로 주입한 손상·잠금·생성 예외는 app.log에 오류로 기록되며 테스트 실패를 뜻하지 않습니다.

- [신뢰성·대량 검증 보고서](../output/reliability_validation_cdo3sxjy/report.json)
- [생성·보존·취소·사용자 세션 보호 보고서](../output/generation_validation__7qfgcg3/report.json)
- [썸네일·캐시·스레드 회귀 보고서](../output/thumbnail_validation_aczr7bw4/validation_report.json)


검증 자료의 암호는 PowerPoint의 [Presentation.Password API](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.presentation.password)로 설정합니다. 암호 입력 기능을 추가하는 작업은 포함하지 않습니다.

## 사용자 수동 확인

2026-10-09 사용자가 안내한 수동 확인 1~3번이 모두 정상이라고 확인했습니다.

- 실제 자료로 PPT 생성·슬라이드 순서·중복 추가 확인: 정상.
- 생성 취소·창 닫기와 재실행 후 생성 확인: 정상.
- 실제 창에서 스크롤·다중 선택·드래그 순서 변경 확인: 정상.

사용자 확인에 따른 기록이며, 사용한 파일·슬라이드 수와 콘텐츠별 상세 비교 결과는 별도로 수집하지 않았습니다.

## 재검증 방법

PowerPoint를 닫고 실행합니다. 테스트는 고유한 output 폴더에서 합성 원본과 결과를 만들며 개인 입력 파일을 수정하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests/unit -v

$env:PPT_MERGE_RELIABILITY_COM_TESTS = '1'
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests/integration -p test_reliability_com.py -v

$env:PPT_MERGE_GENERATION_COM_TESTS = '1'
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests/integration -p test_generation_com.py -v

$env:PPT_MERGE_COM_TESTS = '1'
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests/integration -p test_thumbnail_com.py -v
```

대량 테스트는 수 분이 걸립니다. 실제 Office 검증을 활성화하지 않으면 통합 테스트는 건너뜁니다. 보고서·PPT·PNG·실행 로그는 Git에서 제외되는 output·logs에 남습니다.

## 검증 범위와 다음 단계

500장 전체가 서로 다른 무거운 미디어·OLE·SmartArt로 구성된 자료의 부하는 측정하지 않았습니다. 고급 콘텐츠 보존은 별도의 기존 고급 자료 통합 검증으로 확인합니다. 실제 VBA 매크로 실행/보존과 모든 가능한 OOXML 손상을 보장하는 검증은 아닙니다.

기존 사용자 PowerPoint가 열려 있으면 새 COM 작업은 거부하고 그 세션은 보존합니다. 캐시 사용은 계속 가능합니다. 사용자가 작업 도중 새 PowerPoint를 여는 동시 사용은 지원 범위에 포함하지 않습니다.

Phase 6의 자동 검증과 위 사용자 수동 확인을 완료했습니다. 다음 개발 단계는 Phase 7 UX 다듬기입니다. 프로젝트 저장·Undo/Redo·검색 등 Post-MVP 기능은 별도 요청 대상입니다.
