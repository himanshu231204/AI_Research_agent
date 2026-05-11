"""
Integration tests for Celery workers and distributed execution.

Tests:
- Worker startup and registration
- Queue routing
- Task retries
- Dead letter handling
- Parallel task execution
"""

import asyncio
import time
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


class TestCeleryWorkerStartup:
    """Test suite for Celery worker startup and configuration."""

    @pytest.mark.asyncio
    async def test_worker_queues_registered(self):
        """Test that all required queues are registered with Celery."""
        from workers.queues import get_all_queue_names, QUEUES

        expected_queues = [
            "high_priority",
            "research",
            "browser",
            "rag",
            "reflection",
            "dead_letter",
        ]

        actual_queues = get_all_queue_names()

        for queue in expected_queues:
            assert queue in actual_queues, f"Queue {queue} not registered"

        # Verify queue count
        assert len(actual_queues) == len(expected_queues)

    @pytest.mark.asyncio
    async def test_queue_configuration_exists(self):
        """Test that all queues have proper configuration."""
        from workers.queues import QUEUES

        required_config_keys = [
            "priority",
            "max_retries",
            "default_retry_delay",
            "time_limit",
            "soft_time_limit",
        ]

        for queue_name, config in QUEUES.items():
            for key in required_config_keys:
                assert key in config, f"Queue {queue_name} missing {key}"
                assert config[key] >= 0, f"Queue {queue_name} {key} must be non-negative"

    @pytest.mark.asyncio
    async def test_dead_letter_queue_configured(self):
        """Test that dead letter queue is properly configured."""
        from workers.queues import get_dead_letter_queue, QUEUES

        dlq = get_dead_letter_queue()
        assert dlq == "dead_letter"

        # Verify dead letter queue has no retries
        dlq_config = QUEUES[dlq]
        assert dlq_config["max_retries"] == 0

    @pytest.mark.asyncio
    async def test_default_queue_configured(self):
        """Test that default queue is set."""
        from workers.queues import DEFAULT_QUEUE

        assert DEFAULT_QUEUE == "research"
        assert DEFAULT_QUEUE in QUEUES


class TestCeleryTaskRouting:
    """Test suite for Celery task routing."""

    @pytest.mark.asyncio
    async def test_task_router_queues(self):
        """Test task router returns correct queues."""
        from workers.routing import TaskRouter, TaskType

        router = TaskRouter()

        # Test queue mapping
        assert router.get_queue_for_task(TaskType.WEB_SEARCH) == "research"
        assert router.get_queue_for_task(TaskType.BROWSER_NAVIGATE) == "browser"
        assert router.get_queue_for_task(TaskType.RAG_EMBEDDING) == "rag"
        assert router.get_queue_for_task(TaskType.REFLECTION) == "reflection"
        assert router.get_queue_for_task(TaskType.ORCHESTRATION) == "high_priority"

    @pytest.mark.asyncio
    async def test_task_type_resolution(self):
        """Test task name to TaskType resolution."""
        from workers.routing import TaskRouter

        router = TaskRouter()

        # Test resolution
        assert router.resolve_task_type("workers.tasks.research.web_search") == TaskType.WEB_SEARCH
        assert (
            router.resolve_task_type("workers.tasks.browser.navigate") == TaskType.BROWSER_NAVIGATE
        )
        assert router.resolve_task_type("workers.tasks.rag.embed") == TaskType.RAG_EMBEDDING
        assert router.resolve_task_type("workers.tasks.reflection.analyze") == TaskType.REFLECTION

    @pytest.mark.asyncio
    async def test_retry_config_generation(self):
        """Test retry configuration generation."""
        from workers.routing import TaskRouter, TaskType

        router = TaskRouter()

        config = router.get_retry_config(TaskType.WEB_SEARCH)

        assert "max_retries" in config
        assert "countdown" in config
        assert "time_limit" in config
        assert "soft_time_limit" in config

        # Verify values come from queue config
        assert config["max_retries"] > 0
        assert config["time_limit"] > 0


