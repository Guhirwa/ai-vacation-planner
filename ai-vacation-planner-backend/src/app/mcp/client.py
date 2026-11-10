"""
client.py

Lightweight MCP tool caller for use within the FastAPI application.

Instead of spawning a subprocess to talk to the MCP server, this module
calls the same underlying service functions directly while presenting
them through an MCP-compatible interface. This keeps the MCP server
definition as the single source of truth for tool schemas while avoiding
the overhead of subprocess communication for in-process calls.
"""

import logging
from app.services.weather_service import get_weather_summary
from app.services.knowledge_service import search_knowledge

logger = logging.getLogger(__name__)


async def call_mcp_tool(name: str, arguments: dict) -> str:
    """Call a travel planning tool by its MCP tool name.

    Dispatches to the appropriate service function based on the tool name.
    This mirrors the MCP server's call_tool handler so the same tool
    definitions work both in-process and over the MCP stdio protocol.

    Args:
        name: The MCP tool name to call.
        arguments: The tool input arguments as a dict.

    Returns:
        The tool result as a plain string.
    """
    try:
        if name == "get_weather":
            return await get_weather_summary(arguments["destination"])

        elif name == "search_knowledge":
            result = await search_knowledge(
                arguments["destination"],
                arguments.get("query", ""),
            )
            return result or f"No knowledge found for {arguments['destination']}"

        elif name == "get_place_info":
            import httpx
            destination = arguments["destination"]
            place_type = arguments["place_type"]
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={
                        "q": f"{place_type} in {destination}",
                        "format": "json",
                        "limit": 5,
                    },
                    headers={"User-Agent": "ai-vacation-planner/1.0"},
                    timeout=10,
                )
                places = response.json()
                if places:
                    names = [p.get("display_name", "Unknown").split(",")[0] for p in places]
                    return f"Places of type '{place_type}' in {destination}: {', '.join(names)}"
                return f"No {place_type} found in {destination}"

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        logger.error("MCP tool call failed for %s: %s", name, str(e))
        return f"Tool {name} is temporarily unavailable"
