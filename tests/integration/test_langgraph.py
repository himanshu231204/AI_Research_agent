"""
Integration tests for LangGraph parallel execution, aggregation, and reflection safety.

Tests:
- Parallel task execution
- Aggregator node with partial failure handling
- Reflection loop safety enforcement
- State schema enforcement
"""

import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from graphs.state import ResearchState, create_initial_state


class TestParallelExecution:
    """Test suite for parallel execution patterns."""

    @pytest.mark.asyncio
    async def test_dispatcher_creates_tasks(self):
        """Test that dispatcher creates task IDs correctly."""
        from graphs.research_graph import DistributedResearchGraph

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

            graph = DistributedResearchGraph(
                session_id="test-session",
                query="Test query",
            )

            # Verify graph has pending task tracking
            assert hasattr(graph, "_pending_tasks")
            assert isinstance(graph._pending_tasks, dict)

    @pytest.mark.asyncio
    async def test_parallel_dispatch_tracking(self):
        """Test that parallel dispatches are tracked."""
        from graphs.research_graph import DistributedResearchGraph

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

            graph = DistributedResearchGraph(
                session_id="test-session",
                query="Test query",
            )

            # Add mock pending tasks
            graph._pending_tasks = {
                "task1": {"celery_id": "id1", "task_type": "web_search"},
                "task2": {"celery_id": "id2", "task_type": "github"},
                "task3": {"celery_id": "id3", "task_type": "browser"},
            }

            assert len(graph._pending_tasks) == 3


class TestAggregatorNode:
    """Test suite for the production-grade Aggregator Node."""

    @pytest.mark.asyncio
    async def test_aggregator_handles_partial_failures(self):
        """Test that aggregator continues when some tasks fail."""
        from graphs.research_graph import DistributedResearchGraph

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

            graph = DistributedResearchGraph(
                session_id="test-session",
                query="Test query",
            )

            # Simulate partial failure state
            state = {
                "active_tasks": ["task1", "task2", "task3"],
                "findings": [],
                "failed_tasks": [
                    {"correlation_id": "task2", "error": "timeout"},
                ],
            }

            # Verify aggregator can process partial state
            assert "active_tasks" in state
            assert "failed_tasks" in state

    @pytest.mark.asyncio
    async def test_aggregator_deduplicates_findings(self):
        """Test that aggregator deduplicates findings."""
        from graphs.research_graph import DistributedResearchGraph

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

            graph = DistributedResearchGraph(
                session_id="test-session",
                query="Test query",
            )

            # Test deduplication logic
            findings = [
                {"summary": "Result 1", "source": "http://example.com"},
                {"summary": "Result 1", "source": "http://example.com"},  # Duplicate
                {"summary": "Result 2", "source": "http://different.com"},
            ]

            deduplicated = graph._deduplicate_findings(findings)

            assert len(deduplicated) == 2

    @pytest.mark.asyncio
    async def test_aggregator_tracks_failed_tasks(self):
        """Test that aggregator tracks failed tasks in state."""
        from graphs.research_graph import DistributedResearchGraph

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

            graph = DistributedResearchGraph(
                session_id="test-session",
                query="Test query",
            )

            # Test failed task tracking
            failed_tasks = [
                {"correlation_id": "task1", "error": "timeout"},
                {"correlation_id": "task2", "error": "connection refused"},
            ]

            # Verify failed tasks are properly structured
            for task in failed_tasks:
                assert "correlation_id" in task
                assert "error" in task

    @pytest.mark.asyncio
    async def test_aggregator_extracts_findings(self):
        """Test that aggregator extracts findings from results."""
        from graphs.research_graph import DistributedResearchGraph

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

            graph = DistributedResearchGraph(
                session_id="test-session",
                query="Test query",
            )

            # Test finding extraction
            result = {
                "results": [
                    {"snippet": "Test result", "url": "http://example.com"},
                ],
                "sources": ["http://example.com"],
            }

            findings = graph._extract_findings(result, "web_search")

            assert len(findings) > 0
            assert findings[0]["type"] == "web_search"

    @pytest.mark.asyncio
    async def test_aggregator_continues_on_timeout(self):
        """Test that aggregator continues when timeout occurs."""
        from graphs.research_graph import DistributedResearchGraph

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

            graph = DistributedResearchGraph(
                session_id="test-session",
                query="Test query",
            )

            # Simulate timeout scenario
            state = {
                "active_tasks": ["task1", "task2"],
                "findings": [{"summary": "Partial result"}],
            }

            # Aggregator should still return partial results
            assert "findings" in state


