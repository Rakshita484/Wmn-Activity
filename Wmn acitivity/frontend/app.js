// ==========================================================
// GLOBALS & STATE CONFIGURATION
// ==========================================================
let socket = null;
let networkState = null;
let throughputChart = null;
let latencyChart = null;

// RENDER SETTINGS & INTERACTION STATE
const canvas = document.getElementById("topology-canvas");
const ctx = canvas.getContext("2d");
let hoveredNode = null;
let packetParticles = [];

// Slice Configurations (Colors and labels matched to HSL standard variables)
const sliceMeta = {
    "eMBB": { color: "#00d2ff", name: "eMBB (Enhanced Broadband)", glow: "rgba(0, 210, 255, 0.6)" },
    "URLLC": { color: "#ff3b30", name: "URLLC (Ultra-Reliable Low-Latency)", glow: "rgba(255, 59, 48, 0.6)" },
    "mMTC": { color: "#4cd964", name: "mMTC (Massive IoT)", glow: "rgba(76, 217, 100, 0.6)" }
};

// ==========================================================
// CHART.JS INTEGRATION
// ==========================================================
function initCharts() {
    const chartOptions = (title, yLabel) => ({
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: true, labels: { color: "#94a3b8", font: { size: 10, family: 'Inter' } } },
            title: { display: true, text: title, color: "#f8fafc", font: { size: 12, family: 'Orbitron', weight: 'bold' } }
        },
        scales: {
            x: { grid: { color: "rgba(255,255,255,0.03)" }, ticks: { color: "#64748b", font: { size: 8 } } },
            y: { grid: { color: "rgba(255,255,255,0.03)" }, ticks: { color: "#64748b", font: { size: 8 } }, title: { display: true, text: yLabel, color: "#94a3b8", font: { size: 10 } } }
        }
    });

    throughputChart = new Chart(document.getElementById("throughput-chart").getContext("2d"), {
        type: "line",
        data: { labels: [], datasets: [
            { label: "eMBB", borderColor: sliceMeta["eMBB"].color, backgroundColor: "transparent", data: [], borderWidth: 2, pointRadius: 1, tension: 0.3 },
            { label: "URLLC", borderColor: sliceMeta["URLLC"].color, backgroundColor: "transparent", data: [], borderWidth: 2, pointRadius: 1, tension: 0.3 },
            { label: "mMTC", borderColor: sliceMeta["mMTC"].color, backgroundColor: "transparent", data: [], borderWidth: 2, pointRadius: 1, tension: 0.3 }
        ]},
        options: chartOptions("Throughput Trends", "Bandwidth (Mbps)")
    });

    latencyChart = new Chart(document.getElementById("latency-chart").getContext("2d"), {
        type: "line",
        data: { labels: [], datasets: [
            { label: "eMBB", borderColor: sliceMeta["eMBB"].color, backgroundColor: "transparent", data: [], borderWidth: 2, pointRadius: 1, tension: 0.3 },
            { label: "URLLC", borderColor: sliceMeta["URLLC"].color, backgroundColor: "transparent", data: [], borderWidth: 2, pointRadius: 1, tension: 0.3 },
            { label: "mMTC", borderColor: sliceMeta["mMTC"].color, backgroundColor: "transparent", data: [], borderWidth: 2, pointRadius: 1, tension: 0.3 }
        ]},
        options: chartOptions("Latency SLA Tracking", "Delay (ms)")
    });
}

function updateCharts(history) {
    if (!history || !history["eMBB"] || history["eMBB"].length === 0) return;
    if (!throughputChart || !latencyChart) return; // Safety check in case charts failed to initialize

    const ticks = history["eMBB"].map(h => `T-${h.tick}`);
    
    // Throughput dataset update
    throughputChart.data.labels = ticks;
    throughputChart.data.datasets[0].data = history["eMBB"].map(h => h.throughput);
    throughputChart.data.datasets[1].data = history["URLLC"].map(h => h.throughput);
    throughputChart.data.datasets[2].data = history["mMTC"].map(h => h.throughput);
    throughputChart.update('none'); // Update without full recalculation animation (efficient)

    // Latency dataset update
    latencyChart.data.labels = ticks;
    latencyChart.data.datasets[0].data = history["eMBB"].map(h => h.latency);
    latencyChart.data.datasets[1].data = history["URLLC"].map(h => h.latency);
    latencyChart.data.datasets[2].data = history["mMTC"].map(h => h.latency);
    latencyChart.update('none');
}

