# 5G Network Slicing Lifecycle Workflow

This document explains the end-to-end lifecycle of network slice management in our 5G WMN system — from slice creation and resource allocation through monitoring, dynamic adaptation, and MCP-driven optimization.

---

## 1. What is 5G Network Slicing?

Network slicing is a fundamental 5G architecture concept that allows a single physical network infrastructure to be logically partitioned into multiple isolated virtual networks called **slices**. Each slice is tailored for a specific service type with distinct Quality-of-Service (QoS) guarantees.

### The Three Standard 5G Slices

| Slice | Full Name | Use Case | Bandwidth | Latency Target | Priority |
|:---|:---|:---|:---:|:---:|:---:|
| **eMBB** | Enhanced Mobile Broadband | 4K video streaming, AR/VR, file downloads | 100 Mbps | ≤50 ms | 2 (Weighted Fair) |
| **URLLC** | Ultra-Reliable Low-Latency Communication | Autonomous vehicles, tele-surgery, emergency | 20 Mbps | ≤5 ms | 1 (Strict Bypass) |
| **mMTC** | Massive Machine-Type Communication | Smart sensors, agricultural IoT, smart grid | 10 Mbps | ≤200 ms | 3 (Best Effort) |

---

## 2. Slice Creation Flow

When the system boots via `run.py`, the database is seeded with three pre-configured slices:

```
[run.py] → [init_db()] → Seeds SQLite with:
    ├── slice-embb:  eMBB  (bandwidth=100, latency=50ms,  priority=2, color=#00d2ff)
    ├── slice-urllc: URLLC (bandwidth=20,  latency=5ms,   priority=1, color=#ff3b30)
    └── slice-mmtc:  mMTC  (bandwidth=10,  latency=200ms, priority=3, color=#4cd964)
```

Each slice has:
- **Separate QoS parameters** stored in the `slices` database table
- **Separate queue buffers** at every mesh router (per-slice FIFO deques in the simulator)
- **Separate monitoring metrics** (throughput, latency, PDR tracked independently)

---

## 3. Resource Allocation

Resources are allocated at two levels:

### Level 1: Bandwidth & Priority Allocation (Database Layer)

Each slice's `allocated_bandwidth` and `priority` determine how the queue scheduler distributes processing capacity:

```python
# At each router, per simulation tick (processing_budget = 12 packets):
Step 1: Drain URLLC queue completely (priority=1, strict bypass)
Step 2: Serve eMBB with guaranteed minimum share:
        embb_guarantee = max(1, min(floor(budget * bw/120), remaining_budget))
Step 3: Serve remaining eMBB + mMTC on best-effort basis
```

### Level 2: Dynamic Link Capacity (Physical Layer)

Link capacity is NOT statically divided between slices. Instead:
- All slices share the same physical wireless links
- **Queue-level isolation** ensures separation: URLLC packets skip ahead of eMBB/mMTC
- The scheduler guarantees each slice's SLA regardless of competing traffic

This is faithful to real 5G RAN resource scheduling, where Physical Resource Blocks (PRBs) are dynamically allocated based on slice priority and traffic demand.

---

## 4. Slice Monitoring

The simulator calculates and broadcasts four key metrics per slice every tick via WebSocket:

| Metric | Formula | Significance |
|:---|:---|:---|
| **Throughput** (Mbps) | $\frac{\text{delivered\_packets} \times \text{avg\_size}}{0.1s}$ | Effective data delivery rate |
| **Latency** (ms) | $\frac{\sum \text{hop\_delays}}{\text{delivered\_count}}$ + priority penalty | Average end-to-end delay |
| **PDR** (%) | $\frac{\text{delivered}}{\text{delivered} + \text{dropped}} \times 100$ | Packet Delivery Ratio — SLA health indicator |
| **Active Users** | Count of online clients bound to this slice | Connected device population |

### Monitoring Data Flow

```
[Simulator.step()]
    │
    ├── generate_traffic()      → Clients inject packets into router queues
    ├── process_node_queues()   → Routers forward packets hop-by-hop
    ├── compile_tick_metrics()  → Calculate throughput/latency/PDR per slice
    │
    └── get_simulation_payload() → Package full state
            │
            ├── WebSocket broadcast → Frontend dashboard (real-time)
            └── metrics_history[]   → Last 30 ticks for Chart.js graphs
```

---

## 5. Dynamic Adaptation

When network conditions change, the system adapts through two mechanisms:

### 5a. Manual Adaptation (Dashboard UI)

Users can open the QoS configuration modal for any slice and modify:
- Guaranteed bandwidth allocation
- Latency SLA target
- Scheduler priority level
- Active/inactive status

```
[Dashboard] → PUT /api/slices/{type} → [Database] → simulator.load_from_db()
                                                          ↓
                                              Queue scheduler weights updated
                                              immediately on next tick
```

### 5b. AI-Driven Adaptation (MCP Agent)

The MCP AI Agent performs autonomous optimization via the following workflow:

```
User Request → MCP Server receives context
     ↓
MCP reads network://metrics resource
     ↓
AI analyzes: "eMBB PDR dropped to 72% — SLA violated"
     ↓
AI calls tool: route_optimize(policy="load_balanced")
     ↓
AI calls tool: modify_slice_qos(slice_type="eMBB", bandwidth=180)
     ↓
Simulator reloads configuration → Queue weights adjust → PDR recovers to 100%
     ↓
Dashboard reflects changes in real-time via WebSocket
```

---

## 6. Slice Isolation Proof

The system mathematically proves slice isolation through the strict priority scheduler:

### Scenario: eMBB Congestion Under URLLC Protection

```
Given:
  - eMBB congestion multiplier = 4.0× (heavy video traffic)
  - Router processing budget = 12 packets/tick

Scheduler behavior at each router:
  1. URLLC queue: 5 packets → ALL 5 served first (budget = 7 remaining)
  2. eMBB queue: 20 packets → Only 7 served (budget exhausted)
  3. mMTC queue: 3 packets → 0 served (starved)

Result:
  - URLLC latency: <5ms (SLA maintained ✓)
  - eMBB latency: 25-40ms (degraded but tolerable)
  - mMTC latency: high (best-effort, acceptable)
```

This is verified by the `test_queues.py::TestSliceIsolation::test_urllc_latency_stays_low_under_embb_congestion` automated test.

---

## 7. End-to-End Execution Flow Summary

```
1. User device (Client-eMBB-1) generates video stream packet
2. Packet classified as "eMBB" slice → enters Router-D's eMBB queue
3. Router-D scheduler serves URLLC first, then eMBB (weighted fair share)
4. Packet forwarded to next hop: Router-D → Router-C (Dijkstra routing)
5. Router-C scheduler processes packet → forwards to Router-A
6. Router-A scheduler processes packet → forwards to Core (destination)
7. Packet delivered! Latency and throughput metrics updated
8. Monitoring engine broadcasts via WebSocket to dashboard
9. Dashboard renders real-time charts and animated packet flow
10. If PDR drops below SLA threshold:
    → MCP AI Agent detects → calls modify_slice_qos → SLA restored
```
