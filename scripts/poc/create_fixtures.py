"""PowerPoint 자체로 기본 테스트 PPT를 만든다. 기존 자료는 덮어쓰지 않는다."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
import shutil
from typing import Any

from com_session import ROOT, PowerPointSession, configure_logging

LOGGER = logging.getLogger("ppt_merge.poc")


def rgb(red: int, green: int, blue: int) -> int:
    return red | green << 8 | blue << 16


def text(slide: Any, name: str, content: str, x: float, y: float,
         width: float, height: float, size: int = 24) -> Any:
    shape = slide.Shapes.AddTextbox(1, x, y, width, height)
    shape.Name = name
    shape.TextFrame.TextRange.Text = content
    shape.TextFrame.TextRange.Font.Name = "맑은 고딕"
    shape.TextFrame.TextRange.Font.Size = size
    shape.TextFrame.TextRange.Font.Color.RGB = rgb(30, 41, 59)
    return shape


def note(slide: Any, content: str) -> None:
    for shape in slide.NotesPage.Shapes:
        if shape.Type == 14 and shape.PlaceholderFormat.Type == 2:
            shape.TextFrame.TextRange.Text = content
            return
    raise RuntimeError("발표자 노트 자리 표시자를 찾지 못했습니다.")


def base_slide(presentation: Any, marker: str, title: str) -> Any:
    slide = presentation.Slides.Add(presentation.Slides.Count + 1, 12)
    slide.Name = marker
    text(slide, "test_title", f"{marker}  {title}", 42, 38, 850, 58, 30)
    note(slide, f"NOTES_{marker}: 원본과 결합 결과에서 이 노트가 같아야 합니다.")
    return slide


def configure_theme(presentation: Any, label: str, accent: int, background: int) -> None:
    presentation.PageSetup.SlideWidth = 960
    presentation.PageSetup.SlideHeight = 540
    master = presentation.SlideMaster
    master.Name = f"{label}_MASTER"
    master.Theme.ThemeColorScheme.Colors(5).RGB = accent
    master.Background.Fill.Solid()
    master.Background.Fill.ForeColor.RGB = background
    band = master.Shapes.AddShape(1, 0, 516, 960, 24)
    band.Name = f"{label}_MASTER_BAND"
    band.Fill.ForeColor.ObjectThemeColor = 5
    band.Line.Visible = False
    master.CustomLayouts.Item(7).Name = f"{label}_CUSTOM_LAYOUT"


def add_table(slide: Any) -> None:
    shape = slide.Shapes.AddTable(3, 3, 460, 145, 450, 160)
    shape.Name = "editable_table"
    values = (("항목", "수량", "금액"), ("테스트 A", "2", "120"), ("테스트 B", "3", "180"))
    for row, cells in enumerate(values, 1):
        for col, value in enumerate(cells, 1):
            cell = shape.Table.Cell(row, col).Shape
            cell.TextFrame.TextRange.Text = value
            cell.TextFrame.TextRange.Font.Name = "맑은 고딕"
            cell.TextFrame.TextRange.Font.Size = 18


def add_chart(slide: Any) -> None:
    shape = slide.Shapes.AddChart(51, 90, 140, 780, 310)
    shape.Name = "native_column_chart"
    chart = shape.Chart
    workbook = None
    try:
        chart.ChartData.Activate()
        workbook = chart.ChartData.Workbook
        sheet = workbook.Worksheets.Item(1)
        sheet.Range("A1:B4").Value = (("항목", "샘플"), ("1월", 10), ("2월", 20), ("3월", 15))
        chart.SetSourceData(f"'{sheet.Name}'!$A$1:$B$4")
        chart.HasTitle = True
        chart.ChartTitle.Text = "검증용 가상 데이터"
        chart.HasLegend = False
        chart.ChartArea.Format.TextFrame2.TextRange.Font.Name = "맑은 고딕"
        sheet = None
    finally:
        if workbook is not None:
            workbook.Close(True)
        workbook = chart = shape = None


def make_deck(session: PowerPointSession, folder: Path, label: str,
              accent: int, background: int, image: Path) -> None:
    presentation = session.new(with_window=True)
    try:
        configure_theme(presentation, label, accent, background)
        slide = base_slide(presentation, f"{label}-1", "텍스트와 하이퍼링크")
        body = text(slide, "mixed_text", "한글 글꼴 검증\nEnglish text 123\n굵게와 색상", 70, 155, 810, 155, 28)
        body.TextFrame.TextRange.Paragraphs(3).Font.Bold = True
        body.TextFrame.TextRange.Paragraphs(3).Font.Color.ObjectThemeColor = 5
        link = text(slide, "external_hyperlink", "외부 하이퍼링크", 70, 350, 600, 45, 22)
        link.ActionSettings(1).Hyperlink.Address = "https://example.com/"

        slide = base_slide(presentation, f"{label}-2", "이미지, 그룹 도형, 표, 애니메이션")
        picture = slide.Shapes.AddPicture(str(image), False, True, 70, 145, 320, 180)
        picture.Name = "embedded_image"
        first = slide.Shapes.AddShape(1, 70, 335, 120, 70)
        first.Name = "group_rectangle"
        first.Fill.ForeColor.ObjectThemeColor = 5
        second = slide.Shapes.AddShape(9, 220, 335, 90, 70)
        second.Name = "group_ellipse"
        second.Fill.ForeColor.RGB = rgb(245, 158, 11)
        group = slide.Shapes.Range((first.Name, second.Name)).Group()
        group.Name = "grouped_shapes"
        effect = slide.TimeLine.MainSequence.AddEffect(group, 10, 0, 1)  # fade, on click
        effect.Timing.Duration = 0.8
        slide.SlideShowTransition.EntryEffect = 1793  # fade smoothly
        add_table(slide)
        text(slide, "animation_instruction", "슬라이드 쇼에서 클릭하면 그룹 도형이 나타납니다.", 70, 450, 820, 42, 20)

        slide = base_slide(presentation, f"{label}-3", "편집 가능한 기본 차트")
        add_chart(slide)

        slide = base_slide(presentation, f"{label}-4", "소스 테마, 마스터, 레이아웃")
        themed = slide.Shapes.AddShape(1, 90, 170, 340, 180)
        themed.Name = "theme_accent_shape"
        themed.Fill.ForeColor.ObjectThemeColor = 5
        themed.Line.Visible = False
        text(slide, "theme_description", f"{label} 테마 강조색과 배경\n마스터에 포함된 하단 띠", 480, 185, 400, 140, 24)
        effect = slide.TimeLine.MainSequence.AddEffect(themed, 10, 0, 1)
        effect.Timing.Duration = 0.6
        slide.SlideShowTransition.EntryEffect = 1793
        # COM 자식 참조는 저장/종료 전에 해제한다.
        slide = body = link = picture = first = second = group = effect = themed = None
        destination = folder / f"{label}.pptx"
        presentation.SaveAs(str(destination), 24)
        LOGGER.info("테스트 PPT 저장 %s", destination)
    finally:
        session.close_presentation(presentation)
        presentation = None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "tests/fixtures/basic")
    parser.add_argument("--image", type=Path, default=Path("C:/Windows/Web/Wallpaper/Windows/img0.jpg"))
    args = parser.parse_args()
    configure_logging()
    folder = args.directory.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    if not args.image.is_file():
        raise FileNotFoundError("--image 옵션으로 지정할 테스트 이미지가 필요합니다.")
    for name in ("A.pptx", "B.pptx", "C_4x3.pptx", "sample.jpg"):
        if (folder / name).exists():
            raise FileExistsError(f"기존 테스트 자료를 덮어쓰지 않습니다: {folder / name}")
    image = folder / "sample.jpg"
    shutil.copyfile(args.image, image)
    session = PowerPointSession()
    with session:
        make_deck(session, folder, "A", rgb(37, 99, 235), rgb(239, 246, 255), image)
        make_deck(session, folder, "B", rgb(5, 150, 105), rgb(236, 253, 245), image)
        presentation = session.new()
        presentation.PageSetup.SlideWidth = 720
        presentation.PageSetup.SlideHeight = 540
        slide = base_slide(presentation, "C-1", "4:3 크기 불일치 검증")
        text(slide, "size_description", "이 파일은 4:3입니다. 결합 전에 크기 경고가 필요합니다.", 50, 160, 610, 130)
        slide = None
        presentation.SaveAs(str(folder / "C_4x3.pptx"), 24)
        session.close_presentation(presentation)
        presentation = None
    if not session.cleanup["owned_process_exited"]:
        raise RuntimeError("테스트 자료 생성 후 PowerPoint가 종료되지 않았습니다.")


if __name__ == "__main__":
    main()
