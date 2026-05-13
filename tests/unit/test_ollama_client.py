"""
Unit tests for the legacy OllamaClient wrapper.

These tests cover model fallback resolution for the writer agent path.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch

from models.ollama_client import OllamaClient


@pytest.mark.asyncio
async def test_generate_falls_back_to_installed_model_when_default_missing():
    client = OllamaClient(model="qwen3")

    with patch.object(client, "list_models", AsyncMock(return_value=[{"name": "llama3.2:3b"}, {"name": "mistral:latest"}])):
        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_response = Mock()
            mock_response.raise_for_status = Mock(return_value=None)
            mock_response.json.return_value = {"response": "writer fallback ok"}
            mock_http_client.post.return_value = mock_response
            mock_get_client.return_value = mock_http_client

            result = await client.generate("Write a summary")

            assert result == "writer fallback ok"
            assert mock_http_client.post.await_count == 1
            assert mock_http_client.post.call_args.kwargs["json"]["model"] == "llama3.2:3b"
