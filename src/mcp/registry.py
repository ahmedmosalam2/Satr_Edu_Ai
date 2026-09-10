"""
src/mcp/registry.py
────────────────────
MCP Tool Registry — Auto-discovery لكل الـ tools.

كل tool بتورّث من MCPTool وبتتسجل تلقائياً هنا.
الـ agent بيسأل الـ registry: "ايه الـ tools المتاحة؟"
وبيختار التي يحتاجها بناءً على الـ intent.

مثال إضافة tool جديدة:

    # src/mcp/tools/weather_tool.py
    class WeatherTool(MCPTool):
        name = "weather"
        description = "بيجيب الطقس الحالي لأي مدينة"
        input_schema = {"city": "string"}

        async def execute(self, city: str) -> str:
            ...
            return f"الطقس في {city}: ☀️ 28 درجة"

    # بعدها تلقائياً بيظهر في GET /mcp/tools
"""

import logging
import importlib
import pkgutil
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger("uvicorn.error")


# ── MCPTool Base ──────────────────────────────────────────────────────────────

class MCPTool(ABC):
    """
    Abstract base لكل MCP Tools.

    كل tool لازم تعرّف:
      - name        : اسم فريد
      - description : وصف للـ LLM يفهم من وين يستخدمه
      - input_schema: الـ parameters المطلوبة
      - execute()   : التنفيذ الفعلي
    """

    name: str = ""
    description: str = ""
    input_schema: Dict[str, str] = {}   # {"param_name": "type (str/int/bool)"}
    category: str = "general"          # "knowledge" | "calculation" | "student" | "general"
    requires_auth: bool = False

    def to_manifest(self) -> dict:
        """بيانات الـ tool للـ LLM."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "category": self.category,
        }

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """تنفيذ الـ tool."""
        ...


# ── MCP Registry ──────────────────────────────────────────────────────────────

class MCPRegistry:
    """
    Registry لكل الـ MCP Tools.
    Singleton — instance واحد في الـ app.
    """

    _instance: Optional["MCPRegistry"] = None

    def __init__(self):
        self._tools: Dict[str, MCPTool] = {}

    @classmethod
    def get_instance(cls) -> "MCPRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, tool: MCPTool) -> None:
        """سجّل tool جديد."""
        if not tool.name:
            raise ValueError(f"Tool {type(tool).__name__} must have a non-empty name")
        self._tools[tool.name] = tool
        logger.info(f"[MCPRegistry] Registered tool: {tool.name}")

    def get(self, name: str) -> Optional[MCPTool]:
        """جيب tool بالاسم."""
        return self._tools.get(name)

    def list_all(self) -> List[dict]:
        """قائمة كل الـ tools المتاحة."""
        return [t.to_manifest() for t in self._tools.values()]

    def list_by_category(self, category: str) -> List[MCPTool]:
        """جيب كل الـ tools من نوع معين."""
        return [t for t in self._tools.values() if t.category == category]

    async def execute(self, tool_name: str, **kwargs) -> Any:
        """تنفيذ tool باسمه."""
        tool = self.get(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found in MCP Registry")
        return await tool.execute(**kwargs)

    def auto_discover(self, package_path: str = "src.mcp.tools") -> int:
        """
        Auto-discovery: بيشوف كل الـ classes في src/mcp/tools/
        اللي بتورّث من MCPTool وبيسجلهم تلقائياً.
        """
        discovered = 0
        try:
            package = importlib.import_module(package_path)
            package_dir = package.__path__

            for _, module_name, _ in pkgutil.iter_modules(package_dir):
                try:
                    module = importlib.import_module(f"{package_path}.{module_name}")
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (
                            isinstance(attr, type)
                            and issubclass(attr, MCPTool)
                            and attr is not MCPTool
                            and attr.name  # لازم يكون عنده name
                        ):
                            instance = attr()
                            self.register(instance)
                            discovered += 1
                except Exception as e:
                    logger.warning(f"[MCPRegistry] Failed to load {module_name}: {e}")

        except Exception as e:
            logger.error(f"[MCPRegistry] Auto-discovery failed: {e}")

        logger.info(f"[MCPRegistry] Auto-discovered {discovered} tools")
        return discovered


# ── Global Registry Instance ──────────────────────────────────────────────────

mcp_registry = MCPRegistry.get_instance()
