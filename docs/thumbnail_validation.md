# 썸네일 생성·캐시 검증

2026-10-08 Windows / PowerPoint 16.0에서 썸네일 엔진을 구현하고 단위 테스트 **15개**, 실제 Office 통합 테스트 **8개**를 통과했습니다. UI는 다음 단계입니다. 아래 미리보기는 생성된 썸네일을 모아 놓은 정적 이미지입니다.

같은 날 사용자가 미리보기의 내용·잘림·비율 확인 안내 후 ‘ㅇㅋ 굿’으로 응답했습니다. 썸네일 미리보기의 수동 확인도 **통과**로 기록합니다.

## 바로 확인할 파일

- [18장 썸네일 미리보기](</C:/Work/Side Project/ppt_merge/output/thumbnails__j72iu03/preview.png>) — `C:\Work\Side Project\ppt_merge\output\thumbnails__j72iu03\preview.png`
- [첫 생성 보고서](</C:/Work/Side Project/ppt_merge/output/thumbnails__j72iu03/report.json>) — `C:\Work\Side Project\ppt_merge\output\thumbnails__j72iu03\report.json`
- [캐시 재사용 보고서](</C:/Work/Side Project/ppt_merge/output/thumbnails_vceupmfa/report.json>) — `C:\Work\Side Project\ppt_merge\output\thumbnails_vceupmfa\report.json`
- [실제 PowerPoint 통합 검증 보고서](</C:/Work/Side Project/ppt_merge/output/thumbnail_validation_vftpfw6m/validation_report.json>) — `C:\Work\Side Project\ppt_merge\output\thumbnail_validation_vftpfw6m\validation_report.json`

사용자가 코드를 실행하거나 PPT의 클릭·재생 테스트를 다시 할 필요는 없습니다. 미리보기를 열어 슬라이드 내용이 보이는지 확인할 수 있습니다. 왼쪽부터 각 행을 읽으면 A 1~4장, B 1~4장, advanced 1~9장, C 1장 순서입니다. 작은 이미지는 애니메이션·미디어의 정적 미리보기이며 슬라이드 쇼 재생 화면은 아닙니다.

개별 이미지의 정확한 경로 예:

- [A 1장](</C:/Work/Side Project/ppt_merge/cache/f712b7dfd66f2398abb2f5357540d3ab9d8cc383f69eb59a6aab5dfb8b757bb9/slide_1.png>) — `C:\Work\Side Project\ppt_merge\cache\f712b7dfd66f2398abb2f5357540d3ab9d8cc383f69eb59a6aab5dfb8b757bb9\slide_1.png`
- [SmartArt, advanced 2장](</C:/Work/Side Project/ppt_merge/cache/332e56d83df2cb9ebac669526a34be7bb466f9cd742e9f49159c4dbd6a3a12ba/slide_2.png>) — `C:\Work\Side Project\ppt_merge\cache\332e56d83df2cb9ebac669526a34be7bb466f9cd742e9f49159c4dbd6a3a12ba\slide_2.png`
- [4:3, C 1장](</C:/Work/Side Project/ppt_merge/cache/7a037e677c2725154c1383e459676435c6f58b3bc4525e91732f68778c5e7fed/slide_1.png>) — `C:\Work\Side Project\ppt_merge\cache\7a037e677c2725154c1383e459676435c6f58b3bc4525e91732f68778c5e7fed\slide_1.png`

캐시는 로컬 생성물로 Git에서 제외됩니다. 원본 변경이나 다른 환경에서는 캐시 키도 달라집니다.

## 구현한 동작

- PowerPoint의 `Slide.Export()`로 PNG를 생성하고 원본 슬라이드 비율을 유지합니다. 기본 너비는 480px이며 16:9는 480×270, 4:3는 480×360입니다.
- 슬라이드 번호·ID·제목·이미지 절대 경로를 불변 dataclass로 반환합니다. COM 객체는 외부에 반환하지 않습니다.
- 캐시 키에는 소스의 절대 경로·크기·수정 시각·SHA-256, 이미지 너비, 캐시 버전을 포함합니다. 크기·수정 시각이 같아도 내용이 바뀌면 감지합니다.
- 캐시 적중 시 PowerPoint를 실행하지 않고 PNG 크기·형식·해시와 메타데이터의 무결성을 확인합니다.
- 누락·손상 이미지는 해당 슬라이드만 재생성합니다. 메타데이터가 손상되면 전체 캐시를 새로 만듭니다.
- 생성 결과는 임시 폴더에서 완성한 뒤 게시합니다. 취소·내보내기 오류는 임시 자료를 정리하고 기존 캐시를 유지합니다. 교체 실패는 이전 폴더를 복원하며 복원도 실패하면 복구용 백업을 보관합니다.
- 작업 시작·진행·완료·캐시 재사용 콜백과 취소 콜백을 제공합니다. 원본이 작업 중 바뀌면 새 결과를 게시하지 않습니다.
- COM은 같은 작업 스레드에서 초기화·해제합니다. 앱 소유 PowerPoint만 종료하고, 기존 사용자 PowerPoint가 열려 있으면 새 생성은 거부합니다. 이미 저장된 썸네일은 이때도 열 수 있습니다.