// ==========================================================
// 2D CANVAS TOPOLOGY & PARTICLE FLOW RENDERER
// ==========================================================
class PacketParticle {
    constructor(sourceId, targetId, path, sliceType) {
        this.path = path; // list of nodes in path e.g. ["Client-1", "Router-D", "Router-C", "Core"]
        this.pathIndex = 0;
        this.sliceType = sliceType;
        this.color = sliceMeta[sliceType].color;
        
        this.x = 0;
        this.y = 0;
        this.progress = 0.0; // 0.0 to 1.0 between hops
        this.speed = sliceType === "URLLC" ? 0.08 : sliceType === "eMBB" ? 0.04 : 0.02; // speed profiles
        
        this.initSegment();
    }

    initSegment() {
        const currentId = this.path[this.pathIndex];
        const nextId = this.path[this.pathIndex + 1];
        
        const current = networkState.nodes.find(n => n.id === currentId);
        const next = networkState.nodes.find(n => n.id === nextId);
        
        if (current && next) {
            this.startX = current.x;
            this.startY = current.y;
            this.endX = next.x;
            this.endY = next.y;
            this.progress = 0.0;
        } else {
            this.progress = 1.0; // Fail segment immediately
        }
    }

    update() {
        this.progress += this.speed;
        if (this.progress >= 1.0) {
            this.pathIndex++;
            if (this.pathIndex >= this.path.length - 1) {
                return false; // Packet reached destination core, delete
            }
            this.initSegment();
        }
        
        this.x = this.startX + (this.endX - this.startX) * this.progress;
        this.y = this.startY + (this.endY - this.startY) * this.progress;
        return true;
    }

    draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.sliceType === "URLLC" ? 4 : this.sliceType === "eMBB" ? 5 : 3, 0, Math.PI * 2);
        ctx.fillStyle = this.color;
        ctx.shadowBlur = 10;
        ctx.shadowColor = this.color;
        ctx.fill();
        ctx.shadowBlur = 0; // Reset shadow
    }
}

