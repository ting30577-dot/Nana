"""v0.2.0-dev 遗留算法演示页；仅底层轨迹与绘图能力计划复用。"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QFrame,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QStyle,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.theme import PALETTE
from visualizer.array_canvas import ArrayCanvas


@dataclass(frozen=True, slots=True)
class PatternInfo:
    key: str
    family: str
    title: str
    subtitle: str
    time: str
    space: str
    scene: str
    constraint: str
    code: str
    links: tuple[tuple[str, str], ...]

    def code_for(self, language: str) -> str:
        """返回当前模式指定语言的代码，Python 作为最终回退版本。"""

        if language == "Python":
            return self.code
        return CODE_VARIANTS.get(self.key, {}).get(language, self.code)


FIXED_INFO = PatternInfo(
    key="fixed",
    family="滑动窗口",
    title="固定窗口",
    subtitle="窗口长度固定，每次右移一格，并增量更新窗口统计量。",
    time="O(n)",
    space="O(1)",
    scene="定长连续子数组",
    constraint="right - left + 1 = k",
    code="""def max_sum_subarray(nums, k):
    if k <= 0 or k > len(nums):
        raise ValueError("invalid window size")
    window_sum = sum(nums[:k])
    best = window_sum
    for right in range(k, len(nums)):
        window_sum += nums[right] - nums[right - k]
        best = max(best, window_sum)
    return best""",
    links=(
        ("#643", "https://leetcode.com/problems/maximum-average-subarray-i/"),
        ("#1343", "https://leetcode.com/problems/number-of-sub-arrays-of-size-k-and-average-greater-than-or-equal-to-threshold/"),
        ("#2090", "https://leetcode.com/problems/k-radius-subarray-averages/"),
    ),
)

VARIABLE_INFO = PatternInfo(
    key="variable",
    family="滑动窗口",
    title="可变窗口",
    subtitle="右指针扩张，满足条件后移动左指针收缩，寻找最优连续区间。",
    time="O(n)",
    space="O(1)",
    scene="满足条件的最短/最长连续区间",
    constraint="窗口内状态可增量维护",
    code="""def min_subarray_len(target, nums):
    if target <= 0 or any(value < 0 for value in nums):
        raise ValueError("requires positive target and non-negative values")
    left = 0
    window_sum = 0
    best = float("inf")
    for right, value in enumerate(nums):
        window_sum += value
        while window_sum >= target:
            best = min(best, right - left + 1)
            window_sum -= nums[left]
            left += 1
    return 0 if best == float("inf") else best""",
    links=(
        ("#3", "https://leetcode.com/problems/longest-substring-without-repeating-characters/"),
        ("#76", "https://leetcode.com/problems/minimum-window-substring/"),
        ("#209", "https://leetcode.com/problems/minimum-size-subarray-sum/"),
        ("#239", "https://leetcode.com/problems/sliding-window-maximum/"),
    ),
)

TWO_COLLISION_INFO = PatternInfo(
    key="two_collision",
    family="双指针",
    title="对撞指针",
    subtitle="两个指针从有序序列两端向中间移动，利用单调性排除不可能的答案。",
    time="O(n)",
    space="O(1)",
    scene="有序数组配对、区间面积",
    constraint="根据判断结果安全排除一端",
    code="""def two_sum_sorted(nums, target):
    left, right = 0, len(nums) - 1
    while left < right:
        total = nums[left] + nums[right]
        if total == target:
            return [left + 1, right + 1]
        if total < target:
            left += 1
        else:
            right -= 1
    return []""",
    links=(
        ("#167", "https://leetcode.com/problems/two-sum-ii-input-array-is-sorted/"),
        ("#11", "https://leetcode.com/problems/container-with-most-water/"),
    ),
)

TWO_FAST_SLOW_INFO = PatternInfo(
    key="two_fast_slow",
    family="双指针",
    title="快慢指针",
    subtitle="两个指针同向但速度不同；在环中快指针最终会追上慢指针。",
    time="O(n)",
    space="O(1)",
    scene="链表判环、链表中点",
    constraint="slow 走 1 步，fast 走 2 步",
    code="""def has_cycle(head):
    slow = fast = head
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
        if slow is fast:
            return True
    return False""",
    links=(
        ("#141", "https://leetcode.com/problems/linked-list-cycle/"),
        ("#876", "https://leetcode.com/problems/middle-of-the-linked-list/"),
    ),
)

PREFIX_1D_INFO = PatternInfo(
    key="prefix_1d",
    family="前缀和",
    title="一维前缀和",
    subtitle="先累计从起点到每个位置的和，让任意区间查询只需要一次减法。",
    time="构建 O(n)，查询 O(1)",
    space="O(n)",
    scene="静态数组的多次区间求和",
    constraint="prefix[i + 1] = prefix[i] + nums[i]",
    code="""def build_prefix(nums):
    prefix = [0] * (len(nums) + 1)
    for index, value in enumerate(nums):
        prefix[index + 1] = prefix[index] + value
    return prefix

