"""
mcp.py

Router exposing MCP tool calls as REST endpoints.

Allows clients to call any MCP-registered travel tool via a simple
POST request without needing to implement the MCP protocol themselves.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.mcp.client import call_mcp_tool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["MCP Tools"])


class MCPToolRequest(BaseModel):
    """Request schema for calling an MCP tool.

    Attributes:
        tool: The name of the MCP tool to call.
        arguments: The input arguments for the tool as a key-value dict.
    """
    tool: str
    arguments: dict


class MCPToolResponse(BaseModel):
    """Response schema for an MCP tool call.

    Attributes:
        tool: The name of the tool that was called.
        result: The plain-text result returned by the tool.
    """
    tool: str
    result: str


@router.post("/call", response_model=MCPToolResponse, status_code=200)
async def call_tool(
    request: MCPToolRequest,
    current_user: User = Depends(get_current_user),
) -> MCPToolResponse:
    """Call a travel planning tool by its MCP tool name.

    Exposes all MCP-registered tools (get_weather, search_knowledge,
    get_place_info) as a single REST endpoint so clients can call any
    tool without implementing the MCP protocol directly.

    Args:
        request: The tool name and input arguments.
        current_user: The authenticated user making the request.

    Returns:
        An MCPToolResponse containing the tool name and its result.

    Raises:
        HTTPException(400): If the tool name is not recognised.
    """
    allowed_tools = {"get_weather", "search_knowledge", "get_place_info"}
    if request.tool not in allowed_tools:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown tool: {request.tool}. Allowed tools: {', '.join(sorted(allowed_tools))}"
        )

    result = await call_mcp_tool(request.tool, request.arguments)
    return MCPToolResponse(tool=request.tool, result=result)


@router.get("/tools", status_code=200)
async def list_tools(
    current_user: User = Depends(get_current_user),
) -> dict:
    """List all available MCP tools and their descriptions.

    Returns:
        A dict containing the list of available tool names and descriptions.
    """
    return {
        "tools": [
            {
                "name": "get_weather",
                "description": "Get the current weather forecast for a travel destination.",
                "arguments": {"destination": "string"},
            },
            {
                "name": "search_knowledge",
                "description": "Search the travel knowledge base for tips and guides.",
                "arguments": {"destination": "string", "query": "string"},
            },
            {
                "name": "get_place_info",
                "description": "Find points of interest of a specific type at a destination.",
                "arguments": {"destination": "string", "place_type": "string"},
            },
        ]
    }
