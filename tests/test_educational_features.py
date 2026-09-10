"""
tests/test_educational_features.py
───────────────────────────────────
Unit tests for ConceptMapTool, PythonScratchpadTool, and SocraticAgent.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.agent.tools.python_scratchpad import PythonScratchpadTool
from src.agent.tools.concept_map import ConceptMapTool
from src.agent.agents.socratic_agent import SocraticAgent


class TestPythonScratchpad:
    """Tests for PythonScratchpadTool."""

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        tool = PythonScratchpadTool()
        code = "print(123 + 456)"
        result = await tool.execute(code=code)
        assert "579" in result
        assert "Exit Code" in result or "رمز الخروج" in result

    @pytest.mark.asyncio
    async def test_error_handling(self):
        tool = PythonScratchpadTool()
        code = "raise ValueError('testing error')"
        result = await tool.execute(code=code)
        assert "ValueError" in result
        assert "testing error" in result

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        # Set a very short timeout of 0.2 seconds to speed up the test
        tool = PythonScratchpadTool(timeout_seconds=0.2)
        code = "import time\ntime.sleep(2)"
        result = await tool.execute(code=code)
        assert "timeout" in result.lower() or "انتهت مهلة التشغيل" in result


class TestConceptMap:
    """Tests for ConceptMapTool."""

    @pytest.mark.asyncio
    async def test_concept_map_generation(self):
        # Mock NLP controller and LLM generation client
        nlp_controller = MagicMock()
        nlp_controller.search_vector_db_collection = AsyncMock(return_value=[])

        generation_client = MagicMock()
        generation_client.generate_text = MagicMock(return_value="```mermaid\ngraph TD\n    A --> B\n```")

        project = MagicMock()

        tool = ConceptMapTool(
            nlp_controller=nlp_controller,
            project=project,
            generation_client=generation_client
        )

        result = await tool.execute(query="Artificial Intelligence", language="en")
        assert "graph TD" in result
        nlp_controller.search_vector_db_collection.assert_called_once()
        generation_client.generate_text.assert_called_once()


class TestSocraticAgent:
    """Tests for SocraticAgent."""

    @pytest.mark.asyncio
    async def test_socratic_agent_response(self):
        search_tool = MagicMock()
        search_tool.name = "knowledge_search"
        search_tool.execute = AsyncMock(return_value="Second Newton Law: F = ma")

        generation_client = MagicMock()
        generation_client.generate_text = MagicMock(return_value="What happens if acceleration is doubled?")

        agent = SocraticAgent(
            generation_client=generation_client,
            tools=[search_tool],
            language="en"
        )

        result = await agent.run(query="Explain second law of Newton")
        assert "What happens" in result.answer
        assert result.steps_count > 0
        search_tool.execute.assert_called_once()
        generation_client.generate_text.assert_called_once()