function renderTopology() {
    if (!networkState) return;

    // 1. Clear Screen
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw fine technological graph grid lines
    ctx.beginPath();
    ctx.strokeStyle = "rgba(255, 255, 255, 0.02)";
    ctx.lineWidth = 1;
    for (let x = 0; x < canvas.width; x += 40) {
        ctx.moveTo(x, 0); ctx.lineTo(x, canvas.height);
    }
    for (let y = 0; y < canvas.height; y += 40) {
        ctx.moveTo(0, y); ctx.lineTo(canvas.width, y);
    }
    ctx.stroke();

    // 2. Draw Backbone and Edge Links
    networkState.links.forEach(link => {
        const src = networkState.nodes.find(n => n.id === link.source_id);
        const tgt = networkState.nodes.find(n => n.id === link.target_id);
        if (!src || !tgt) return;

        const isOnline = link.status === "online" && src.status === "online" && tgt.status === "online";
        
        ctx.beginPath();
        ctx.moveTo(src.x, src.y);
        ctx.lineTo(tgt.x, tgt.y);
        
        if (isOnline) {
            // Width represents base capacity
            ctx.lineWidth = Math.max(1.5, link.capacity / 40);
            ctx.strokeStyle = "rgba(255, 255, 255, 0.12)";
            ctx.shadowBlur = 0;
            ctx.stroke();
            
            // Draw a subtle animated dashed line representing physical data routing load
            if (link.load > 0) {
                ctx.save();
                ctx.setLineDash([4, 10]);
                ctx.lineDashOffset = -window.performance.now() / 60;
                ctx.lineWidth = 1;
                ctx.strokeStyle = "rgba(139, 92, 246, 0.6)"; // glowing violet for loading
                ctx.stroke();
                ctx.restore();
            }
        } else {
            // offline links drawn dotted
            ctx.lineWidth = 1;
            ctx.strokeStyle = "rgba(239, 68, 68, 0.25)";
            ctx.save();
            ctx.setLineDash([3, 5]);
            ctx.stroke();
            ctx.restore();
        }
    });

    // 3. Update & Draw Dynamic flowing packet particles
    // We filter particles that successfully advanced
    packetParticles = packetParticles.filter(p => p.update());
    packetParticles.forEach(p => p.draw());

    // 4. Draw Nodes
    networkState.nodes.forEach(node => {
        const isHovered = hoveredNode && hoveredNode.id === node.id;
        
        // Setup node styling bases
        let radius = 12;
        let color = "#94a3b8";
        let shadow = "rgba(0,0,0,0.5)";
        
        if (node.type === "Core") {
            radius = 20;
            color = "#a78bfa"; // Violet Core Gateway
            shadow = "rgba(167, 139, 250, 0.5)";
        } else if (node.type === "Router") {
            radius = 15;
            color = node.status === "online" ? "#e2e8f0" : "#ef4444";
            shadow = node.status === "online" ? "rgba(255,255,255,0.2)" : "rgba(239, 68, 68, 0.4)";
        } else if (node.type === "Client") {
            radius = 10;
            color = sliceMeta[node.slice_type].color;
            shadow = sliceMeta[node.slice_type].glow;
        }

        // Draw outer glowing halo on active hovered elements
        if (isHovered) {
            ctx.beginPath();
            ctx.arc(node.x, node.y, radius + 6, 0, Math.PI * 2);
            ctx.fillStyle = node.type === "Core" ? "rgba(167, 139, 250, 0.15)" : "rgba(255,255,255,0.08)";
            ctx.fill();
        }

        // Draw physical node circular background
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
        ctx.fillStyle = "#090d16";
        ctx.strokeStyle = color;
        ctx.lineWidth = isHovered ? 3 : 2;
        
        if (node.status === "online") {
            ctx.shadowBlur = isHovered ? 15 : 6;
            ctx.shadowColor = color;
        }
        ctx.fill();
        ctx.stroke();
        ctx.shadowBlur = 0; // reset

        // Draw status offline markers
        if (node.status === "offline") {
            ctx.beginPath();
            ctx.moveTo(node.x - 5, node.y - 5);
            ctx.lineTo(node.x + 5, node.y + 5);
            ctx.moveTo(node.x + 5, node.y - 5);
            ctx.lineTo(node.x - 5, node.y + 5);
            ctx.strokeStyle = "#ef4444";
            ctx.lineWidth = 2;
            ctx.stroke();
        }

        // Renders node identifier labels
        ctx.font = node.type === "Core" ? "bold 10px Orbitron" : "10px Inter";
        ctx.fillStyle = isHovered ? "#ffffff" : "#94a3b8";
        ctx.textAlign = "center";
        ctx.fillText(node.id, node.x, node.y - radius - 6);
    });

    // Request subsequent frames
    requestAnimationFrame(renderTopology);
}

// Spawns particles dynamically based on simulated throughput trends
function triggerTrafficParticles() {
    if (!networkState) return;

    networkState.nodes.forEach(node => {
        if (node.type !== "Client" || node.status === "offline") return;
        
        const sType = node.slice_type;
        const metrics = networkState.metrics[sType];
        
        // Spawn probability proportional to active slice throughput
        let spawnChance = 0.05;
        if (sType === "eMBB") spawnChance = Math.min(0.5, metrics.throughput / 150.0);
        else if (sType === "URLLC") spawnChance = Math.min(0.4, metrics.throughput / 30.0);
        else spawnChance = 0.08;

        if (Math.random() < spawnChance) {
            // Find active path to core
            const path = computeRoutePath(node.id, "Core");
            if (path && path.length > 1) {
                packetParticles.push(new PacketParticle(node.id, "Core", path, sType));
            }
        }
    });
}

function computeRoutePath(sourceId, targetId) {
    if (!networkState || !networkState.routing_table) return null;
    
    let path = [sourceId];
    let curr = sourceId;
    
    // Trace through next hops using simulator routing table values
    while (curr !== targetId) {
        let next = networkState.routing_table[curr];
        if (!next || path.includes(next)) {
            return null; // Route broken/cyclical
        }
        path.push(next);
        curr = next;
    }
    return path;
}

// Every 150ms check if particles should spawn based on latest metrics
setInterval(triggerTrafficParticles, 150);

// ==========================================================
// INTERACTIVE COLLISION DETECTION & NODE CLICKING
// ==========================================================
canvas.addEventListener("mousemove", (e) => {
    if (!networkState) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    let found = null;
    networkState.nodes.forEach(node => {
        const dx = node.x - mx;
        const dy = node.y - my;
        const dist = Math.sqrt(dx*dx + dy*dy);
        
        // Check collision bounding radius
        if (dist < 20) {
            found = node;
        }
    });
    
    hoveredNode = found;
    canvas.style.cursor = found ? "pointer" : "default";
});

