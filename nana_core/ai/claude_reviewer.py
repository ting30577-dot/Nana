"""通过 Claude 获取独立、只读、平等的项目共同设计意见。"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any
from urllib.parse import urlparse


DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_MAX_OUTPUT_TOKENS = 16_000
RATE_LIMIT_FALLBACK_MAX_OUTPUT_TOKENS = 4_096
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30.0
NANA_API_KEY_ENV = "NANA_CLAUDE_API_KEY"
NANA_BASE_URL_ENV = "NANA_CLAUDE_BASE_URL"
NANA_MODEL_ENV = "NANA_CLAUDE_MODEL"
OFFICIAL_API_HOST = "api.anthropic.com"

SYSTEM_PROMPT = """\
你是 Nana 项目的独立、平等的产品与技术共同设计者。你与 Codex 面对同一证据包，
双方都没有天然的主导权或服从义务；最终共识必须经由独立提案、论据交换、交叉
反驳和显式收敛形成。

你的职责：
1. 独立判断问题，不迎合用户、Codex 或既有规划；
2. 明确区分事实、假设、推论、风险与建议，并给出可审查的决策依据摘要；
3. 主动寻找反例、替代方案和会使方案失败的条件；
4. 对重要决策拥有异议权：未被证据解决时明确标为“未达成共识”；
5. 优先检查产品价值、交互闭环、架构一致性、安全边界、可测试性和执行路径；
6. 不直接修改文件，不声称执行过未执行的测试；
7. 如果上下文不足，明确指出需要补充的证据。

