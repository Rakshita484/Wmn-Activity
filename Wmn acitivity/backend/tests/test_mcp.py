"""
test_mcp.py — Integration Tests for MCP Protocol Server & FastAPI REST Endpoints

Validates:
  1. REST CRUD for 5G slices (GET, PUT)
  2. REST node power toggling with link cascade
  3. REST routing policy modification and telemetry retrieval
  4. MCP JSON-RPC 2.0 handshake and capability negotiation
  5. MCP tool discovery (tools/list) — all 6 tools verified
  6. MCP tool execution — list_slices, modify_slice_qos, get_network_health,
     route_optimize, toggle_node_status, trigger_congestion_leak
  7. MCP resource discovery (resources/list) and resolution (resources/read)
  8. MCP prompt template retrieval (prompts/list, prompts/get)
  9. MCP error handling — invalid JSON-RPC, unknown methods, missing tools
"""
import pytest
import json
from fastapi.testclient import TestClient
from backend.app.main import app, simulator, mcp_server
from backend.app.database import SessionLocal, SliceModel, NodeModel, LinkModel


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


def _mcp_rpc(client, method, params=None, msg_id="test-id"):
    """Helper to send a standard JSON-RPC 2.0 request to the MCP endpoint."""
    payload = {
        "jsonrpc": "2.0",
        "id": msg_id,
        "method": method,
        "params": params or {}
    }
    return client.post("/api/mcp/rpc", json=payload)


# ============================================================
# 1. REST CRUD FOR NETWORK SLICES
# ============================================================

