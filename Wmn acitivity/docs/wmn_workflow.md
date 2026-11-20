# Wireless Mesh Network (WMN) Topology & Multi-Hop Routing Workflow

This document explains the WMN simulation layer in detail — how mesh nodes are organized, how packets traverse multi-hop paths, and how the network self-heals after failures.

---

## 1. What is a Wireless Mesh Network?

A Wireless Mesh Network is a decentralized network architecture where every node cooperatively forwards traffic on behalf of others. Unlike traditional star or hub-spoke topologies, mesh networks provide:

- **No single point of failure** — if one node dies, traffic reroutes automatically.
- **Multi-hop packet delivery** — packets traverse several intermediate routers to reach the core gateway.
- **Self-healing** — Dijkstra-based routing dynamically recalculates paths when links degrade or nodes fail.
- **Scalability** — new mesh routers can be added without reconfiguring the entire network.

---

## 2. Our WMN Topology

The simulated WMN contains **11 nodes** positioned on an 800×600 coordinate grid:

```
                        Client-eMBB-2 (250,100)
                             |
    Client-eMBB-1 (50,100)   |
           |                 |
           v                 v
        Router-D --------Router-A ---------> Core (700,300)
        (150,300)   |     (500,150)    |
           |        |                  |
           |     Router-C              |
           |     (300,300)             |
           |        |                  |
           +-----Router-B ---------> Core
    Client-URLLC-1  (500,450)    
    (50,300)            |
                   Client-URLLC-2 (450,550)
    Client-mMTC-1       |
    (50,500)        Client-mMTC-2 (250,500)
```

### Node Types

| Type | Count | Role |
|:---|:---:|:---|
| **Core (5G UPF Gateway)** | 1 | Central exit point to external networks (internet). All traffic terminates here. |
| **Mesh Routers** | 4 | Backbone forwarding nodes. Run Dijkstra routing and per-slice queue scheduling. |
| **Mesh Clients** | 6 | End-user devices bound to specific 5G slices. Generate traffic into nearest routers. |

### Link Structure

The mesh contains **14 bidirectional links** with varying base capacities and propagation delays:

| Link | Base Capacity (Mbps) | Base Latency (ms) | Purpose |
|:---|:---:|:---:|:---|
| Router-A ↔ Core | 250 | 2.0 | Primary backhaul to gateway |
| Router-B ↔ Core | 250 | 2.0 | Primary backhaul to gateway |
| Router-C ↔ Router-A | 150 | 4.0 | Mid-tier backbone mesh |
| Router-C ↔ Router-B | 150 | 4.0 | Mid-tier backbone mesh |
| Router-D ↔ Router-C | 100 | 5.0 | Inner mesh backbone |
| Router-A ↔ Router-B | 100 | 6.0 | Cross-backbone redundancy |
| Router-D ↔ Router-A | 80 | 8.0 | Redundant backup path |
| Router-D ↔ Router-B | 80 | 8.0 | Redundant backup path |
| Client-eMBB-1 ↔ Router-D | 80 | 8.0 | eMBB access link |
| Client-eMBB-2 ↔ Router-A | 100 | 5.0 | eMBB access link |
| Client-URLLC-1 ↔ Router-D | 30 | 3.0 | URLLC access link |
| Client-URLLC-2 ↔ Router-B | 40 | 2.0 | URLLC access link |
| Client-mMTC-1 ↔ Router-D | 15 | 15.0 | mMTC access link |
| Client-mMTC-2 ↔ Router-C | 20 | 10.0 | mMTC access link |

---

## 3. Physical & Link Layer Dynamics

### Signal-to-Noise Ratio (SNR) Model

Radio signal quality is modeled using **free-space path loss**:

$$SNR(d) = 75 - 20 \cdot \log_{10}(d) + \epsilon$$

Where:
- $d$ = Euclidean distance between node coordinates (meters)
- $\epsilon$ = random fading factor $\in [-1.5, +1.5]$ dB (simulates wireless channel variability)
- Result is clamped to $[5, 45]$ dB

### Dynamic Link Capacity (Shannon-Hartley)

Actual link throughput capacity adjusts dynamically based on SNR:

$$C_{actual} = C_{base} \times \min\left(1.0, \frac{SNR}{35}\right)$$

This means:
- **High SNR (>35 dB)**: Link operates at full base capacity
- **Low SNR (<15 dB)**: Link capacity degrades significantly, and packets may be randomly dropped (BER simulation)

---

## 4. Multi-Hop Routing Engine

### Dijkstra's Algorithm with Three Policies

The routing engine computes shortest paths from every node **to the Core gateway** using Dijkstra's algorithm. The link cost function varies by policy:

| Policy | Cost Function | When to Use |
|:---|:---|:---|
| `shortest_hop` | $w = 1.0$ | Minimum hop count. Default policy. |
| `snr_based` | $w = 100 / \max(1, SNR)$ | Avoids weak radio links. Used during node failures. |
| `load_balanced` | $w = latency + 10 \times (load/10)^2$ | Avoids congested queues. Used during traffic spikes. |

### Routing Table Structure

The routing table is a map: `node_id → next_hop_id`. For example:

```
Router-D → Router-C
Router-C → Router-A
Router-A → Core
```

This means a packet originating from Client-eMBB-1 follows:
```
Client-eMBB-1 → Router-D → Router-C → Router-A → Core
```

---

## 5. Self-Healing Workflow

When a router goes offline (e.g., Router-C is powered down):

```
1. Router-C status changes to "offline"
2. All links connected to Router-C are marked "offline"
3. Dijkstra routing table is recalculated for all remaining online nodes
4. Packets that previously traversed Router-C are automatically rerouted:
   - Router-D → Router-A → Core  (via redundant backup link)
   - Router-D → Router-B → Core  (via redundant backup link)
5. No manual intervention required — routing converges within 1 simulation tick
```

### Self-Healing Sequence Diagram

```
[User/AI Agent]          [MCP Server]           [Simulator]          [Database]
      |                       |                      |                    |
      |-- toggle_node_status →|                      |                    |
      |   (Router-C: offline) |-- Update node ------→|                    |
      |                       |-- Cascade links ----→|                    |
      |                       |-- Persist changes ---+-----------------→ |
      |                       |-- Reload from DB ---→|                    |
      |                       |                      |-- Dijkstra ------→ |
      |                       |                      |   recalculates     |
      |                       |                      |   routing table    |
      |                       |                      |                    |
      |                       |-- Next sim tick ----→|                    |
      |                       |                      |-- Packets reroute  |
      |                       |                      |   via backup paths |
      |←-- WebSocket update --|←- Broadcast payload -|                    |
      |   (topology redrawn)  |                      |                    |
```
