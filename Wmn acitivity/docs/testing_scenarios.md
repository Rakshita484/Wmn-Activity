# Testing Scenarios & Verification Guide

This document provides formal test scenarios with step-by-step procedures, expected outcomes, and the automated pytest tests that verify each behavior.

---

## Automated Test Suite Summary

The project includes **64 automated tests** across 3 test files:

| Test File | Tests | Coverage Area |
|:---|:---:|:---|
| `test_simulator.py` | 19 | SNR physics, Shannon capacity, Dijkstra routing, self-healing, traffic generation |
| `test_queues.py` | 8 | Priority scheduling, fair share, starvation, overflow, slice isolation |
| `test_mcp.py` | 37 | REST CRUD, node cascade, all 6 MCP tools, resources, prompts, error handling |

### Running All Tests

```bash
cd "Wmn acitivity"
PYTHONPATH=. .venv/bin/pytest backend/tests/ -v
```

---

## Scenario 1: Verify Strict Slice Isolation (URLLC Protection)

### Objective
Prove that URLLC latency remains below 5ms even when eMBB is heavily congested.

### Manual Procedure (Dashboard)
1. Open `http://localhost:8000`
2. Toggle the **"Inject eMBB Traffic Congestion"** switch ON
3. Observe the charts panel:
   - eMBB throughput spikes, then latency rises significantly
   - eMBB PDR may drop below 95% (shown in red)
4. **Verify**: URLLC latency line stays flat and below 5ms
5. **Verify**: mMTC throughput drops (starved by eMBB flood)
6. Toggle congestion OFF to restore normal operation

### Expected Outcome
- eMBB: Throughput surges → queue overflow → latency 25-50ms → PDR drops
- URLLC: Latency remains <5ms → PDR stays near 100% → **SLA protected**
- mMTC: Best-effort starvation → low throughput → acceptable behavior

### Automated Tests
- `test_queues.py::TestURILCPriorityBypass::test_urllc_fully_drained_before_embb`
- `test_queues.py::TestMMTCBestEffort::test_mmtc_starved_under_full_urllc_load`
- `test_queues.py::TestSliceIsolation::test_urllc_latency_stays_low_under_embb_congestion`

---

## Scenario 2: Verify Dynamic Mesh Self-Healing

### Objective
Prove that when a router fails, traffic automatically reroutes through redundant paths with zero manual intervention.

### Manual Procedure (Dashboard)
1. Open `http://localhost:8000`
2. Click directly on **Router-C** (center node) on the 2D topology canvas
3. Observe:
   - Router-C turns red with an ✕ marker
   - All links connected to Router-C become dashed red (offline)
   - Animated packet particles immediately reroute through alternative paths
4. **Verify**: Packets from Client-mMTC-2 now flow via Router-D → Router-A → Core
5. Click Router-C again to restore it online
6. **Verify**: Routing reconverges within 1 tick

### Expected Outcome
- No packet loss during rerouting (PDR stays near 100%)
- Routing table recalculates within 1 simulation tick (~1 second)
- Alternative paths: Router-D → Router-A → Core or Router-D → Router-B → Core

### Automated Tests
- `test_simulator.py::TestSelfHealing::test_single_router_failure_bypass`
- `test_simulator.py::TestSelfHealing::test_double_router_failure`
- `test_simulator.py::TestSelfHealing::test_core_offline_produces_empty_routes`
- `test_simulator.py::TestDijkstraRouting::test_all_clients_have_path_to_core`

---

## Scenario 3: Verify MCP AI Congestion Optimizer Agent

### Objective
Demonstrate autonomous AI-driven congestion resolution using MCP tools.

### Manual Procedure (Dashboard)
1. Open `http://localhost:8000`
2. In the MCP Controller Panel (bottom right), click **"Run Congestion Optimizer Agent"**
3. Watch the terminal console log each step:
   - Step 1: Agent injects eMBB congestion
   - Step 2: Agent queries `get_network_health` to detect queue overflows
   - Step 3: Agent calls `route_optimize(load_balanced)` to spread traffic
   - Step 4: Agent calls `modify_slice_qos(eMBB, bandwidth=180)` to increase capacity
   - Step 5: Agent disables congestion flood
