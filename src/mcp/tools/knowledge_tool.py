"""
src/mcp/tools/knowledge_tool.py
────────────────────────────────
MCP Wrapper لـ KnowledgeSearchTool الموجود.

هذا الملف بيعرض الـ KnowledgeSearch كـ MCP Tool
عشان الـ MCP Server يقدر يستخدمه.
"""

from src.mcp.registry import MCPTool


class KnowledgeMCPTool(MCPTool):
    """بحث في قاعدة المعرفة التعليمية."""

    name = "knowledge_search"
    description = (
        "يبحث في المحتوى التعليمي للمشروع عن إجابات للأسئلة. "
        "استخدمه لأي سؤال يحتاج معلومات من المواد الدراسية."
    )
    input_schema = {
        "query": "string — السؤال أو الكلمات المفتاحية للبحث",
        "limit": "int (optional) — عدد النتائج، افتراضي 5",
    }
    category = "knowledge"

    def __init__(self, nlp_controller=None, project=None):
        self._nlp_controller = nlp_controller
        self._project = project
        self._inner_tool = None

    def set_context(self, nlp_controller, project):
        """ضبط الـ context (بيتعمل بعد التسجيل في الـ registry)."""
        from src.agent.tools.knowledge_search import KnowledgeSearchTool
        self._nlp_controller = nlp_controller
        self._project = project
        self._inner_tool = KnowledgeSearchTool(
            nlp_controller=nlp_controller,
            project=project,
        )

    async def execute(self, query: str, limit: int = 5) -> str:
        if not self._inner_tool:
            return "Knowledge search not configured for this request."
        return await self._inner_tool.execute(query=query, limit=limit)


class CalculatorMCPTool(MCPTool):
    """حاسبة رياضية للتعبيرات الحسابية."""

    name = "calculator"
    description = "يحسب التعبيرات الرياضية. استخدمه لأي سؤال يحتاج حساب."
    input_schema = {
        "expression": "string — التعبير الرياضي مثل '2 + 2' أو '(5 * 3) / 2'"
    }
    category = "calculation"

    async def execute(self, expression: str) -> str:
        from src.agent.tools.calculator import CalculatorTool
        tool = CalculatorTool()
        return await tool.execute(expression=expression)