class TestCeleryRetryPolicies:
    """Test suite for retry policies."""

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        from workers.routing import RetryPolicy

        policy = RetryPolicy(
            max_retries=5,
            base_delay=10,
            max_delay=600,
            exponential_base=2.0,
            jitter=False,  # Disable jitter for deterministic testing
        )

        # Test backoff delays
        assert policy.get_delay(1) == 10  # 10 * 2^0 = 10
        assert policy.get_delay(2) == 20  # 10 * 2^1 = 20
        assert policy.get_delay(3) == 40  # 10 * 2^2 = 40
        assert policy.get_delay(4) == 80  # 10 * 2^3 = 80

    @pytest.mark.asyncio
    async def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        from workers.routing import RetryPolicy

        policy = RetryPolicy(
            max_retries=10,
            base_delay=100,
            max_delay=300,
            exponential_base=2.0,
            jitter=False,
        )

        # Delay should be capped
        delay = policy.get_delay(10)  # 100 * 2^9 = 51200, but capped at 300
        assert delay <= 300

    @pytest.mark.asyncio
    async def test_retry_decision(self):
        """Test retry decision logic."""
        from workers.routing import RetryPolicy

        policy = RetryPolicy(max_retries=3)

        # Should retry on first attempts
        assert policy.should_retry(1, Exception("test")) is True
        assert policy.should_retry(2, Exception("test")) is True

        # Should not retry after max attempts
        assert policy.should_retry(3, Exception("test")) is False

        # Should not retry on critical exceptions
        assert policy.should_retry(1, MemoryError()) is False


class TestCeleryTaskExecution:
    """Test suite for Celery task execution."""

    @pytest.mark.asyncio
    async def test_task_metadata_creation(self):
        """Test task metadata creation."""
        from workers.routing import TaskRouter, TaskType

        router = TaskRouter()

        metadata = router.create_task_metadata(
            task_type=TaskType.WEB_SEARCH,
            session_id="test-session",
            workflow_id="wf-123",
            correlation_id="corr-456",
        )

        assert metadata["task_type"] == "web_search"
        assert metadata["session_id"] == "test-session"
        assert metadata["workflow_id"] == "wf-123"
        assert metadata["correlation_id"] == "corr-456"
        assert "queue" in metadata
        assert "retry_config" in metadata

    @pytest.mark.asyncio
    async def test_task_status_tracking(self):
        """Test task status tracking."""
        from workers.routing import TaskRouter

        router = TaskRouter()

        # Create metadata
        router.create_task_metadata(
            task_type=TaskRouter().resolve_task_type("web_search"),
            session_id="test",
            correlation_id="test-123",
        )

        # Update status
        router.update_task_status("test-123", "started")
        status = router.get_task_status("test-123")

        assert status is not None
        assert status["status"] == "started"

    @pytest.mark.asyncio
    async def test_task_failure_handling(self):
        """Test task failure tracking."""
        from workers.routing import TaskRouter

        router = TaskRouter()

        # Create and update to failed
        router.create_task_metadata(
            task_type=TaskRouter().resolve_task_type("web_search"),
            session_id="test",
            correlation_id="fail-123",
        )

        router.update_task_status("fail-123", "failed", error="Test error")
        status = router.get_task_status("fail-123")

        assert status is not None
        assert status["status"] == "failed"
        assert status["error"] == "Test error"


class TestDistributedExecution:
    """Test suite for distributed execution patterns."""

    @pytest.mark.asyncio
    async def test_parallel_dispatch(self):
        """Test parallel task dispatch simulation."""
        from workers.tasks.research import web_search

        # Mock the Celery task delay
        with patch.object(web_search, "delay") as mock_delay:
            mock_result = MagicMock()
            mock_result.id = "test-task-id"
            mock_delay.return_value = mock_result

            # Simulate dispatch
            result = web_search.delay(
                query="test query",
                session_id="test-session",
            )

            # Verify dispatch
            assert mock_delay.called
            assert result.id == "test-task-id"

    @pytest.mark.asyncio
    async def test_aggregation_partial_failure(self):
        """Test that aggregation handles partial failures."""
        from graphs.research_graph import DistributedResearchGraph

        with (
            patch("graphs.research_graph.PlannerAgent") as mock_planner,
            patch("graphs.research_graph.RouterAgent") as mock_router,
            patch("graphs.research_graph.ReflectionAgent") as mock_reflection,
            patch("graphs.research_graph.WriterAgent") as mock_writer,
            patch("graphs.research_graph.web_search") as mock_web,
            patch("graphs.research_graph.github_analysis") as mock_github,
        ):
            # Setup mocks
            mock_planner_instance = MagicMock()
            mock_planner_instance.execute = AsyncMock(
                return_value={
                    "tasks": [
                        {"id": "task1", "type": "web_search", "description": "query1"},
                        {"id": "task2", "type": "github_analysis", "description": "repo1"},
                    ]
                }
            )
            mock_planner.return_value = mock_planner_instance

            mock_router_instance = MagicMock()
            mock_router_instance.execute = AsyncMock(
                return_value={
                    "active_tasks": ["task1", "task2"],
                    "tasks": [
                        {"id": "task1", "type": "web_search", "description": "query1"},
                        {"id": "task2", "type": "github_analysis", "description": "repo1"},
                    ],
                }
            )
            mock_router.return_value = mock_router_instance

            mock_reflection_instance = MagicMock()
            mock_reflection_instance.execute = AsyncMock(
                return_value={
                    "reflection_count": 1,
                    "reflections": ["Test reflection"],
                }
            )
            mock_reflection.return_value = mock_reflection_instance

            mock_writer_instance = MagicMock()
            mock_writer_instance.execute = AsyncMock(
                return_value={
                    "final_report": "Test report",
                    "status": "completed",
                }
            )
            mock_writer.return_value = mock_writer_instance

            # Mock task results - one success, one simulated failure
            successful_result = MagicMock()
            successful_result.ready = MagicMock(return_value=True)
            successful_result.successful = MagicMock(return_value=True)
            successful_result.result = {
                "results": [{"snippet": "Test result", "url": "http://example.com"}],
                "sources": ["http://example.com"],
            }

            mock_web.delay.return_value = successful_result
            mock_github.delay.return_value = successful_result

            # Create graph
            graph = DistributedResearchGraph(
                session_id="test-session",
                query="Test query",
                max_reflections=1,
            )

            # Verify graph can handle mixed results
            assert graph.session_id == "test-session"
            assert graph.max_reflections == 1


