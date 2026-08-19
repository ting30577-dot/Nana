"""从命令行邀请 Claude 作为平等共同设计者讨论 Nana 开发议题。"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def _configure_stdio_utf8() -> None:
    """Keep Chinese CLI output readable on Windows consoles and Codex terminals."""

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            # Some embedded/redirected streams do not allow reconfiguration.
            # In that case keep the original stream rather than failing review.
            pass


_configure_stdio_utf8()


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from nana_core.ai import ClaudeReviewer


DEFAULT_CONTEXT_FILES = (
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "docs" / "project_overview.md",
)
MAX_CONTEXT_CHARS = 120_000


def load_context(paths: list[Path]) -> str:
    sections: list[str] = []
    remaining = MAX_CONTEXT_CHARS
    for path in paths:
        resolved = path.resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"上下文文件不存在：{path}")
        content = resolved.read_text(encoding="utf-8")
        excerpt = content[:remaining]
        sections.append(f"### {resolved.relative_to(PROJECT_ROOT)}\n{excerpt}")
        remaining -= len(excerpt)
        if remaining <= 0:
            break
    return "\n\n".join(sections)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="邀请 Claude 共同设计 Nana")
    parser.add_argument("question", help="希望 Claude 独立判断或共同审议的问题")
    parser.add_argument(
        "--context",
        action="append",
        type=Path,
        help="附加上下文文件；可重复使用。未指定时读取 README 和项目全景文档。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    context_paths = args.context or list(DEFAULT_CONTEXT_FILES)
    try:
        context = load_context(context_paths)
        review = ClaudeReviewer().review(args.question, context)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"无法完成评审：{exc}", file=sys.stderr)
        return 2

    print(review.text)
    print(
        "\n---\n"
        f"模型：{review.model}；输入：{review.input_tokens} tokens；"
        f"输出：{review.output_tokens} tokens；"
        f"缓存命中：{review.cache_read_input_tokens} tokens"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
