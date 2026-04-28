"""
src/agent/base_agent.py
───────────────────────
Base Agent — Abstract interface for all agents.

Agent = LLM + Tools + Memory
بيقدر يفكر في خطوات متعددة ويستخدم أدوات.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class AgentAction:
    """فعل اتخذه الـ agent."""
    tool_name: str
    tool_input: Dict[str, Any]
    tool_output: str = ""
    reasoning: str = ""


@dataclass
class AgentResult:
    """نتيجة تنفيذ الـ agent."""
    answer: str
    actions: List[AgentAction] = field(default_factory=list)
    sources: List[Dict] = field(default_factory=list)
    steps_count: int = 0
    total_tokens: int = 0

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "actions": [
                {
                    "tool": a.tool_name,
                    "input": a.tool_input,
                    "output": a.tool_output[:200],
                    "reasoning": a.reasoning,
                }
                for a in self.actions
            ],
            "sources": self.sources,
            "steps_count": self.steps_count,
        }


class BaseTool(ABC):
    """Abstract base for agent tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        ...


class BaseAgent(ABC):
    """Abstract base for agents."""

    @abstractmethod
    async def run(self, query: str, **kwargs) -> AgentResult:
        ...
