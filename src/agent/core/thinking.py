"""
src/agent/core/thinking.py
──────────────────────────
ReAct Thinking Protocol — كل agent بيفكر بنفس البنية.

Think → Plan → Act → Observe → Reflect → (loop or finish)

ده قلب النظام — اللي بيخلي الـ LLM يقرر بنفسه
بدل ما يكون الكود هو اللي بيقرر.
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("uvicorn.error")


@dataclass
class ThoughtStep:
    """خطوة تفكير واحدة."""
    step_type: str  # think | plan | act | observe | reflect | finish
    content: str
    tool_name: str = ""
    tool_input: Dict[str, Any] = field(default_factory=dict)
    tool_output: str = ""


@dataclass
class ThinkingTrace:
    """تسلسل التفكير الكامل."""
    steps: List[ThoughtStep] = field(default_factory=list)
    final_answer: str = ""
    agent_name: str = ""
    total_tokens: int = 0

    def add(self, step_type: str, content: str, **kwargs):
        self.steps.append(ThoughtStep(step_type=step_type, content=content, **kwargs))

    def to_dict(self) -> list:
        return [
            {
                "step": i + 1,
                "type": s.step_type,
                "content": s.content,
                "tool": s.tool_name or None,
                "tool_output": s.tool_output[:200] if s.tool_output else None,
            }
            for i, s in enumerate(self.steps)
        ]


# ── ReAct Prompt Templates ────────────────────────────────────────────────────

REACT_SYSTEM_AR = """أنت {agent_role}. اسمك {agent_name}.

لديك الأدوات التالية:
{tools_desc}

استخدم هذا التنسيق بالضبط:

Thought: [فكّر في ما تحتاج أن تفعله]
Action: [اسم_الأداة]
Action Input: {{"key": "value"}}
Observation: [سيتم ملء هذا تلقائياً بنتيجة الأداة]
... (كرر Thought/Action/Observation حسب الحاجة)
Thought: لديّ الآن إجابة كافية
Final Answer: [إجابتك النهائية]

قواعد مهمة:
- فكّر دائماً قبل أي إجراء
- إذا لم تحتاج أداة، اذهب مباشرة لـ Final Answer
- لا تخترع معلومات — استخدم الأدوات فقط
- الحد الأقصى: {max_steps} خطوات

السؤال: {query}"""

REACT_SYSTEM_EN = """You are {agent_role}. Your name is {agent_name}.

You have the following tools:
{tools_desc}

Use this EXACT format:

Thought: [think about what you need to do]
Action: [tool_name]
Action Input: {{"key": "value"}}
Observation: [will be filled with tool result]
... (repeat Thought/Action/Observation as needed)
Thought: I now have a sufficient answer
Final Answer: [your final answer]

Rules:
- Always think before acting
- If no tool is needed, go directly to Final Answer
- Never make up information — use tools only
- Maximum: {max_steps} steps

Question: {query}"""


def build_react_prompt(
    agent_name: str,
    agent_role: str,
    tools: dict,
    query: str,
    language: str = "ar",
    max_steps: int = 5,
    context: str = "",
) -> str:
    """Build the ReAct prompt for an agent."""
    tools_desc = "\n".join([
        f"- {name}: {tool.description}"
        for name, tool in tools.items()
    ])

    template = REACT_SYSTEM_AR if language == "ar" else REACT_SYSTEM_EN

    prompt = template.format(
        agent_name=agent_name,
        agent_role=agent_role,
        tools_desc=tools_desc,
        query=query,
        max_steps=max_steps,
    )

    if context:
        prompt += f"\n\nسياق إضافي:\n{context}"

    return prompt


def parse_react_output(output: str) -> List[Dict[str, str]]:
    """
    Parse LLM ReAct output into structured steps.

    Returns list of dicts with keys: type, content, tool, input
    """
    steps = []
    lines = output.strip().split("\n")

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        if line.startswith("Thought:"):
            steps.append({
                "type": "think",
                "content": line[len("Thought:"):].strip(),
            })

        elif line.startswith("Action:"):
            tool_name = line[len("Action:"):].strip()

            # Next line should be Action Input
            action_input = {}
            if i + 1 < len(lines) and lines[i + 1].strip().startswith("Action Input:"):
                i += 1
                raw_input = lines[i][len("Action Input:"):].strip()
                try:
                    action_input = json.loads(raw_input)
                except json.JSONDecodeError:
                    action_input = {"raw": raw_input}

            steps.append({
                "type": "act",
                "content": f"Using tool: {tool_name}",
                "tool": tool_name,
                "input": action_input,
            })

        elif line.startswith("Observation:"):
            steps.append({
                "type": "observe",
                "content": line[len("Observation:"):].strip(),
            })

        elif line.startswith("Final Answer:"):
            # Collect all remaining lines as the answer
            answer_lines = [line[len("Final Answer:"):].strip()]
            for j in range(i + 1, len(lines)):
                answer_lines.append(lines[j])
            steps.append({
                "type": "finish",
                "content": "\n".join(answer_lines).strip(),
            })
            break

        i += 1

    return steps
