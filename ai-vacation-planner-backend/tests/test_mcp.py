"""Tests for the MCP tools: REST argument validation and the stdio server's error reporting."""

import pytest

from app.mcp.server import app as mcp_app
from mcp import types


def test_list_tools(client, auth_headers):
    response = client.get("/mcp/tools", headers=auth_headers)
    assert response.status_code == 200
    names = {tool["name"] for tool in response.json()["tools"]}
    assert names == {"get_weather", "search_knowledge", "get_place_info"}


def test_call_unknown_tool_is_rejected(client, auth_headers):
    response = client.post(
        "/mcp/call",
        json={"tool": "bogus_tool", "arguments": {}},
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_call_requires_auth(client):
    response = client.post(
        "/mcp/call",
        json={"tool": "get_weather", "arguments": {"destination": "Paris"}},
        headers={},
    )
    assert response.status_code == 403


def test_get_weather_rejects_empty_arguments(client, auth_headers):
    response = client.post(
        "/mcp/call",
        json={"tool": "get_weather", "arguments": {}},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_get_place_info_rejects_missing_place_type(client, auth_headers):
    response = client.post(
        "/mcp/call",
        json={"tool": "get_place_info", "arguments": {"destination": "Paris"}},
        headers=auth_headers,
    )
    assert response.status_code == 422


def test_search_knowledge_without_query_is_accepted(client, auth_headers):
    """query is genuinely optional, the search falls back to destination alone."""
    response = client.post(
        "/mcp/call",
        json={"tool": "search_knowledge", "arguments": {"destination": "Paris"}},
        headers=auth_headers,
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_stdio_server_marks_a_failed_call_as_an_error():
    handler = mcp_app.request_handlers[types.CallToolRequest]
    request = types.CallToolRequest(
        params=types.CallToolRequestParams(name="bogus_tool", arguments={})
    )
    result = await handler(request)
    assert result.root.isError is True


@pytest.mark.asyncio
async def test_stdio_server_handles_a_call_right_after_a_failed_one():
    handler = mcp_app.request_handlers[types.CallToolRequest]

    failing_request = types.CallToolRequest(
        params=types.CallToolRequestParams(name="bogus_tool", arguments={})
    )
    await handler(failing_request)

    ok_request = types.CallToolRequest(
        params=types.CallToolRequestParams(
            name="search_knowledge", arguments={"destination": "Paris"}
        )
    )
    result = await handler(ok_request)
    assert result.root.isError is False
