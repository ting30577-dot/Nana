"""滑动窗口纯计算逻辑测试。"""

from __future__ import annotations

import unittest

from algorithms.sliding_window import fixed_window_steps, variable_window_steps


class FixedWindowTests(unittest.TestCase):
    def test_generates_every_fixed_window(self) -> None:
        states = fixed_window_steps([2, 1, 5, 1, 3, 2], 3)

        self.assertEqual(len(states), 4)
        self.assertEqual(
            [(state.left, state.right) for state in states],
            [(0, 2), (1, 3), (2, 4), (3, 5)],
        )
        self.assertEqual(states[-1].max_sum, 9)

    def test_rejects_invalid_size(self) -> None:
        with self.assertRaises(ValueError):
            fixed_window_steps([1, 2], 0)
        with self.assertRaises(ValueError):
            fixed_window_steps([1, 2], 3)


class VariableWindowTests(unittest.TestCase):
    def test_finds_shortest_matching_window(self) -> None:
        states = variable_window_steps([2, 3, 1, 2, 4, 3], 7)

        self.assertEqual(states[-1].best_length, 2)
        self.assertTrue({"expand", "match", "shrink"} <= {s.phase for s in states})

    def test_empty_input_has_no_states(self) -> None:
        self.assertEqual(variable_window_steps([], 7), [])

    def test_rejects_invalid_target(self) -> None:
        with self.assertRaises(ValueError):
            variable_window_steps([1, 2], 0)

    def test_rejects_negative_values_that_break_monotonicity(self) -> None:
        with self.assertRaisesRegex(ValueError, "非负数组"):
            variable_window_steps([1, -1, 5], 5)


if __name__ == "__main__":
    unittest.main()