## 검증 결과

| 검증 | 결과 |
| --- | --- |
| A·B·C·advanced PPTX·PPTM 5개, 총 27장 | PNG 생성·크기·슬라이드 수·제목·캐시 재사용 통과 |
| 최초 생성 전후 원본 파일 해시 | 일치, 원본 미변경 |
| 같은 파일 재요청 | COM 추가 실행 0회, PNG 수정 시각 유지 |
| advanced 이미지 2개 누락·손상 | 2장만 복구, 모든 PNG 해시가 최초와 일치 |
| 실제 PPT 제목 변경 후 재요청 | 새 캐시와 변경된 썸네일 생성 |
| 슬라이드 1장 후 취소·의도적 오류 | PowerPoint 종료, 부분 캐시 미게시 |
| 기존 사용자 세션을 대신하는 소유 테스트 세션 | 새 생성 거부, 기존 문서 유지, 캐시 적중 가능 |
| 백그라운드 스레드 실행 | 성공, 결과 직렬화 가능 |
| 다른 스레드에서 COM 세션 접근 | 접근 거부 |
| 정상 PNG 교체·메타데이터 손상·같은 크기/시각의 내용 변경 | 단위 테스트에서 감지 확인 |
| 캐시 게시·복원 실패 | 단위 테스트에서 이전 데이터 유지 또는 백업 보관 확인 |

CLI도 같은 18장을 두 번 실행했습니다. 첫 실행은 전부 생성하고, 두 번째는 모든 자료가 `cache_hit: true`, `generated_slides: 0`이었습니다. 생성된 전체 미리보기 이미지를 직접 확인했습니다. 테스트 완료 후 실행 중인 앱 소유 PowerPoint가 남지 않았습니다.

## API 및 재실행

```python
from pathlib import Path
from src.ppt.thumbnail_service import ThumbnailService

service = ThumbnailService(Path("cache"))
result = service.load(Path("tests/fixtures/basic/A.pptx"),
                      progress=on_progress, cancel=cancel_event.is_set)
# result.presentation.slides: tuple[SlideItem, ...]
# on_progress는 ThumbnailProgress 데이터를 받으며 cancel은 bool을 반환한다.
```

서비스는 호출 스레드에서 동작합니다. 화면에서 직접 호출하지 않고 워커 안에서 호출해야 합니다. 각 호출의 COM 세션은 그 호출에서 열고 닫습니다. 여러 소스는 한 워커에서 순서대로 처리하며 동일 캐시의 동시 생성은 잠금 파일로 거부합니다.

```powershell
.\.venv\Scripts\python.exe scripts/export_thumbnails.py tests/fixtures/basic/A.pptx tests/fixtures/basic/B.pptx
.\.venv\Scripts\python.exe -m unittest discover -s tests/unit -v
$env:PPT_MERGE_COM_TESTS = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests/integration -p test_thumbnail_com.py -v
```

`--width`와 `--cache-root`로 이미지 너비와 저장 위치를 바꿀 수 있습니다. 로그는 `C:\Work\Side Project\ppt_merge\logs\app.log`입니다. 설치 의존성은 기존 `requirements-poc.txt`를 사용합니다.

## 현재 범위

- 첫 생성은 전체 슬라이드를 처리합니다. 수백 장 자료의 성능 측정·지연 로딩과 PySide6 QThread 연결은 후속 단계입니다.
- 외부 Excel 파일만 바뀌고 PPT 자체는 바뀌지 않았다면 캐시 키는 그대로입니다. 외부 연결 값을 PPT에 갱신·저장한 뒤 다시 읽어야 변경을 반영합니다.
- 이전 버전의 캐시는 자동 삭제하지 않습니다. 강제 프로세스 종료 후 남는 임시·잠금 파일의 자동 복구도 아직 구현하지 않았습니다. 이 경우 생성 작업이 끝났는지 확인한 뒤 해당 캐시의 잠금을 정리해야 합니다.
- 암호 보호 컨테이너와 잘못된 ZIP/XML을 자동 작업 전 거부하지만, 실제 암호 파일·다양한 손상 유형 전체를 테스트한 것은 아닙니다.
- VBA가 없는 `.pptm`만 검증했고, 매크로 실행은 비활성화합니다.

Microsoft의 [Slide.Export](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.slide.export)와 [Presentations.Open](https://learn.microsoft.com/en-us/office/vba/api/powerpoint.presentations.open) API를 참고했습니다. 위 결과는 실제 로컬 테스트 기록입니다.
