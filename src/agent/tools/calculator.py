
import logging
import math
from src.agent.base_agent import BaseTool

logger = logging.getLogger("uvicorn.error")

# Safe math functions allowed in eval
SAFE_MATH = {
    "abs": abs, "round": round, "min": min, "max": max,
    "sum": sum, "pow": pow, "int": int, "float": float,
    "sqrt": math.sqrt, "pi": math.pi, "e": math.e,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log10": math.log10, "log2": math.log2,
    "ceil": math.ceil, "floor": math.floor,
    "factorial": math.factorial,
}


class CalculatorTool(BaseTool):
    """حل تعبيرات رياضية بأمان."""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return (
            "Evaluate a mathematical expression. "
            "Input: a math expression like '2 + 3 * 4' or 'sqrt(16)'. "
            "Supports: +, -, *, /, **, sqrt, sin, cos, tan, log, pi, e, factorial."
        )

    async def execute(self, expression: str = "", **kwargs) -> str:
        if not expression:
            return "Error: No expression provided"

        try:
            # Sanitize — only allow safe characters
            allowed_chars = set("0123456789+-*/().,%^ ")
            allowed_words = set(SAFE_MATH.keys())

            # Replace ^ with ** for power
            expression = expression.replace("^", "**")

            # Evaluate safely
            result = eval(expression, {"__builtins__": {}}, SAFE_MATH)
            return f"{expression} = {result}"

        except ZeroDivisionError:
            return "Error: Division by zero"
        except Exception as e:
            return f"Error: Could not evaluate '{expression}' — {str(e)}"