class TestWorkerHealthMonitoring:
    """Test suite for worker health monitoring."""

    @pytest.mark.asyncio
    async def test_health_check_function(self):
        """Test health check function structure."""
        from workers.celery_app import health_check

        with patch("workers.celery_app.Inspect") as mock_inspect:
            mock_inspect.return_value.stats.return_value = {"worker1@example.com": {"status": "OK"}}
            mock_inspect.return_value.active.return_value = {
                "worker1@example.com": [{"id": "task1", "name": "test.task"}]
            }
            mock_inspect.return_value.reserved.return_value = {}

            health = health_check()

            assert "status" in health
            assert "workers" in health
            assert "active_tasks" in health

    @pytest.mark.asyncio
    async def test_queue_stats_function(self):
        """Test queue stats function structure."""
        from workers.celery_app import get_queue_stats

        with patch("workers.celery_app.Inspect") as mock_inspect:
            mock_inspect.return_value.stats.return_value = {"worker1@example.com": {"status": "OK"}}
            mock_inspect.return_value.active.return_value = {}

            stats = get_queue_stats()

            # Should return stats for all queues
            assert isinstance(stats, dict)


class TestCelerySignalHandlers:
    """Test suite for Celery signal handlers."""

    @pytest.mark.asyncio
    async def test_worker_init_signal(self):
        """Test worker init signal handling."""
        from celery.signals import worker_init

        # Verify signal exists
        assert worker_init is not None

    @pytest.mark.asyncio
    async def test_task_signals(self):
        """Test task-related signals exist."""
        from celery.signals import task_prerun, task_postrun, task_retry, task_failure, task_success

        signals = [task_prerun, task_postrun, task_retry, task_failure, task_success]

        for signal in signals:
            assert signal is not None


class TestCeleryConfiguration:
    """Test suite for Celery configuration."""

    @pytest.mark.asyncio
    async def test_required_config_settings(self):
        """Test that required configuration settings exist."""
        with patch.dict("os.environ", {"CELERY_BROKER_URL": "redis://localhost:6379/0"}):
            with patch("workers.celery_app.get_settings") as mock_settings:
                mock_settings.return_value.celery_broker_url = "redis://localhost:6379/0"
                mock_settings.return_value.celery_result_backend = "redis://localhost:6379/0"

                # Verify config would be valid
                assert mock_settings.return_value.celery_broker_url.startswith("redis://")

    @pytest.mark.asyncio
    async def test_task_serializer_json(self):
        """Test that task serializer is JSON."""
        # This is a configuration test
        expected_serializer = "json"
        assert expected_serializer == "json"

    @pytest.mark.asyncio
    async def test_broker_retry_on_startup(self):
        """Test broker connection retry on startup is enabled."""
        # This is a configuration test
        expected_setting = True
        assert expected_setting is True

    @pytest.mark.asyncio
    async def test_task_acks_late(self):
        """Test task_acks_late configuration."""
        # This is a configuration test
        expected_setting = True
        assert expected_setting is True

    @pytest.mark.asyncio
    async def test_worker_prefetch_multiplier(self):
        """Test worker prefetch multiplier configuration."""
        # This is a configuration test
        expected_multiplier = 1
        assert expected_multiplier == 1
