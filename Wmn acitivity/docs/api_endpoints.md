# API Endpoints Specification

This document details the REST APIs and the Model Context Protocol (MCP) JSON-RPC specification.

---

## 1. REST HTTP API Layer

The REST layer provides standard telemetry retrieval and manual overrides.

### Network Slices CRUD
- **GET** `/api/slices/`
  - **Description**: List all active slices and their QoS parameters.
  - **Response**: Array of `SliceResponse` objects.
- **GET** `/api/slices/{slice_type}`
  - **Description**: Retrieve current QoS settings for a specific slice (`slice-embb`, `slice-urllc`, `slice-mmtc`).
- **PUT** `/api/slices/{slice_type}`
  - **Description**: Dynamically modify the slice parameter profiles.
  - **Request Body**:
    ```json
    {
      "allocated_bandwidth": 120.0,
      "latency_limit": 15.0,
      "priority": 2,
      "status": "active"
    }
    ```

### WMN Topology Control
- **GET** `/api/network/nodes`
  - **Description**: Fetch coordinates, type, and status of all simulated mesh nodes.
- **GET** `/api/network/links`
  - **Description**: Retrieve active links, capacity, and status.
- **PUT** `/api/network/nodes/{node_id}/status`
  - **Description**: Manually toggle the power status of a mesh node. Used to simulate physical router failures.
  - **Request Body**:
    ```json
    { "status": "offline" }
    ```
- **POST** `/api/network/routing-policy`
  - **Description**: Toggle routing algorithm constraints.
  - **Request Body**:
    ```json
    { "policy": "load_balanced" }
    ```

---

## 2. MCP JSON-RPC 2.0 Specifications

The MCP server handles standardized JSON-RPC payloads.

### Handshake Initializer
- **Method**: `initialize`
- **Request Payload**:
  ```json
  {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "capabilities": {},
      "clientInfo": { "name": "claude-desktop", "version": "1.0.0" }
    }
  }
  ```
- **Response Result**:
  ```json
  {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
      "protocolVersion": "2024-11-05",
      "capabilities": {
        "tools": {},
        "resources": {},
        "prompts": {}
      },
      "serverInfo": { "name": "5g-wmn-mcp-slicing-manager", "version": "1.0.0" }
    }
  }
  ```

### Tool Execution (`tools/call`)
- **Method**: `tools/call`
- **Request Payload (Example: Optimizing routes)**:
  ```json
  {
    "jsonrpc": "2.0",
    "id": 4,
    "method": "tools/call",
    "params": {
      "name": "route_optimize",
      "arguments": { "policy": "load_balanced" }
    }
  }
  ```
- **Response Result**:
  ```json
  {
    "jsonrpc": "2.0",
    "id": 4,
    "result": {
      "content": [
        {
          "type": "text",
          "text": "{\n  \"success\": true,\n  \"message\": \"WMN multi-hop routing optimized to use policy: 'load_balanced'\"\n}"
        }
      ]
    }
  }
  ```
