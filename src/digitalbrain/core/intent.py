from dataclasses import dataclass
from enum import StrEnum


class IntentType(StrEnum):
  CONVERSATION = "conversation"
  QUESTION = "question"
  GOAL = "goal"
  INSTRUCTION = "instruction"
  UNCLEAR = "unclear"
  
@dataclass(frozen=True, slots=True)
class IntentResult:
  intent: IntentType
  confidence: float
  needs_clarification: bool
  explanation: str
