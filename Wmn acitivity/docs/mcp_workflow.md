# MCP Slicing Orchestration Workflows

This document outlines the sequential call flows showing how the Model Context Protocol (MCP) orchestrates autonomous operations in our WMN system.

---

## 1. Congestion Resolution Workflow

When high throughput triggers packet drops on the eMBB slice, an MCP-integrated AI Agent resolves the SLA violation using this flow:

```
[ AI Agent ]             [ MCP Server ]             [ DB / Simulator ]
     |                          |                            |
     |--- 1. Read Metrics ----->|                            |
     |    (network://metrics)   |--- Query active database ->|
     |<-- Return telemetry -----|<-- Slice performance data -|
     |                          |                            |
     | [AI Analyzes SLA:        |                            |
     |  eMBB PDR < 95%]         |                            |
     |                          |                            |
     |--- 2. route_optimize --->|                            |
     |    (policy=load_balance) |--- Modify routing policy ->|
     |<-- Success response -----|<-- Routing recalculated ---|
     |                          |                            |
     |--- 3. modify_slice_qos ->|                            |
     |    (bandwidth=180Mbps)   |--- Update Slice Schema ----|
     |                          |--- Reload configurations ->|
     |<-- QoS sync success -----|<-- Simulator updated ------|
     |                          |                            |
     |--- 4. Verify telemetry ->|                            |
     |<-- PDR restored to 100% -|                            |
```

---

## 2. Self-Healing Redundancy Recovery

When a router node powers down, the self-healing agent coordinates backup path routing:

```
[ AI Agent ]             [ MCP Server ]             [ DB / Simulator ]
     |                          |                            |
     | [Alarm: Client isolated] |                            |
     |                          |                            |
     |--- 1. get_network_health |                            |
     |    RPC tool call ------->|--- Inspect router state ->|
     |<-- Router-C: OFFLINE ----|<-- Return link states -----|
     |                          |                            |
     |--- 2. route_optimize --->|                            |
     |    (policy=snr_based)    |--- Dijkstra computes ------|
     |                          |    redundant backup links -|
     |<-- Paths recalculated ---|<-- Simulator updated ------|
     |                          |                            |
     |--- 3. Verify URLLC SLA --|                            |
     |<-- Delay target: <5ms ---|                            |
```
