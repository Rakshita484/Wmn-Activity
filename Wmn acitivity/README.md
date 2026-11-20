# MCP-Based Network Slicing Management in 5G Wireless Mesh Networks (WMN)

An advanced, academically-robust, production-style engineering implementation integrating the **Model Context Protocol (MCP)** with a **5G Wireless Mesh Network (WMN)** environment for intelligent, automated network slice orchestration, SLA monitoring, and dynamic self-healing routing.

---

## 1. Project Overview
This project simulates a fully functioning 5G Wireless Mesh Network with dynamic packet routing and priority-based queue scheduling. It introduces 5G Network Slicing concepts (eMBB, URLLC, mMTC) to demonstrate traffic isolation. The intelligence layer is powered by a **Model Context Protocol (MCP) Server**, enabling autonomous AI agents to manage slice configurations, monitor telemetry, and optimize routing dynamically under congestion or hardware failure.

## 2. Problem Understanding
The core problem is managing the complexity of diverse traffic requirements in a decentralized mesh network. Traditional networks treat all traffic equally, leading to SLA violations for critical data during congestion. By applying 5G Network Slicing, we isolate traffic types (Bandwidth-hungry vs. Latency-critical). By integrating MCP, we allow context-aware AI models to act as the network orchestrator, analyzing live telemetry and making real-time resource adjustments to guarantee Service Level Agreements (SLAs).

## 3. Architecture Diagram
The system follows a modular, decoupled architecture:

```text
                        +----------------------------------+
                        |    Premium Dashboard Web UI      |
                        +----------------------------------+
                                   |            |
                          (REST & WebSockets)  (JSON-RPC MCP API)
                                   v            v
                        +----------------------------------+
                        |         FastAPI App Server       |
                        +----------------------------------+
                                   |            |
                                   |      +-----+-----+
                                   |      |           |
                                   v      v           v
                        +--------------------+  +--------------------+
                        | 5G WMN Simulator   |  | MCP Protocol Server|
                        +--------------------+  +--------------------+
                                   |                      |
                                   +----------+-----------+
                                              |
                                              v
                                   +--------------------+
                                   | SQLite DB (SQLAlchemy) |
                                   +--------------------+
```
*For deep technical details on physics and scheduling, see [Architecture Details](docs/architecture.md).*

## 4. Technology Stack
- **Backend & Simulator**: Python 3.10+, FastAPI, Uvicorn, asyncio
- **Database**: SQLite, SQLAlchemy ORM
- **Intelligence Layer**: Model Context Protocol (JSON-RPC 2.0, STDIO)
- **Frontend Dashboard**: Vanilla HTML5, premium HSL-tailored CSS, interactive 2D Canvas engine, Chart.js
- **Testing**: pytest, httpx

## 5. Folder Structure
The project uses an enterprise-style modular directory structure:
```text
Wmn acitivity/
├── backend/                 # Core server and simulation logic
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py          # FastAPI Entry, WebSocket handler
│   │   ├── database.py      # SQLite Database (SQLAlchemy models)
│   │   ├── simulator.py     # 5G WMN Simulator & QoS queues
│   │   ├── mcp_server.py    # MCP Server (JSON-RPC tools & resources)
│   │   ├── schemas.py       # Pydantic schemas for REST
│   │   └── routes/          # API Routers (slices, network, mcp)
│   ├── requirements.txt
│   └── tests/               # Automated Pytest Suite (64 tests)
├── frontend/                # Glassmorphic UI Dashboard
│   ├── index.html
│   ├── style.css
│   └── app.js
├── docs/                    # Comprehensive Technical Documentation
│   ├── api_endpoints.md
│   ├── architecture.md
│   ├── deployment_guide.md
│   ├── future_enhancements.md
│   ├── mcp_workflow.md
│   ├── slicing_workflow.md
│   ├── testing_scenarios.md
│   └── wmn_workflow.md
├── run.py                   # Automatic bootstrap and launch script
└── README.md
```

## 6. Backend Implementation
The backend is driven by FastAPI and contains three main engines:
1. **Simulator Engine (`simulator.py`)**: Computes SNR, Shannon capacity, Dijkstra routing, and handles strict priority queue processing.
2. **REST API (`routes/`)**: Exposes network state and manual configuration overrides.
3. **MCP Server (`mcp_server.py`)**: Parses standard JSON-RPC requests, exposing 6 specialized tools for AI orchestration.

## 7. Frontend Implementation
A single-page application built with modern web standards (no heavy frameworks required). Features a dark cyberpunk UI with a 2D Canvas visualizing the mesh topology and animated multi-hop packet flows. It includes live telemetry charts (Chart.js) and an integrated MCP AI Terminal to simulate agent actions.

## 8. Database Design
Uses SQLite via SQLAlchemy for persistent state management.
- **Slices Table**: `id`, `type`, `allocated_bandwidth`, `latency_limit`, `priority`, `status`
- **Nodes Table**: `id`, `type` (Router/Client/Core), `x`, `y` (coordinates), `status`
- **Links Table**: `source_id`, `target_id`, `capacity`, `latency`, `status`

## 9. API Documentation
The system supports both HTTP REST and MCP JSON-RPC 2.0 endpoints.
*Full specification available in [API Endpoints](docs/api_endpoints.md).*

## 10. MCP Workflow
MCP acts as the intelligence layer. AI agents can read network state via `network://metrics`, analyze congestion, and execute tools like `modify_slice_qos` and `route_optimize` to autonomously heal the network.
*See sequence diagrams in [MCP Workflow](docs/mcp_workflow.md).*

## 11. WMN Workflow
Nodes use coordinate-based free-space path loss to determine link capacities dynamically. Routing is handled by Dijkstra's algorithm supporting Shortest Hop, SNR-based, or Load-Balanced pathing. If a node fails, the network self-heals by instantly bypassing the offline node.
*Read more in [WMN Workflow](docs/wmn_workflow.md).*

## 12. Network Slicing Workflow
At every routing hop, traffic is sorted into isolated queues. URLLC (Ultra-Reliable Low-Latency) uses strict priority bypass, eMBB (Enhanced Mobile Broadband) gets weighted fair sharing, and mMTC (Massive IoT) uses best-effort scheduling, ensuring SLA isolation even under massive congestion.
*Read more in [Slicing Workflow](docs/slicing_workflow.md).*

## 13. Testing Scenarios
The project includes a comprehensive 64-test automated suite (pytest) covering physics math, priority queue starvation, Dijkstra convergence, and MCP protocol compliance. It also defines interactive UI scenarios for viva/demonstration purposes.
*See [Testing Scenarios](docs/testing_scenarios.md).*

## 14. Future Enhancements
Planned enhancements include ML-based predictive traffic shaping, Docker/Kubernetes horizontal scaling, NS-3 integration for hardware emulation, and Grafana telemetry exporting.
*See [Future Enhancements](docs/future_enhancements.md).*

## 15. Deployment Guide
The project features a zero-configuration bootstrap script (`run.py`) that handles virtual environments, dependencies, database seeding, and server launch automatically.
*For detailed setup, production Gunicorn config, and Claude Desktop integration, see [Deployment Guide](docs/deployment_guide.md).*

---

## ⚡ Quick Start

```bash
# Clone/Navigate to project directory
cd "Wmn acitivity"

# Run the automated bootstrap launcher
python3 run.py
```
Open your browser to: `http://localhost:8000`

To run the automated verification test suite:
```bash
PYTHONPATH=. .venv/bin/pytest backend/tests/ -v
```
