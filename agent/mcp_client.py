"""Dynamic MCP Client for ExceptionOps Agent.

Dynamically discovers tools from the MCP server without hardcoding tool schemas
in the graph logic. Provides risk lookup and structured execution.
"""

import asyncio
import json
import logging
from typing import Any, Literal

from mcp_server.risk import TOOL_RISK, is_high_risk
from mcp_server.server import mcp as mcp_server_instance

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for discovering and executing MCP server tools dynamically."""

    def __init__(self):
        self._server = mcp_server_instance
        self._cached_tools: dict[str, dict[str, Any]] = {}

    def discover_tools(self) -> list[dict[str, Any]]:
        """Query the MCP server dynamically to list all registered tools."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # In active loop (e.g. within async server or test)
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    tools = executor.submit(asyncio.run, self._server.list_tools()).result()
            else:
                tools = loop.run_until_complete(self._server.list_tools())
        except RuntimeError:
            tools = asyncio.run(self._server.list_tools())

        discovered = []
        for tool in tools:
            name = tool.name
            desc = tool.description or ""
            risk = TOOL_RISK.get(name, "high" if "high" in desc.lower() else "low")
            tool_dict = {
                "name": name,
                "description": desc,
                "risk": risk,
                "input_schema": getattr(tool, "input_schema", {}),
            }
            self._cached_tools[name] = tool_dict
            discovered.append(tool_dict)

        return discovered

    def get_tool_risk(self, tool_name: str) -> Literal["low", "high"]:
        """Return the code-enforced risk level for a given tool."""
        if not self._cached_tools:
            self.discover_tools()
        return "high" if is_high_risk(tool_name) else "low"

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool dynamically through the MCP server and parse output."""
        if not self._cached_tools:
            self.discover_tools()

        if tool_name not in self._cached_tools:
            return {
                "status": "error",
                "error": f"Tool '{tool_name}' is not registered on the MCP server.",
            }

        try:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        result = executor.submit(
                            asyncio.run, self._server.call_tool(tool_name, arguments)
                        ).result()
                else:
                    result = loop.run_until_complete(self._server.call_tool(tool_name, arguments))
            except RuntimeError:
                result = asyncio.run(self._server.call_tool(tool_name, arguments))

            # Parse content from TextContent
            if hasattr(result, "content") and result.content:
                text_payload = result.content[0].text
                try:
                    return json.loads(text_payload)
                except json.JSONDecodeError:
                    return {"status": "success", "text": text_payload}
            return {"status": "success", "result": str(result)}

        except Exception as e:
            logger.error("Error executing MCP tool '%s': %s", tool_name, e)
            return {
                "status": "error",
                "error": f"Execution error in tool '{tool_name}': {str(e)}",
            }


# Shared singleton instance
mcp_client = MCPClient()

