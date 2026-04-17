from __future__ import annotations

import json

from llm.types import ChatRequest, ChatResponse


class MockLLMClient:
    async def chat(self, req: ChatRequest) -> ChatResponse:
        role = (req.meta or {}).get("role")

        if role == "planner":
            payload = {
                "goal": "Mock plan",
                "assumptions": [],
                "steps": [
                    {
                        "id": 1,
                        "title": "Mock step",
                        "type": "generic",
                        "input": "mock input",
                        "output": "mock output",
                        "success_criteria": ["mock criterion"],
                    }
                ],
            }
            return ChatResponse(text=json.dumps(payload))

        if role == "critic":
            payload = {
                "approved": True,
                "issues": [],
                "summary": "Mock approved",
            }
            return ChatResponse(text=json.dumps(payload))

        last_user = ""
        for m in reversed(req.messages):
            if m.role == "user":
                last_user = m.content
                break

        return ChatResponse(text=f"[MOCK] {last_user}")