canvas.addEventListener("click", async () => {
    if (!hoveredNode) return;
    
    // Core and Clients cannot fail physically in this WMN layout model
    if (hoveredNode.type !== "Router") return;
    
    const newStatus = hoveredNode.status === "online" ? "offline" : "online";
    logTerminal(`[User Command] Request to power ${hoveredNode.id} -> ${newStatus.toUpperCase()}`, "system");
    
    try {
        const res = await fetch(`/api/network/nodes/${hoveredNode.id}/status`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ status: newStatus })
        });
        
        if (res.ok) {
            logTerminal(`[Node Controller] Power state cascaded successfully. Routing rebuilding.`, "success");
        } else {
            logTerminal(`[Node Controller] Failed to adjust status.`, "error");
        }
    } catch (err) {
        console.error(err);
        logTerminal(`[Error] Link failure execution failed: ${err.message}`, "error");
    }
});

// ==========================================================
// WEBSOCKET TELEMETRY CONNECTION
// ==========================================================
function connectWebSocket() {
    const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${wsProto}//${window.location.host}/ws`;
    
    socket = new WebSocket(wsUrl);
    
    socket.onopen = () => {
        console.log("WebSocket connected.");
        document.getElementById("ws-status").innerHTML = `
            <span class="status-dot connected"></span>
            <span class="status-text">WS CONNECTED</span>
        `;
    };
    
    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        networkState = data;
        
        // Update global indicators
        document.getElementById("sim-tick").innerText = data.tick;
        document.getElementById("routing-policy-select").value = data.routing_policy;
        document.getElementById("congestion-toggle").checked = data.congestion;

        // Update Slice Telemetry Cards
        updateSliceCards(data.metrics);
        
        // Update Chart graphs
        updateCharts(data.history);
    };
    
    socket.onclose = () => {
        console.log("WebSocket connection closed. Retrying...");
        document.getElementById("ws-status").innerHTML = `
            <span class="status-dot disconnected"></span>
            <span class="status-text">WS RECONNECTING...</span>
        `;
        setTimeout(connectWebSocket, 4000);
    };

    socket.onerror = (err) => {
        console.error("WebSocket error: ", err);
    };
}

function updateSliceCards(metrics) {
    if (!metrics) return;
    
    for (const [slice, m] of Object.entries(metrics)) {
        const id = slice.toLowerCase();
        
        // Update text labels
        document.getElementById(`val-${id}-throughput`).innerHTML = `${m.throughput.toFixed(2)} <small>Mbps</small>`;
        document.getElementById(`val-${id}-latency`).innerHTML = `${m.latency.toFixed(1)} <small>ms</small>`;
        
        const pdrVal = document.getElementById(`val-${id}-pdr`);
        pdrVal.innerHTML = `${m.pdr.toFixed(1)} <small>%</small>`;
        
        // Alarm indicator if latency budget or PDR SLA is breached
        if (m.pdr < 95.0) {
            pdrVal.className = "value text-alarm";
            pdrVal.style.color = "#ef4444";
        } else {
            pdrVal.className = "value";
            pdrVal.style.color = sliceMeta[slice].color;
        }
    }
}

// ==========================================================
// QOS PROFILE CONFIGURATION MODAL
// ==========================================================
async function openConfigModal(sliceType) {
    try {
        const res = await fetch(`/api/slices/slice-${sliceType.toLowerCase()}`);
        if (!res.ok) return;
        
        const data = await res.json();
        
        document.getElementById("modal-slice-type").value = sliceType;
        document.getElementById("modal-slice-title").innerText = `Tune ${sliceType} QoS Profiles`;
        document.getElementById("modal-bandwidth").value = data.allocated_bandwidth;
        document.getElementById("modal-latency").value = data.latency_limit;
        document.getElementById("modal-priority").value = data.priority;
        document.getElementById("modal-status").value = data.status;
        
        document.getElementById("qos-modal").classList.add("open");
    } catch (err) {
        console.error(err);
    }
}

function closeConfigModal() {
    document.getElementById("qos-modal").classList.remove("open");
}

