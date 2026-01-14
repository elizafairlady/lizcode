"""Conversation state management for LizCode."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Mode(Enum):
    """Operating modes for LizCode."""

    PLAN = "plan"
    ACT = "act"
    BASH = "bash"

    def __str__(self) -> str:
        return self.value


class Role(Enum):
    """Message roles in conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"

    def __str__(self) -> str:
        return self.value


@dataclass
class ToolCall:
    """Represents a tool call request from the model."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """Represents the result of a tool execution."""

    tool_call_id: str
    name: str
    result: str
    success: bool = True


@dataclass
class Message:
    """A message in the conversation."""

    role: Role
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tool_calls: list[ToolCall] | None = None
    tool_result: ToolResult | None = None

    def to_api_format(self) -> dict[str, Any]:
        """Convert to API message format."""
        msg: dict[str, Any] = {
            "role": self.role.value,
            "content": self.content,
        }

        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in self.tool_calls
            ]

        if self.tool_result:
            msg["role"] = "tool"
            msg["tool_call_id"] = self.tool_result.tool_call_id
            msg["name"] = self.tool_result.name
            msg["content"] = self.tool_result.result

        return msg


@dataclass
class ConversationState:
    """Manages the state of a conversation session."""

    messages: list[Message] = field(default_factory=list)
    mode: Mode = Mode.ACT
    working_directory: str = "."
    model: str = ""
    provider: str = ""

    def add_message(self, role: Role, content: str, **kwargs: Any) -> Message:
        """Add a message to the conversation."""
        message = Message(role=role, content=content, **kwargs)
        self.messages.append(message)
        return message

    def add_user_message(self, content: str) -> Message:
        """Add a user message."""
        return self.add_message(Role.USER, content)

    def add_assistant_message(
        self, content: str, tool_calls: list[ToolCall] | None = None
    ) -> Message:
        """Add an assistant message."""
        return self.add_message(Role.ASSISTANT, content, tool_calls=tool_calls)

    def add_tool_result(self, tool_result: ToolResult) -> Message:
        """Add a tool result message."""
        return self.add_message(Role.TOOL, tool_result.result, tool_result=tool_result)

    def get_api_messages(self, include_system: bool = True) -> list[dict[str, Any]]:
        """Get messages in API format."""
        return [
            msg.to_api_format()
            for msg in self.messages
            if include_system or msg.role != Role.SYSTEM
        ]

    def set_mode(self, mode: Mode) -> None:
        """Change the current mode."""
        self.mode = mode

    def clear(self) -> None:
        """Clear conversation history."""
        self.messages.clear()

    @property
    def is_plan_mode(self) -> bool:
        """Check if in plan mode."""
        return self.mode == Mode.PLAN

    @property
    def is_act_mode(self) -> bool:
        """Check if in act mode."""
        return self.mode == Mode.ACT

    @property
    def is_bash_mode(self) -> bool:
        """Check if in bash mode."""
        return self.mode == Mode.BASH

    def to_dict(self) -> dict[str, Any]:
        """Serialize state to dict for checkpointing."""
        return {
            "mode": self.mode.value,
            "working_directory": self.working_directory,
            "model": self.model,
            "provider": self.provider,
            "messages": [
                {
                    "role": msg.role.value,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "tool_calls": [
                        {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                        for tc in msg.tool_calls
                    ] if msg.tool_calls else None,
                    "tool_result": {
                        "tool_call_id": msg.tool_result.tool_call_id,
                        "name": msg.tool_result.name,
                        "result": msg.tool_result.result,
                        "success": msg.tool_result.success,
                    } if msg.tool_result else None,
                }
                for msg in self.messages
            ],
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        """Restore state from dict."""
        if "mode" in data:
            self.mode = Mode(data["mode"])
        if "working_directory" in data:
            self.working_directory = data["working_directory"]
        if "model" in data:
            self.model = data["model"]
        if "provider" in data:
            self.provider = data["provider"]
        if "messages" in data:
            self.messages = []
            for msg_data in data["messages"]:
                tool_calls = None
                if msg_data.get("tool_calls"):
                    tool_calls = [
                        ToolCall(
                            id=tc["id"],
                            name=tc["name"],
                            arguments=tc["arguments"],
                        )
                        for tc in msg_data["tool_calls"]
                    ]
                tool_result = None
                if msg_data.get("tool_result"):
                    tr = msg_data["tool_result"]
                    tool_result = ToolResult(
                        tool_call_id=tr["tool_call_id"],
                        name=tr["name"],
                        result=tr["result"],
                        success=tr.get("success", True),
                    )
                self.messages.append(Message(
                    role=Role(msg_data["role"]),
                    content=msg_data["content"],
                    timestamp=datetime.fromisoformat(msg_data["timestamp"]) if msg_data.get("timestamp") else datetime.now(),
                    tool_calls=tool_calls,
                    tool_result=tool_result,
                ))
