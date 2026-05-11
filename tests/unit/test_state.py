"""
Unit tests for state schema and factory functions.
"""

import pytest

from graphs.state import ResearchState, create_initial_state


class TestCreateInitialState:
    """Test suite for create_initial_state function."""

    def test_returns_correct_structure(self):
        """Test that create_initial_state returns a valid ResearchState dict."""
        state = create_initial_state(
            session_id="test-session-123",
            query="What is machine learning?",
        )

        assert isinstance(state, dict)
        assert "session_id" in state
        assert "query" in state
        assert "tasks" in state
        assert "findings" in state
        assert "reflections" in state
        assert "status" in state

    def test_session_id_is_set(self):
        """Test that session_id is correctly set."""
        session_id = "unique-session-id"
        state = create_initial_state(session_id=session_id, query="Test query")

        assert state["session_id"] == session_id

    def test_query_is_set(self):
        """Test that query is correctly set."""
        query = "What is artificial intelligence?"
        state = create_initial_state(session_id="test", query=query)

        assert state["query"] == query

    def test_required_fields_present(self):
        """Test all required fields are present in initial state."""
        state = create_initial_state(session_id="test", query="Test query")

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
            "progress",
            "error_state",
            "requires_human_input",
            "token_usage",
            "metadata",
        ]

        for field in required_fields:
            assert field in state, f"Required field '{field}' is missing"

    def test_default_values_correct(self):
        """Test that default values are set correctly."""
        state = create_initial_state(session_id="test", query="Test query")

        # Lists should be empty
        assert state["tasks"] == []
        assert state["active_tasks"] == []
        assert state["completed_tasks"] == []
        assert state["failed_tasks"] == []
        assert state["findings"] == []
        assert state["sources"] == []
        assert state["reflections"] == []

        # Dicts should be empty
        assert state["memory_context"] == {}
        assert state["token_usage"] == {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        # Strings should be empty
        assert state["draft_report"] == ""
        assert state["final_report"] == ""
        assert state["current_agent"] == ""

    def test_reflection_count_starts_at_zero(self):
        """Test that reflection_count defaults to 0."""
        state = create_initial_state(session_id="test", query="Test query")

        assert state["reflection_count"] == 0

    def test_max_reflections_default_is_3(self):
        """Test that max_reflections defaults to 3."""
        state = create_initial_state(session_id="test", query="Test query")

        assert state["max_reflections"] == 3

    def test_max_reflections_custom_value(self):
        """Test that max_reflections can be customized."""
        custom_max = 5
        state = create_initial_state(
            session_id="test",
            query="Test query",
            max_reflections=custom_max,
        )

        assert state["max_reflections"] == custom_max

    def test_next_action_defaults_to_planner(self):
        """Test that next_action defaults to 'planner'."""
        state = create_initial_state(session_id="test", query="Test query")

        assert state["next_action"] == "planner"

    def test_status_defaults_to_initiated(self):
        """Test that status defaults to 'initiated'."""
        state = create_initial_state(session_id="test", query="Test query")

        assert state["status"] == "initiated"

    def test_progress_defaults_to_zero(self):
        """Test that progress defaults to 0.0."""
        state = create_initial_state(session_id="test", query="Test query")

        assert state["progress"] == 0.0

    def test_requires_human_input_defaults_to_false(self):
        """Test that requires_human_input defaults to False."""
        state = create_initial_state(session_id="test", query="Test query")

        assert state["requires_human_input"] is False

    def test_error_state_defaults_to_none(self):
        """Test that error_state defaults to None."""
        state = create_initial_state(session_id="test", query="Test query")

        assert state["error_state"] is None

    def test_metadata_structure(self):
        """Test that metadata has expected structure."""
        state = create_initial_state(session_id="test", query="Test query")

        assert "started_at" in state["metadata"]
        assert "completed_at" in state["metadata"]
        assert "model_used" in state["metadata"]

        # All should be None initially
        assert state["metadata"]["started_at"] is None
        assert state["metadata"]["completed_at"] is None
        assert state["metadata"]["model_used"] is None

    def test_token_usage_structure(self):
        """Test that token_usage has expected structure."""
        state = create_initial_state(session_id="test", query="Test query")

        assert "prompt_tokens" in state["token_usage"]
        assert "completion_tokens" in state["token_usage"]
        assert "total_tokens" in state["token_usage"]

        # All should be 0 initially
        assert state["token_usage"]["prompt_tokens"] == 0
        assert state["token_usage"]["completion_tokens"] == 0
        assert state["token_usage"]["total_tokens"] == 0

    def test_returns_typeddict_type(self):
        """Test that the return type is compatible with ResearchState."""
        state = create_initial_state(session_id="test", query="Test query")

        # Should be usable as ResearchState
        typed_state: ResearchState = state
        assert typed_state["session_id"] == "test"
