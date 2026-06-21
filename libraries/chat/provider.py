"""LLM provider abstraction. AnthropicProvider is the only concrete impl today;
a local-model provider can be added later without touching the engine or tools."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from libraries.chat import config


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    text: Optional[str]            # final assistant prose, if any
    tool_calls: list               # list[ToolCall] the model wants run
    stop_reason: str
    raw_assistant_content: list = field(default_factory=list)  # SDK content blocks


class LLMProvider(ABC):
    @abstractmethod
    def create(self, system: str, messages: list, tools: list) -> LLMResponse:
        """Send one request and return a normalized response."""


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str = config.MODEL, max_tokens: int = config.MAX_TOKENS):
        import anthropic
        self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        self._model = model
        self._max_tokens = max_tokens

    def create(self, system: str, messages: list, tools: list) -> LLMResponse:
        raw = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=messages,
            tools=tools,
        )
        return self._normalize(raw)

    @staticmethod
    def _normalize(raw) -> LLMResponse:
        text_parts = []
        tool_calls = []
        for block in raw.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, arguments=block.input))
        return LLMResponse(
            text="".join(text_parts) or None,
            tool_calls=tool_calls,
            stop_reason=raw.stop_reason,
            raw_assistant_content=raw.content,
        )