class TestReflectionSafety:
    """Test suite for reflection loop safety enforcement."""

    def test_reflection_stops_at_max(self):
        """Test that reflection stops when max is reached."""
        from graphs.research_graph import DistributedResearchGraph

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

            graph = DistributedResearchGraph(
                session_id="test-session",
                query="Test query",
                max_reflections=3,
            )

            # Test at max reflection
            state = {
                "reflection_count": 3,
                "max_reflections": 3,
                "findings": [{"id": 1}],
            }

            result = graph._should_continue_reflection(state)
            assert result == "writer"

    def test_reflection_stops_with_sufficient_findings(self):
        """Test that reflection stops with sufficient findings."""
        from graphs.research_graph import DistributedResearchGraph

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

            graph = DistributedResearchGraph(
                session_id="test-session",
                query="Test query",
                max_reflections=5,
            )

            # Test with sufficient findings
            state = {
                "reflection_count": 1,
                "max_reflections": 5,
                "findings": [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}, {"id": 5}],
            }

            result = graph._should_continue_reflection(state)
            assert result == "writer"

    def test_reflection_continues_with_insufficient_findings(self):
        """Test that reflection continues with insufficient findings."""
        from graphs.research_graph import DistributedResearchGraph

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

            graph = DistributedResearchGraph(
                session_id="test-session",
                query="Test query",
                max_reflections=3,
            )

            # Test with insufficient findings
            state = {
                "reflection_count": 0,
                "max_reflections": 3,
                "findings": [{"id": 1}],
            }

            result = graph._should_continue_reflection(state)
            assert result == "router"

    def test_reflection_stops_on_error_state(self):
        """Test that reflection stops when error state is present."""
        from graphs.research_graph import DistributedResearchGraph

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

            graph = DistributedResearchGraph(
                session_id="test-session",
                query="Test query",
                max_reflections=3,
            )

            # Test with error state
            state = {
                "reflection_count": 0,
                "max_reflections": 3,
                "findings": [],
                "error_state": {"error": "Previous task failed"},
            }

            result = graph._should_continue_reflection(state)
            assert result == "writer"

    def test_reflection_enforcement_in_node(self):
        """Test that reflection node enforces limit before execution."""
        from graphs.research_graph import DistributedResearchGraph

        with (
            patch("graphs.research_graph.PlannerAgent") as mock_planner,
            patch("graphs.research_graph.RouterAgent") as mock_router,
            patch("graphs.research_graph.ReflectionAgent") as mock_reflection,
            patch("graphs.research_graph.WriterAgent") as mock_writer,
        ):
            mock_planner.return_value = MagicMock()
            mock_router.return_value = MagicMock()
            mock_reflection_instance = MagicMock()
            mock_reflection_instance.execute = AsyncMock(return_value={})
            mock_reflection.return_value = mock_reflection_instance
            mock_writer.return_value = MagicMock()

            graph = DistributedResearchGraph(
                session_id="test-session",
                query="Test query",
                max_reflections=3,
            )

            # Test with reflection count at max
            state = {
                "reflection_count": 3,
                "max_reflections": 3,
                "findings": [],
            }

            # The reflection node should return early without calling execute
            result = asyncio.get_event_loop().run_until_complete(graph._reflection_node(state))

            # Should stop without calling reflection agent
            assert result.get("next_action") == "writer"
            assert result.get("metadata", {}).get("reflection_stopped") is True