class TestRESTSlices:
    """Verify REST API for slice management."""

    def test_get_all_slices(self, client):
        """GET /api/slices/ must return all three standard 5G slices."""
        resp = client.get("/api/slices/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 3
        types = {s["type"] for s in data}
        assert types >= {"eMBB", "URLLC", "mMTC"}

    def test_get_single_slice_by_type(self, client):
        """GET /api/slices/URLLC must return URLLC slice details."""
        resp = client.get("/api/slices/URLLC")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "URLLC"
        assert data["priority"] == 1  # Highest priority

    def test_get_nonexistent_slice_returns_404(self, client):
        """GET /api/slices/INVALID must return 404."""
        resp = client.get("/api/slices/INVALID")
        assert resp.status_code == 404

    def test_update_slice_qos_parameters(self, client):
        """PUT /api/slices/eMBB must update bandwidth and latency in DB."""
        payload = {
            "allocated_bandwidth": 160.0,
            "latency_limit": 40.0,
            "priority": 2,
            "status": "active"
        }
        resp = client.put("/api/slices/eMBB", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["allocated_bandwidth"] == 160.0
        assert data["latency_limit"] == 40.0

        # Verify persisted in database
        db = SessionLocal()
        s = db.query(SliceModel).filter(SliceModel.type == "eMBB").first()
        assert s.allocated_bandwidth == 160.0
        db.close()

    def test_update_nonexistent_slice_returns_404(self, client):
        """PUT /api/slices/INVALID must return 404."""
        resp = client.put("/api/slices/INVALID", json={"allocated_bandwidth": 50.0})
        assert resp.status_code == 404


# ============================================================
# 2. REST NODE TOGGLING WITH LINK CASCADE
# ============================================================

class TestRESTNodeToggling:
    """Verify node power control and cascading link updates."""

    def test_node_offline_cascade(self, client):
        """Disabling Router-C must cascade offline to all connected links."""
        resp = client.put("/api/network/nodes/Router-C/status",
                          json={"status": "offline"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "offline"

        # Verify connected links are also offline
        db = SessionLocal()
        links = db.query(LinkModel).filter(
            (LinkModel.source_id == "Router-C") | (LinkModel.target_id == "Router-C")
        ).all()
        for l in links:
            assert l.status == "offline", f"Link {l.source_id}->{l.target_id} should be offline"
        db.close()

        # Restore
        client.put("/api/network/nodes/Router-C/status", json={"status": "online"})

    def test_node_online_restore(self, client):
        """Restoring Router-C must cascade online to all connected links."""
        # First disable
        client.put("/api/network/nodes/Router-C/status", json={"status": "offline"})
        # Then restore
        resp = client.put("/api/network/nodes/Router-C/status",
                          json={"status": "online"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "online"

        db = SessionLocal()
        links = db.query(LinkModel).filter(
            (LinkModel.source_id == "Router-C") | (LinkModel.target_id == "Router-C")
        ).all()
        for l in links:
            assert l.status == "online", f"Link {l.source_id}->{l.target_id} should be online"
        db.close()

    def test_toggle_nonexistent_node_returns_404(self, client):
        """Toggling a non-existent node must return 404."""
        resp = client.put("/api/network/nodes/FAKE-NODE/status",
                          json={"status": "offline"})
        assert resp.status_code == 404


# ============================================================
# 3. REST ROUTING POLICY & TELEMETRY
# ============================================================

class TestRESTNetwork:
    """Verify routing policy changes and telemetry retrieval."""

    def test_set_routing_policy(self, client):
        """POST /api/network/routing-policy must change the simulator routing policy."""
        for policy in ["shortest_hop", "snr_based", "load_balanced"]:
            resp = client.post("/api/network/routing-policy",
                               json={"policy": policy})
            assert resp.status_code == 200
            assert resp.json()["policy"] == policy

    def test_invalid_routing_policy_returns_400(self, client):
        """Invalid routing policy must return 400."""
        resp = client.post("/api/network/routing-policy",
                           json={"policy": "random_policy"})
        assert resp.status_code == 400

    def test_get_network_nodes(self, client):
        """GET /api/network/nodes must return all 11 nodes."""
        resp = client.get("/api/network/nodes")
        assert resp.status_code == 200
        assert len(resp.json()) >= 11

    def test_get_network_links(self, client):
        """GET /api/network/links must return all 14 links."""
        resp = client.get("/api/network/links")
        assert resp.status_code == 200
        assert len(resp.json()) >= 14

    def test_get_telemetry_payload(self, client):
        """GET /api/network/telemetry must return full simulation payload."""
        resp = client.get("/api/network/telemetry")
        assert resp.status_code == 200
        data = resp.json()
        assert "tick" in data
        assert "nodes" in data
        assert "links" in data
        assert "metrics" in data


# ============================================================
# 4. MCP JSON-RPC 2.0 HANDSHAKE & CAPABILITY NEGOTIATION
# ============================================================

class TestMCPHandshake:
    """Verify the MCP initialization handshake and protocol metadata."""

    def test_initialize_returns_protocol_version(self, client):
        """initialize must return protocolVersion 2024-11-05."""
        resp = _mcp_rpc(client, "initialize", msg_id="init-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "init-1"
        result = data["result"]
        assert result["protocolVersion"] == "2024-11-05"
        assert result["serverInfo"]["name"] == "5g-wmn-mcp-slicing-manager"
        assert result["serverInfo"]["version"] == "1.0.0"

    def test_initialize_advertises_capabilities(self, client):
        """initialize must advertise tools, resources, and prompts capabilities."""
        resp = _mcp_rpc(client, "initialize")
        caps = resp.json()["result"]["capabilities"]
        assert "tools" in caps
        assert "resources" in caps
        assert "prompts" in caps

    def test_invalid_jsonrpc_version(self, client):
        """Request with jsonrpc != '2.0' must return error code -32600."""
        payload = {"jsonrpc": "1.0", "id": "bad", "method": "initialize", "params": {}}
        resp = client.post("/api/mcp/rpc", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == -32600

    def test_unknown_method_returns_error(self, client):
        """Unknown method must return error code -32601 (Method not found)."""
        resp = _mcp_rpc(client, "nonexistent/method")
        data = resp.json()
        assert "error" in data
        assert data["error"]["code"] == -32601


# ============================================================
# 5. MCP TOOL DISCOVERY
# ============================================================

class TestMCPToolDiscovery:
    """Verify tools/list returns all 6 registered MCP tools."""

    def test_tools_list_returns_all_tools(self, client):
        """tools/list must return exactly 6 tools with correct names."""
        resp = _mcp_rpc(client, "tools/list")
        tools = resp.json()["result"]["tools"]
        names = {t["name"] for t in tools}
        expected = {"list_slices", "modify_slice_qos", "get_network_health",
                    "route_optimize", "toggle_node_status", "trigger_congestion_leak"}
        assert names == expected

    def test_each_tool_has_input_schema(self, client):
        """Every tool must have a valid inputSchema with type 'object'."""
        resp = _mcp_rpc(client, "tools/list")
        for tool in resp.json()["result"]["tools"]:
            assert "inputSchema" in tool, f"Tool {tool['name']} missing inputSchema"
            assert tool["inputSchema"]["type"] == "object"


# ============================================================
# 6. MCP TOOL EXECUTION — ALL 6 TOOLS
# ============================================================

class TestMCPToolExecution:
    """Execute each MCP tool and verify response schema compliance."""

    def test_tool_list_slices(self, client):
        """list_slices must return success=True with slice array."""
        resp = _mcp_rpc(client, "tools/call", {
            "name": "list_slices", "arguments": {}
        })
        content = json.loads(resp.json()["result"]["content"][0]["text"])
        assert content["success"] is True
        assert len(content["slices"]) >= 3

    def test_tool_modify_slice_qos(self, client):
        """modify_slice_qos must update URLLC bandwidth and return updated slice."""
        resp = _mcp_rpc(client, "tools/call", {
            "name": "modify_slice_qos",
            "arguments": {"slice_type": "URLLC", "bandwidth": 30.0, "priority": 1}
        })
        content = json.loads(resp.json()["result"]["content"][0]["text"])
        assert content["success"] is True
        assert content["updated_slice"]["allocated_bandwidth_mbps"] == 30.0

    def test_tool_get_network_health(self, client):
        """get_network_health must return routers, links, and slice_telemetry."""
        resp = _mcp_rpc(client, "tools/call", {
            "name": "get_network_health", "arguments": {}
        })
        content = json.loads(resp.json()["result"]["content"][0]["text"])
        assert content["success"] is True
        assert "routers" in content
        assert "links" in content
        assert "slice_telemetry" in content

    def test_tool_route_optimize(self, client):
        """route_optimize must accept valid policies and return success."""
        for policy in ["shortest_hop", "snr_based", "load_balanced"]:
            resp = _mcp_rpc(client, "tools/call", {
                "name": "route_optimize",
                "arguments": {"policy": policy}
            })
            content = json.loads(resp.json()["result"]["content"][0]["text"])
            assert content["success"] is True

    def test_tool_toggle_node_status(self, client):
        """toggle_node_status must switch Router-D offline then online."""
        # Offline
        resp = _mcp_rpc(client, "tools/call", {
            "name": "toggle_node_status",
            "arguments": {"node_id": "Router-D", "status": "offline"}
        })
        content = json.loads(resp.json()["result"]["content"][0]["text"])
        assert content["success"] is True

        # Restore online
        resp = _mcp_rpc(client, "tools/call", {
            "name": "toggle_node_status",
            "arguments": {"node_id": "Router-D", "status": "online"}
        })
        content = json.loads(resp.json()["result"]["content"][0]["text"])
        assert content["success"] is True

    def test_tool_trigger_congestion(self, client):
        """trigger_congestion_leak must activate and deactivate congestion."""
        # Activate
        resp = _mcp_rpc(client, "tools/call", {
            "name": "trigger_congestion_leak",
            "arguments": {"status": True}
        })
        content = json.loads(resp.json()["result"]["content"][0]["text"])
        assert content["success"] is True
        assert "activated" in content["message"]

        # Deactivate
        resp = _mcp_rpc(client, "tools/call", {
            "name": "trigger_congestion_leak",
            "arguments": {"status": False}
        })
        content = json.loads(resp.json()["result"]["content"][0]["text"])
        assert content["success"] is True
        assert "deactivated" in content["message"]

    def test_tool_unknown_returns_error(self, client):
        """Calling an unknown tool must return success=False."""
        resp = _mcp_rpc(client, "tools/call", {
            "name": "nonexistent_tool", "arguments": {}
        })
        content = json.loads(resp.json()["result"]["content"][0]["text"])
        assert content["success"] is False


# ============================================================
# 7. MCP RESOURCE DISCOVERY & RESOLUTION
# ============================================================

class TestMCPResources:
    """Verify MCP resource listing and content reading."""

    def test_resources_list(self, client):
        """resources/list must return topology and metrics URIs."""
        resp = _mcp_rpc(client, "resources/list")
        resources = resp.json()["result"]["resources"]
        uris = {r["uri"] for r in resources}
        assert "network://topology" in uris
        assert "network://metrics" in uris

    def test_read_topology_resource(self, client):
        """resources/read for network://topology must return nodes and links."""
        resp = _mcp_rpc(client, "resources/read", {"uri": "network://topology"})
        result = resp.json()["result"]
        content = json.loads(result["contents"][0]["text"])
        assert "nodes" in content
        assert "links" in content
        assert len(content["nodes"]) >= 11
        assert len(content["links"]) >= 14

    def test_read_metrics_resource(self, client):
        """resources/read for network://metrics must return slice telemetry data."""
        resp = _mcp_rpc(client, "resources/read", {"uri": "network://metrics"})
        result = resp.json()["result"]
        content = json.loads(result["contents"][0]["text"])
        assert "eMBB" in content
        assert "URLLC" in content
        assert "mMTC" in content


# ============================================================
# 8. MCP PROMPT TEMPLATE RETRIEVAL
# ============================================================

class TestMCPPrompts:
    """Verify MCP prompt discovery and content retrieval."""

    def test_prompts_list(self, client):
        """prompts/list must return resolve_congestion and routing_recovery."""
        resp = _mcp_rpc(client, "prompts/list")
        prompts = resp.json()["result"]["prompts"]
        names = {p["name"] for p in prompts}
        assert "resolve_congestion" in names
        assert "routing_recovery" in names

    def test_get_resolve_congestion_prompt(self, client):
        """prompts/get for resolve_congestion must return structured messages."""
        resp = _mcp_rpc(client, "prompts/get", {"name": "resolve_congestion"})
        result = resp.json()["result"]
        assert "messages" in result
        assert len(result["messages"]) >= 1
        assert result["messages"][0]["role"] == "user"
        # Should mention key tools in the prompt text
        text = result["messages"][0]["content"]["text"]
        assert "get_network_health" in text
        assert "modify_slice_qos" in text

    def test_get_routing_recovery_prompt(self, client):
        """prompts/get for routing_recovery must return structured messages."""
        resp = _mcp_rpc(client, "prompts/get", {"name": "routing_recovery"})
        result = resp.json()["result"]
        assert "messages" in result
        text = result["messages"][0]["content"]["text"]
        assert "route_optimize" in text


# ============================================================
# 9. MCP REST CONVENIENCE ENDPOINTS
# ============================================================

class TestMCPRESTEndpoints:
    """Verify the convenience REST endpoints for MCP discovery."""

    def test_get_mcp_tools_endpoint(self, client):
        """GET /api/mcp/tools must return the tool list."""
        resp = client.get("/api/mcp/tools")
        assert resp.status_code == 200
        assert len(resp.json()) >= 6

    def test_get_mcp_resources_endpoint(self, client):
        """GET /api/mcp/resources must return the resource list."""
        resp = client.get("/api/mcp/resources")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    def test_get_mcp_prompts_endpoint(self, client):
        """GET /api/mcp/prompts must return the prompt list."""
        resp = client.get("/api/mcp/prompts")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2
