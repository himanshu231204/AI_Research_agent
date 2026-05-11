"""
Unit tests for state schema validation.
"""

import pytest

from graphs.state import ResearchState, create_initial_state


class TestResearchStateFields:
    """Test suite for ResearchState field validation."""

    def test_research_state_has_all_required_fields(self):
        """Test that ResearchState TypedDict has all required fields."""
        state = create_initial_state(session_id="test", query="Test query")

        expected_fields = {
            "session_id": str,
            "query": str,
            "tasks": list,
            "active_tasks": list,
            "completed_tasks": list,
            "failed_tasks": list,
            "findings": list,
            "sources": list,
            "memory_context": dict,
            "reflections": list,
            "reflection_count": int,
            "max_reflections": int,
            "draft_report": str,
            "final_report": str,
            "current_agent": str,
            "next_action": str,
            "status": str,
            "progress": float,
            "error_state": type(None),  # Optional
            "requires_human_input": bool,
            "token_usage": dict,
            "metadata": dict,
        }

        for field, expected_type in expected_fields.items():
            assert field in state, f"Missing required field: {field}"
            if expected_type != type(None):
                assert isinstance(state[field], expected_type), (
                    f"Field '{field}' should be {expected_type}, got {type(state[field])}"
                )

    def test_session_id_type(self):
        """Test session_id field type."""
        state = create_initial_state(session_id="abc123", query="Test")

        assert isinstance(state["session_id"], str)
        assert state["session_id"] == "abc123"

    def test_query_type(self):
        """Test query field type."""
        state = create_initial_state(session_id="test", query="What is AI?")

        assert isinstance(state["query"], str)
        assert state["query"] == "What is AI?"

    def test_tasks_type(self):
        """Test tasks field type and initialization."""
        state = create_initial_state(session_id="test", query="Test")

        assert isinstance(state["tasks"], list)

    def test_active_tasks_type(self):
        """Test active_tasks field type."""
        state = create_initial_state(session_id="test", query="Test")

        assert isinstance(state["active_tasks"], list)

    def test_completed_tasks_type(self):
        """Test completed_tasks field type."""
        state = create_initial_state(session_id="test", query="Test")

        assert isinstance(state["completed_tasks"], list)

    def test_failed_tasks_type(self):
        """Test failed_tasks field type."""
        state = create_initial_state(session_id="test", query="Test")

        assert isinstance(state["failed_tasks"], list)

    def test_findings_type(self):
        """Test findings field type."""
        state = create_initial_state(session_id="test", query="Test")

        assert isinstance(state["findings"], list)

    def test_sources_type(self):
        """Test sources field type."""
        state = create_initial_state(session_id="test", query="Test")

        assert isinstance(state["sources"], list)

    def test_memory_context_type(self):
        """Test memory_context field type."""
        state = create_initial_state(session_id="test", query="Test")

        assert isinstance(state["memory_context"], dict)

    def test_reflections_type(self):
        """Test reflections field type."""
        state = create_initial_state(session_id="test", query="Test")

        assert isinstance(state["reflections"], list)

    def test_reflection_count_type(self):
        """Test reflection_count field type and logic."""
        state = create_initial_state(session_id="test", query="Test")

        assert isinstance(state["reflection_count"], int)
        assert state["reflection_count"] == 0

    def test_max_reflections_type(self):
        """Test max_reflections field type."""
        state = create_initial_state(session_id="test", query="Test", max_reflections=5)

        assert isinstance(state["max_reflections"], int)
        assert state["max_reflections"] == 5

    def test_draft_report_type(self):
        """Test draft_report field type."""
        state = create_initial_state(session_id="test", query="Test")

        assert isinstance(state["draft_report"], str)

    def test_final_report_type(self):
        """Test final_report field type."""
        state = create_initial_state(session_id="test", query="Test")

        assert isinstance(state["final_report"], str)

    def test_current_agent_type(self):
        """Test current_agent field type."""
        state = create_initial_state(session_id="test", query="Test")

        assert isinstance(state["current_agent"], str)

    def test_next_action_type(self):
        """Test next_action field type."""
        state = create_initial_state(session_id="test", query="Test")

        assert isinstance(state["next_action"], str)
        assert state["next_action"] == "planner"

    def test_status_type(self):
        """Test status field type."""
        state = create_initial_state(session_id="test", query="Test")

        assert isinstance(state["status"], str)
        assert state["status"] == "initiated"

    def test_progress_type(self):
        """Test progress field type."""
        state = create_initial_state(session_id="test", query="Test")

        assert isinstance(state["progress"], float)
        assert state["progress"] == 0.0

    def test_error_state_type(self):
        """Test error_state field type."""
        state = create_initial_state(session_id="test", query="Test")

        assert state["error_state"] is None

    def test_requires_human_input_type(self):
        """Test requires_human_input field type."""
        state = create_initial_state(session_id="test", query="Test")

        assert isinstance(state["requires_human_input"], bool)
        assert state["requires_human_input"] is False

    def test_token_usage_structure(self):
        """Test token_usage field structure."""
        state = create_initial_state(session_id="test", query="Test")
        token_usage = state["token_usage"]

        assert isinstance(token_usage, dict)
        assert "prompt_tokens" in token_usage
        assert "completion_tokens" in token_usage
        assert "total_tokens" in token_usage

    def test_metadata_structure(self):
        """Test metadata field structure."""
        state = create_initial_state(session_id="test", query="Test")
        metadata = state["metadata"]

        assert isinstance(metadata, dict)
        assert "started_at" in metadata
        assert "completed_at" in metadata
        assert "model_used" in metadata


