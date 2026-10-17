# 마지막 폴더와 PPT 저장 경로 기억

2026-10-17 변경.

- 최상위 폴더 선택이 성공하면 즉시 설정 파일에 저장하고 다음 실행에 복원한다.
- PPT 생성이 성공하면 전체 저장 경로와 확장자를 포함한 파일명을 저장한다. 다음 저장 창에서 그대로 제안한다.
- 폴더·저장 창 취소, 덮어쓰기 거절, 생성 실패·취소는 이전 성공값을 바꾸지 않는다.
- 이전 루트가 없으면 바탕화면(바탕화면이 없으면 사용자 홈)을 사용한다. 저장된 루트는 보관해 드라이브가 다시 연결되면 복원할 수 있다.
- 이전 저장 폴더가 없어졌으면 현재 루트 폴더와 이전 파일명을 제안한다. 결과 파일만 삭제되었으면 이전 저장 경로를 계속 제안한다.
- 최초 저장 이름은 기존과 동일한 `result.pptx`다. 기존 결과 덮어쓰기 확인과 원본 덮어쓰기 방지는 유지한다.

`QSettings`의 INI 파일을 사용하며 변경 즉시 `sync()`한다. 소스 실행은 프로젝트 루트의 `settings.ini`, EXE는 `%LOCALAPPDATA%/PPTMerge/settings.ini`를 사용한다. 쓰기 실패는 로그에 기록한다. 원본 목록과 출력 슬라이드 편집 목록은 복원 대상에 포함하지 않는다.

검증: 전체 단위 테스트 **151개 통과**. 추가한 8개 테스트는 별도 Python 프로세스에서 디스크 설정 읽기, 창 재생성 후 폴더와 저장 경로 복원, 한글·공백 경로, 폴더 삭제, 결과 파일 삭제, 확장자 자동 추가, 취소·실패·덮어쓰기 거절 및 기존 덮어쓰기 확인을 포함한다. PowerPoint 생성은 이 테스트에서 가짜 서비스로 검증한다.

`dist/PPTMerge.exe` 빌드·교체 완료. 격리된 사용자 데이터와 실제 Windows Qt 화면에서 EXE 검증 **19개 통과**, 종료 코드 0. 테스트 원본 2개의 썸네일을 읽어 4장 PPT를 생성하고, 40장 생성 중 창 닫기 취소와 PowerPoint 정리를 확인했다. EXE가 `settings.ini`에 성공한 출력 경로를 기록했으며 후속 취소에도 그 값이 유지되었다. 보고서는 `output/package_validation_iyaqct14/report.json`에 있다. 배포 파일과 검증한 빌드의 SHA-256 일치도 확인했다.

실행 명령:

```powershell
$env:TEMP = Join-Path (Get-Location) 'temp'
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests/unit
.\.venv\Scripts\python.exe -X utf8 scripts/build_exe.py
```
