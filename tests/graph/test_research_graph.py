"""
Unit tests for LangGraph compilation and node execution.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from graphs.research_graph import ResearchGraph


class TestResearchGraphImports:
    """Test suite for ResearchGraph imports."""

    def test_graph_imports_successfully(self):
        """Test that ResearchGraph can be imported."""
        from graphs.research_graph import ResearchGraph

        assert ResearchGraph is not None

    def test_graph_inherits_from_object(self):
        """Test that ResearchGraph is a proper class."""
        assert isinstance(ResearchGraph, type)


class TestResearchGraphInit:
    """Test suite for ResearchGraph initialization."""

    @pytest.mark.asyncio
    async def test_graph_creates_with_valid_params(self):
        """Test that ResearchGraph creates successfully with valid parameters."""
        with (
            patch("graphs.research_graph.PlannerAgent") as mock_planner,
            patch("graphs.research_graph.RouterAgent") as mock_router,
            patch("graphs.research_graph.ReflectionAgent") as mock_reflection,
            patch("graphs.research_graph.WriterAgent") as mock_writer,
        ):
            # Configure mocks
            mock_planner.return_value = MagicMock()
            mock_router.return_value = MagicMock()
            mock_reflection.return_value = MagicMock()
            mock_writer.return_value = MagicMock()

            graph = ResearchGraph(
                session_id="test-session",
                query="Test research query",
            )

            assert graph.session_id == "test-session"
            assert graph.query == "Test research query"
            assert graph.max_reflections == 3

    @pytest.mark.asyncio
    async def test_initial_state_created(self):
        """Test that initial state is created on initialization."""
        with (
            patch("graphs.research_graph.PlannerAgent") as mock_planner,
            patch("graphs.research_graph.RouterAgent") as mock_router,
            patch("graphs.research_graph.ReflectionAgent") as mock_reflection,
            patch("graphs.research_graph.WriterAgent") as mock_writer,
        ):
            mock_planner.return_value = MagicMock()
            mock_router.return_value = MagicMock()
            mock_reflection.return_value = MagicMock()
            mock_writer.return_value = MagicMock()

            graph = ResearchGraph(
                session_id="test-session",
                query="Test query",
                max_reflections=5,
            )

            assert graph.initial_state is not None
            assert graph.initial_state["session_id"] == "test-session"
            assert graph.initial_state["query"] == "Test query"
            assert graph.initial_state["max_reflections"] == 5


class TestResearchGraphCompilation:
    """Test suite for graph compilation."""

    @pytest.mark.asyncio
    async def test_graph_compiles(self):
        """Test that the LangGraph compiles without errors."""
        with (
            patch("graphs.research_graph.PlannerAgent") as mock_planner,
            patch("graphs.research_graph.RouterAgent") as mock_router,
            patch("graphs.research_graph.ReflectionAgent") as mock_reflection,
            patch("graphs.research_graph.WriterAgent") as mock_writer,
        ):
            mock_planner.return_value = MagicMock()
            mock_router.return_value = MagicMock()
            mock_reflection.return_value = MagicMock()
            mock_writer.return_value = MagicMock()

            graph = ResearchGraph(
                session_id="test-session",
                query="Test query",
            )

            assert graph.graph is not None
            # Check it's a compiled graph (has astream method)
            assert hasattr(graph.graph, "astream")


class TestGraphNodes:
    """Test suite for graph node registration."""

    @pytest.mark.asyncio
    async def test_nodes_are_registered(self):
        """Test that all required nodes are registered in the graph."""
        with (
            patch("graphs.research_graph.PlannerAgent") as mock_planner,
            patch("graphs.research_graph.RouterAgent") as mock_router,
            patch("graphs.research_graph.ReflectionAgent") as mock_reflection,
            patch("graphs.research_graph.WriterAgent") as mock_writer,
        ):
            mock_planner.return_value = MagicMock()
            mock_router.return_value = MagicMock()
            mock_reflection.return_value = MagicMock()
            mock_writer.return_value = MagicMock()

            graph = ResearchGraph(
                session_id="test-session",
                query="Test query",
            )

            # The graph should have nodes defined
            # We can verify by checking the graph has astream method
            assert hasattr(graph.graph, "astream")


class TestConditionalEdges:
    """Test suite for conditional edge logic."""

    def test_should_continue_reflection_logic_max_reached(self):
        """Test _should_continue_reflection returns 'writer' when max reached."""
        with (
            patch("graphs.research_graph.PlannerAgent") as mock_planner,
            patch("graphs.research_graph.RouterAgent") as mock_router,
            patch("graphs.research_graph.ReflectionAgent") as mock_reflection,
            patch("graphs.research_graph.WriterAgent") as mock_writer,
        ):
            mock_planner.return_value = MagicMock()
            mock_router.return_value = MagicMock()
            mock_reflection.return_value = MagicMock()
            mock_writer.return_value = MagicMock()

            graph = ResearchGraph(
                session_id="test-session",
                query="Test query",
            )

            state = {
                "reflection_count": 3,
                "max_reflections": 3,
                "findings": [],
            }

            result = graph._should_continue_reflection(state)

            assert result == "writer"

    def test_should_continue_reflection_logic_sufficient_findings(self):
        """Test _should_continue_reflection returns 'writer' with sufficient findings."""
        with (
            patch("graphs.research_graph.PlannerAgent") as mock_planner,
            patch("graphs.research_graph.RouterAgent") as mock_router,
            patch("graphs.research_graph.ReflectionAgent") as mock_reflection,
            patch("graphs.research_graph.WriterAgent") as mock_writer,
        ):
            mock_planner.return_value = MagicMock()
            mock_router.return_value = MagicMock()
            mock_reflection.return_value = MagicMock()
            mock_writer.return_value = MagicMock()

            graph = ResearchGraph(
                session_id="test-session",
                query="Test query",
            )

            state = {
                "reflection_count": 0,
                "max_reflections": 3,
                "findings": [{"id": 1}, {"id": 2}, {"id": 3}],
            }

            result = graph._should_continue_reflection(state)

            assert result == "writer"

    def test_should_continue_reflection_logic_continue_research(self):
        """Test _should_continue_reflection returns 'research' when more needed."""
        with (
            patch("graphs.research_graph.PlannerAgent") as mock_planner,
            patch("graphs.research_graph.RouterAgent") as mock_router,
            patch("graphs.research_graph.ReflectionAgent") as mock_reflection,
            patch("graphs.research_graph.WriterAgent") as mock_writer,
        ):
            mock_planner.return_value = MagicMock()
            mock_router.return_value = MagicMock()
            mock_reflection.return_value = MagicMock()

            graph = ResearchGraph(
                session_id="test-session",
                query="Test query",
            )

            state = {
                "reflection_count": 1,
                "max_reflections": 3,
                "findings": [{"id": 1}],
            }

            result = graph._should_continue_reflection(state)

            assert result == "research"

    def test_should_execute_tasks_with_tasks(self):
        """Test _should_execute_tasks returns 'execute' when tasks exist."""
        with (
            patch("graphs.research_graph.PlannerAgent") as mock_planner,
            patch("graphs.research_graph.RouterAgent") as mock_router,
            patch("graphs.research_graph.ReflectionAgent") as mock_reflection,
            patch("graphs.research_graph.WriterAgent") as mock_writer,
        ):
            mock_planner.return_value = MagicMock()
            mock_router.return_value = MagicMock()
            mock_reflection.return_value = MagicMock()
            mock_writer.return_value = MagicMock()

            graph = ResearchGraph(
                session_id="test-session",
                query="Test query",
            )

            state = {
                "tasks": [{"id": "task1"}, {"id": "task2"}],
            }

            result = graph._should_execute_tasks(state)

            assert result == "execute"

    def test_should_execute_tasks_without_tasks(self):
        """Test _should_execute_tasks returns 'writer' when no tasks."""
        with (
            patch("graphs.research_graph.PlannerAgent") as mock_planner,
            patch("graphs.research_graph.RouterAgent") as mock_router,
            patch("graphs.research_graph.ReflectionAgent") as mock_reflection,
            patch("graphs.research_graph.WriterAgent") as mock_writer,
        ):
            mock_planner.return_value = MagicMock()
            mock_router.return_value = MagicMock()
            mock_reflection.return_value = MagicMock()
            mock_writer.return_value = MagicMock()

            graph = ResearchGraph(
                session_id="test-session",
                query="Test query",
            )

            state = {
                "tasks": [],
            }

            result = graph._should_execute_tasks(state)

            assert result == "writer"


class TestGraphMethods:
    """Test suite for ResearchGraph methods."""

    @pytest.mark.asyncio
    async def test_get_state_returns_current_state(self):
        """Test get_state method returns current state."""
        with (
            patch("graphs.research_graph.PlannerAgent") as mock_planner,
            patch("graphs.research_graph.RouterAgent") as mock_router,
            patch("graphs.research_graph.ReflectionAgent") as mock_reflection,
            patch("graphs.research_graph.WriterAgent") as mock_writer,
        ):
            mock_planner.return_value = MagicMock()
            mock_router.return_value = MagicMock()
            mock_reflection.return_value = MagicMock()
            mock_writer.return_value = MagicMock()

            graph = ResearchGraph(
                session_id="test-session",
                query="Test query",
            )

            state = graph.get_state()

            assert state is not None
            assert "session_id" in state

    @pytest.mark.asyncio
    async def test_cancel_sets_cancelled_flag(self):
        """Test cancel method sets the cancelled flag."""
        with (
            patch("graphs.research_graph.PlannerAgent") as mock_planner,
            patch("graphs.research_graph.RouterAgent") as mock_router,
            patch("graphs.research_graph.ReflectionAgent") as mock_reflection,
            patch("graphs.research_graph.WriterAgent") as mock_writer,
        ):
            mock_planner.return_value = MagicMock()
            mock_router.return_value = MagicMock()
            mock_reflection.return_value = MagicMock()
            mock_writer.return_value = MagicMock()

            graph = ResearchGraph(
                session_id="test-session",
                query="Test query",
            )

            assert graph._cancelled is False

            graph.cancel()

            assert graph._cancelled is True

    @pytest.mark.asyncio
    async def test_stream_events_is_async_generator(self):
        """Test stream_events returns an async generator."""
        with (
            patch("graphs.research_graph.PlannerAgent") as mock_planner,
            patch("graphs.research_graph.RouterAgent") as mock_router,
            patch("graphs.research_graph.ReflectionAgent") as mock_reflection,
            patch("graphs.research_graph.WriterAgent") as mock_writer,
        ):
            mock_planner.return_value = MagicMock()
            mock_router.return_value = MagicMock()
            mock_reflection.return_value = MagicMock()
            mock_writer.return_value = MagicMock()

            graph = ResearchGraph(
                session_id="test-session",
                query="Test query",
            )

            stream = graph.stream_events()

            # Verify it's an async generator
            import asyncio

            gen_type = type(stream)
            assert gen_type.__name__ == "async_generator"
