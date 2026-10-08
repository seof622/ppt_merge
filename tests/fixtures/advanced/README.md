# 고급 테스트 자료

`scripts/poc/create_advanced_fixtures.py`로 이 컴퓨터의 PowerPoint와 Excel에서 생성했습니다. 슬라이드 크기는 960×540pt이며 보라색 테마를 사용합니다. `advanced.pptx`와 `advanced_container.pptm`은 같은 9장입니다. PPTM 파일에는 실제 VBA 매크로가 없습니다.

| 원본 슬라이드 | 검증 대상 |
| --- | --- |
| G-1 | SVG 원본과 미리보기 이미지 |
| G-2 | 편집 가능한 기본 프로세스 SmartArt, 단계 1·2·3 |
| G-3 | 내장 WAV 오디오, 2초·440Hz 테스트음 |
| G-4 | 내장 MP4 영상, 3초·640×360·15fps 움직이는 패턴, 무음 |
| G-5 | G-6으로 이동하는 내부 슬라이드 링크 |
| G-6 | 링크 도착 지점 |
| G-7 | Excel 통합문서 내장 OLE 객체 |
| G-8 | 외부 Excel 연결 OLE 차트 (`Excel.Sheet.12`) |
| G-9 | 클릭 시 1.5초 원형 모션 경로 애니메이션 |

각 슬라이드 노트에는 `NOTES_G-<번호>`가 있습니다. `sample.svg`, `tone.wav`, `test_pattern.mp4`는 테스트 코드가 만든 합성 자료입니다. `source_data.xlsx`의 `TestData` 시트에는 가상 값 `10, 20, 15`와 세로 막대형 차트가 있습니다.

외부 연결에는 생성 당시의 절대 경로 `C:\Work\Side Project\ppt_merge\tests\fixtures\advanced\source_data.xlsx`가 포함되어 있습니다. 다른 경로 또는 컴퓨터에서는 Excel과 PowerPoint를 닫고 새 폴더에 재생성하세요. 생성기는 기존 PPT·통합문서·미디어를 덮어쓰지 않습니다.

연결 차트는 Excel OLE 방식입니다. PowerPoint 기본 차트의 외부 `ChartData` 연결, 실제 VBA 프로젝트 보존, 파일 이동 후 자동 경로 수정은 이 자료의 검증 범위에 포함되지 않습니다. 검증 결과와 사용자 확인 절차는 [고급 검증 안내](../../../docs/advanced_validation.md)를 참고하세요.
