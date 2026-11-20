# Deployment Guide

This document provides complete instructions for setting up, installing, running, and deploying the 5G WMN MCP Slicing Management project.

---

## Prerequisites

| Requirement | Minimum Version | Purpose |
|:---|:---|:---|
| Python | 3.10+ | Backend runtime |
| pip | 21.0+ | Package manager (auto-upgraded by launcher) |
| Modern Web Browser | Chrome/Firefox/Edge | Dashboard UI |
| Git | 2.0+ | (Optional) Version control |

No additional system dependencies are required. The project uses only pure Python packages and vanilla HTML/CSS/JS.

---

## Quick Start (Single Command)

```bash
# Navigate to the project directory
cd "Wmn acitivity"

# Run the all-in-one launcher
python3 run.py
```

The launcher automatically:
1. Creates a Python virtual environment (`.venv/`)
2. Upgrades pip to latest version
3. Installs all dependencies from `backend/requirements.txt`
4. Seeds the SQLite database with initial topology and slice configurations
5. Starts the Uvicorn development server with hot-reload

**Open your browser**: `http://localhost:8000`

---

## Manual Setup (Step-by-Step)

If you prefer manual control over each step:

### Step 1: Create Virtual Environment

```bash
cd "Wmn acitivity"
python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
```

### Step 2: Install Dependencies

```bash
pip install --upgrade pip
pip install -r backend/requirements.txt
```

### Step 3: Initialize Database

```bash
PYTHONPATH=. python3 -c "from backend.app.database import init_db; init_db()"
```

### Step 4: Start Server

```bash
PYTHONPATH=. uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 5: Open Dashboard

Navigate to `http://localhost:8000` in your browser.

---

## Running Tests

```bash
cd "Wmn acitivity"
PYTHONPATH=. .venv/bin/pytest backend/tests/ -v
```

Expected output: **64 tests passed**.

---

## Dependencies

All Python dependencies are listed in `backend/requirements.txt`:

| Package | Version | Purpose |
|:---|:---|:---|
| `fastapi` | ≥0.100.0 | REST API framework with automatic OpenAPI docs |
| `uvicorn` | ≥0.20.0 | ASGI server for FastAPI |
| `sqlalchemy` | ≥2.0.0 | ORM for SQLite database access |
| `pydantic` | ≥2.0.0 | Data validation and serialization |
| `websockets` | ≥11.0 | WebSocket protocol support |
| `pytest` | ≥7.0.0 | Test framework |
| `httpx` | ≥0.24.0 | HTTP client for FastAPI TestClient |

Frontend dependencies are loaded via CDN (no npm/node required):
- **Chart.js** — Real-time line charts
- **Google Fonts** — Inter, Orbitron, Fira Code typefaces

---

## API Access Points

Once the server is running, the following endpoints are available:

| URL | Purpose |
|:---|:---|
| `http://localhost:8000` | Dashboard UI |
| `http://localhost:8000/docs` | Interactive Swagger/OpenAPI documentation |
| `http://localhost:8000/api/slices/` | REST: List all network slices |
| `http://localhost:8000/api/network/nodes` | REST: List all mesh nodes |
| `http://localhost:8000/api/network/links` | REST: List all mesh links |
| `http://localhost:8000/api/network/telemetry` | REST: Full simulation payload |
| `http://localhost:8000/api/mcp/rpc` | MCP: JSON-RPC 2.0 endpoint |
| `http://localhost:8000/api/mcp/tools` | MCP: List available tools |
| `ws://localhost:8000/ws` | WebSocket: Real-time telemetry stream |

---

## MCP STDIO Transport

For connecting to standard MCP hosts (Claude Desktop, MCP Inspector):

```bash
cd "Wmn acitivity"
PYTHONPATH=. .venv/bin/python -m backend.app.mcp_server
```

This starts the MCP server in STDIO mode, reading JSON-RPC from stdin and writing responses to stdout.

### Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or equivalent:

```json
{
  "mcpServers": {
    "5g-wmn-slicing": {
      "command": "python3",
      "args": ["-m", "backend.app.mcp_server"],
      "cwd": "/path/to/Wmn acitivity",
      "env": {
        "PYTHONPATH": "."
      }
    }
  }
}
```

---

## Database Management

The SQLite database (`wmn_slicing.db`) is auto-created and seeded on first run.

### Reset Database

To completely reset the database to initial state:

```bash
rm wmn_slicing.db
python3 run.py  # Will re-seed automatically
```

### Database Schema

| Table | Columns | Purpose |
|:---|:---|:---|
| `slices` | id, name, type, allocated_bandwidth, latency_limit, priority, status, color | 5G network slice configurations |
| `nodes` | id, name, type, x, y, status, slice_type | Mesh topology node positions and types |
| `links` | id, source_id, target_id, capacity, latency, status | Physical link connections |

---

## Production Deployment Considerations

### Using Gunicorn (Multi-Worker)

For production deployments with multiple workers:

```bash
pip install gunicorn
PYTHONPATH=. gunicorn backend.app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind 0.0.0.0:8000
```

> **Note**: The simulation loop runs in-memory. Multiple workers will each have their own simulator instance. For shared state, migrate to Redis or PostgreSQL.

### Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name wmn-slicing.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000/ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Docker Deployment (Future)

A Dockerfile for containerized deployment:

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t wmn-slicing .
docker run -p 8000:8000 wmn-slicing
```

---

## Troubleshooting

| Issue | Solution |
|:---|:---|
| `ModuleNotFoundError: No module named 'backend'` | Ensure `PYTHONPATH=.` is set, or use `run.py` |
| Port 8000 already in use | Kill existing process: `lsof -ti:8000 | xargs kill` |
| Database locked | Stop all running server instances before modifying DB |
| WebSocket disconnects frequently | Check browser console for errors; ensure no proxy is stripping WS headers |
| Tests fail with import errors | Run from the `Wmn acitivity` directory with `PYTHONPATH=.` |
