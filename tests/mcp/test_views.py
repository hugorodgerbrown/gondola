"""Tests for apps/mcp/views.py: the shared auth contract, then the protocol."""

import json
from typing import Any

import pytest
from django.test import Client
from mcp_auth.testing import MCPAuthContract

from apps.mcp import views
from apps.mcp.tools import TOOLS
from tests.factories import UserFactory


class TestMCPAuth(MCPAuthContract):
    """Every Titan MCP server passes the same OAuth contract."""

    mcp_path = "/mcp"

    def make_allowed_user(self, django_user_model: Any) -> Any:
        """A user who may connect: any active account."""
        return UserFactory.create()

    def make_refused_user(self, django_user_model: Any) -> Any:
        """A user who may not connect: an inactive account."""
        return UserFactory.create(is_active=False)


def test_initialize_and_list_tools() -> None:
    """Initialize names the server; tools/list lists every tool."""
    init = views._dispatch(None, "initialize", {"protocolVersion": "2025-06-18"})
    assert init["serverInfo"]["name"] == "gondola"
    assert init["protocolVersion"] == "2025-06-18"
    assert views._dispatch(None, "initialize", {})["protocolVersion"] == "2025-11-25"
    names = {t["name"] for t in views._dispatch(None, "tools/list", {})["tools"]}
    assert names == set(TOOLS)


def test_writes_are_not_read_only() -> None:
    """Only set_days and clear_days say they change anything."""
    writers = {
        t["name"]
        for t in views._dispatch(None, "tools/list", {})["tools"]
        if not t["annotations"]["readOnlyHint"]
    }
    assert writers == {"set_days", "clear_days"}


def call_endpoint(client: Client, body: Any, headers: dict[str, str] | None = None) -> Any:
    """POST ``body`` to /mcp with a valid bearer token for an ordinary user."""
    token = TestMCPAuth().token_for(UserFactory.create())
    return client.post(
        "/mcp",
        body if isinstance(body, str) else json.dumps(body),
        content_type="application/json",
        headers={"Authorization": f"Bearer {token}", **(headers or {})},
    )


def rpc(method: str, params: Any) -> dict[str, Any]:
    """Return a JSON-RPC request body."""
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        ("{nope", 400, -32700),
        ({"jsonrpc": "1.0"}, 400, -32600),
        (rpc("nope", {}), 200, -32601),
        (rpc("tools/list", "x"), 200, -32602),
        (rpc("tools/call", {"name": "x"}), 200, -32602),
        (rpc("tools/call", {"name": "my_days", "arguments": "x"}), 200, -32602),
    ],
)
def test_protocol_errors(client: Client, body: Any, status: int, code: int) -> None:
    """Malformed JSON-RPC gets the standard error codes."""
    response = call_endpoint(client, body)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


@pytest.mark.django_db
def test_notifications_get_202_and_old_versions_are_refused(client: Client) -> None:
    """A notification needs no answer; an unknown protocol version is refused."""
    notification = {"jsonrpc": "2.0", "method": "initialized"}
    assert call_endpoint(client, notification).status_code == 202
    response = call_endpoint(
        client,
        {"jsonrpc": "2.0", "id": 1, "method": "ping"},
        {"MCP-Protocol-Version": "1999-01-01"},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_ping_with_a_token(client: Client) -> None:
    """A valid token reaches the tools."""
    response = call_endpoint(client, {"jsonrpc": "2.0", "id": 7, "method": "ping"})
    assert response.json() == {"jsonrpc": "2.0", "id": 7, "result": {}}


@pytest.mark.django_db
def test_a_tool_call_answers_as_the_token_user(client: Client) -> None:
    """tools/call runs the tool and returns its result as text and structure."""
    response = call_endpoint(client, rpc("tools/call", {"name": "my_days"}))
    result = response.json()["result"]
    assert result["structuredContent"] == {"days": []}
    assert json.loads(result["content"][0]["text"]) == {"days": []}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("tool", "heading"),
    [("privacy_policy", "# Privacy notice"), ("terms_of_service", "# Terms"), ("help", "# Help")],
)
def test_public_pages_come_back_as_markdown(client: Client, tool: str, heading: str) -> None:
    """The text content is the Markdown itself; structuredContent adds title and URL."""
    result = call_endpoint(client, rpc("tools/call", {"name": tool})).json()["result"]
    text = result["content"][0]["text"]
    assert heading in text
    assert text == result["structuredContent"]["markdown"]
    assert result["structuredContent"]["url"].startswith("http")


@pytest.mark.django_db
def test_a_tool_error_is_readable(client: Client) -> None:
    """A bad argument is an isError result, not a protocol error."""
    body = rpc("tools/call", {"name": "find_resort", "arguments": {}})
    result = call_endpoint(client, body).json()["result"]
    assert result["isError"] is True
    assert result["content"][0]["text"] == "query is required."


@pytest.mark.django_db
def test_endpoint_refuses_anonymous_calls(client: Client) -> None:
    """No bearer token, no tools: a 401 that starts OAuth discovery."""
    response = client.post("/mcp", json.dumps(rpc("ping", {})), content_type="application/json")
    assert response.status_code == 401
    assert "resource_metadata" in response["WWW-Authenticate"]


@pytest.mark.django_db
def test_endpoint_refuses_a_deactivated_account(client: Client) -> None:
    """Deactivating an account cuts its connected clients off at once."""
    user = UserFactory.create()
    token = TestMCPAuth().token_for(user)
    user.is_active = False
    user.save()
    response = client.post(
        "/mcp",
        json.dumps(rpc("ping", {})),
        content_type="application/json",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_account_page_offers_connected_apps(client: Client) -> None:
    """Everyone's account page says how to connect and links to their apps."""
    client.force_login(UserFactory.create())
    page = client.get("/app/account/").content.decode()
    assert "/oauth/connected/" in page
    assert "/mcp" in page


@pytest.mark.django_db
def test_connected_apps_page_uses_the_site_layout(client: Client) -> None:
    """mcp-auth's pages render inside Gondola's own layout."""
    client.force_login(UserFactory.create())
    page = client.get("/oauth/connected/").content.decode()
    assert "Connected apps" in page
    assert "topbar" in page
