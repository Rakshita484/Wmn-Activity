import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .simulator import WMNNetworkSimulator
from .mcp_server import MCPServer

# Initialize Simulator and MCP Server globals
simulator = WMNNetworkSimulator()
mcp_server = MCPServer(simulator)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Send initial data immediately upon connecting
        try:
            initial_payload = simulator.get_simulation_payload()
            await websocket.send_json(initial_payload)
        except Exception as e:
            print(f"Error sending initial WS payload: {e}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

async def simulation_tick_loop():
    """Background loop that steps the simulator and broadcasts updates."""
    print("Background simulation tick loop started.")
    while True:
        try:
            simulator.step()
            payload = simulator.get_simulation_payload()
            await manager.broadcast(payload)
        except Exception as e:
            print(f"Exception in simulation step loop: {e}")
        await asyncio.sleep(1.0)  # 1-second simulation tick interval

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    init_db()
    # Synchronize simulator configs from freshly initialized DB
    simulator.load_from_db()
    # Start background tick thread/loop
    tick_task = asyncio.create_task(simulation_tick_loop())
    yield
    # Shutdown tasks
    tick_task.cancel()
    try:
        await tick_task
    except asyncio.CancelledError:
        pass
    print("Simulation tick loop stopped.")

app = FastAPI(
    title="5G Wireless Mesh Slicing & MCP Orchestrator",
    description="5G WMN Network slicing dynamic management simulator controlled via Model Context Protocol.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for standard web local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Lazy import routes to prevent circular imports
from .routes import slices, network, mcp
app.include_router(slices.router)
app.include_router(network.router)
app.include_router(mcp.router)

# WebSocket Endpoint for real-time telemetry updates on frontend
@app.websocket("/ws")
async def websocket_telemetry(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # We listen for client notifications (like manual tick triggers) or keep-alive
            data = await websocket.receive_text()
            # If client requests a manual sync
            if data == "sync":
                payload = simulator.get_simulation_payload()
                await websocket.send_json(payload)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Mount the static frontend files
# This serves index.html at http://localhost:8000/
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    print(f"Mounted static frontend files from: {frontend_dir}")
else:
    print(f"Warning: Static frontend directory not found at: {frontend_dir}")
