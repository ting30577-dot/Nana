"""迁移期遗留算法实现与边界测试。"""

from __future__ import annotations

import unittest

from algorithms.binary_search import binary_answer_steps, binary_search_left_steps
from algorithms.monotonic_stack import next_greater_steps, trap_rain_steps
from algorithms.prefix_sum import prefix_1d_steps, prefix_2d_steps
from algorithms.two_pointers import collision_steps, fast_slow_cycle_steps


class TwoPointerTests(unittest.TestCase):
    def test_collision_pointer_finds_target(self) -> None:
        states = collision_steps([1, 2, 4, 6, 10], 8)

        self.assertTrue(states[-1].payload["done"])
        self.assertEqual(states[-1].payload["total"], 8)
        self.assertEqual(
            (states[-1].payload["left"], states[-1].payload["right"]),
            (1, 3),
        )

    def test_collision_pointer_rejects_unsorted_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "非递减数组"):
            collision_steps([3, 1, 2], 4)

    def test_fast_slow_pointers_meet_in_cycle(self) -> None:
        states = fast_slow_cycle_steps([3, 2, 0, -4], [1, 2, 3, 1])

        self.assertTrue(states[-1].payload["met"])
        self.assertEqual(states[-1].payload["slow"], states[-1].payload["fast"])

    def test_fast_slow_pointers_validate_link_shape_and_range(self) -> None:
        with self.assertRaisesRegex(ValueError, "数量必须一致"):
            fast_slow_cycle_steps([1, 2], [1])
        with self.assertRaisesRegex(ValueError, "超出节点范围"):
            fast_slow_cycle_steps([1, 2], [1, 2])


class PrefixSumTests(unittest.TestCase):
    def test_one_dimensional_query(self) -> None:
        states = prefix_1d_steps([2, -1, 3, 5, -2], 1, 3)

        self.assertEqual(states[-1].payload["result"], 7)

    def test_two_dimensional_query(self) -> None:
        states = prefix_2d_steps(
            [[3, 0, 1], [5, 6, 3], [1, 2, 0]],
            1,
            1,
            2,
            2,
        )

        self.assertEqual(states[-1].payload["result"], 11)

    def test_two_dimensional_query_rejects_ragged_matrix(self) -> None:
        with self.assertRaisesRegex(ValueError, "每一行必须等长"):
            prefix_2d_steps([[], [1]], 0, 0, 0, 0)


class BinarySearchTests(unittest.TestCase):
    def test_left_boundary(self) -> None:
        states = binary_search_left_steps([1, 3, 3, 5], 3)

        self.assertEqual(states[-1].payload["result"], 1)
        self.assertTrue(states[-1].payload["found"])

    def test_left_boundary_rejects_unsorted_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "非递减数组"):
            binary_search_left_steps([1, 4, 2], 2)

    def test_binary_answer(self) -> None:
        states = binary_answer_steps([3, 6, 7, 11], 8)

        self.assertEqual(states[-1].payload["result"], 4)

    def test_binary_answer_rejects_impossible_hours(self) -> None:
        with self.assertRaisesRegex(ValueError, "不存在可行速度"):
            binary_answer_steps([3, 6], 1)

    def test_binary_answer_keeps_large_visual_domain_bounded(self) -> None:
        states = binary_answer_steps([1_000_000_000], 1)

        self.assertEqual(states[-1].payload["result"], 1_000_000_000)
        self.assertLessEqual(len(states[-1].payload["domain"]), 25)
        self.assertEqual(states[-1].payload["domain"][0], 1)
        self.assertEqual(states[-1].payload["domain"][-1], 1_000_000_000)


class MonotonicStackTests(unittest.TestCase):
    def test_next_greater_from_left_to_right(self) -> None:
        states = next_greater_steps([2, 1, 2, 4, 3])

        self.assertEqual(states[-1].payload["result"], (4, 2, 4, -1, -1))
        self.assertTrue(any(state.payload["phase"] == "pop" for state in states))

    def test_trapping_rain_water(self) -> None:
        states = trap_rain_steps([0, 1, 0, 2, 1, 0, 1, 3, 2, 1, 2, 1])

        self.assertEqual(states[-1].payload["water"], 6)

    def test_trapping_rain_water_rejects_negative_height(self) -> None:
        with self.assertRaisesRegex(ValueError, "不能为负数"):
            trap_rain_steps([2, -1, 2])


if __name__ == "__main__":
    unittest.main()