4. **Verify**: eMBB PDR recovers from degraded to ~100%
5. **Verify**: Charts show the congestion spike and subsequent recovery

### Expected Outcome
- MCP tools are executed in sequence with JSON-RPC 2.0 compliance
- Each tool call shows request/response in the terminal
- Network metrics visibly improve after optimization

### Automated Tests
- `test_mcp.py::TestMCPToolExecution::test_tool_modify_slice_qos`
- `test_mcp.py::TestMCPToolExecution::test_tool_route_optimize`
- `test_mcp.py::TestMCPToolExecution::test_tool_trigger_congestion`
- `test_mcp.py::TestMCPToolExecution::test_tool_get_network_health`

---

## Scenario 4: Verify MCP Self-Healing Agent

### Objective
Demonstrate autonomous routing recovery after physical node failure using MCP.

### Manual Procedure (Dashboard)
1. Click **"Run WMN Self-Healing Agent"** in the MCP Controller Panel
2. Watch the terminal log:
   - Step 1: Agent powers down Router-C via `toggle_node_status`
   - Step 2: Agent queries `get_network_health` to detect offline router
   - Step 3: Agent optimizes routing to `snr_based` policy
   - Step 4: Agent restores Router-C to online
3. **Verify**: Topology canvas shows Router-C going offline then recovering
4. **Verify**: URLLC latency stays within SLA during the entire process

### Automated Tests
- `test_mcp.py::TestMCPToolExecution::test_tool_toggle_node_status`
- `test_mcp.py::TestRESTNodeToggling::test_node_offline_cascade`
- `test_mcp.py::TestRESTNodeToggling::test_node_online_restore`

---

## Scenario 5: Verify Manual QoS Tuning

### Objective
Prove that manual QoS parameter changes take effect immediately in the simulation.

### Manual Procedure (Dashboard)
1. Click **"Tune QoS"** on the eMBB slice card
2. Change **Guaranteed Bandwidth** from 100 to 200 Mbps
3. Change **Priority** from 2 to 1 (strict bypass)
4. Click **"Apply QoS Profiles"**
5. **Verify**: eMBB throughput increases in the live chart
6. **Verify**: eMBB latency decreases (now has higher priority)

### Automated Tests
- `test_mcp.py::TestRESTSlices::test_update_slice_qos_parameters`
- `test_mcp.py::TestRESTSlices::test_get_single_slice_by_type`

---

## Scenario 6: Verify SNR & Capacity Physics

### Objective
Validate that the free-space path loss model and Shannon capacity calculations are mathematically correct.

### Verification
This is purely algorithmic — verified by automated unit tests:

- `test_simulator.py::TestSNRCalculation::test_snr_mathematical_accuracy`
  - Computes: Router-A (500,150) → Core (700,300), distance = 250m
  - Expected SNR ≈ 75 - 20·log₁₀(250) ≈ 27.04 dB (±1.5 fading)
  - Averages 50 samples to account for random fading
- `test_simulator.py::TestSNRCalculation::test_snr_monotonic_distance_decay`
  - Proves closer nodes always have higher SNR
- `test_simulator.py::TestLinkCapacity::test_capacity_bounded_by_base`
  - Proves dynamic capacity never exceeds configured base capacity
- `test_simulator.py::TestLinkCapacity::test_capacity_scales_with_snr`
  - Proves higher SNR links have higher efficiency ratios

---

## Scenario 7: Verify Routing Policy Switching

### Objective
Confirm that switching between the three routing policies produces different optimal paths.

### Manual Procedure (Dashboard)
1. Use the **"Mesh Routing Policy"** dropdown in the Network Orchestration Center
2. Switch between `Shortest Hop`, `Radio Signal-Quality (SNR)`, and `Congestion Load Balanced`
3. **Verify**: Packet flow animations change paths on the topology canvas
4. **Verify**: Latency values adjust in the charts (load-balanced should reduce congestion-related spikes)

### Automated Tests
- `test_simulator.py::TestDijkstraRouting::test_shortest_hop_direct_routers_reach_core`
- `test_simulator.py::TestDijkstraRouting::test_snr_based_routing_converges`
- `test_simulator.py::TestDijkstraRouting::test_load_balanced_routing_converges`
- `test_mcp.py::TestRESTNetwork::test_set_routing_policy`
