"""
server.py

MCP (Model Context Protocol) server for the travel planning tools.

Exposes weather lookup, knowledge base search, and place information
as MCP-compatible tools so any MCP-enabled client can call them in a
standardized way without depending on internal service implementations.

Run this server standalone with:
    python -m app.mcp.server
"""

import asyncio
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from app.services.weather_service import get_weather_summary
from app.services.knowledge_service import search_knowledge
from app.schemas.mcp import TOOL_ARGUMENT_MODELS
from app.guardrails.input_guardrails import validate_search_term
from app.guardrails.output_guardrails import wrap_untrusted_content

logger = logging.getLogger(__name__)

# Initialize the MCP server with a unique name
app = Server("travel-planner")

TOOL_DESCRIPTIONS = {
    "get_weather": "Get the current weather forecast for a travel destination.",
    "search_knowledge": "Search the travel knowledge base for tips and guides about a destination.",
    "get_place_info": "Find points of interest of a specific type at a destination.",
}


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    """Return the list of tools this MCP server exposes.

    Builds each tool's input schema from the same Pydantic argument models
    the REST endpoint validates against, so both paths agree on what a
    valid call looks like.

    Returns:
        A list of Tool definitions describing the available travel tools,
        their input schemas, and what they do.
    """
    return [
        types.Tool(
            name=tool_name,
            description=TOOL_DESCRIPTIONS[tool_name],
            inputSchema=args_model.model_json_schema(),
        )
        for tool_name, args_model in TOOL_ARGUMENT_MODELS.items()
    ]


@app.call_tool()
async def call_tool(
    name: str,
    arguments: dict,
) -> list[types.TextContent]:
    """Execute a tool call and return the result as MCP TextContent.

    Dispatches to the appropriate service function based on the tool name.
    Any failure is logged and re-raised so the MCP SDK's own call_tool
    wrapper can report it as a proper tool error (isError=true) instead of
    a successful text result.

    Args:
        name: The name of the tool to call.
        arguments: The tool input arguments as a dict.

    Returns:
        A list containing a single TextContent with the tool result.

    Raises:
        Exception: Re-raised after logging, so the SDK marks the call as
            failed instead of reporting it as a successful text result.
    """
    try:
        if name == "get_weather":
            result = await get_weather_summary(arguments["destination"])

        elif name == "search_knowledge":
            result = await search_knowledge(
                arguments["destination"],
                arguments.get("query", ""),
            )
            if not result:
                result = f"No knowledge found for {arguments['destination']}"
            else:
                result = wrap_untrusted_content(result)

        elif name == "get_place_info":
            import httpx
            destination = arguments["destination"]
            place_type = arguments["place_type"]
            validate_search_term(destination, "destination")
            validate_search_term(place_type, "place_type")
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
                    result = f"Places of type '{place_type}' in {destination}: {', '.join(names)}"
                else:
                    result = f"No {place_type} found in {destination}"
        else:
            raise ValueError(f"Unknown tool: {name}")

    except Exception as e:
        logger.error("MCP tool call failed for %s: %s", name, str(e))
        raise

    return [types.TextContent(type="text", text=result)]


async def main() -> None:
    """Run the MCP server over stdio.

    This allows any MCP-compatible client to connect to the travel
    planning tools by running this module as a subprocess.
    """
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
