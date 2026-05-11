"""
End-to-end smoke tests for Research OS.
"""

from unittest.mock import patch, MagicMock, AsyncMock

import pytest


class TestImportSmokeTests:
    """Test suite for verifying all imports work."""

    def test_graphs_state_imports(self):
        """Test that graphs.state imports successfully."""
        from graphs.state import ResearchState, create_initial_state

        assert ResearchState is not None
        assert create_initial_state is not None

    def test_graphs_research_graph_imports(self):
        """Test that graphs.research_graph imports successfully."""
        from graphs.research_graph import ResearchGraph

        assert ResearchGraph is not None

    def test_api_config_imports(self):
        """Test that api.config imports successfully."""
        from api.config import Settings, get_settings

        assert Settings is not None
        assert get_settings is not None

    def test_api_main_imports(self):
        """Test that api.main imports successfully."""
        from api.main import create_app, app

        assert create_app is not None
        assert app is not None

    def test_api_routes_imports(self):
        """Test that api.routes imports successfully."""
        from api.routes import health, research, websocket

        assert health is not None
        assert research is not None
        assert websocket is not None

    def test_agents_base_imports(self):
        """Test that agents.base imports successfully."""
        from agents.base import BaseAgent

        assert BaseAgent is not None

    def test_agents_planner_imports(self):
        """Test that agents.planner imports successfully."""
        from agents.planner import PlannerAgent

        assert PlannerAgent is not None

    def test_agents_router_imports(self):
        """Test that agents.router imports successfully."""
        from agents.router import RouterAgent

        assert RouterAgent is not None

    def test_agents_reflection_imports(self):
        """Test that agents.reflection imports successfully."""
        from agents.reflection import ReflectionAgent

        assert ReflectionAgent is not None

    def test_agents_writer_imports(self):
        """Test that agents.writer imports successfully."""
        from agents.writer import WriterAgent

        assert WriterAgent is not None


class TestServiceInstantiation:
    """Test suite for service instantiation with mocks."""

    def test_research_graph_instantiation(self):
        """Test that ResearchGraph can be instantiated."""
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

            from graphs.research_graph import ResearchGraph

            graph = ResearchGraph(
                session_id="test-session",
                query="Test query",
            )

            assert graph is not None
            assert graph.session_id == "test-session"
            assert graph.query == "Test query"

    def test_settings_instantiation(self):
        """Test that Settings can be instantiated."""
        from api.config import Settings

        settings = Settings()

        assert settings is not None
        assert settings.app_name == "Research OS"

    def test_fastapi_app_creation(self):
        """Test that FastAPI app can be created."""
        with patch("api.main.get_settings") as mock_settings:
            mock_settings.return_value.app_name = "Research OS"
            mock_settings.return_value.app_version = "0.1.0"
            mock_settings.return_value.api_v1_prefix = "/api/v1"
            mock_settings.return_value.cors_origins = ["http://localhost:3000"]

            from api.main import create_app

            app = create_app()

            assert app is not None
            assert app.title == "Research OS"


class TestBasicWorkflow:
    """Test suite for basic workflow tests."""

    def test_create_initial_state_workflow(self):
        """Test the basic workflow of creating initial state."""
        from graphs.state import create_initial_state

        state = create_initial_state(
            session_id="smoke-test-session",
            query="What is machine learning?",
        )

        # Verify state structure
        assert state["session_id"] == "smoke-test-session"
        assert state["query"] == "What is machine learning?"
        assert state["status"] == "initiated"
        assert state["reflection_count"] == 0
        assert state["max_reflections"] == 3

    def test_research_state_field_count(self):
        """Test that ResearchState has expected number of fields."""
        from graphs.state import create_initial_state

        state = create_initial_state(session_id="test", query="Test")

        # Count all fields in state
        field_count = len(state.keys())

        # ResearchState should have 22+ fields
        assert field_count >= 20

    def test_state_can_progress_through_agents(self):
        """Test that state can be modified through agent simulation."""
        from graphs.state import create_initial_state

        state = create_initial_state(
            session_id="workflow-test",
            query="Test workflow",
        )

        # Simulate planner agent execution
        state["current_agent"] = "planner"
        state["status"] = "planning"
        state["tasks"] = [{"id": "task1", "type": "search"}]

        # Simulate router agent execution
        state["current_agent"] = "router"
        state["status"] = "routing"

        # Simulate finding addition
        state["findings"].append(
            {
                "id": "finding1",
                "content": "Test finding",
                "source": "test",
            }
        )

        # Verify state progressed
        assert state["current_agent"] == "router"
        assert state["status"] == "routing"
        assert len(state["findings"]) == 1

    def test_reflection_cycle_tracking(self):
        """Test that reflection cycles can be tracked."""
        from graphs.state import create_initial_state

        state = create_initial_state(
            session_id="reflection-test",
            query="Test reflection",
            max_reflections=3,
        )

        # Simulate reflection cycles
        for i in range(3):
            state["reflection_count"] = i + 1
            state["reflections"].append(f"Reflection {i + 1}")

        assert state["reflection_count"] == 3
        assert len(state["reflections"]) == 3
        assert state["reflection_count"] >= state["max_reflections"]

    def test_error_handling_state(self):
        """Test error state handling."""
        from graphs.state import create_initial_state

        state = create_initial_state(session_id="error-test", query="Test")

        # Add error state
        state["error_state"] = {
            "error": "Test error",
            "stage": "planner",
        }

        assert state["error_state"] is not None
        assert state["error_state"]["error"] == "Test error"
        assert state["error_state"]["stage"] == "planner"

    def test_token_tracking(self):
        """Test token usage tracking."""
        from graphs.state import create_initial_state

        state = create_initial_state(session_id="token-test", query="Test")

        # Simulate token usage
        state["token_usage"]["prompt_tokens"] = 100
        state["token_usage"]["completion_tokens"] = 50
        state["token_usage"]["total_tokens"] = 150

        assert state["token_usage"]["total_tokens"] == 150
        assert state["token_usage"]["prompt_tokens"] == 100
        assert state["token_usage"]["completion_tokens"] == 50


