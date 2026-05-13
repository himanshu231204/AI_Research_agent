"""
Router Agent for Research OS.

Responsible for:
- Determining required tools
- Routing tasks to specialized agents
- Managing task execution flow
- Autonomous tool selection using MCP
"""

import logging
import json
from typing import Any, Dict, List, Optional

from agents.base import BaseAgent
from graphs.state import ResearchState
from models.ollama_client import OllamaClient
from mcplib.registry import ToolRegistry, RegistryConfig
from mcplib.client.pool import ConnectionPool, PoolConfig
from mcplib.client.client import MCPClientConfig
from mcplib.transport import TransportType
from mcplib.config import load_mcp_config, get_enabled_mcp_servers

logger = logging.getLogger(__name__)


class ToolSelectionResult:
    """Result of tool selection"""

    def __init__(
        self,
        selected_tools: List[Dict[str, Any]],
        reasoning: str,
        confidence: float,
    ):
        self.selected_tools = selected_tools
        self.reasoning = reasoning
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "selected_tools": self.selected_tools,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
        }


class RouterAgent(BaseAgent):
    """
    Router agent for directing tasks to appropriate execution paths.

    Analyzes tasks and determines the best way to execute them.
    Supports autonomous tool selection via MCP.
    """

    def __init__(self):
        super().__init__(agent_name="router")
        self.ollama = OllamaClient()
        self._registry: Optional[ToolRegistry] = None
        self._pool: Optional[ConnectionPool] = None
        self._initialized = False

    async def initialize_mcp(self) -> None:
        """Initialize MCP components for tool selection using JSON configuration"""
        if self._initialized:
            return

        try:
            # Load MCP configuration from JSON
            mcp_config = load_mcp_config()

            # Create connection pool from config
            pool_config = PoolConfig(
                max_connections=mcp_config.pool.max_connections,
                max_per_server=mcp_config.pool.max_per_server,
                connection_timeout=mcp_config.pool.connection_timeout,
                idle_timeout=mcp_config.pool.idle_timeout,
                max_retries=mcp_config.pool.max_retries,
                health_check_interval=mcp_config.pool.health_check_interval,
            )
            self._pool = ConnectionPool(pool_config)

            # Register MCP servers from JSON config
            enabled_servers = mcp_config.get_enabled_servers()
            for server in enabled_servers:
                transport_type = (
                    TransportType.STDIO if server.transport == "stdio" else TransportType.HTTP
                )

                await self._pool.register_server(
                    MCPClientConfig(
                        server_name=server.name,
                        server_url=server.url,
                        transport_type=transport_type,
                        timeout=server.timeout,
                        command=server.command,
                        args=tuple(server.args),
                        env=server.env,
                        headers=server.config.get("headers", {}),
                    )
                )
                logger.info(f"Registered MCP server: {server.name} ({server.transport})")
                # Try to establish connection for HTTP/STDIO servers so tools can be discovered
                try:
                    connected = await self._pool.connect_server(server.name)
                    if connected:
                        logger.info(f"Connected to MCP server: {server.name}")
                    else:
                        logger.warning(f"Failed to connect to MCP server: {server.name}")
                except Exception as e:
                    logger.warning(f"Error connecting to MCP server {server.name}: {e}")

            # Create registry
            registry_config = RegistryConfig(
                enable_auto_discovery=mcp_config.registry.enable_auto_discovery,
                discovery_interval=mcp_config.registry.discovery_interval,
                cache_ttl=mcp_config.registry.cache_ttl,
                max_tools=mcp_config.registry.max_tools,
            )
            self._registry = ToolRegistry(registry_config, self._pool)

            # Load tools from JSON configuration
            server_configs = [
                {
                    "name": s.name,
                    "enabled": s.enabled,
                    "capabilities": s.capabilities,
                    "timeout": s.timeout,
                }
                for s in enabled_servers
            ]
            await self._registry.load_from_config(server_configs)

            await self._registry.start()

            self._initialized = True
            logger.info(f"MCP components initialized with {len(enabled_servers)} servers")

        except FileNotFoundError as e:
            logger.warning(f"MCP config file not found: {e}, using fallback mode")
            self._initialized = False
        except Exception as e:
            logger.warning(f"MCP initialization failed: {e}, using fallback mode")
            self._initialized = False

    async def execute(self, state: ResearchState) -> Dict[str, Any]:
        """
        Execute the router agent.

        Analyzes tasks and prepares them for execution.
        Supports autonomous tool selection.

        Args:
            state: Current research state with tasks

        Returns:
            Updated state with active tasks and selected tools
        """
        tasks = state.get("tasks", [])
        session_id = state["session_id"]

        logger.info(f"[{session_id}] Routing {len(tasks)} tasks")

        if not tasks:
            logger.warning(f"[{session_id}] No tasks to route")
            return {
                "next_action": "writer",
                "status": "routed",
            }

        try:
            # Initialize MCP if needed
            await self.initialize_mcp()

            # Analyze and categorize tasks
            categorized_tasks = await self._categorize_tasks(tasks)

            # Autonomous tool selection for each task
            tool_selections = []
            for task in categorized_tasks:
                selection = await self._select_tools_for_task(task)
                tool_selections.append(selection)

                # Add selected tools to task
                task["selected_tools"] = selection.selected_tools
                task["tool_reasoning"] = selection.reasoning

            # Mark tasks as active
            active_task_ids = [t["id"] for t in categorized_tasks]

            logger.info(f"[{session_id}] Activated {len(active_task_ids)} tasks")
            logger.info(f"[{session_id}] Selected tools: {len(tool_selections)} task-tool mappings")

            return {
                "tasks": categorized_tasks,
                "active_tasks": active_task_ids,
                "tool_selections": [s.to_dict() for s in tool_selections],
                "next_action": "aggregator",
                "status": "routed",
                "progress": 0.2,
            }

        except Exception as e:
            logger.error(f"[{session_id}] Routing failed: {e}")
            return {
                "error_state": {
                    "error": str(e),
                    "stage": "routing",
                },
                "status": "failed",
            }

    async def _select_tools_for_task(self, task: Dict[str, Any]) -> ToolSelectionResult:
        """
        Autonomously select appropriate tools for a task.

        Uses LLM reasoning to select from available MCP tools.

        Args:
            task: Task dictionary

        Returns:
            ToolSelectionResult with selected tools and reasoning
        """
        task_type = task.get("type", "general")
        task_description = task.get("description", "")
        task_context = task.get("context", {})

        # Get available tools from registry
        available_tools = []
        if self._registry:
            all_tools = self._registry.tools
            for tool_name, tool in all_tools.items():
                available_tools.append(
                    {
                        "name": tool_name,
                        "description": tool.description,
                        "category": tool.category.value,
                        "parameters": [p.name for p in tool.parameters],
                    }
                )

        # Use LLM to select tools
        if available_tools and self.ollama:
            try:
                prompt = self._build_tool_selection_prompt(
                    task_type, task_description, task_context, available_tools
                )

                response = await self.ollama.generate(
                    prompt=prompt,
                    temperature=0.3,
                )

                # Parse LLM response
                selected_tools, reasoning, confidence = self._parse_tool_selection(response)

                return ToolSelectionResult(
                    selected_tools=selected_tools,
                    reasoning=reasoning,
                    confidence=confidence,
                )

            except Exception as e:
                logger.warning(f"LLM tool selection failed: {e}")

        # Fallback to rule-based selection
        return self._fallback_tool_selection(task_type)

    def _build_tool_selection_prompt(
        self,
        task_type: str,
        task_description: str,
        task_context: Dict[str, Any],
        available_tools: List[Dict[str, Any]],
    ) -> str:
        """Build prompt for LLM tool selection"""
        tools_json = json.dumps(available_tools, indent=2)

        prompt = f"""You are a tool selection expert. Given a task, select the most appropriate tools from the available list.

Task Type: {task_type}
Task Description: {task_description}
Task Context: {json.dumps(task_context)}

Available Tools:
{tools_json}

Select tools and provide:
1. List of tool names to use
2. Reasoning for selection
3. Confidence score (0-1)

Respond in JSON format:
{{
    "selected_tools": ["tool1", "tool2"],
    "reasoning": "explanation",
    "confidence": 0.9
}}
"""
        return prompt

    def _parse_tool_selection(self, response: str) -> tuple[List[Dict[str, Any]], str, float]:
        """Parse LLM tool selection response"""
        try:
            # Try to extract JSON from response
            import re

            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())

                selected = data.get("selected_tools", [])
                tools = [{"name": t, "server": self._infer_server(t)} for t in selected]

                return (
                    tools,
                    data.get("reasoning", "LLM selected tools"),
                    data.get("confidence", 0.7),
                )
        except Exception as e:
            logger.warning(f"Failed to parse tool selection: {e}")

        return [], "Failed to parse LLM response", 0.0

    def _infer_server(self, tool_name: str) -> str:
        """Infer MCP server from tool name"""
        if tool_name.startswith("browser_"):
            return "browser"
        elif tool_name.startswith("github_"):
            return "github"
        elif tool_name.startswith("filesystem_"):
            return "filesystem"
        elif tool_name.startswith("terminal_"):
            return "terminal"
        return "unknown"

    def _fallback_tool_selection(self, task_type: str) -> ToolSelectionResult:
        """Fallback rule-based tool selection using registry"""
        # Use registry-based lookup if available
        if self._registry and self._registry.tools:
            # Get all tools and filter by category based on task type
            category_map = {
                "web_search": ["browser_navigate", "browser_evaluate", "browser_screenshot"],
                "github_analysis": ["github_search_repos", "github_get_file", "github_list_files"],
                "browser": [
                    "browser_navigate",
                    "browser_screenshot",
                    "browser_click",
                    "browser_type",
                ],
                "pdf_analysis": ["filesystem_read"],
                "terminal": ["terminal_execute"],
            }

            relevant_tools = category_map.get(task_type, [])
            selected = []

            for tool_name in relevant_tools:
                tool = self._registry.tools.get(tool_name)
                if tool:
                    selected.append(
                        {
                            "name": tool.name,
                            "server": tool.server_name,
                        }
                    )

            if selected:
                return ToolSelectionResult(
                    selected_tools=selected,
                    reasoning=f"Registry-based fallback for task type: {task_type}",
                    confidence=0.6,
                )

        # Fallback to hardcoded mapping if registry not available
        tool_map = {
            "web_search": [
                {"name": "browser_navigate", "server": "browser"},
                {"name": "browser_evaluate", "server": "browser"},
            ],
            "github_analysis": [
                {"name": "github_search_repos", "server": "github"},
                {"name": "github_get_file", "server": "github"},
            ],
            "browser": [
                {"name": "browser_navigate", "server": "browser"},
                {"name": "browser_screenshot", "server": "browser"},
            ],
            "pdf_analysis": [
                {"name": "filesystem_read", "server": "filesystem"},
            ],
            "terminal": [
                {"name": "terminal_execute", "server": "terminal"},
            ],
        }

        selected = tool_map.get(task_type, [])

        return ToolSelectionResult(
            selected_tools=selected,
            reasoning=f"Fallback selection for task type: {task_type}",
            confidence=0.5,
        )

    async def _categorize_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Categorize tasks and add execution metadata.

        Args:
            tasks: List of task dictionaries

        Returns:
            Categorized tasks with execution metadata
        """
        categorized = []

        for task in tasks:
            task_type = task.get("type", "general")

            # Add execution metadata based on task type
            execution_info = self._get_execution_info(task_type)

            categorized_task = {
                **task,
                "execution": execution_info,
                "status": "ready",
            }

            categorized.append(categorized_task)

        return categorized

    def _get_execution_info(self, task_type: str) -> Dict[str, Any]:
        """
        Get execution metadata for a task type.

        Args:
            task_type: Type of task

        Returns:
            Execution metadata dictionary
        """
        execution_map = {
            "web_search": {
                "method": "celery",
                "queue": "research",
                "agent": "web_research",
                "timeout": 60,
            },
            "github_analysis": {
                "method": "celery",
                "queue": "research",
                "agent": "github",
                "timeout": 120,
            },
            "pdf_analysis": {
                "method": "celery",
                "queue": "research",
                "agent": "pdf_rag",
                "timeout": 180,
            },
            "browser": {
                "method": "celery",
                "queue": "browser",
                "agent": "browser_automation",
                "timeout": 300,
            },
            "general": {
                "method": "async",
                "queue": None,
                "agent": "general",
                "timeout": 60,
            },
        }

        return execution_map.get(task_type, execution_map["general"])
