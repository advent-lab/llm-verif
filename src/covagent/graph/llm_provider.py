"""LLM provider implementations — OpenAI for real runs, Mock for tests."""

from __future__ import annotations

import os
import json
from collections.abc import Iterable
from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import Runnable, RunnableLambda

from covagent.config import RunConfig


class OpenAILLMProvider:
    """Real provider — instantiates `ChatOpenAI` per role."""

    def __init__(self, config: RunConfig) -> None:
        from langchain_openai import ChatOpenAI  # imported lazily

        self._models: dict[str, BaseChatModel] = {
            "init": ChatOpenAI(
                base_url=os.environ.get("OPENAI_BASE_URL"),
                model=config.models.init, 
                temperature=config.models.temperature
            ),
            "orchestrate": ChatOpenAI(
                base_url=os.environ.get("OPENAI_BASE_URL"),
                model=config.models.orchestrator, 
                temperature=config.models.temperature
            ),
            "agent": ChatOpenAI(
                base_url=os.environ.get("OPENAI_BASE_URL"),
                model=config.models.agent, 
                temperature=config.models.temperature
            ),
        }

    def get(self, role: Literal["init", "orchestrate", "agent"]) -> BaseChatModel:
        return self._models[role]

class _CursorMockModel(FakeMessagesListChatModel):
    """A `FakeMessagesListChatModel` that consumes from a shared cursor.

    `bind_tools` and `with_structured_output` return wrappers over this same
    model, so every invocation advances the same script.
    """

    def bind_tools(self, tools: list[Any], **_: Any) -> "_CursorMockModel":  # type: ignore[override]
        return self

    def with_structured_output(self, schema: Any, **_: Any) -> Runnable:  # type: ignore[override]
        underlying = self

        def _parse(input_: Any) -> Any:
            ai = underlying.invoke(input_)
            text = ai.content if isinstance(ai.content, str) else json.dumps(ai.content)
            try:
                data = json.loads(text) if text else {}
            except json.JSONDecodeError:
                data = {}
            try:
                return schema(**data)
            except Exception:
                return schema()

        return RunnableLambda(_parse)


class MockLLMProvider:
    """Test provider — replays a scripted list of messages per role.

    The cursor for each role advances across all `.get(role).invoke(...)` calls,
    so a script of `[empty_ai, dispatch_json, empty_ai, terminate_json]` drives
    the orchestrator through tool-loop-turn → dispatch → tool-loop-turn → terminate.

    Default scripts (when none configured) make the orchestrator terminate
    immediately so smoke runs don't loop.
    """

    def __init__(
        self,
        scripts: dict[str, Iterable[BaseMessage]] | None = None,
    ) -> None:
        self._scripts: dict[str, list[BaseMessage]] = {
            k: list(v) for k, v in (scripts or {}).items()
        }
        # One persistent _CursorMockModel per role; we hand it back from .get()
        # so its `i` cursor (FakeMessagesListChatModel internal) keeps advancing.
        self._cached: dict[str, _CursorMockModel] = {}

    def set_script(
        self,
        role: Literal["init", "orchestrate", "agent"],
        messages: Iterable[BaseMessage],
    ) -> None:
        self._scripts[role] = list(messages)
        self._cached.pop(role, None)

    def get(self, role: Literal["init", "orchestrate", "agent"]) -> BaseChatModel:
        if role in self._cached:
            return self._cached[role]
        msgs = self._scripts.get(role)
        if not msgs:
            if role == "orchestrate":
                msgs = [
                    AIMessage(content=""),
                    AIMessage(content=json.dumps({
                        "kind": "terminate",
                        "dispatch_briefs": [],
                        "rationale": "mock terminate",
                        "route_run_status": "done",
                        "route_reason": "mock provider, no work to do",
                    })),
                ]
            elif role == "init":
                msgs = [AIMessage(content="design_digest: mock")]
            else:
                msgs = [AIMessage(content="")]
        model = _CursorMockModel(responses=list(msgs))
        self._cached[role] = model
        return model
