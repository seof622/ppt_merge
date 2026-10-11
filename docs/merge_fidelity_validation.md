# 실제 파일 병합과 원본 구조 보존

2026-10-11, 사용자 지정 폴더의 실제 PPT 2개·전체 5장을 병합해 원본과 비교했다.

## 확인한 문제

제목 슬라이드 레이아웃을 사용하는 원본에서 제목·부제 자리 표시자가 삭제된 상태였다. `Slides.InsertFromFile`과 디자인 적용까지는 원본 도형을 유지했으나, `CustomLayout`을 다시 지정하면서 PowerPoint가 삭제된 자리 표시자를 생성했다. 원본 도형 1개인 장은 3개, 2개인 장은 4개가 됐다.

이 빈 입력 상자는 PNG 내보내기에 나타나지 않아 그림 비교만으로는 검출하지 못했다. 앞선 합성 자료는 주로 빈 레이아웃을 사용해 이 조건이 빠졌다. 실제 파일의 앞선 수정 결과에는 그림 배경이 보존되어 있었지만, 편집 가능한 도형 구조가 달랐다.

## 수정

삽입 직후 도형 ID를 기록하고 원본 디자인·레이아웃을 적용한 뒤, 그 과정에서 새로 생성된 자리 표시자만 PowerPoint COM으로 삭제한다. 원본 도형이나 원본에 있던 자리 표시자는 삭제하지 않는다. 배경 XML·이미지 복원은 그대로 유지한다.

기본 실행 경로 `dist/PPTMerge.exe`를 최신 수정본으로 다시 빌드했다. 앞서 제공한 별도 경로 `dist/background-fix/PPTMerge.exe`도 동일한 실행 파일로 맞췄다. 어떤 실행 파일을 사용했는지 확인할 수 있도록 앱 시작 로그에 실행 파일 경로를 추가했다.

## 검증

- 전체 단위 테스트 135개 통과.
- 실제 Office 자리 표시자 회귀 테스트: 제목만 있는 장, 제목·부제가 있는 장, 삭제된 장, 빈 장과 중복을 합친 5장. 도형 타입·이름·텍스트·좌표·개수와 렌더링이 모두 원본과 일치했다.
- 실제 지정 원본 2개·5장의 서비스 병합 결과: 모든 장의 배경 XML·이미지 해시, 도형 구조, 960×720 PNG의 픽셀이 원본과 일치했다. 원본 해시·수정 시각은 유지했고 남은 PowerPoint 프로세스는 없었다. 보고서: `output/merge_fidelity_wuxly_dc/fidelity_report.json`.
- 같은 실제 원본을 `dist/PPTMerge.exe`의 Qt 워커로 전체 병합한 결과도 5장 모두 배경·내용·도형 구조·픽셀이 일치했다. 진단 19개(썸네일·생성·취소·종료 포함) 통과, 남은 PowerPoint 프로세스 없음. 최종 결과는 `output/merge_fidelity_dzzvxhn7/merged.pptx`, 보고서는 같은 폴더의 `fidelity_report.json`이다.

반복 검증 도구는 `scripts/validate_merge_fidelity.py`이다. 지정한 순서대로 각 원본의 모든 장을 합쳐, 단순 장수 확인에 더해 구조·배경·렌더링과 원본 변경 여부를 검사한다. `--exe`를 지정하면 frozen EXE의 Qt 워커에서 병합한 결과를 검증한다. 개발용 전체 장수 진단은 `--package-check-all-slides`로 활성화한다.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.validate_merge_fidelity --exe dist/PPTMerge.exe <원본1.pptx> <원본2.pptx>
```

검증 결과와 PNG는 매 실행마다 새 `output/merge_fidelity_*` 폴더에 저장한다. 입력 파일이나 사용자의 기존 결과 파일은 덮어쓰지 않는다.

## Polaris Office에서 제목만 표시된 문제

같은 결과 파일을 PowerPoint 편집 화면과 슬라이드 쇼에서 열면 5장의 악보·그림 배경이 표시됐지만, Polaris Office에서 열면 제목만 남고 5장 모두 그림이 사라졌다. PowerPoint 렌더링과 구조 비교만으로 다른 Office의 표시 호환성까지 확인했다고 판단해서는 안 된다.

배경 복원 시 ElementTree가 `[Content_Types].xml`과 슬라이드 `.rels`의 기본 네임스페이스를 `ns0:` 접두사로 바꿨다. 네임스페이스 URI는 같아 PowerPoint에서는 읽혔지만, Polaris에서는 그림 연결이 처리되지 않았다. 기존 패키지의 기본 네임스페이스·접두사 표기를 DOM으로 보존하고, 새 그림 관계와 형식 항목에도 같은 표기를 사용하도록 수정했다. 전역 네임스페이스 등록은 사용하지 않는다.

실패 결과의 위 표기만 원래 기본 네임스페이스로 되돌리고 새 복원 코드로 저장한 `output/polaris_validation/merged_polaris_fixed.pptx`를 Polaris에서 직접 열었다. 첫 장의 악보·배경과 5장 모두의 썸네일이 표시되는 것을 확인했다. 수정 전 파일은 제목만 보이는 상태를 같은 앱에서 재현했다. 기본 및 기존 접두사 입력을 보존하는 회귀 테스트를 추가했다.

최종 수정으로 `dist/PPTMerge.exe`를 다시 빌드하고 `dist/background-fix/PPTMerge.exe`에도 동일한 바이트를 배포했다. 원본 2개를 새 EXE로 병합한 `output/merge_fidelity_tv05c_jb/merged.pptx`는 5장 모두 픽셀·도형 구조·배경 XML/이미지가 원본과 일치했고, 19개 패키지 진단을 통과했다. 이 파일의 동일한 복사본 `output/polaris_validation/merged_polaris_verified.pptx`를 Polaris에서 열어 악보·그림 배경과 5장 썸네일 표시를 다시 확인했다. 원본은 변경하지 않았다.

전체 단위 테스트는 오프스크린 모드에서 136개 모두 통과했다(28.114초). 앞선 화면 모드 실행은 UI 대기 상태에서 멈춰 중단했다. 검증 로그는 `output/polaris_validation/unit_tests.log`, 최종 생성 보고서는 `output/merge_fidelity_tv05c_jb/fidelity_report.json`이다.
