from enum import StrEnum
class IntentType(StrEnum):
  CONVERSATION = "conversation"
  QUESTION = "question"
  GOAL = "goal"
  INSTRUCTION = "instruction"
  UNCLEAR = "unclear"
  
