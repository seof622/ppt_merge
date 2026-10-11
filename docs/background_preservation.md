# 개별 그림 배경 보존

2026-10-11, ‘배경 서식 → 그림 또는 질감 채우기 → 파일’로 넣은 그림이 합친 PPT에서 사라지는 문제를 수정했다.

## 원인과 수정

이 환경의 PowerPoint 16.0에서 `Slides.InsertFromFile`과 일반 복사·붙여넣기 모두 개별 그림 배경을 마스터 배경으로 바꿨다. 기존 코드는 디자인·레이아웃과 `FollowMasterBackground`만 복원하므로 누락된 그림을 되살리지 못했다. 앞선 기본 보존 테스트는 단색 마스터 배경 중심이었고, 개별 그림 채우기는 검증 범위에 없었다.

슬라이드 자체의 복사는 기존 PowerPoint COM 방식을 유지한다. COM이 저장하고 닫은 로컬 임시 결과에서 원본 슬라이드의 `p:bg` 정의 전체를 복사하고 배경이 참조하는 이미지의 관계 ID·경로를 연결한다. 이미지 원본 바이트, 투명도, 자르기, 타일·오프셋 등의 배경 XML을 보존하며, 그림을 새 도형으로 만들어 덮지 않는다. 마스터·레이아웃에서 상속하는 배경은 복제된 디자인을 그대로 사용한다. 원본 파일과 최종 저장 경로에는 이 복원 단계에서 쓰지 않는다.

담당 코드는 `src/ppt/background_preservation.py`이며 `PowerPointService.generate()`에서 원본 변경 확인 후 호출한다. 참조가 손상되면 최종 결과를 게시하지 않는다. 취소나 실패 시 수정 중인 임시 파일을 정리하며 기존 출력 파일을 보존한다.

## 검증

- 단위 테스트 5개: 투명도·자르기·타일 XML과 이미지 바이트 보존, 원본별 관계 ID 충돌과 중복, 상속 배경 유지, 누락된 관계의 안전한 실패, 복원 중 취소와 임시 파일 정리, 단색 배경 교체.
- 전체 단위 테스트 135개 통과.
- 기존 실제 Office 생성 회귀 테스트 9개 통과(154.875초). 기본·고급·PPTM 보존, 내부 링크, 취소·예외, 크기 혼합, 기존 사용자 세션 보호, 생성 중 종료, 원본 10개 처리를 재검증했다. 보고서는 `output/generation_validation_sm9em3wq/report.json`이다.
- 실제 Office 회귀 검증: 개별 그림, 35% 투명도, 사용자 질감과 타일 배치, 단색, 그라데이션, 마스터 그림, 서로 다른 원본과 중복을 섞은 8장. 배경 XML·이미지 해시를 비교하고 저장 결과를 PowerPoint로 다시 열어 960×540 PNG의 픽셀 완전 일치를 확인했다.
- 수정 전 COM 결과에서는 8장 중 마스터 그림 1장만 일치했고, 수정 후 8장 모두 일치했다. 원본 파일의 SHA-256은 유지됐으며 남은 `POWERPNT.EXE` 프로세스는 없었다.
- 수정된 frozen EXE를 한글 배포 폴더에 단독 복사해 개발 Python·가상환경을 찾지 않는 PATH에서 실행했다. 생성·썸네일·취소·종료 등 진단 19개를 통과했고, EXE가 생성한 A2 → B4 → A1 → A2 결과를 PowerPoint로 다시 열어 4장 모두 원본과 픽셀이 일치함을 확인했다. 보고서는 `output/background_exe_validation_5vdgund2/report.json`이다.

실제 Office 검증 보고서: `output/background_validation_t101r2pe/report.json`. 사용자 개인 PPT 원본은 제공받지 않았으므로 동일 방식으로 만든 재현 자료에서 검증했다.

배포 파일은 `dist/PPTMerge.exe`이다. 앞서 별도로 만든 `dist/background-fix/PPTMerge.exe`도 같은 최신 버전으로 맞췄다. 후속으로 확인한 원본에 없던 자리 표시자 생성 문제는 [실제 파일 병합 검증](merge_fidelity_validation.md)에 정리했다.

재검증:

```powershell
$env:PPT_MERGE_GENERATION_COM_TESTS = '1'
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests/integration -p test_background_com.py -v
```

EXE 검증 스크립트는 `--sources <A.pptx> <B.pptx>`로 별도 배경 재현 자료를 받을 수 있다. 두 원본은 각각 4장 이상이어야 하며 선택 순서는 A2 → B4 → A1 → A2이다.