请使用中文，并按以下结构回答：
## 结论
## 决策依据摘要
## 支持与反对证据
## 对另一方案的分歧或反驳
## 收敛条件与可执行建议
## 尚未达成共识的问题
"""


@dataclass(frozen=True)
class ClaudeReview:
    """一次 Claude 评审的文本与用量信息。"""

    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int


class ClaudeReviewer:
    """Claude 的只读、平等共同设计适配器。

    API Key 仅从 ``NANA_CLAUDE_API_KEY`` 读取，并且必须同时配置
    ``NANA_CLAUDE_BASE_URL``。适配器不读取官方 ``ANTHROPIC_API_KEY``，也不
    允许把官方 Anthropic API 当作默认或回退通道。
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model = model or os.environ.get(NANA_MODEL_ENV, DEFAULT_MODEL)
        self._client = client

    def review(self, question: str, project_context: str = "") -> ClaudeReview:
        if not question.strip():
            raise ValueError("评审问题不能为空")

        client = self._client or self._create_client()
        prompt = self._build_prompt(question, project_context)

        max_tokens = DEFAULT_MAX_OUTPUT_TOKENS
        for attempt in range(2):
            try:
                response = self._request(
                    client,
                    prompt,
                    max_tokens=max_tokens,
                    reduced=attempt > 0,
                )
                break
            except Exception as exc:
                if attempt == 0 and self._is_rate_limit_error(exc):
                    max_tokens = RATE_LIMIT_FALLBACK_MAX_OUTPUT_TOKENS
                    continue
                if attempt == 0 and self._is_interrupted_stream(exc):
                    continue
                self._raise_friendly_api_error(exc)

        text = "\n".join(
            block.text for block in response.content if block.type == "text"
        ).strip()
        usage = response.usage
        return ClaudeReview(
            text=text,
            model=response.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_input_tokens=getattr(
                usage, "cache_read_input_tokens", 0
            )
            or 0,
        )

    def _request(
        self,
        client: Any,
        prompt: str,
        *,
        max_tokens: int,
        reduced: bool = False,
    ) -> Any:
        request: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": prompt}],
        }
        if not reduced:
            request.update(
                thinking={"type": "adaptive"},
                output_config={"effort": "high"},
                cache_control={"type": "ephemeral"},
            )

        # The configured Anthropic-compatible gateway acknowledges streaming
        # requests but may never terminate its SSE response.  Use the same
        # request body through the non-streaming endpoint for real gateway
        # clients; test doubles (which only expose ``stream``) retain the
        # original path and its retry semantics.
        base_url = os.environ.get(NANA_BASE_URL_ENV, "").strip()
        if base_url and hasattr(client.messages, "create"):
            # Keep gateway calls within the bounded response size that the
            # compatibility service reliably completes.  The normal Anthropic
            # path still uses the caller's full budget.
            request["max_tokens"] = min(
                request["max_tokens"], RATE_LIMIT_FALLBACK_MAX_OUTPUT_TOKENS
            )
            # Some compatible gateways accept these fields syntactically but
            # spend unbounded time on adaptive-thinking/cache negotiation.
            # The review remains read-only and fully specified by the prompt,
            # so omit optional controls on this transport path.
            request.pop("thinking", None)
            request.pop("output_config", None)
            request.pop("cache_control", None)
            return client.messages.create(**request)

        with client.messages.stream(**request) as stream:
            return stream.get_final_message()

    @staticmethod
    def _is_interrupted_stream(exc: Exception) -> bool:
        import httpx

        return isinstance(exc, (httpx.RemoteProtocolError, httpx.ReadError))

    @staticmethod
    def _is_rate_limit_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return "rate_limit_error" in text or "concurrency limit" in text

    @staticmethod
    def _build_prompt(question: str, project_context: str) -> str:
        context = project_context.strip() or "（本次未提供额外项目上下文）"
        return (
            "请独立评审下面的 Nana 开发议题。\n\n"
            f"【项目上下文】\n{context}\n\n"
            f"【待讨论问题】\n{question.strip()}"
        )

    @staticmethod
    def _create_client() -> Any:
        api_key = os.environ.get(NANA_API_KEY_ENV, "").strip()
        if not api_key:
            raise RuntimeError(
                f"未设置 {NANA_API_KEY_ENV}。Nana 只允许通过已配置的 Claude 中转站，"
                "不会直连官方 Anthropic，也不会请求官方授权。"
            )

        base_url = os.environ.get(NANA_BASE_URL_ENV, "").strip().rstrip("/")
        if not base_url:
            raise RuntimeError(
                f"未设置 {NANA_BASE_URL_ENV}。请配置 Claude 兼容中转站地址；"
                "不会回退到官方 Anthropic API。"
            )
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise RuntimeError(
                f"{NANA_BASE_URL_ENV} 不是有效的 HTTP(S) 中转站地址。"
            )
        if parsed.hostname and parsed.hostname.lower() == OFFICIAL_API_HOST:
            raise RuntimeError(
                f"{NANA_BASE_URL_ENV} 指向官方 Anthropic 地址。Nana 只允许使用中转站，"
                "请改为中转站 Base URL。"
            )

        import anthropic

        kwargs: dict[str, Any] = {
            "api_key": api_key,
            # A gateway that never completes must not stall the D3 gate
            # indefinitely. The caller can retry after the bounded failure.
            "timeout": DEFAULT_REQUEST_TIMEOUT_SECONDS,
        }
        if base_url.endswith("/v1"):
            # 官方 SDK 自己会追加 /v1/messages，避免形成 /v1/v1/messages。
            base_url = base_url[:-3]
        if base_url:
            kwargs["base_url"] = base_url
        return anthropic.Anthropic(**kwargs)

    @staticmethod
    def _raise_friendly_api_error(exc: Exception) -> None:
        if ClaudeReviewer._is_interrupted_stream(exc):
            raise RuntimeError(
                "Claude 流式响应连续两次被中转站提前断开，请稍后重试或切换渠道。"
            ) from exc

        try:
            import anthropic
        except ImportError:
            raise RuntimeError(f"Claude 请求失败：{exc}") from exc

        if isinstance(exc, anthropic.AuthenticationError):
            raise RuntimeError(
                "Claude 鉴权失败。请检查当前渠道的 API Key 和 Base URL 是否匹配。"
            ) from exc
        if isinstance(exc, anthropic.NotFoundError):
            raise RuntimeError(
                "Claude 模型或接口不存在。请检查 NANA_CLAUDE_MODEL 和 "
                "NANA_CLAUDE_BASE_URL。"
            ) from exc
        if isinstance(exc, anthropic.RateLimitError):
            raise RuntimeError("Claude 请求受到限流，请稍后重试。") from exc
        if isinstance(exc, anthropic.APIConnectionError):
            raise RuntimeError(
                "无法连接 Claude 服务，请检查网络和 NANA_CLAUDE_BASE_URL。"
            ) from exc
        if isinstance(exc, anthropic.APIStatusError):
            raise RuntimeError(
                f"Claude 服务返回错误（HTTP {exc.status_code}）：{exc.message}"
            ) from exc
        raise RuntimeError(f"Claude 请求失败：{exc}") from exc
