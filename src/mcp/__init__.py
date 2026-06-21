"""
src/mcp/__init__.py
───────────────────
MCP (Model Context Protocol) Layer.

هذا الـ layer بيخلي إضافة tools/resources جديدة سهلة جداً:
  1. أنشئ ملف في src/mcp/tools/
  2. اورّث من MCPTool
  3. بيتسجل تلقائياً في MCPRegistry

بدون ما تعدل أي agent أو route!
"""

from src.mcp.registry import MCPRegistry

__all__ = ["MCPRegistry"]