def range_sum(prefix, left, right):
    return prefix[right + 1] - prefix[left]""",
    links=(
        ("#303", "https://leetcode.com/problems/range-sum-query-immutable/"),
        ("#560", "https://leetcode.com/problems/subarray-sum-equals-k/"),
        ("#1248", "https://leetcode.com/problems/count-number-of-nice-subarrays/"),
    ),
)

PREFIX_2D_INFO = PatternInfo(
    key="prefix_2d",
    family="前缀和",
    title="二维前缀和",
    subtitle="把一维累计推广到矩阵，用四个前缀值组合出任意矩形区域的和。",
    time="构建 O(mn)，查询 O(1)",
    space="O(mn)",
    scene="矩阵区域求和",
    constraint="上 + 左 - 左上重复 + 当前值",
    code="""def build_prefix_2d(matrix):
    rows, cols = len(matrix), len(matrix[0])
    prefix = [[0] * (cols + 1) for _ in range(rows + 1)]
    for row in range(rows):
        for col in range(cols):
            prefix[row + 1][col + 1] = (
                prefix[row][col + 1]
                + prefix[row + 1][col]
                - prefix[row][col]
                + matrix[row][col]
            )
    return prefix""",
    links=(
        ("#304", "https://leetcode.com/problems/range-sum-query-2d-immutable/"),
    ),
)

BINARY_STANDARD_INFO = PatternInfo(
    key="binary_standard",
    family="二分查找",
    title="标准二分",
    subtitle="在有序数组的半开区间 [left, right) 中不断缩小目标所在范围。",
    time="O(log n)",
    space="O(1)",
    scene="查找目标值或插入位置",
    constraint="目标候选始终保留在 [left, right)",
    code="""def binary_search_left(nums, target):
    left, right = 0, len(nums)
    while left < right:
        middle = (left + right) // 2
        if nums[middle] < target:
            left = middle + 1
        else:
            right = middle
    return left""",
    links=(
        ("#704", "https://leetcode.com/problems/binary-search/"),
        ("#35", "https://leetcode.com/problems/search-insert-position/"),
        ("#33", "https://leetcode.com/problems/search-in-rotated-sorted-array/"),
        ("#153", "https://leetcode.com/problems/find-minimum-in-rotated-sorted-array/"),
    ),
)

BINARY_ANSWER_INFO = PatternInfo(
    key="binary_answer",
    family="二分查找",
    title="二分答案",
    subtitle="不在数组下标上搜索，而是在答案值域中利用可行性的单调分界寻找最优值。",
    time="O(n log V)",
    space="O(1)",
    scene="最小化最大值、最大化最小值",
    constraint="check(value) 在值域上具有单调性",
    code="""def min_eating_speed(piles, hours_limit):
    if not piles or hours_limit < len(piles):
        raise ValueError("infeasible input")

    def feasible(speed):
        hours = sum((pile + speed - 1) // speed for pile in piles)
        return hours <= hours_limit

    left, right = 1, max(piles)
    while left < right:
        middle = (left + right) // 2
        if feasible(middle):
            right = middle
        else:
            left = middle + 1
    return left""",
    links=(
        ("#875", "https://leetcode.com/problems/koko-eating-bananas/"),
        ("#1011", "https://leetcode.com/problems/capacity-to-ship-packages-within-d-days/"),
        ("#410", "https://leetcode.com/problems/split-array-largest-sum/"),
    ),
)

STACK_NEXT_INFO = PatternInfo(
    key="stack_next_greater",
    family="单调栈",
    title="下一个更大元素",
    subtitle="从左向右遍历；当前值更大时，连续弹出栈顶并结算它们的答案。",
    time="O(n)",
    space="O(n)",
    scene="下一个更大/更小元素",
    constraint="栈中下标对应的值单调递减",
    code="""def next_greater(nums):
    result = [-1] * len(nums)
    stack = []
    for index, value in enumerate(nums):
        while stack and nums[stack[-1]] < value:
            result[stack.pop()] = value
        stack.append(index)
    return result""",
    links=(
        ("#496", "https://leetcode.com/problems/next-greater-element-i/"),
        ("#739", "https://leetcode.com/problems/daily-temperatures/"),
    ),
)

STACK_RAIN_INFO = PatternInfo(
    key="stack_rain",
    family="单调栈",
    title="接雨水",
    subtitle="从左向右维护递减栈；更高的右边界出现时，弹出谷底并计算这一层积水。",
    time="O(n)",
    space="O(n)",
    scene="接雨水、柱状图边界",
    constraint="每次出栈确定谷底的左右边界",
    code="""def trap(height):
    stack = []
    water = 0
    for right, value in enumerate(height):
        while stack and height[stack[-1]] < value:
            bottom = stack.pop()
            if not stack:
                break
            left = stack[-1]
            width = right - left - 1
            bounded = min(height[left], value) - height[bottom]
            water += width * bounded
        stack.append(right)
    return water""",
    links=(
        ("#42", "https://leetcode.com/problems/trapping-rain-water/"),
        ("#84", "https://leetcode.com/problems/largest-rectangle-in-histogram/"),
    ),
)

SUPPORTED_LANGUAGES = ("C", "C++", "Python")

# 代码区域只展示核心算法，省略了输入输出与平台模板；每种语言都保持同一个算法语义。
CODE_VARIANTS: dict[str, dict[str, str]] = {
    "fixed": {
        "C": """int max_sum_subarray(const int nums[], int n, int k) {
    if (k <= 0 || k > n) return 0;
    int window_sum = 0;
    for (int i = 0; i < k; ++i) window_sum += nums[i];
    int best = window_sum;
    for (int right = k; right < n; ++right) {
        window_sum += nums[right] - nums[right - k];
        if (window_sum > best) best = window_sum;
    }
    return best;
}""",
        "C++": """int max_sum_subarray(const vector<int>& nums, int k) {
    int window_sum = accumulate(nums.begin(), nums.begin() + k, 0);
    int best = window_sum;
    for (int right = k; right < nums.size(); ++right) {
        window_sum += nums[right] - nums[right - k];
        best = max(best, window_sum);
    }
    return best;
}""",
    },
    "variable": {
        "C": """int min_subarray_len(int target, const int nums[], int n) {
    if (target <= 0) return 0;
    for (int i = 0; i < n; ++i)
        if (nums[i] < 0) return 0;
    int left = 0, window_sum = 0, best = n + 1;
    for (int right = 0; right < n; ++right) {
        window_sum += nums[right];
        while (window_sum >= target) {
            int candidate = right - left + 1;
            if (candidate < best) best = candidate;
            window_sum -= nums[left++];
        }
    }
    return best == n + 1 ? 0 : best;
}""",
        "C++": """int min_subarray_len(int target, const vector<int>& nums) {
    if (target <= 0 || any_of(nums.begin(), nums.end(),
            [](int value) { return value < 0; }))
        throw invalid_argument("requires non-negative values");
    int left = 0, window_sum = 0, best = nums.size() + 1;
    for (int right = 0; right < nums.size(); ++right) {
        window_sum += nums[right];
        while (window_sum >= target) {
            best = min(best, right - left + 1);
            window_sum -= nums[left++];
        }
    }
    return best == nums.size() + 1 ? 0 : best;
}""",
    },
    "two_collision": {
        "C": """int two_sum_sorted(
    const int nums[], int n, int target, int result[2]) {
    int left = 0, right = n - 1;
    while (left < right) {
        int total = nums[left] + nums[right];
        if (total == target) {
            result[0] = left + 1;
            result[1] = right + 1;
            return 1;
        }
        if (total < target) ++left;
        else --right;
    }
    return 0;
}""",
        "C++": """vector<int> two_sum_sorted(
    const vector<int>& nums, int target) {
    int left = 0, right = nums.size() - 1;
    while (left < right) {
        int total = nums[left] + nums[right];
        if (total == target) return {left + 1, right + 1};
        if (total < target) ++left;
        else --right;
    }
    return {};
}""",
    },
    "two_fast_slow": {
        "C": """typedef struct Node {
    int value;
    struct Node* next;
} Node;

int has_cycle(Node* head) {
    Node* slow = head;
    Node* fast = head;
    while (fast != NULL && fast->next != NULL) {
        slow = slow->next;
        fast = fast->next->next;
        if (slow == fast) return 1;
    }
    return 0;
}""",
        "C++": """bool has_cycle(ListNode* head) {
    ListNode* slow = head;
    ListNode* fast = head;
    while (fast != nullptr && fast->next != nullptr) {
        slow = slow->next;
        fast = fast->next->next;
        if (slow == fast) return true;
    }
    return false;
}""",
    },
    "prefix_1d": {
        "C": """void build_prefix(
    const int nums[], int n, int prefix[]) {
    prefix[0] = 0;
    for (int i = 0; i < n; ++i)
        prefix[i + 1] = prefix[i] + nums[i];
}

int range_sum(const int prefix[], int left, int right) {
    return prefix[right + 1] - prefix[left];
}""",
        "C++": """vector<int> build_prefix(const vector<int>& nums) {
    vector<int> prefix(nums.size() + 1);
    for (int i = 0; i < nums.size(); ++i)
        prefix[i + 1] = prefix[i] + nums[i];
    return prefix;
}

int range_sum(const vector<int>& prefix, int left, int right) {
    return prefix[right + 1] - prefix[left];
}""",
    },
    "prefix_2d": {
        "C": """void build_prefix_2d(
    int matrix[][MAX_COL], int rows, int cols,
    int prefix[][MAX_COL + 1]) {
    for (int r = 0; r < rows; ++r) {
        for (int c = 0; c < cols; ++c) {
            prefix[r + 1][c + 1] =
                prefix[r][c + 1] + prefix[r + 1][c]
                - prefix[r][c] + matrix[r][c];
        }
    }
}""",
        "C++": """vector<vector<int>> build_prefix_2d(
    const vector<vector<int>>& matrix) {
    int rows = matrix.size(), cols = matrix[0].size();
    vector<vector<int>> prefix(rows + 1, vector<int>(cols + 1));
    for (int r = 0; r < rows; ++r) {
        for (int c = 0; c < cols; ++c) {
            prefix[r + 1][c + 1] =
                prefix[r][c + 1] + prefix[r + 1][c]
                - prefix[r][c] + matrix[r][c];
        }
    }
    return prefix;
}""",
    },
    "binary_standard": {
        "C": """int binary_search_left(
    const int nums[], int n, int target) {
    int left = 0, right = n;
    while (left < right) {
        int middle = left + (right - left) / 2;
        if (nums[middle] < target) left = middle + 1;
        else right = middle;
    }
    return left;
}""",
        "C++": """int binary_search_left(
    const vector<int>& nums, int target) {
    int left = 0, right = nums.size();
    while (left < right) {
        int middle = left + (right - left) / 2;
        if (nums[middle] < target) left = middle + 1;
        else right = middle;
    }
    return left;
}""",
    },
    "binary_answer": {
        "C": """int min_eating_speed(
    const int piles[], int n, int hours_limit) {
    if (n <= 0 || hours_limit < n) return -1;
    int left = 1, right = piles[0];
    for (int i = 1; i < n; ++i)
        if (piles[i] > right) right = piles[i];
    while (left < right) {
        int middle = left + (right - left) / 2;
        long long hours = 0;
        for (int i = 0; i < n; ++i)
            hours += (piles[i] + middle - 1) / middle;
        if (hours <= hours_limit) right = middle;
        else left = middle + 1;
    }
    return left;
}""",
        "C++": """int min_eating_speed(
    const vector<int>& piles, int hours_limit) {
    if (piles.empty() || hours_limit < piles.size())
        throw invalid_argument("infeasible input");
    int left = 1, right = *max_element(piles.begin(), piles.end());
    while (left < right) {
        int middle = left + (right - left) / 2;
        long long hours = 0;
        for (int pile : piles)
            hours += (pile + middle - 1) / middle;
        if (hours <= hours_limit) right = middle;
        else left = middle + 1;
    }
    return left;
}""",
    },
    "stack_next_greater": {
        "C": """void next_greater(
    const int nums[], int n, int result[]) {
    int stack[n], top = 0;
    for (int i = 0; i < n; ++i) result[i] = -1;
    for (int i = 0; i < n; ++i) {
        while (top > 0 && nums[stack[top - 1]] < nums[i])
            result[stack[--top]] = nums[i];
        stack[top++] = i;
    }
}""",
        "C++": """vector<int> next_greater(const vector<int>& nums) {
    vector<int> result(nums.size(), -1);
    vector<int> stack;
    for (int i = 0; i < nums.size(); ++i) {
        while (!stack.empty() && nums[stack.back()] < nums[i]) {
            result[stack.back()] = nums[i];
            stack.pop_back();
        }
        stack.push_back(i);
    }
    return result;
}""",
    },
    "stack_rain": {
        "C": """int trap(const int height[], int n) {
    int stack[n], top = 0, water = 0;
    for (int right = 0; right < n; ++right) {
        while (top > 0 && height[stack[top - 1]] < height[right]) {
            int bottom = stack[--top];
            if (top == 0) break;
            int left = stack[top - 1];
            int width = right - left - 1;
            int boundary = height[left] < height[right]
                         ? height[left] : height[right];
            int bounded = boundary - height[bottom];
            water += width * bounded;
        }
        stack[top++] = right;
    }
    return water;
}""",
        "C++": """int trap(const vector<int>& height) {
    vector<int> stack;
    int water = 0;
    for (int right = 0; right < height.size(); ++right) {
        while (!stack.empty() && height[stack.back()] < height[right]) {
            int bottom = stack.back();
            stack.pop_back();
            if (stack.empty()) break;
            int left = stack.back();
            int width = right - left - 1;
            int bounded = min(height[left], height[right])
                          - height[bottom];
            water += width * bounded;
        }
        stack.push_back(right);
    }
    return water;
}""",
    },
}

PATTERNS = {
    pattern.key: pattern
    for pattern in (
        FIXED_INFO,
        VARIABLE_INFO,
        TWO_COLLISION_INFO,
        TWO_FAST_SLOW_INFO,
        PREFIX_1D_INFO,
        PREFIX_2D_INFO,
        BINARY_STANDARD_INFO,
        BINARY_ANSWER_INFO,
        STACK_NEXT_INFO,
        STACK_RAIN_INFO,
    )
}

PATTERN_TREE = (
    ("滑动窗口", (FIXED_INFO, VARIABLE_INFO)),
    ("双指针", (TWO_COLLISION_INFO, TWO_FAST_SLOW_INFO)),
    ("前缀和", (PREFIX_1D_INFO, PREFIX_2D_INFO)),
    ("二分查找", (BINARY_STANDARD_INFO, BINARY_ANSWER_INFO)),
    ("单调栈", (STACK_NEXT_INFO, STACK_RAIN_INFO)),
)


class InfoCard(QFrame):
    def __init__(self, label: str, value: str) -> None:
        super().__init__()
        self.setObjectName("infoCard")
        self.setFixedHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        label_widget = QLabel(label)
        label_widget.setObjectName("cardLabel")
        value_widget = QLabel(value)
        value_widget.setObjectName("cardValue")
        value_widget.setWordWrap(True)
        layout.addWidget(label_widget)
        layout.addWidget(value_widget)


class AlgorithmWorkspace(QWidget):
    """模式树、代码展示和统一动画播放器组成的算法工作台。"""

    def __init__(self) -> None:
        super().__init__()
        self._pattern = FIXED_INFO

        self.pattern_tree = QTreeWidget()
        self.pattern_tree.setHeaderLabel("算法模式")
        self.pattern_tree.setFixedWidth(204)
        self.pattern_tree.setRootIsDecorated(True)
        first_item: QTreeWidgetItem | None = None
        for family, patterns in PATTERN_TREE:
            root = QTreeWidgetItem(self.pattern_tree, [family])
            for pattern in patterns:
                item = QTreeWidgetItem(root, [pattern.title])
                item.setData(0, Qt.ItemDataRole.UserRole, pattern.key)
                first_item = first_item or item
            root.setExpanded(True)
        if first_item is not None:
            self.pattern_tree.setCurrentItem(first_item)
        self.pattern_tree.itemClicked.connect(self._pattern_clicked)

        self.title_label = QLabel()
        self.title_label.setObjectName("pageTitle")
        self.title_label.setFixedHeight(38)
        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("mutedText")
        self.subtitle_label.setFixedHeight(24)
        self.subtitle_label.setWordWrap(False)

        self.cards_layout = QGridLayout()
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(8)
        self.cards_panel = QWidget()
        self.cards_panel.setFixedHeight(80)
        self.cards_panel.setLayout(self.cards_layout)

        self.code_view = QTextEdit()
        self.code_view.setReadOnly(True)
        self.code_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.code_view.setFont(QFont("Consolas", 10))
        self.code_view.setMinimumWidth(280)

        self.code_label = QLabel("Code")
        self.code_label.setObjectName("codeSectionLabel")
        self.language_combo = QComboBox()
        self.language_combo.setFixedWidth(112)
        self.language_combo.addItems(SUPPORTED_LANGUAGES)
        self.language_combo.currentTextChanged.connect(self._language_changed)

        self.canvas = ArrayCanvas()

        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 10)
        self.speed_slider.setValue(5)
        self.speed_slider.setFixedWidth(120)
        self.speed_slider.valueChanged.connect(self.canvas.set_speed)

        self.start_button = QPushButton("开始")
        self.pause_button = QPushButton("暂停")
        self.reset_button = QPushButton("重置")
        self.back_button = QPushButton("上一步")
        self.step_button = QPushButton("下一步")
        self.start_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self.pause_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause)
        )
        self.reset_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        self.back_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipBackward)
        )
        self.step_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSkipForward)
        )
        self.start_button.clicked.connect(self.canvas.start)
        self.pause_button.clicked.connect(self.canvas.pause)
        self.reset_button.clicked.connect(self.canvas.reset)
        self.back_button.clicked.connect(self.canvas.step_back)
        self.step_button.clicked.connect(self.canvas.step_once)

        self.links_label = QLabel()
        self.links_label.setOpenExternalLinks(False)
        self.links_label.linkActivated.connect(self._open_link)
        self.links_label.setTextFormat(Qt.TextFormat.RichText)
        self.links_label.setWordWrap(True)

        self._language_by_pattern = {
            pattern.key: "C" for pattern in PATTERNS.values()
        }

        self._build_layout()
        self._apply_pattern(FIXED_INFO)

    def _build_layout(self) -> None:
        pattern_panel = QWidget()
        pattern_panel.setFixedWidth(224)
        pattern_panel.setStyleSheet(
            f"background: {PALETTE['surface_alt']};"
        )
        pattern_panel_layout = QVBoxLayout(pattern_panel)
        pattern_panel_layout.setContentsMargins(12, 18, 8, 14)
        pattern_panel_layout.addWidget(self.pattern_tree)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(22, 18, 22, 14)
        right_layout.setSpacing(10)
        right_layout.addWidget(self.title_label)
        right_layout.addWidget(self.subtitle_label)
        right_layout.addWidget(self.cards_panel)

        split = QHBoxLayout()
        split.setSpacing(10)
        code_panel = QFrame()
        code_panel.setObjectName("codeCard")
        code_panel_layout = QVBoxLayout(code_panel)
        code_panel_layout.setContentsMargins(12, 10, 12, 12)
        code_panel_layout.setSpacing(12)
        code_header = QHBoxLayout()
        code_header.setContentsMargins(4, 0, 4, 0)
        code_header.addWidget(self.code_label)
        code_header.addStretch(1)
        code_header.addWidget(self.language_combo)
        code_panel_layout.addLayout(code_header)
        code_panel_layout.addWidget(self.code_view, 1)
        split.addWidget(code_panel, 4)
        split.addWidget(self.canvas, 6)
        right_layout.addLayout(split, 1)

        controls = QHBoxLayout()
        controls.setSpacing(7)
        controls.addWidget(QLabel("速度"))
        controls.addWidget(QLabel("慢"))
        controls.addWidget(self.speed_slider)
        controls.addWidget(QLabel("快"))
        controls.addSpacing(6)
        controls.addWidget(self.start_button)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.reset_button)
        controls.addWidget(self.back_button)
        controls.addWidget(self.step_button)
        controls.addStretch(1)
        right_layout.addLayout(controls)
        right_layout.addWidget(self.links_label)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(pattern_panel)
        outer.addWidget(right_panel, 1)

    def _pattern_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if key in PATTERNS:
            self._apply_pattern(PATTERNS[key])

    def _language_changed(self, language: str) -> None:
        if not self._pattern:
            return
        self._language_by_pattern[self._pattern.key] = language
        self._refresh_code()

    def _apply_pattern(self, pattern: PatternInfo) -> None:
        self._pattern = pattern
        self.title_label.setText(f"{pattern.family} · {pattern.title}")
        self.subtitle_label.setText(pattern.subtitle)

        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        cards = (
            ("时间复杂度", pattern.time),
            ("空间复杂度", pattern.space),
            ("适用场景", pattern.scene),
            ("核心约束", pattern.constraint),
        )
        for column, (label, value) in enumerate(cards):
            self.cards_layout.addWidget(InfoCard(label, value), 0, column)

        self.language_combo.blockSignals(True)
        self.language_combo.setCurrentText(
            self._language_by_pattern.get(pattern.key, "C")
        )
        self.language_combo.blockSignals(False)
        self._refresh_code()
        self.canvas.set_mode(pattern.key)
        links = "　".join(
            (
                f'<a href="{html.escape(url)}" '
                f'style="color:{PALETTE["primary_strong"]};">'
                f"LeetCode {html.escape(label)}</a>"
            )
            for label, url in pattern.links
        )
        self.links_label.setText(f"关联题目：{links}")

    def _refresh_code(self) -> None:
        language = self._language_by_pattern[self._pattern.key]
        self.code_view.setHtml(
            self._highlight_code(
                self._pattern.code_for(language),
                language,
            )
        )

    @staticmethod
    def _highlight_code(code: str, language: str = "Python") -> str:
        keywords = (
            "def|return|for|in|range|while|if|elif|else|float|"
            "max|min|sum|enumerate|len|True|False|break|raise|ValueError|"
            "int|long|void|bool|const|struct|typedef|vector|"
            "nullptr|NULL|true|false|size_t|auto"
        )
        lines = html.escape(code, quote=False).splitlines()
        rendered = []
        for line in lines:
            if "#" in line:
                code_part, comment = line.split("#", 1)
                code_part = re.sub(
                    rf"\b({keywords})\b",
                    rf'<span style="color:{PALETTE["primary_strong"]};">\1</span>',
                    code_part,
                )
                line = (
                    f'{code_part}<span style="color:{PALETTE["muted"]};">'
                    f"#{comment}</span>"
                )
            else:
                line = re.sub(
                    rf"\b({keywords})\b",
                    rf'<span style="color:{PALETTE["primary_strong"]};">\1</span>',
                    line,
                )
            rendered.append(line)
        return (
            '<pre style="font-family: Consolas, monospace; font-size: 10pt; '
            f'color:{PALETTE["text_soft"]}; line-height: 1.4; '
            'padding-top: 14px;">'
            + "\n".join(rendered)
            + "</pre>"
        )

    @staticmethod
    def _open_link(url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))
