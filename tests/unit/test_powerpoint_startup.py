"""COM 시작의 제한된 재시도와 사용자 프로세스 보호."""
from unittest import TestCase
from unittest.mock import Mock, patch

from src.ppt.presentation_manager import PresentationManager


class ServerFailure(RuntimeError):
    hresult = -2146959355


class StartupTests(TestCase):
    def test_retry_only_once_when_failed_server_has_no_process(self):
        app = object()
        dispatch = Mock(side_effect=[ServerFailure(), app])
        with patch("src.ppt.presentation_manager.process_pids", return_value=set()), \
             patch("src.ppt.presentation_manager.time.sleep") as sleep:
            self.assertIs(PresentationManager()._start_application(dispatch), app)
        self.assertEqual(dispatch.call_count, 2)
        sleep.assert_called_once_with(1)

    def test_persistent_start_failure_stops_after_second_attempt(self):
        dispatch = Mock(side_effect=ServerFailure())
        with patch("src.ppt.presentation_manager.process_pids", return_value=set()), \
             patch("src.ppt.presentation_manager.time.sleep"):
            with self.assertRaises(ServerFailure):
                PresentationManager()._start_application(dispatch)
        self.assertEqual(dispatch.call_count, 2)

    def test_existing_process_after_failure_is_never_retried(self):
        dispatch = Mock(side_effect=ServerFailure())
        with patch("src.ppt.presentation_manager.process_pids", return_value={123}), \
             patch("src.ppt.presentation_manager.time.sleep") as sleep:
            with self.assertRaises(ServerFailure):
                PresentationManager()._start_application(dispatch)
        self.assertEqual(dispatch.call_count, 1)
        sleep.assert_not_called()

    def test_user_process_appears_during_wait_is_never_attached(self):
        dispatch = Mock(side_effect=ServerFailure())
        with patch("src.ppt.presentation_manager.process_pids", side_effect=[set(), {123}]), \
             patch("src.ppt.presentation_manager.time.sleep"):
            with self.assertRaises(ServerFailure):
                PresentationManager()._start_application(dispatch)
        self.assertEqual(dispatch.call_count, 1)

    def test_other_start_error_is_not_retried(self):
        dispatch = Mock(side_effect=RuntimeError("다른 원인"))
        with patch("src.ppt.presentation_manager.time.sleep") as sleep:
            with self.assertRaises(RuntimeError):
                PresentationManager()._start_application(dispatch)
        self.assertEqual(dispatch.call_count, 1)
        sleep.assert_not_called()
