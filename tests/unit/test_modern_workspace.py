"""편집 복구·격자 드롭·검색·세션 복원을 사용자 흐름으로 검증한다."""
from dataclasses import replace
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from src.models.presentation_model import PresentationInfo
from src.models.slide_model import SlideItem
from src.ui.main_window import MainWindow
from src.ui.slide_preview import SlidePreview
from src.ui.slide_mime import make_slide_mime
from src.utils.slide_text import read_slide_texts
from src.utils.workspace_store import WorkspaceStore
import test_ui as fixture


class ModernWorkspaceTests(unittest.TestCase):
    setUpClass = classmethod(fixture.UiTests.setUpClass.__func__)
    setUp = fixture.UiTests.setUp
    tearDown = fixture.UiTests.tearDown
    load = fixture.UiTests.load

    def restart(self):
        self.window.close()
        self.app.processEvents()
        fixture.dispose_widget(self.window)
        self.window = MainWindow(self.root/'cache', self.factory)
        self.window.show()
        self.app.processEvents()
        fixture.wait_until(lambda: not self.window.is_loading and not self.window._restoring)

    def test_undo_redo_keeps_duplicates_selection_and_invalidates_drag(self):
        self.load(self.a)
        panel = self.window.output_panel
        slides = self.window.slide_grid.model.slides
        panel.add_slides(slides)
        panel.select_rows([1])
        stale = panel.model.mimeData([panel.model.index(1, 0)])
        panel.duplicate_selected()
        self.assertEqual([s.slide_index for s in panel.output_slides], [1,2,2,3])
        self.window.undo_action.trigger()
        self.assertEqual(panel.output_slides,list(slides))
        self.assertEqual(panel.selected_rows(),[1])
        self.assertFalse(panel.model.canDropMimeData(stale, Qt.DropAction.MoveAction,0,0,panel.model.index(-1,0)))
        self.window.redo_action.trigger()
        self.assertEqual([s.slide_index for s in panel.output_slides],[1,2,2,3])
        self.assertEqual(panel.selected_rows(),[2])
        self.window.undo_action.trigger()
        panel.remove_selected()
        self.assertFalse(self.window.redo_action.isEnabled())
        self.window.undo_action.trigger()
        self.assertEqual(panel.output_slides,list(slides))

    def test_keyboard_undo_and_redo_restore_clear(self):
        self.load(self.a)
        panel=self.window.output_panel
        slides=self.window.slide_grid.model.slides
        panel.add_slides(slides)
        panel.clear_button.click()
        self.app.setActiveWindow(self.window)
        panel.view.setFocus()
        QTest.keyClick(panel.view, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(panel.output_slides,list(slides))
        QTest.keyClick(panel.view, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(panel.output_slides,[])

    def test_grid_drop_targets_second_row_and_undo_restores_it(self):
        self.load(self.a)
        panel=self.window.output_panel
        slides=self.window.slide_grid.model.slides
        panel.add_slides(slides*3)
        panel.view.doItemsLayout()
        first=panel.view.visualRect(panel.model.index(0,0))
        row=next(r for r in range(1,9) if panel.view.visualRect(panel.model.index(r,0)).top()>first.top())
        rect=panel.view.visualRect(panel.model.index(row,0))
        target=panel.view.insertion_row(QPoint(rect.left()+4,rect.center().y()))
        self.assertEqual(target,row)
        mime=make_slide_mime(panel.model.drag_token,(slides[2],))
        self.assertTrue(panel.model.dropMimeData(mime,Qt.DropAction.CopyAction,target,0,panel.model.index(-1,0)))
        self.assertEqual(panel.output_slides[row],slides[2])
        panel.model.undo_stack.undo()
        self.assertEqual(panel.output_slides,list(slides*3))

    def test_body_filter_adds_only_matches_and_usage_tracks_undo(self):
        self.load(self.a)
        grid=self.window.slide_grid
        slides=grid.model.slides
        info=PresentationInfo(str(self.a),self.a.name,960,540,slides)
        grid.show_presentation(info,{1:'사과 제품',2:'고객 의견',3:'운영 계획'})
        grid.search.setText('고객')
        self.assertEqual(grid.model.slides,(slides[1],))
        grid.all_button.click()
        self.assertEqual(self.window.output_panel.output_slides,[slides[1]])
        self.assertEqual(grid.model.usage_counts[(slides[1].source_file,slides[1].slide_id)],1)
        self.window.undo_action.trigger()
        self.assertEqual(grid.model.usage_counts,{})
        grid.search.setText('없는 검색어')
        self.assertEqual(grid.model.rowCount(),0)
        self.assertFalse(grid.all_button.isEnabled())
        grid.search.clear()
        self.assertEqual(grid.model.slides,slides)

    def test_preview_space_navigates_without_adding_a_slide(self):
        self.load(self.a)
        grid=self.window.slide_grid
        grid.view.setCurrentIndex(grid.model.index(1,0))
        grid.view.setFocus()
        self.app.setActiveWindow(self.window)
        QTest.keyClick(grid.view,Qt.Key.Key_Space)
        QTest.qWait(20)
        dialog=self.window.findChild(SlidePreview)
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.row,1)
        dialog.next.click()
        self.assertEqual(dialog.row,2)
        self.assertFalse(dialog.next.isEnabled())
        self.assertEqual(self.window.output_panel.output_slides,[])
        dialog.close()
        self.app.processEvents()

    def test_multiple_file_picker_adds_both_without_changing_root(self):
        root=self.window.source_panel.root_path
        with patch('src.ui.main_window.QFileDialog.getOpenFileNames',return_value=([str(self.a),str(self.b)],'')):
            self.window.file_add_action.trigger()
        fixture.wait_until(lambda:not self.window.is_loading)
        self.assertEqual(self.window.source_panel.list.count(),2)
        self.assertEqual(self.window.source_panel.root_path,root)
        self.assertEqual(self.window.source_panel.tabs.currentIndex(),0)

    def test_restart_restores_mixed_sources_order_and_duplicate_occurrences(self):
        self.load(self.a,self.b)
        states=list(self.window._sources.values())
        a,b=[s.result.presentation.slides for s in states]
        expected=[a[1],b[0],a[1],b[2]]
        self.window.output_panel.add_slides(expected)
        self.restart()
        self.assertEqual(self.window.output_panel.output_slides,expected)
        self.assertFalse(self.window.undo_action.isEnabled())
        self.assertTrue(self.window.generate_button.isEnabled())

    def test_restore_changed_or_missing_sources_preserves_old_record_until_edit(self):
        self.load(self.a)
        old=replace(self.window.slide_grid.model.slides[0],source_revision='older-revision')
        missing=SlideItem(str(self.root/'missing.pptx'),'missing.pptx',1,256)
        self.window.output_panel.add_slides([old,missing])
        self.restart()
        self.assertEqual(self.window.output_panel.output_slides,[])
        self.assertIn('제외된 슬라이드 2장',self.window.notice.text())
        record=self.root/'workspace.json'
        before=record.read_bytes()
        self.window._save_workspace()
        self.assertEqual(record.read_bytes(),before)
        self.window.output_panel.add_slides(self.window.slide_grid.model.slides[:1])
        self.window._save_workspace()
        self.assertNotEqual(record.read_bytes(),before)

    def test_search_uses_presentation_order_and_rejects_corrupt_archive(self):
        file=self.root/'text.pptx'
        with ZipFile(file,'w') as archive:
            archive.writestr('ppt/presentation.xml','<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId r:id="r2"/><p:sldId r:id="r1"/></p:sldIdLst></p:presentation>')
            archive.writestr('ppt/_rels/presentation.xml.rels','<Relationships><Relationship Id="r1" Target="slides/slide1.xml"/><Relationship Id="r2" Target="slides/slide2.xml"/></Relationships>')
            for i,text in ((1,'Second'),(2,'First')):
                archive.writestr(f'ppt/slides/slide{i}.xml',f'<s xmlns:a="drawing"><a:t>{text}</a:t></s>')
        self.assertEqual(read_slide_texts(file),{1:'first',2:'second'})
        self.assertEqual(read_slide_texts(file,lambda:True),{})
        self.assertEqual(read_slide_texts(self.a),{})

    def test_corrupt_workspace_does_not_break_startup(self):
        store=WorkspaceStore(self.root/'bad.json')
        store.path.write_text('{bad json',encoding='utf-8')
        self.assertEqual(store.load(),([],[]))
        store.path.write_text(json.dumps({'version':1,'sources':None,'slides':[]}),encoding='utf-8')
        self.assertEqual(store.load(),([],[]))

    def test_short_source_view_keeps_a_complete_card_visible(self):
        self.load(self.a)
        self.window.resize(1000,640)
        self.window.set_workspace_mode('source')
        QTest.qWait(30)
        grid=self.window.slide_grid
        self.assertLessEqual(grid.model.card_size.height()+2*grid.view.spacing(),grid.view.viewport().height())
