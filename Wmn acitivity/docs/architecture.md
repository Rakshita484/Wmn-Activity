# 5G Wireless Mesh Slicing & MCP Architecture

This document presents the detailed architectural and engineering principles of the Model Context Protocol (MCP) Integrated 5G Wireless Mesh Network (WMN) slicing manager.

---

## 1. 5G Wireless Mesh Network (WMN) Simulation Engine

A Wireless Mesh Network is characterized by decentralized, multi-hop routing where nodes forward packets dynamically on behalf of their peers. Our system simulates three categories of nodes:
- **5G UPF Core Network Gateway**: The central ingress point where all client data streams must terminate to access external networks.
- **Mesh Routers (Backhaul Nodes)**: High-power static routers forming the mesh backhaul structure. They run dynamic routing and handle queue-level slice isolation.
- **Mesh Clients (User Terminals)**: Mobile or static client terminals bound to specific 5G slices, injecting traffic into nearest WMN routers.

### Physical & Link Dynamics
Physical radio channels are subject to signal path attenuation and fading. Our engine models distance-based path loss:

$$SNR(d) = P_{tx} - 20\log_{10}(d) - N_0$$

Where $P_{tx}$ is transmitting power, $N_0$ is white noise, and $d$ is coordinates-based distance.

Dynamic link bandwidth capacity is modeled using the Shannon-Hartley theorem:

$$Capacity_{actual} = B \log_{2}(1 + SNR)$$

This means link throughput capacity degrades dynamically as links experience interference or distance increases.

---

## 2. 5G Network Slicing & Queue Scheduling (SLA Isolation)

Each routing node maintains three isolated buffers, preventing eMBB high-throughput traffic from drowning out critical low-latency URLLC streams:

```
Packet Arrival ---> [Classifier]
                         |
                         +---> [URLLC Queue] (Strict Priority Bypass)  ---> [Processor]
                         |
                         +---> [eMBB Queue]  (Weighted Fair Queuing)   ---> [Processor]
                         |
                         +---> [mMTC Queue]  (Best-Effort Scheduling)  ---> [Processor]
```

### Scheduling Algorithms:
1. **URLLC Queue (Strict Priority Bypass)**: Packets are served first. As long as any URLLC packet resides in the node buffer, it bypasses other queues, achieving near-zero queue delay ($<5$ ms propagation latency).
2. **eMBB Queue (Weighted Fair Queuing - WFQ)**: Receives a guaranteed percentage share of remaining processing bandwidth, allowing fast massive file transmissions without starving lower slices.
3. **mMTC Queue (Best-Effort)**: Massive IoT sensor bursts tolerate high delays. They are processed only during router idle periods, preventing control overhead bottlenecks.

---

## 3. Model Context Protocol (MCP) Integration

The **Model Context Protocol (MCP)** provides a standard interface to allow AI models (LLMs) to interact with external tools and data sources. In this project, MCP serves as the intelligent management plane:

```
[ AI Agent Orchestrator ]
          |
     (JSON-RPC)
          v
  [ MCP Server Engine ]
    +-- Tools (Modify QoS, Toggle Nodes, Optimize Routing)
    +-- Resources (Read network://topology, network://metrics)
    +-- Prompts (Guided congestion & failure scenarios)
          |
    (ORM Layer)
          v
 [ SQLite Database ] <---> [ 5G WMN Simulator ]
```

### Key Capabilities of MCP Slicing:
- **Dynamic Optimization**: The AI reads `network://metrics` to identify congestion, and uses the `modify_slice_qos` tool to reconfigure scheduler weights on the fly.
- **Self-Healing Routing**: If a physical router fails (status `offline`), the AI notices the drop via `get_network_health` and executes the `route_optimize` tool to compute alternative path matrices.
