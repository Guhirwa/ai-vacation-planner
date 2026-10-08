"""
mcp.py

Pydantic models for MCP tool arguments.

These are the single source of truth for what each tool accepts, used both
to build the stdio MCP server's input schemas and to validate requests on
the REST /mcp/call endpoint, so a bad request is rejected the same way on
both paths instead of only one of them checking.
"""

from typing import Optional
from pydantic import BaseModel, Field


class GetWeatherArgs(BaseModel):
    """Arguments for the get_weather tool."""

    destination: str = Field(
        ..., min_length=1, description="The city or place to get weather for."
    )


class SearchKnowledgeArgs(BaseModel):
    """Arguments for the search_knowledge tool.

    query is genuinely optional: the underlying search falls back to
    searching by destination alone when it is not provided.
    """

    destination: str = Field(
        ..., min_length=1, description="The destination to search knowledge for."
    )
    query: Optional[str] = Field(
        None,
        description="A specific aspect to search for, e.g. hidden gems, local food.",
    )


class GetPlaceInfoArgs(BaseModel):
    """Arguments for the get_place_info tool."""

    destination: str = Field(
        ..., min_length=1, description="The city or area to search in."
    )
    place_type: str = Field(
        ..., min_length=1, description="The type of place to find, e.g. museums, restaurants, parks."
    )


TOOL_ARGUMENT_MODELS: dict[str, type[BaseModel]] = {
    "get_weather": GetWeatherArgs,
    "search_knowledge": SearchKnowledgeArgs,
    "get_place_info": GetPlaceInfoArgs,
}
