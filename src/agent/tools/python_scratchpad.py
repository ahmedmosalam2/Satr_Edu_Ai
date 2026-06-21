"""
src/agent/tools/python_scratchpad.py
──────────────────────────────────────
Python Scratchpad Tool — لتشغيل وتجربة كود بايثون بأمان في بيئة معزولة (Subprocess) مع حد أقصى للوقت.
"""

import sys
import subprocess
import logging
import time
from typing import Dict, Any
from src.agent.base_agent import BaseTool

logger = logging.getLogger("uvicorn.error")


class PythonScratchpadTool(BaseTool):
    """
    Python Scratchpad Tool.
    يأخذ كود بايثون، ينفذه في subprocess، ويرجع الناتج أو الأخطاء.
    """

    def __init__(self, timeout_seconds: float = 3.0):
        self.timeout_seconds = timeout_seconds

    @property
    def name(self) -> str:
        return "python_scratchpad"

    @property
    def description(self) -> str:
        return (
            "Safely runs a Python code snippet and returns stdout, stderr, and execution time. "
            "Input: python code string."
        )

    async def execute(self, code: str = "", **kwargs) -> str:
        if not code:
            return "Error: No code provided to run."

        # Clean command prefixes if called directly from agent query
        prefixes = [
            "شغل الكود:", "شغل الكود", "شغل كود:", "شغل كود",
            "نفذ الكود:", "نفذ الكود", "نفذ كود:", "نفذ كود",
            "run python:", "run python", "run code:", "run code",
            "run:", "execute:", "compile:"
        ]
        code_trimmed = code.strip()
        code_lower = code_trimmed.lower()
        for prefix in prefixes:
            if code_lower.startswith(prefix):
                code = code_trimmed[len(prefix):].strip()
                if code.startswith(":"):
                    code = code[1:].strip()
                break

        # Clean/sanitize code block markup if LLM sent it wrapped in ```python ... ```
        if "```" in code:
            lines = code.splitlines()
            cleaned_lines = []
            in_block = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_block = not in_block
                    # If it's a python block identifier like ```python, strip it
                    continue
                cleaned_lines.append(line)
            code = "\n".join(cleaned_lines)

        logger.info(f"[PythonScratchpad] Executing code (len={len(code)})...")
        
        start_time = time.perf_counter()
        try:
            # Execute python snippet via subprocess with UTF-8 env
            import os
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            process = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout_seconds,
                env=env,
            )
            elapsed = time.perf_counter() - start_time

            stdout = process.stdout.strip()
            stderr = process.stderr.strip()
            exit_code = process.returncode

            result_parts = []
            result_parts.append(f"Execution Time: {elapsed:.3f} seconds")
            result_parts.append(f"Exit Code: {exit_code}")

            if stdout:
                result_parts.append(f"\nStdout:\n{stdout}")
            if stderr:
                result_parts.append(f"\nStderr:\n{stderr}")
            if not stdout and not stderr:
                result_parts.append("\nCode executed successfully with no output.")

            return "\n".join(result_parts)

        except subprocess.TimeoutExpired:
            return f"Error: Execution timeout ({self.timeout_seconds} seconds). Possible infinite loop?"
        except Exception as e:
            logger.error(f"[PythonScratchpad] Error executing code: {e}")
            return f"Error executing code: {str(e)}"
