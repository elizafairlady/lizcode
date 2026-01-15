"""Mock provider for integration tests."""

from __future__ import annotations

import json
from typing import Any


class MockProvider:
    """A mock provider that returns scripted responses.
    
    Used for testing agent workflow without calling real LLMs.
    """

    def __init__(self, responses: list[dict[str, Any]] | None = None):
        """Initialize with scripted responses.
        
        Each response should be a dict with:
        - content: str (text response)
        - tool_calls: list[dict] (optional tool calls)
        
        Responses are consumed in order.
        """
        self.responses = responses or []
        self.response_index = 0
        self.call_history: list[dict] = []
        self.name = "mock"
        self.model = "mock-model"

    async def chat(
        self,
        messages: list[dict],
        tools: list | None = None,
    ) -> dict[str, Any]:
        """Return the next scripted response."""
        # Record call
        self.call_history.append({
            "messages": messages,
            "tools": [t.name for t in (tools or [])],
        })

        if self.response_index >= len(self.responses):
            # Default: return empty response (ends conversation)
            return {"content": "", "tool_calls": []}

        response = self.responses[self.response_index]
        self.response_index += 1
        
        return response

    async def close(self) -> None:
        """No-op cleanup."""
        pass

    def add_response(
        self,
        content: str = "",
        tool_calls: list[dict] | None = None,
    ) -> MockProvider:
        """Add a response to the queue. Returns self for chaining."""
        response = {"content": content}
        if tool_calls:
            response["tool_calls"] = [
                {
                    "id": f"call_{len(self.responses)}_{i}",
                    "name": tc["name"],
                    "arguments": tc.get("arguments", {}),
                }
                for i, tc in enumerate(tool_calls)
            ]
        self.responses.append(response)
        return self

    def reset(self) -> None:
        """Reset for reuse."""
        self.response_index = 0
        self.call_history.clear()


def create_planning_provider() -> MockProvider:
    """Create a provider that simulates good planning behavior."""
    provider = MockProvider()
    
    # Response 1: Read a file to understand context
    provider.add_response(
        content="Let me explore the codebase first.",
        tool_calls=[{"name": "read_file", "arguments": {"file_path": "main.py"}}],
    )
    
    # Response 2: Create a plan
    provider.add_response(
        content="I'll create a plan for this task.",
        tool_calls=[{
            "name": "create_plan",
            "arguments": {
                "title": "Test Implementation Plan",
                "objective": "Implement the requested feature",
            },
        }],
    )
    
    # Response 3: Add steps to plan
    provider.add_response(
        content="Adding implementation steps.",
        tool_calls=[{
            "name": "update_plan",
            "arguments": {
                "action": "add_step",
                "content": "Step 1: Set up the foundation",
            },
        }],
    )
    
    # Response 4: Add more steps
    provider.add_response(
        content="",
        tool_calls=[{
            "name": "update_plan",
            "arguments": {
                "action": "add_step",
                "content": "Step 2: Implement core functionality",
            },
        }],
    )
    
    # Response 5: Finalize plan
    provider.add_response(
        content="The plan is ready for implementation.",
        tool_calls=[{
            "name": "finalize_plan",
            "arguments": {
                "summary": "Plan complete with 2 steps",
                "ready_to_implement": True,
            },
        }],
    )
    
    return provider


def create_act_mode_provider(task_ids: list[str]) -> MockProvider:
    """Create a provider that works through tasks properly.
    
    Args:
        task_ids: List of task IDs to work through
    """
    provider = MockProvider()
    
    for i, task_id in enumerate(task_ids):
        # Start task
        provider.add_response(
            content=f"Starting task {i+1}.",
            tool_calls=[{
                "name": "todo_write",
                "arguments": {"action": "start", "task_id": task_id},
            }],
        )
        
        # Do some work (mock file edit)
        provider.add_response(
            content="",
            tool_calls=[{
                "name": "write_file",
                "arguments": {
                    "file_path": f"output_{i}.txt",
                    "content": f"Task {i+1} output",
                },
            }],
        )
        
        # Complete task
        provider.add_response(
            content="Task completed.",
            tool_calls=[{
                "name": "todo_write",
                "arguments": {"action": "complete", "task_id": task_id},
            }],
        )
    
    # Final: attempt_completion
    provider.add_response(
        content="All tasks complete.",
        tool_calls=[{
            "name": "attempt_completion",
            "arguments": {
                "result": f"Completed all {len(task_ids)} tasks successfully.",
            },
        }],
    )
    
    return provider


def create_bad_act_provider() -> MockProvider:
    """Create a provider that demonstrates bad behavior (forgets tasks).
    
    This is useful for testing detection of bad patterns.
    """
    provider = MockProvider()
    
    # Just does random edits without tracking tasks
    for i in range(10):
        provider.add_response(
            content="Making some changes...",
            tool_calls=[{
                "name": "write_file",
                "arguments": {
                    "file_path": f"random_{i}.txt",
                    "content": "random content",
                },
            }],
        )
    
    return provider
