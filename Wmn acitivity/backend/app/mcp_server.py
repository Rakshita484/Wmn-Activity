import sys
import json
import traceback
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from .database import SessionLocal, SliceModel, NodeModel, LinkModel

# Official MCP Specifications Metadata
MCP_VERSION = "2024-11-05"

class MCPServer:
    def __init__(self, simulator_instance=None):
        self.simulator = simulator_instance
        
        # Define tools, resources and prompts according to MCP specification
        self.tools = [
            {
                "name": "list_slices",
                "description": "Retrieve all 5G network slices and their current QoS SLA configurations.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "modify_slice_qos",
                "description": "Dynamically reconfigure 5G QoS slice parameters such as guaranteed bandwidth, target latency budget, scheduling priority, or toggle status.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "slice_type": {"type": "string", "enum": ["eMBB", "URLLC", "mMTC"], "description": "Target slice type to modify"},
                        "bandwidth": {"type": "number", "description": "Guaranteed bandwidth in Mbps (1.0 to 300.0)"},
                        "latency_limit": {"type": "number", "description": "Max acceptable latency SLA in ms (1.0 to 500.0)"},
                        "priority": {"type": "integer", "enum": [1, 2, 3], "description": "Scheduling priority (1 = highest bypass queue, 3 = best effort)"},
                        "status": {"type": "string", "enum": ["active", "inactive"], "description": "Toggle active state of this network slice"}
                    },
                    "required": ["slice_type"]
                }
            },
            {
                "name": "get_network_health",
                "description": "Examine the status of physical wireless mesh routers, current multihop queue depths, physical links capacity, signal quality (SNR) levels, and packet drops.",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "route_optimize",
                "description": "Change the routing cost optimization metrics across the Wireless Mesh Network (WMN) backhaul.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "policy": {
                            "type": "string", 
                            "enum": ["shortest_hop", "snr_based", "load_balanced"],
                            "description": "shortest_hop (minimum hop counts), snr_based (avoids weak radio signals), load_balanced (avoids congested nodes)"
                        }
                    },
                    "required": ["policy"]
                }
            },
            {
                "name": "toggle_node_status",
                "description": "Simulate physical node failure or restoration by toggling a mesh router's power state. Triggers dynamic routing self-healing.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string", "description": "Identifier of the target router (e.g., Router-A, Router-C)"},
                        "status": {"type": "string", "enum": ["online", "offline"], "description": "Power state"}
                    },
                    "required": ["node_id", "status"]
                }
            },
            {
                "name": "trigger_congestion_leak",
                "description": "Simulate a severe traffic congestion event on the eMBB slice by generating excessive load spikes, causing router queues to overflow.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "boolean", "description": "Set true to activate congestion simulation, false to normalize"}
                    },
                    "required": ["status"]
                }
            }
        ]
        
        self.resources = [
            {
                "uri": "network://topology",
                "name": "Active 5G WMN Node Topology",
                "description": "Current coordinate-based layout map of physical routers, clients, gateway core, and their dynamic connection status.",
                "mimeType": "application/json"
            },
            {
                "uri": "network://metrics",
                "name": "Real-time 5G Slice Telemetry",
                "description": "Throughput, average latency, and packet delivery ratio (PDR) values monitored across active slices.",
                "mimeType": "application/json"
            }
        ]
        
        self.prompts = [
            {
                "name": "resolve_congestion",
                "description": "Guide on detecting high packet drops on eMBB due to congestion and using MCP tools to adjust QoS bandwidth and priority.",
                "arguments": []
            },
            {
                "name": "routing_recovery",
                "description": "Analyze mesh network isolation after a router goes offline and execute tools to restore redundant multi-hop path routing.",
                "arguments": []
            }
        ]

    def handle_request(self, request_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse and execute JSON-RPC 2.0 messages from MCP Client."""
        # Standard JSON-RPC fields validation
        if "jsonrpc" not in request_payload or request_payload["jsonrpc"] != "2.0":
            return {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request: missing jsonrpc version"}, "id": request_payload.get("id")}
            
        method = request_payload.get("method")
        msg_id = request_payload.get("id")
        params = request_payload.get("params", {})
        
        try:
            # 1. MCP Initialization Handshake
            if method == "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": MCP_VERSION,
                        "capabilities": {
                            "tools": {},
                            "resources": {},
                            "prompts": {}
                        },
                        "serverInfo": {
                            "name": "5g-wmn-mcp-slicing-manager",
                            "version": "1.0.0"
                        }
                    }
                }
                
            elif method == "initialized":
                # client notification, no response required
                return None
                
            # 2. Tool discovery and execution
            elif method == "tools/list":
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": self.tools}
                }
                
            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                tool_result = self.execute_tool(tool_name, arguments)
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(tool_result, indent=2)
                            }
                        ]
                    }
                }
                
            # 3. Resource discovery and read
            elif method == "resources/list":
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"resources": self.resources}
                }
                
            elif method == "resources/read":
                uri = params.get("uri")
                content = self.read_resource(uri)
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": "application/json",
                                "text": json.dumps(content, indent=2)
                            }
                        ]
                    }
                }
                
            # 4. Prompt templates discovery
            elif method == "prompts/list":
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"prompts": self.prompts}
                }
                
            elif method == "prompts/get":
                prompt_name = params.get("name")
                content = self.get_prompt(prompt_name)
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": content
                }
                
            # Method not found
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Method not found: {method}"}
                }
                
        except Exception as e:
            traceback.print_exc()
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32603, "message": f"Internal Server Error: {str(e)}"}
            }

    # ==========================================
    # TOOL IMPLEMENTATION MODULES
    # ==========================================
    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Route tool names to direct physical database modifications & simulator updates."""
        db = SessionLocal()
        try:
            if tool_name == "list_slices":
                db_slices = db.query(SliceModel).all()
                return {
                    "success": True,
                    "slices": [
                        {
                            "id": s.id,
                            "name": s.name,
                            "type": s.type,
                            "allocated_bandwidth_mbps": s.allocated_bandwidth,
                            "latency_limit_ms": s.latency_limit,
                            "priority": s.priority,
                            "status": s.status
                        }
                        for s in db_slices
                    ]
                }
                
            elif tool_name == "modify_slice_qos":
                slice_type = arguments.get("slice_type")
                db_slice = db.query(SliceModel).filter(SliceModel.type == slice_type).first()
                if not db_slice:
                    return {"success": False, "error": f"Slice type {slice_type} not found."}
                
                # Apply changes to SQLite
                if "bandwidth" in arguments:
                    db_slice.allocated_bandwidth = float(arguments["bandwidth"])
                if "latency_limit" in arguments:
                    db_slice.latency_limit = float(arguments["latency_limit"])
                if "priority" in arguments:
                    db_slice.priority = int(arguments["priority"])
                if "status" in arguments:
                    db_slice.status = arguments["status"]
                    
                db.commit()
                
                # Sync into the running simulator immediately
                if self.simulator:
                    self.simulator.load_from_db()
                    
                return {
                    "success": True,
                    "message": f"QoS params updated successfully for slice {slice_type}",
                    "updated_slice": {
                        "type": db_slice.type,
                        "allocated_bandwidth_mbps": db_slice.allocated_bandwidth,
                        "latency_limit_ms": db_slice.latency_limit,
                        "priority": db_slice.priority,
                        "status": db_slice.status
                    }
                }
                
            elif tool_name == "get_network_health":
                # Extract details from DB and active Simulator
                db_nodes = db.query(NodeModel).all()
                db_links = db.query(LinkModel).all()
                
                node_health = []
                for n in db_nodes:
                    node_q_size = 0
                    if self.simulator and n.id in self.simulator.queues:
                        node_q_size = sum(len(q) for q in self.simulator.queues[n.id].values())
                        
                    node_health.append({
                        "node_id": n.id,
                        "type": n.type,
                        "status": n.status,
                        "waiting_packet_count": node_q_size
                    })
                    
                link_health = []
                for l in db_links:
                    snr = 0.0
                    cap = l.capacity
                    load = 0
                    if self.simulator:
                        snr = self.simulator.get_snr(l.source_id, l.target_id)
                        cap = self.simulator.get_link_capacity({"status": l.status, "source_id": l.source_id, "target_id": l.target_id, "capacity": l.capacity})
                        load = self.simulator.get_link_load(l.source_id, l.target_id)
                        
                    link_health.append({
                        "source": l.source_id,
                        "target": l.target_id,
                        "status": l.status,
                        "signal_quality_snr_db": round(snr, 1) if l.status == "online" else 0.0,
                        "active_capacity_mbps": round(cap, 1) if l.status == "online" else 0.0,
                        "pending_forward_load": load
                    })
                    
                metrics = self.simulator.latest_metrics if self.simulator else {}
                
                return {
                    "success": True,
                    "routers": node_health,
                    "links": link_health,
                    "slice_telemetry": metrics
                }
                
            elif tool_name == "route_optimize":
                policy = arguments.get("policy")
                if self.simulator:
                    self.simulator.routing_policy = policy
                    return {"success": True, "message": f"WMN multi-hop routing optimized to use policy: '{policy}'"}
                return {"success": False, "error": "Simulator instance not active."}
                
            elif tool_name == "toggle_node_status":
                node_id = arguments.get("node_id")
                status = arguments.get("status")
                
                db_node = db.query(NodeModel).filter(NodeModel.id == node_id).first()
                if not db_node:
                    return {"success": False, "error": f"Node {node_id} not found"}
                    
                db_node.status = status
                
                # If node is offline, also disable all physical links connected to it
                db_links = db.query(LinkModel).filter((LinkModel.source_id == node_id) | (LinkModel.target_id == node_id)).all()
                for l in db_links:
                    l.status = status
                    
                db.commit()
                
                # Sync into simulator
                if self.simulator:
                    self.simulator.load_from_db()
                    
                return {
                    "success": True,
                    "message": f"Physical node {node_id} state changed to {status}. Links status updated."
                }
                
            elif tool_name == "trigger_congestion_leak":
                status = arguments.get("status")
                if self.simulator:
                    self.simulator.trigger_congestion(status)
                    state = "activated" if status else "deactivated"
                    return {"success": True, "message": f"Severe traffic congestion simulation {state} on eMBB slice."}
                return {"success": False, "error": "Simulator instance not active"}
                
            else:
                return {"success": False, "error": f"Tool '{tool_name}' unknown."}
                
        finally:
            db.close()

    # ==========================================
    # RESOURCE IMPLEMENTATION MODULES
    # ==========================================
    def read_resource(self, uri: str) -> Dict[str, Any]:
        """Retrieve telemetry states when an AI agent requests to view dynamic MCP URI resources."""
        db = SessionLocal()
        try:
            if uri == "network://topology":
                db_nodes = db.query(NodeModel).all()
                db_links = db.query(LinkModel).all()
                return {
                    "nodes": [{"id": n.id, "name": n.name, "type": n.type, "x": n.x, "y": n.y, "status": n.status} for n in db_nodes],
                    "links": [{"id": l.id, "source": l.source_id, "target": l.target_id, "capacity_mbps": l.capacity, "latency_ms": l.latency, "status": l.status} for l in db_links]
                }
            elif uri == "network://metrics":
                if self.simulator:
                    return self.simulator.latest_metrics
                return {}
            else:
                raise ValueError(f"Resource {uri} not found.")
        finally:
            db.close()

    # ==========================================
    # PROMPT IMPLEMENTATION MODULES
    # ==========================================
    def get_prompt(self, prompt_name: str) -> Dict[str, Any]:
        """Serve specific context prompting frameworks to guide AI agent orchestrations."""
        if prompt_name == "resolve_congestion":
            return {
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": (
                                "You are an autonomous 5G Slice Orchestration Agent.\n"
                                "A high-packet-loss event has occurred on the eMBB slice due to traffic congestion.\n"
                                "Please follow this execution sequence:\n"
                                "1. Call `get_network_health` to locate the router queues experiencing overflows.\n"
                                "2. Inspect current slice bandwidth guarantees via `list_slices`.\n"
                                "3. Optimize routing cost weights using `route_optimize` (set policy to 'load_balanced' to spread data load away from the bottleneck).\n"
                                "4. Call `modify_slice_qos` to throttle eMBB or increase scheduling priorities if SLA limits are violated.\n"
                                "5. Report back the final status of packet delivery ratio (PDR) once healed."
                            )
                        }
                    }
                ]
            }
        elif prompt_name == "routing_recovery":
            return {
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": (
                                "You are a Self-Healing Wireless Mesh Orchestrator.\n"
                                "Router-B has powered down, severing the path from high-priority Client-URLLC-2.\n"
                                "Please execute these steps:\n"
                                "1. Query the offline status of nodes using `get_network_health`.\n"
                                "2. Trigger node recovery or force dynamic route path calculations via `route_optimize` using policy 'snr_based' to guarantee reliable alternate signal routes.\n"
                                "3. Confirm that URLLC slice latency has dropped back below its 5ms target SLA threshold."
                            )
                        }
                    }
                ]
            }
        else:
            raise ValueError(f"Prompt '{prompt_name}' not found.")

# ==========================================================
# STANDARD INPUT / OUTPUT PARSER FOR CLAUDE/MCP HOSTS
# ==========================================================
def run_stdio_mcp_server():
    """Stdio execution loop allowing direct CLI connection by standard MCP clients."""
    print("5G WMN MCP Slicing Server running in STDIO transport mode.", file=sys.stderr)
    mcp_server = MCPServer()
    
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
                
            request_data = json.loads(line)
            response = mcp_server.handle_request(request_data)
            
            if response:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except Exception as e:
            err_response = {
                "jsonrpc": "2.0",
                "error": {"code": -32603, "message": f"STDIO Exception: {str(e)}"}
            }
            sys.stdout.write(json.dumps(err_response) + "\n")
            sys.stdout.flush()

if __name__ == "__main__":
    run_stdio_mcp_server()