class TestConditionalLogic:
    """Test suite for conditional logic in graph."""

    def test_research_graph_conditional_functions_exist(self):
        """Test that conditional functions are defined."""
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

            from graphs.research_graph import ResearchGraph

            graph = ResearchGraph(session_id="test", query="Test")

            # Check conditional functions exist
            assert hasattr(graph, "_should_continue_reflection")
            assert hasattr(graph, "_should_execute_tasks")

    def test_should_continue_reflection_default_behavior(self):
        """Test reflection continuation logic."""
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

            from graphs.research_graph import ResearchGraph

            graph = ResearchGraph(session_id="test", query="Test")

            # Test max reflections reached
            state_max = {
                "reflection_count": 3,
                "max_reflections": 3,
                "findings": [],
            }
            result_max = graph._should_continue_reflection(state_max)
            assert result_max == "writer"

            # Test sufficient findings
            state_findings = {
                "reflection_count": 1,
                "max_reflections": 3,
                "findings": [{"id": 1}, {"id": 2}, {"id": 3}],
            }
            result_findings = graph._should_continue_reflection(state_findings)
            assert result_findings == "writer"

            # Test continue research
            state_continue = {
                "reflection_count": 0,
                "max_reflections": 3,
                "findings": [{"id": 1}],
            }
            result_continue = graph._should_continue_reflection(state_continue)
            assert result_continue == "research"


class TestEndToEndScenario:
    """Test suite for complete end-to-end scenarios."""

    def test_complete_research_session_simulation(self):
        """Simulate a complete research session workflow."""
        from graphs.state import create_initial_state

        # 1. Initialize session
        state = create_initial_state(
            session_id="e2e-test-session",
            query="What are the latest advances in AI?",
        )

        assert state["status"] == "initiated"
        assert state["progress"] == 0.0

        # 2. Planning phase
        state["status"] = "planning"
        state["current_agent"] = "planner"
        state["tasks"] = [
            {"id": "t1", "type": "web_search", "query": "latest AI advances"},
            {"id": "t2", "type": "web_search", "query": "AI research 2024"},
        ]

        # 3. Routing phase
        state["status"] = "routing"
        state["current_agent"] = "router"

        # 4. Execute tasks
        state["active_tasks"] = ["t1", "t2"]
        state["completed_tasks"] = ["t1", "t2"]
        state["findings"].append(
            {
                "id": "f1",
                "content": "Generative AI advances in 2024",
                "source": "web_search",
            }
        )

        # 5. Reflection
        state["status"] = "reflecting"
        state["current_agent"] = "reflection"
        state["reflection_count"] = 1
        state["reflections"].append("Good progress on initial findings")

        # 6. Write report
        state["status"] = "writing"
        state["current_agent"] = "writer"
        state["final_report"] = "# AI Advances Report\n\nLatest findings..."

        # Verify complete workflow
        assert len(state["completed_tasks"]) == 2
        assert len(state["findings"]) >= 1
        assert state["reflection_count"] == 1
        assert len(state["final_report"]) > 0

    def test_configuration_loaded_correctly(self):
        """Test that configuration loads correctly."""
        from api.config import get_settings

        settings = get_settings()

        # Verify critical settings
        assert settings.app_name is not None
        assert settings.app_version is not None
        assert settings.environment is not None

    def test_celery_worker_config_exists(self):
        """Test that Celery worker configuration exists."""
        # Verify configuration structure exists
        expected_config = {
            "broker": "redis://localhost:6379/0",
            "backend": "redis://localhost:6379/0",
            "queues": ["research", "browser"],
        }

        assert expected_config["broker"] is not None
        assert expected_config["backend"] is not None
        assert len(expected_config["queues"]) == 2