class TestReflectionCountLogic:
    """Test suite for reflection count logic."""

    def test_reflection_count_starts_at_zero(self):
        """Test reflection count initialization."""
        state = create_initial_state(session_id="test", query="Test")

        assert state["reflection_count"] == 0

    def test_reflection_count_can_be_manually_set(self):
        """Test that reflection_count can be set in state."""
        state = create_initial_state(session_id="test", query="Test")
        state["reflection_count"] = 2

        assert state["reflection_count"] == 2

    def test_max_reflections_limits_cycles(self):
        """Test max_reflections is used for cycle limiting."""
        state = create_initial_state(
            session_id="test",
            query="Test",
            max_reflections=5,
        )

        assert state["max_reflections"] == 5
        assert state["reflection_count"] < state["max_reflections"]


class TestMaxReflectionsEnforcement:
    """Test suite for max_reflections enforcement."""

    def test_default_max_reflections_is_3(self):
        """Test default max_reflections value."""
        state = create_initial_state(session_id="test", query="Test")

        assert state["max_reflections"] == 3

    def test_custom_max_reflections(self):
        """Test custom max_reflections value."""
        for custom_max in [1, 2, 5, 10]:
            state = create_initial_state(
                session_id="test",
                query="Test",
                max_reflections=custom_max,
            )
            assert state["max_reflections"] == custom_max

    def test_max_reflections_type_is_int(self):
        """Test max_reflections is an integer."""
        state = create_initial_state(session_id="test", query="Test")

        assert isinstance(state["max_reflections"], int)

    def test_reflection_count_type_is_int(self):
        """Test reflection_count is an integer."""
        state = create_initial_state(session_id="test", query="Test")

        assert isinstance(state["reflection_count"], int)


class TestRequiredFieldTypes:
    """Test suite for required field type validation."""

    def test_session_id_is_string(self):
        """Validate session_id is a string."""
        state = create_initial_state(session_id="abc", query="test")
        assert isinstance(state["session_id"], str)

    def test_query_is_string(self):
        """Validate query is a string."""
        state = create_initial_state(session_id="abc", query="What is this?")
        assert isinstance(state["query"], str)

    def test_status_is_string(self):
        """Validate status is a string."""
        state = create_initial_state(session_id="abc", query="test")
        assert isinstance(state["status"], str)

    def test_next_action_is_string(self):
        """Validate next_action is a string."""
        state = create_initial_state(session_id="abc", query="test")
        assert isinstance(state["next_action"], str)

    def test_progress_is_float(self):
        """Validate progress is a float (0.0)."""
        state = create_initial_state(session_id="abc", query="test")
        assert isinstance(state["progress"], float)

    def test_requires_human_input_is_bool(self):
        """Validate requires_human_input is a boolean."""
        state = create_initial_state(session_id="abc", query="test")
        assert isinstance(state["requires_human_input"], bool)


class TestStateImmutability:
    """Test suite for state immutability patterns."""

    def test_state_can_be_modified(self):
        """Test that state dictionaries can be modified (standard dict behavior)."""
        state = create_initial_state(session_id="test", query="Test")

        # Modify various fields
        state["reflection_count"] = 1
        state["status"] = "running"
        state["findings"].append({"id": 1, "content": "test"})

        assert state["reflection_count"] == 1
        assert state["status"] == "running"
        assert len(state["findings"]) == 1

    def test_nested_structures_can_be_modified(self):
        """Test nested dicts and lists can be modified."""
        state = create_initial_state(session_id="test", query="Test")

        state["token_usage"]["prompt_tokens"] = 100
        state["metadata"]["started_at"] = "2024-01-01"

        assert state["token_usage"]["prompt_tokens"] == 100
        assert state["metadata"]["started_at"] == "2024-01-01"
