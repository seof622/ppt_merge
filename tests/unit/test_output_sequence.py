"""중복 원본과 비연속 선택을 포함한 출력 순서의 의미를 검증한다."""

import unittest

from src.models.project_model import OutputSequence
from src.models.slide_model import SlideItem


def slide(number):
    return SlideItem("C:/A.pptx", "A.pptx", number, 255 + number)


class OutputSequenceTests(unittest.TestCase):
    def setUp(self):
        self.sequence = OutputSequence([slide(number) for number in range(1, 7)])

    def numbers(self):
        return [item.slide_index for item in self.sequence.slides]

    def test_insert_retains_repeat_and_explicit_position(self):
        self.assertEqual(self.sequence.insert([slide(2), slide(2)], 1), [1, 2])
        self.assertEqual(self.numbers(), [1, 2, 2, 2, 3, 4, 5, 6])

    def test_noncontiguous_move_toward_end_preserves_relative_order(self):
        self.assertEqual(self.sequence.move([1, 3], 6), [4, 5])
        self.assertEqual(self.numbers(), [1, 3, 5, 6, 2, 4])

    def test_noncontiguous_move_toward_start_preserves_relative_order(self):
        self.assertEqual(self.sequence.move([2, 4], 0), [0, 1])
        self.assertEqual(self.numbers(), [3, 5, 1, 2, 4, 6])

    def test_drop_inside_selected_block_is_noop(self):
        self.assertEqual(self.sequence.move([1, 2, 3], 3), [1, 2, 3])
        self.assertEqual(self.numbers(), [1, 2, 3, 4, 5, 6])

    def test_duplicate_each_occurrence_immediately_after_original(self):
        self.assertEqual(self.sequence.duplicate([1, 3]), [2, 5])
        self.assertEqual(self.numbers(), [1, 2, 2, 3, 4, 4, 5, 6])
        self.sequence.remove([1])
        self.assertEqual(self.numbers(), [1, 2, 3, 4, 4, 5, 6])

    def test_step_blocks_and_boundaries(self):
        self.assertEqual(self.sequence.step([0, 2, 3, 5], -1), [0, 1, 2, 4])
        self.assertEqual(self.numbers(), [1, 3, 4, 2, 6, 5])
        self.assertEqual(self.sequence.step([0, 1, 2, 4], 1), [1, 2, 3, 5])
        self.assertEqual(self.numbers(), [2, 1, 3, 4, 5, 6])

    def test_delete_last_and_clear_leave_valid_selection(self):
        self.assertEqual(self.sequence.remove([5]), [4])
        self.assertEqual(self.sequence.remove(range(5)), [])
        self.assertEqual(self.sequence.slides, [])

    def test_invalid_operation_does_not_change_order(self):
        for operation in (lambda: self.sequence.move([1], 99),
                          lambda: self.sequence.remove([6]),
                          lambda: self.sequence.duplicate([-1]),
                          lambda: self.sequence.step([0], 0)):
            with self.assertRaises(ValueError):
                operation()
            self.assertEqual(self.numbers(), [1, 2, 3, 4, 5, 6])


if __name__ == "__main__":
    unittest.main()