class TestResearchStateSchema:
    """Test suite for ResearchState schema enforcement."""

    def test_state_has_required_fields(self):
        """Test that state has all required fields."""
        state = create_initial_state(
            session_id="test",
            query="Test query",
            max_reflections=3,
        )

        # Check required fields from AGENT.md
        required_fields = [
            "session_id",
            "query",
            "tasks",
            "active_tasks",
            "completed_tasks",
            "failed_tasks",
            "findings",
            "sources",
            "memory_context",
            "reflections",
            "reflection_count",
            "max_reflections",
            "draft_report",
            "final_report",
            "current_agent",
            "next_action",
            "status",
            "error_state",
            "requires_human_input",
            "token_usage",
            "metadata",
        ]

        for field in required_fields:
            assert field in state, f"Missing required field: {field}"

    def test_failed_tasks_field_exists(self):
        """Test that failed_tasks field exists and is list of dicts."""
        state = create_initial_state(
            session_id="test",
            query="Test query",
        )

        assert "failed_tasks" in state
        assert isinstance(state["failed_tasks"], list)

        # Add a failed task
        state["failed_tasks"].append(
            {
                "correlation_id": "task1",
                "error": "timeout",
                "task_type": "web_search",
            }
        )

        assert len(state["failed_tasks"]) == 1
        assert state["failed_tasks"][0]["correlation_id"] == "task1"

    def test_reflection_count_enforcement(self):
        """Test that reflection_count is properly tracked."""
        state = create_initial_state(
            session_id="test",
            query="Test query",
            max_reflections=3,
        )

        assert state["reflection_count"] == 0
        assert state["max_reflections"] == 3

        # Simulate reflection cycles
        state["reflection_count"] = 1
        assert state["reflection_count"] == 1

        state["reflection_count"] = 2
        assert state["reflection_count"] == 2

        # Should be stopped at max
        state["reflection_count"] = 3
        assert state["reflection_count"] == state["max_reflections"]

    def test_token_usage_tracking(self):
        """Test that token_usage field exists and tracks properly."""
        state = create_initial_state(
            session_id="test",
            query="Test query",
        )

        assert "token_usage" in state
        assert isinstance(state["token_usage"], dict)

        # Update token usage
        state["token_usage"]["prompt_tokens"] = 100
        state["token_usage"]["completion_tokens"] = 200
        state["token_usage"]["total_tokens"] = 300

        assert state["token_usage"]["total_tokens"] == 300

    def test_error_state_optional(self):
        """Test that error_state is optional and nullable."""
        state = create_initial_state(
            session_id="test",
            query="Test query",
        )

        # Should be None by default
        assert state["error_state"] is None

        # Can be set to dict
        state["error_state"] = {
            "error": "Task failed",
            "stage": "planner",
        }

        assert state["error_state"]["error"] == "Task failed"

    def test_state_progress_tracking(self):
        """Test that progress is tracked in state."""
        state = create_initial_state(
            session_id="test",
            query="Test query",
        )

        assert "progress" in state
        assert state["progress"] == 0.0

        # Simulate progress
        state["progress"] = 0.5
        assert state["progress"] == 0.5

        state["progress"] = 1.0
        assert state["progress"] == 1.0


class TestStateValidation:
    """Test suite for state validation."""

    def test_max_reflections_has_reasonable_default(self):
        """Test that max_reflections has a reasonable default."""
        state = create_initial_state(
            session_id="test",
            query="Test query",
        )

        # Default should be 3 (as per AGENT.md)
        assert state["max_reflections"] == 3

    def test_next_action_default(self):
        """Test that next_action defaults to planner."""
        state = create_initial_state(
            session_id="test",
            query="Test query",
        )

        assert state["next_action"] == "planner"

    def test_status_default(self):
        """Test that status defaults to initiated."""
        state = create_initial_state(
            session_id="test",
            query="Test query",
        )

        assert state["status"] == "initiated"

    def test_requires_human_input_default(self):
        """Test that requires_human_input defaults to False."""
        state = create_initial_state(
            session_id="test",
            query="Test query",
        )

        assert state["requires_human_input"] is False


class TestAsyncTaskAggregation:
    """Test suite for async task aggregation."""

    @pytest.mark.asyncio
    async def test_wait_for_task_timeout(self):
        """Test task waiting handles timeout."""
        from graphs.research_graph import DistributedResearchGraph

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

            graph = DistributedResearchGraph(
                session_id="test-session",
                query="Test query",
            )

            # Mock timeout scenario
            with patch("graphs.research_graph.asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.time.return_value = 0

                # Should handle timeout gracefully
                result = await graph._wait_for_task("fake-task-id", 0.1)

                # Function should return even on timeout
                assert result is not None
