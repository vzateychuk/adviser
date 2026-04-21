import re

from llm.protocol import LLMClient
from llm.types import ChatRequest, Message
from flows.pec.models import PlanResult

_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json(text: str) -> str:
    m = _FENCED_JSON_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


class Planner:
  """
    Planner v0.

    Responsibility:
    - Convert user request -> structured PlanResult
    - Call LLM
    - Validate + parse JSON output

    No orchestration logic.
    No routing.
    No persistence.
  """

  def __init__(
        self,
        *,
        llm: LLMClient,
        prompt: str,
  ):
        self.llm = llm
        self.prompt = prompt


  async def plan(self, user_request: str) -> PlanResult:
    """
    Calls LLM and parses structured PlanResult.
    """

    resp = await self.llm.chat(
      ChatRequest(
        messages=[
          Message(role="system", content=self.prompt),
          Message(role="user", content=user_request),
        ],
      )
    )

    # Strip markdown fences if model wrapped JSON in code block
    json_text = _extract_json(resp.text)
    return PlanResult.model_validate_json(json_text)