document.getElementById("qos-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const sliceType = document.getElementById("modal-slice-type").value;
    const body = {
        allocated_bandwidth: parseFloat(document.getElementById("modal-bandwidth").value),
        latency_limit: parseFloat(document.getElementById("modal-latency").value),
        priority: parseInt(document.getElementById("modal-priority").value),
        status: document.getElementById("modal-status").value
    };

    logTerminal(`[QoS Orchestrator] Manually tuning ${sliceType} configurations...`, "system");

    try {
        const res = await fetch(`/api/slices/slice-${sliceType.toLowerCase()}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body)
        });
        
        if (res.ok) {
            logTerminal(`[QoS Orchestrator] Slices updated successfully. Synchronization active.`, "success");
            closeConfigModal();
        } else {
            logTerminal(`[QoS Orchestrator] Failed to adjust QoS profiles.`, "error");
        }
    } catch (err) {
        logTerminal(`[Error] Orchestration failed: ${err.message}`, "error");
    }
});

// REST handlers for global center changes
document.getElementById("routing-policy-select").addEventListener("change", async (e) => {
    const val = e.target.value;
    logTerminal(`[User Action] Change routing metric weight policy -> ${val.toUpperCase()}`, "system");
    try {
        await fetch("/api/network/routing-policy", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ policy: val })
        });
    } catch (err) {
        console.error(err);
    }
});

document.getElementById("congestion-toggle").addEventListener("change", async (e) => {
    const val = e.target.checked;
    logTerminal(`[User Action] Simulated eMBB Congestion Flood -> ${val ? 'ON' : 'OFF'}`, "system");
    
    // Call the specific MCP Tool RPC endpoint to inject congestion
    // Shows direct tool usage
    const rpcPayload = {
        jsonrpc: "2.0",
        id: "congest-rpc-manual",
        method: "tools/call",
        params: {
            name: "trigger_congestion_leak",
            arguments: { status: val }
        }
    };
    
    try {
        await fetch("/api/mcp/rpc", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(rpcPayload)
        });
    } catch (err) {
        console.error(err);
    }
});

// ==========================================================
// MCP AI AGENT TERMINAL ENGINE
// ==========================================================
const term = document.getElementById("mcp-terminal");

function logTerminal(text, type = "info") {
    const el = document.createElement("div");
    el.className = `terminal-line ${type}`;
    
    // Format simple time tag
    const t = new Date().toLocaleTimeString();
    el.innerHTML = `<span style="color:#64748b;margin-right:8px;">[${t}]</span> ${text}`;
    term.appendChild(el);
    
    // Keep scrolled down
    term.scrollTop = term.scrollHeight;
}

// 1. AI Congestion Resolution Agent Simulation
document.getElementById("btn-agent-congest").addEventListener("click", () => {
    runCongestionAgent();
});

// 2. WMN Self-Healing Routing Agent Simulation
document.getElementById("btn-agent-healing").addEventListener("click", () => {
    runSelfHealingAgent();
});

// User Custom Commands parsing
document.getElementById("btn-mcp-send").addEventListener("click", () => {
    handleUserCommand();
});

document.getElementById("mcp-user-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleUserCommand();
});

async function handleUserCommand() {
    const input = document.getElementById("mcp-user-input");
    const val = input.value.trim();
    if (!val) return;

    logTerminal(`AI Agent Query: "${val}"`, "request");
    input.value = "";
    
    // Simple custom NLP router mimicking LLM MCP Orchestration
    if (val.toLowerCase().includes("heal") || val.toLowerCase().includes("online")) {
        logTerminal("AI Agent reasoning: User wants to heal the network routers. Initiating discovery...", "info");
        await delay(1000);
        runSelfHealingAgent();
    } else if (val.toLowerCase().includes("congest") || val.toLowerCase().includes("optimize")) {
        logTerminal("AI Agent reasoning: Congestion/QoS optimization requested. Analyzing metrics...", "info");
        await delay(1000);
        runCongestionAgent();
    } else if (val.toLowerCase().includes("list") || val.toLowerCase().includes("slices")) {
        logTerminal("AI Agent reasoning: Request to list slice profiles. Dispatching MCP JSON-RPC call...", "info");
        await delay(800);
        await callMcpRpc("list_slices", {});
    } else {
        logTerminal("AI Agent reasoning: Custom prompt query processed. Reading network telemetries...", "info");
        await delay(800);
        await callMcpRpc("get_network_health", {});
        logTerminal(`AI Agent Suggestion: Slices are stable. If you notice packet loss, click a backbone router node to trigger dynamic self-healing simulations!`, "success");
    }
}

// Helper RPC caller
async function callMcpRpc(toolName, args) {
    const rpcPayload = {
        jsonrpc: "2.0",
        id: `rpc-${Math.floor(Math.random() * 10000)}`,
        method: "tools/call",
        params: {
            name: toolName,
            arguments: args
        }
    };

    logTerminal(`--&gt; MCP Request: jsonrpc 2.0 | tool: ${toolName}`, "request");
    
    try {
        const res = await fetch("/api/mcp/rpc", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(rpcPayload)
        });
        const data = await res.json();
        
        if (data.result) {
            logTerminal(`&lt;-- MCP Response: Execution successful.`, "response");
            return data.result;
        } else {
            logTerminal(`&lt;-- MCP Response: Error: ${JSON.stringify(data.error)}`, "error");
            return null;
        }
    } catch (e) {
        logTerminal(`[Error] MCP RPC Dispatch fail: ${e.message}`, "error");
        return null;
    }
}

const delay = (ms) => new Promise(res => setTimeout(res, ms));

async function runCongestionAgent() {
    logTerminal("=== STARTING AI CONGESTION OPTIMIZER AGENT ===", "system");
    await delay(1000);
    
    logTerminal("Step 1: Injecting eMBB packet flood to trigger active congestion...", "warning");
    document.getElementById("congestion-toggle").checked = true;
    await callMcpRpc("trigger_congestion_leak", { status: true });
    
    await delay(2500);
    
    logTerminal("Step 2: AI Agent reading telemetry and queue statuses...", "info");
    const health = await callMcpRpc("get_network_health", {});
    
    // Check if congested queues exist
    if (health) {
        logTerminal("Step 3: Analyzer identified high queue depths and degraded SNR bounds.", "warning");
    }
    
    await delay(2000);
    
    logTerminal("Step 4: AI Agent decides to optimize backhaul routing. Switching to Load Balanced Cost...", "info");
    await callMcpRpc("route_optimize", { policy: "load_balanced" });
    
    await delay(2000);
    
    logTerminal("Step 5: AI Agent re-allocating guaranteed slice bandwidth to eMBB (raising to 180Mbps) and elevating scheduler priority.", "info");
    await callMcpRpc("modify_slice_qos", { slice_type: "eMBB", bandwidth: 180.0, priority: 2 });
    
    await delay(3000);
    
    logTerminal("Step 6: AI Agent verifies SLAs. eMBB congestion cleared! Deactivating simulation traffic flood...", "success");
    document.getElementById("congestion-toggle").checked = false;
    await callMcpRpc("trigger_congestion_leak", { status: false });
    
    logTerminal("=== CONGESTION HEAL SEQUENCE COMPLETE ===", "success");
}

async function runSelfHealingAgent() {
    logTerminal("=== STARTING AI ROUTING SELF-HEALING AGENT ===", "system");
    await delay(1000);
    
    logTerminal("Step 1: Simulating power failure of primary Router-C...", "warning");
    await callMcpRpc("toggle_node_status", { node_id: "Router-C", status: "offline" });
    
    await delay(2500);
    
    logTerminal("Step 2: AI Agent queries network topology and routes.", "info");
    await callMcpRpc("get_network_health", {});
    
    await delay(2000);
    
    logTerminal("Step 3: AI Agent detects Router-C offline. Discovered redundant link paths to Core.", "warning");
    logTerminal("Step 4: AI Agent executes route cost optimization to 'snr_based' to prioritize high signal alternate links...", "info");
    await callMcpRpc("route_optimize", { policy: "snr_based" });
    
    await delay(3000);
    
    logTerminal("Step 5: Restoring Router-C power state to check convergence...", "info");
    await callMcpRpc("toggle_node_status", { node_id: "Router-C", status: "online" });
    
    await delay(2000);
    
    logTerminal("Step 6: Routing paths converged! All clients connected. Slice SLAs verified.", "success");
    logTerminal("=== SELF-HEALING SEQUENCE COMPLETE ===", "success");
}

// ==========================================================
// LAUNCHER INIT
// ==========================================================
window.addEventListener("load", () => {
    try {
        initCharts();
    } catch (e) {
        console.warn("Charts disabled: Could not initialize Chart.js.");
    }
    connectWebSocket();
    renderTopology();
});
