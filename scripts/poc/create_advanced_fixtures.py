"""SVG, SmartArt, 미디어, 내부 링크, Excel 객체, 모션 경로를 검증할 자료."""

from __future__ import annotations

import argparse
import gc
import logging
import math
from pathlib import Path
import pythoncom
import struct
import subprocess
import time
import wave
from typing import Any

import imageio_ffmpeg
import win32com.client
import win32process

from com_session import ROOT, PowerPointSession, configure_logging, process_pids
from create_fixtures import base_slide, configure_theme, rgb, text

LOGGER = logging.getLogger("ppt_merge.poc")


def create_assets(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    if any(folder.iterdir()):
        raise FileExistsError(f"기존 고급 테스트 자료를 덮어쓰지 않습니다: {folder}")
    # 보존 검증용 벡터 데이터. 장식용 그림이 아니라 SVG 형식 자체의 테스트다.
    (folder / "sample.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="300" viewBox="0 0 640 300">'
        '<defs><linearGradient id="g"><stop stop-color="#2563eb"/>'
        '<stop offset="1" stop-color="#10b981"/></linearGradient></defs>'
        '<rect x="10" y="10" width="620" height="280" rx="24" fill="url(#g)"/>'
        '<circle cx="150" cy="150" r="85" fill="#fff" fill-opacity="0.8"/>'
        '<path d="M300 230 L400 70 L500 230 Z" fill="#fbbf24" stroke="#111827" stroke-width="5"/>'
        '</svg>', encoding="utf-8",
    )
    with wave.open(str(folder / "tone.wav"), "wb") as audio:
        rate = 44100
        audio.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        samples = [int(6000 * math.sin(2 * math.pi * 440 * n / rate)) for n in range(rate * 2)]
        audio.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-n",
         "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=15:duration=3",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
         str(folder / "test_pattern.mp4")], check=True, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    LOGGER.info("고급 테스트 SVG, 2초 오디오, 3초 영상 생성 %s", folder)


