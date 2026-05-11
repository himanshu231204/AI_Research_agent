# Task Context: Phase 4 - MCP Integration + Browser Automation + Tool Ecosystem

Session ID: 2026-05-11-mcp-browser-automation
Created: 2026-05-11T23:13:00Z
Status: in_progress

## Current Request

Implement Phase 4 of the Autonomous AI Research Operating System: MCP Integration + Browser Automation + Tool Ecosystem. This evolves the platform from "autonomous research intelligence" into a "tool-using autonomous operating system" that can:
- dynamically use tools
- browse websites autonomously
- analyze GitHub repositories
- interact with filesystems
- execute terminal commands safely
- support MCP protocol servers
- run browser automation securely
- orchestrate tools across distributed workers

## Context Files (Standards to Follow)
- `.opencode/context/core/standards/code-quality.md` - Code quality standards (pure functions, immutability, composition, small functions, dependency injection)
- `.opencode/context/development/principles/clean-code.md` - Python clean code principles
- `.opencode/context/openagents-repo/plugins/context/capabilities/tools.md` - Tool building patterns
- `.opencode/context/openagents-repo/plugins/context/architecture/overview.md` - Plugin architecture

## Reference Files (Source Material to Look At)
- `AGENT.md` - Architecture source of truth (1021 lines)
- `agents/router.py` - Existing router agent to upgrade
- `workers/celery_app.py` - Celery workers
- `graphs/research_graph.py` - LangGraph orchestrator
- `api/main.py` - API entry point

## External Docs Fetched
- Playwright Python API patterns (via ExternalScout)
- MCP protocol specification (via ExternalScout)

## Components
1. **MCP Architecture** - Client system, registry, servers, adapters, transport layer
2. **Browser Automation** - Playwright infrastructure, sandbox isolation, worker pool
3. **Tool Integration** - GitHub MCP, Filesystem MCP, Terminal MCP
4. **Tool Invocation Layer** - Dynamic tool registration and execution
5. **Router Agent Upgrade** - Autonomous tool selection with reasoning

## Constraints
- Maintain compatibility with ALL previous phases
- Do NOT simplify the distributed architecture
- Do NOT rewrite working systems unnecessarily
- Browser execution MUST remain isolated and sandboxed
- The API process MUST NEVER execute Playwright directly

## Exit Criteria
- [ ] MCP client system implemented with async communication
- [ ] MCP Registry for dynamic tool registration
- [ ] Browser automation infrastructure with Playwright
- [ ] Browser sandbox isolation (Docker container)
- [ ] Browser worker pool with queues
- [ ] GitHub MCP integration
- [ ] Filesystem MCP integration
- [ ] Terminal MCP integration
- [ ] Tool invocation layer
- [ ] Router agent upgraded for autonomous tool selection