# Future Enhancements & Performance Considerations

This document outlines planned improvements and architectural extensions that can be built on top of the current implementation.

---

## Future Enhancements

### 1. AI-Based Traffic Prediction

**Current State**: Traffic generation uses fixed probabilistic profiles (e.g., eMBB generates at 85% probability per tick).

**Enhancement**: Integrate a lightweight ML model (LSTM or Prophet) trained on historical `metrics_history` data to:
- Predict eMBB throughput spikes 5-10 ticks ahead
- Pre-emptively scale bandwidth allocations before congestion occurs
- Enable the MCP AI Agent to use a `predict_traffic` tool

**Implementation Path**: Add a `predictor.py` module that reads from `metrics_history`, trains a sliding-window model, and exposes predictions via a new MCP tool.

---

### 2. Docker & Kubernetes Deployment

**Current State**: Single-machine deployment via `run.py` with local virtualenv.

**Enhancement**:
- **Dockerfile**: Package the backend + frontend into a single container with multi-stage builds
- **docker-compose.yml**: Orchestrate backend, database (separate SQLite volume), and optional Nginx reverse proxy
- **Kubernetes**: Deploy as a Helm chart with:
  - Backend Deployment + Service
  - ConfigMap for slice configurations
  - PersistentVolumeClaim for SQLite database
  - Horizontal Pod Autoscaler based on WebSocket connection count

---

### 3. Authentication & Role-Based Access Control (RBAC)

**Current State**: No authentication — all endpoints are publicly accessible.

**Enhancement**:
- Add JWT-based authentication via FastAPI `Depends` guards
- Define roles:
  - **Admin**: Full CRUD on slices, node toggling, MCP tool access
  - **Operator**: Read-only monitoring, QoS tuning
  - **Viewer**: Dashboard read-only access
- Store user credentials in the SQLite database with bcrypt password hashing

---

### 4. WebSocket Authentication & Rate Limiting

**Current State**: WebSocket connections are unauthenticated and unlimited.

**Enhancement**:
- Require JWT token in WebSocket handshake headers
- Implement connection rate limiting (max connections per IP)
- Add client heartbeat/keepalive monitoring to detect stale connections

---

### 5. Load Balancing Across Multiple Simulator Instances

**Current State**: Single-threaded simulation loop.

**Enhancement**:
- Run multiple simulator instances (one per WMN region)
- Use Redis Pub/Sub to broadcast state changes across instances
- Frontend connects to a load-balanced WebSocket endpoint
- Enables horizontal scaling for large-scale WMN simulations

---

### 6. NS-3 / Mininet-WiFi Integration

**Current State**: Custom Python discrete-tick simulator.

**Enhancement**: Replace or complement the Python simulator with:
- **NS-3**: High-fidelity packet-level simulation with real 802.11s mesh protocol stacks
- **Mininet-WiFi**: Linux-based emulation with actual WiFi kernel drivers
- Keep the MCP layer and dashboard unchanged — only swap the simulator backend

This would upgrade the project from simulation to emulation level, producing results publishable in academic conferences.

---

### 7. Real-Time Charts with Grafana

**Current State**: Chart.js embedded in the dashboard.

**Enhancement**:
- Export metrics to Prometheus via a `/metrics` endpoint (Prometheus exposition format)
- Deploy Grafana with pre-built dashboards for:
  - Per-slice throughput/latency/PDR panels
  - Node health heatmaps
  - Queue depth gauges
- Enables long-term metric storage and alerting

---

### 8. Dynamic Slice Creation API

**Current State**: Only three pre-seeded slices (eMBB, URLLC, mMTC).

**Enhancement**:
- Add a `POST /api/slices/` endpoint to create custom slices with arbitrary parameters
- Support slice deletion with graceful traffic migration
- Enable per-slice node affinity (bind specific clients to specific slices dynamically)

---

### 9. Network Topology Editor

**Current State**: Fixed 11-node topology seeded from database.

**Enhancement**:
- Add a drag-and-drop canvas editor to:
  - Place new mesh routers and clients
  - Draw links between nodes with configurable capacity/latency
  - Save/load topology presets
- Persist custom topologies in the database

---

### 10. MCP Integration with External LLMs

**Current State**: MCP server runs locally with simulated AI agent sequences.

**Enhancement**:
- Connect the MCP STDIO server to actual LLM hosts:
  - **Claude Desktop**: Register via `claude_desktop_config.json`
  - **MCP Inspector**: Debug tool calls in real-time
  - **Custom LLM**: Any OpenAI-compatible model via STDIO bridge
- The LLM would autonomously decide which tools to call based on network state

---

## Performance Considerations

### Current Performance Characteristics

| Aspect | Value | Notes |
|:---|:---|:---|
| Simulation tick rate | 1 Hz (1 tick/second) | Configurable in `main.py` |
| WebSocket broadcast latency | <10ms | JSON serialization + send |
| Routing table computation | <1ms | Dijkstra with 11 nodes |
| Queue processing per tick | 12 packets/router | 4 routers × 12 = 48 packets/tick max |
| Database queries per tick | 0 | Simulator operates in-memory after initial load |
| Frontend rendering | 60 FPS | Canvas `requestAnimationFrame` |
| Chart.js updates | 1 Hz | Synced with simulation tick |

### Scalability Bottlenecks

1. **Single-threaded asyncio loop**: The simulation and WebSocket broadcast share a single event loop. For >100 concurrent WebSocket clients, consider using a dedicated broadcast worker.

2. **SQLite write contention**: SQLite allows only one writer at a time. For high-frequency QoS updates, consider migrating to PostgreSQL with connection pooling.

3. **Canvas rendering**: With >50 nodes, the 2D canvas may experience frame drops. Consider switching to WebGL (Three.js or PixiJS) for large-scale topologies.

4. **Routing computation**: Dijkstra is $O((V + E) \log V)$. With 11 nodes this is instant, but for 1000+ node meshes, consider pre-computed routing tables with incremental updates.

### Optimization Strategies

- **Batch WebSocket broadcasts**: Aggregate multiple ticks into a single broadcast to reduce overhead
- **Delta compression**: Send only changed metrics instead of full payload each tick
- **Worker threads**: Offload simulation computation to a separate thread using `asyncio.to_thread()`
- **Connection pooling**: Use SQLAlchemy async sessions for non-blocking database access