def populate(session: PowerPointSession, folder: Path) -> dict[str, Any]:
    presentation = session.new(with_window=True)
    excel = workbook = sheet = chart_object = chart = slide = shape = None
    excel_pid = None
    excel_before = process_pids("EXCEL.EXE")
    if excel_before:
        session.close_presentation(presentation)
        raise RuntimeError("Excel 객체 생성 검증을 위해 기존 Excel을 먼저 닫아 주세요.")
    try:
        configure_theme(presentation, "ADVANCED", rgb(124, 58, 237), rgb(250, 245, 255))
        slide = base_slide(presentation, "G-1", "SVG 벡터 이미지")
        shape = slide.Shapes.AddPicture(str(folder / "sample.svg"), False, True, 90, 145, 640, 300)
        shape.Name = "svg_picture"

        slide = base_slide(presentation, "G-2", "편집 가능한 SmartArt")
        layouts = session.app.SmartArtLayouts
        layout = next((item for item in layouts if item.Id.lower().endswith("/process1")), None)
        if layout is None:
            raise RuntimeError("기본 프로세스 SmartArt 레이아웃을 찾지 못했습니다.")
        shape = slide.Shapes.AddSmartArt(layout, 80, 140, 800, 280)
        shape.Name = "native_smartart"
        for i, node in enumerate(shape.SmartArt.AllNodes, 1):
            node.TextFrame2.TextRange.Text = f"단계 {i}"
            node.TextFrame2.TextRange.Font.Name = "맑은 고딕"
            node.TextFrame2.TextRange.Font.Size = 24
        layout = layouts = node = None

        slide = base_slide(presentation, "G-3", "내장 오디오")
        text(slide, "audio_instruction", "오디오 아이콘에서 2초 테스트음을 재생합니다.", 90, 170, 790, 70)
        shape = slide.Shapes.AddMediaObject2(str(folder / "tone.wav"), False, True, 120, 290, 90, 90)
        shape.Name = "embedded_audio"

        slide = base_slide(presentation, "G-4", "내장 비디오")
        shape = slide.Shapes.AddMediaObject2(str(folder / "test_pattern.mp4"), False, True, 100, 120, 640, 360)
        shape.Name = "embedded_video"

        slide = base_slide(presentation, "G-5", "내부 슬라이드 링크")
        text(slide, "internal_jump", "링크 대상 G-6으로 이동", 100, 200, 730, 85, 30)
        slide = base_slide(presentation, "G-6", "링크 도착 지점")
        text(slide, "link_destination", "G-6에 도착했습니다.", 100, 200, 730, 85, 30)
        target = slide
        jump = presentation.Slides.Item(5).Shapes.Item("internal_jump").ActionSettings(1)
        jump.Action = 7
        jump.Hyperlink.Address = ""
        jump.Hyperlink.SubAddress = f"{target.SlideID},{target.SlideIndex},G-6"
        jump = target = None

        excel = win32com.client.DispatchEx("Excel.Application")
        excel_pid = win32process.GetWindowThreadProcessId(int(excel.Hwnd))[1]
        if excel_pid in excel_before:
            raise RuntimeError("Excel이 기존 사용자 인스턴스를 반환했습니다.")
        excel.DisplayAlerts = False
        excel.AutomationSecurity = 3
        excel.Visible = True  # 연결 차트의 클립보드 형식 생성에는 문서 창이 필요하다.
        workbook = excel.Workbooks.Add()
        sheet = workbook.Worksheets.Item(1)
        sheet.Name = "TestData"
        sheet.Range("A1:B4").Value = (("항목", "값"), ("1월", 10), ("2월", 20), ("3월", 15))
        sheet.Columns("A:B").ColumnWidth = 15
        chart_object = sheet.ChartObjects().Add(180, 20, 450, 260)
        chart = chart_object.Chart
        chart.ChartType = 51
        chart.SetSourceData(sheet.Range("A1:B4"))
        chart.HasTitle = True
        chart.ChartTitle.Text = "외부 Excel 연결 검증"
        chart.HasLegend = False
        workbook.SaveAs(str(folder / "source_data.xlsx"), 51)

        slide = base_slide(presentation, "G-7", "내장 Excel OLE 객체")
        shape = slide.Shapes.AddOLEObject(90, 150, 750, 260, FileName=str(folder / "source_data.xlsx"), Link=False)
        shape.Name = "embedded_excel_ole"

        slide = base_slide(presentation, "G-8", "외부 Excel 연결 차트")
        sheet.Activate()
        chart_object.Activate()
        chart_object.Copy()
        pythoncom.PumpWaitingMessages()
        time.sleep(0.3)
        presentation.Windows.Item(1).Activate()
        presentation.Windows.Item(1).View.GotoSlide(8)
        pasted = slide.Shapes.PasteSpecial(10, False, "", 0, "", True)
        shape = pasted.Item(1)
        shape.Name = "linked_excel_chart"
        shape.Left, shape.Top, shape.Width, shape.Height = 90, 140, 720, 320
        pasted = None
        if shape.Type != 10:
            raise RuntimeError("외부 Excel 연결 OLE 차트가 생성되지 않았습니다.")

        slide = base_slide(presentation, "G-9", "모션 경로 애니메이션")
        shape = slide.Shapes.AddShape(9, 100, 240, 100, 100)
        shape.Name = "motion_circle"
        shape.Fill.ForeColor.ObjectThemeColor = 5
        effect = slide.TimeLine.MainSequence.AddEffect(shape, 86, 0, 1)  # msoAnimEffectPathCircle
        effect.Timing.Duration = 1.5
        text(slide, "motion_instruction", "클릭하면 원이 모션 경로를 따라 이동합니다.", 90, 140, 790, 60)
        effect = shape = slide = None

        workbook.Save()
        presentation.SaveAs(str(folder / "advanced.pptx"), 24)
        presentation.SaveAs(str(folder / "advanced_container.pptm"), 25)
        LOGGER.info("고급 테스트 PPTX 및 PPTM 저장 %s", folder)
        return {"slide_count": 9, "features": ["SVG", "SmartArt", "audio", "video", "internal_links",
                "embedded_excel_ole", "linked_excel_ole_chart", "motion_animation", "pptm_container"],
                "linked_chart_kind": "Excel.Sheet.12 linked OLE chart", "contains_vba_macros": False}
    finally:
        shape = slide = chart = chart_object = sheet = None
        if workbook is not None:
            workbook.Close(False)
        workbook = None
        if excel is not None and excel_pid is not None and excel_pid not in excel_before:
            excel.Quit()
        excel = None
        gc.collect()
        session.close_presentation(presentation)
        presentation = None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "tests/fixtures/advanced")
    parser.add_argument("--assets-only", action="store_true")
    args = parser.parse_args()
    configure_logging()
    folder = args.directory.resolve()
    if not (folder / "sample.svg").exists():
        create_assets(folder)
    missing_assets = [name for name in ("sample.svg", "tone.wav", "test_pattern.mp4")
                      if not (folder / name).is_file()]
    if missing_assets:
        raise FileNotFoundError(f"고급 테스트 미디어가 누락되었습니다: {missing_assets}")
    if args.assets_only:
        return
    for name in ("advanced.pptx", "advanced_container.pptm", "source_data.xlsx"):
        if (folder / name).exists():
            raise FileExistsError(f"기존 자료를 덮어쓰지 않습니다: {folder / name}")
    session = PowerPointSession()
    with session:
        summary = populate(session, folder)
    if not session.cleanup["owned_process_exited"] or session.cleanup["errors"]:
        raise RuntimeError("고급 자료 생성 후 PowerPoint 정리에 실패했습니다.")
    LOGGER.info("고급 자료 생성 완료 %s", summary)


if __name__ == "__main__":
    main()
