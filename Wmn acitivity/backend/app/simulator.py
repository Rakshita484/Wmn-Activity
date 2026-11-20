import time
import math
import heapq
import random
from typing import Dict, List, Any, Tuple
from collections import deque
from .database import SessionLocal, NodeModel, LinkModel, SliceModel

class Packet:
    def __init__(self, id: int, slice_type: str, source: str, destination: str, size: float, tick: int):
        self.id = id
        self.slice_type = slice_type
        self.source = source
        self.destination = destination
        self.size = size  # in Megabits (Mb)
        self.creation_tick = tick
        self.current_node = source
        self.hops: List[str] = [source]
        self.latency_accumulated = 0.0  # in ms

class WMNNetworkSimulator:
    def __init__(self):
        # Simulation configuration
        self.current_tick = 0
        self.packet_counter = 0
        self.routing_policy = "shortest_hop"  # shortest_hop, snr_based, load_balanced
        self.congestion_multiplier = 1.0  # Used to inject massive congestion for testing
        
        # In-memory network state
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.links: List[Dict[str, Any]] = []
        self.slices: Dict[str, Dict[str, Any]] = {}
        
        # Node buffers: Separate queues for URLLC, eMBB, mMTC per node
        # Structure: node_id -> { "URLLC": deque, "eMBB": deque, "mMTC": deque }
        self.queues: Dict[str, Dict[str, deque]] = {}
        self.queue_limit = 50  # Max packets per queue buffer
        
        # Telemetry metrics history for the last 50 ticks
        self.metrics_history: Dict[str, List[Dict[str, Any]]] = {
            "eMBB": [],
            "URLLC": [],
            "mMTC": []
        }
        
        # Latest calculated metrics (updated per tick)
        self.latest_metrics: Dict[str, Dict[str, Any]] = {
            "eMBB": {"throughput": 0.0, "latency": 0.0, "pdr": 100.0, "active_users": 0},
            "URLLC": {"throughput": 0.0, "latency": 0.0, "pdr": 100.0, "active_users": 0},
            "mMTC": {"throughput": 0.0, "latency": 0.0, "pdr": 100.0, "active_users": 0}
        }
        
        # Count drops and deliveries in current tick to calculate metrics
        self.tick_stats = {
            s_type: {"generated": 0, "delivered": 0, "dropped": 0, "total_latency": 0.0}
            for s_type in ["eMBB", "URLLC", "mMTC"]
        }
        
        self.load_from_db()

    def load_from_db(self):
        """Sync simulator state with SQLite database configurations."""
        db = SessionLocal()
        try:
            # Load Slices
            db_slices = db.query(SliceModel).all()
            self.slices = {
                s.type: {
                    "id": s.id,
                    "name": s.name,
                    "allocated_bandwidth": s.allocated_bandwidth,
                    "latency_limit": s.latency_limit,
                    "priority": s.priority,
                    "status": s.status,
                    "color": s.color
                }
                for s in db_slices
            }
            
            # Load Nodes
            db_nodes = db.query(NodeModel).all()
            self.nodes = {
                n.id: {
                    "id": n.id,
                    "name": n.name,
                    "type": n.type,
                    "x": n.x,
                    "y": n.y,
                    "status": n.status,
                    "slice_type": n.slice_type
                }
                for n in db_nodes
            }
            
            # Initialize Queues for routers and gateways
            for node_id, node in self.nodes.items():
                if node["type"] in ["Router", "Core"]:
                    self.queues[node_id] = {
                        "URLLC": deque(),
                        "eMBB": deque(),
                        "mMTC": deque()
                    }
            
            # Load Links
            db_links = db.query(LinkModel).all()
            self.links = []
            for l in db_links:
                self.links.append({
                    "id": l.id,
                    "source_id": l.source_id,
                    "target_id": l.target_id,
                    "capacity": l.capacity,
                    "latency": l.latency,
                    "status": l.status
                })
        finally:
            db.close()

    def get_snr(self, node_a_id: str, node_b_id: str) -> float:
        """Calculate dynamic SNR based on coordinate distance and path loss."""
        node_a = self.nodes.get(node_a_id)
        node_b = self.nodes.get(node_b_id)
        if not node_a or not node_b:
            return 0.0
            
        dx = node_a["x"] - node_b["x"]
        dy = node_a["y"] - node_b["y"]
        dist = math.sqrt(dx*dx + dy*dy)
        
        if dist < 10.0:
            dist = 10.0  # Clamp distance to avoid divide by zero/extremely high SNR
            
        # Free-space path loss SNR approximation: 70 - 20*log10(distance)
        snr = 75.0 - 20.0 * math.log10(dist)
        
        # Add slight fading randomness to simulate wireless medium
        fading = random.uniform(-1.5, 1.5)
        return max(5.0, min(45.0, snr + fading))  # Keep SNR between 5dB and 45dB

    def get_link_capacity(self, link: Dict[str, Any]) -> float:
        """Calculate dynamic link capacity using Shannon-Hartley equation based on SNR."""
        if link["status"] == "offline":
            return 0.0
            
        snr = self.get_snr(link["source_id"], link["target_id"])
        
        # Capacity = BaseCapacity * min(1.0, SNR / 40.0)
        # Represents higher signal quality allowing higher coding scheme efficiency
        efficiency = min(1.0, snr / 35.0)
        return max(1.0, link["capacity"] * efficiency)

    def get_link_load(self, source_id: str, target_id: str) -> float:
        """Determine current load on a link in number of waiting packets."""
        # Sum queue counts at the source node to forward towards target node
        source_queues = self.queues.get(source_id)
        if not source_queues:
            return 0.0
        return sum(len(q) for q in source_queues.values())

    def calculate_routing_table(self) -> Dict[str, Dict[str, str]]:
        """
        Compute the dynamic multi-hop routing paths using Dijkstra's algorithm.
        Returns a routing map: source -> next_hop
        """
        routing_table = {}
        
        # We calculate shortest path from all nodes to the 'Core' node
        target = "Core"
        if target not in self.nodes or self.nodes[target]["status"] == "offline":
            return {}

        # Build an adjacency list representation of ONLINE links
        adj = {node_id: [] for node_id, n in self.nodes.items() if n["status"] == "online"}
        
        for link in self.links:
            if link["status"] == "offline":
                continue
                
            src = link["source_id"]
            tgt = link["target_id"]
            
            if src not in adj or tgt not in adj:
                continue
                
            # Compute link weight based on Routing Policy
            base_latency = link["latency"]
            snr = self.get_snr(src, tgt)
            capacity = self.get_link_capacity(link)
            load = self.get_link_load(src, tgt)
            
            if self.routing_policy == "shortest_hop":
                # Metric: minimal hop count
                weight = 1.0
            elif self.routing_policy == "snr_based":
                # Metric: inverse of SNR (avoids degraded links)
                weight = 100.0 / max(1.0, snr)
            elif self.routing_policy == "load_balanced":
                # Metric: base latency + exponential penalty for queue congestion
                congest_factor = (load / 10.0) ** 2  # congestion penalty
                weight = base_latency + (10.0 * congest_factor)
            else:
                weight = 1.0
                
            # Links are bidirectional in mesh
            adj[src].append((tgt, weight))
            adj[tgt].append((src, weight))

        # Run Dijkstra from Core node to all other nodes (to easily get paths TO Core)
        distances = {node_id: float('inf') for node_id in adj}
        next_hops = {node_id: None for node_id in adj}
        
        distances[target] = 0.0
        pq = [(0.0, target)]
        
        while pq:
            dist, u = heapq.heappop(pq)
            
            if dist > distances[u]:
                continue
                
            for v, weight in adj[u]:
                alt = dist + weight
                if alt < distances[v]:
                    distances[v] = alt
                    # Since we search from Core to nodes, u is the NEXT hop on the way TO Core
                    next_hops[v] = u
                    heapq.heappush(pq, (alt, v))
                    
        return next_hops

    def generate_traffic(self):
        """Simulate active 5G clients generating packets destined for the Core Gateway."""
        for client_id, node in self.nodes.items():
            if node["type"] != "Client" or node["status"] == "offline":
                continue
                
            slice_type = node["slice_type"]
            slice_config = self.slices.get(slice_type)
            
            # If slice is inactive, do not generate traffic
            if not slice_config or slice_config["status"] != "active":
                continue
                
            # Traffic profile parameter details:
            # - eMBB: High data rate streams (e.g. video files, AR payloads)
            # - URLLC: Ultra-low size packets generated highly reliably
            # - mMTC: Infrequent periodic micro logs from smart sensors
            
            generate_packet = False
            packet_size = 0.0 # in Megabits (Mb)
            
            # Incorporate congestion factor
            flow_scale = self.congestion_multiplier if slice_type == "eMBB" else 1.0
            
            if slice_type == "eMBB":
                # eMBB generates high throughput continuously
                if random.random() < 0.85 * flow_scale:
                    generate_packet = True
                    # 1.5 to 4.5 Megabits packet
                    packet_size = random.uniform(1.5, 4.5) * flow_scale
            elif slice_type == "URLLC":
                # URLLC generates very frequent, small packets
                if random.random() < 0.95:
                    generate_packet = True
                    # small packet: 0.1 to 0.3 Megabits
                    packet_size = random.uniform(0.1, 0.3)
            elif slice_type == "mMTC":
                # mMTC generates packet occasionally (iot burst)
                if random.random() < 0.25:
                    generate_packet = True
                    # microscopic packet size: 0.01 to 0.05 Megabits
                    packet_size = random.uniform(0.01, 0.05)
                    
            if generate_packet:
                self.packet_counter += 1
                pkt = Packet(
                    id=self.packet_counter,
                    slice_type=slice_type,
                    source=client_id,
                    destination="Core",
                    size=packet_size,
                    tick=self.current_tick
                )
                self.tick_stats[slice_type]["generated"] += 1
                
                # Forward to nearest router connected to this client
                primary_link = next((l for l in self.links if (l["source_id"] == client_id or l["target_id"] == client_id) and l["status"] == "online"), None)
                if primary_link:
                    next_node = primary_link["target_id"] if primary_link["source_id"] == client_id else primary_link["source_id"]
                    
                    # Push into the queue of the router
                    router_queues = self.queues.get(next_node)
                    if router_queues:
                        q = router_queues[slice_type]
                        if len(q) < self.queue_limit:
                            pkt.current_node = next_node
                            pkt.hops.append(next_node)
                            # add base transmission delay of client link
                            pkt.latency_accumulated += primary_link["latency"]
                            q.append(pkt)
                        else:
                            # Buffer overflow at primary entry router!
                            self.tick_stats[slice_type]["dropped"] += 1
                    else:
                        # Router offline
                        self.tick_stats[slice_type]["dropped"] += 1
                else:
                    # Client isolated (all its links offline)
                    self.tick_stats[slice_type]["dropped"] += 1

    def process_node_queues(self, routing_table: Dict[str, str]):
        """
        Tick loop processing multi-hop queues at all routers.
        Applies strict priority scheduling (5G Slicing specs):
        - URLLC served first.
        - eMBB served second with guaranteed slice bandwidth share (Weighted Fair Queuing).
        - mMTC served last (best effort).
        """
        # We process routers in random order to prevent directional pipeline bias
        routers = [node_id for node_id, n in self.nodes.items() if n["type"] == "Router" and n["status"] == "online"]
        random.shuffle(routers)
        
        for r_id in routers:
            r_queues = self.queues[r_id]
            
            # Determine overall packet forwarding capacity of this mesh router in this tick
            # In a WMN, CPU and wireless channel limits bound total processing rate
            processing_budget = 12  # Packets per tick this router can forward
            
            # Get active slice configuration policies
            urllc_config = self.slices.get("URLLC")
            embb_config = self.slices.get("eMBB")
            mmtc_config = self.slices.get("mMTC")
            
            # Strict Priority Scheduling
            # 1. First, drain URLLC completely (up to processing capacity)
            urllc_served = 0
            while r_queues["URLLC"] and processing_budget > 0:
                pkt = r_queues["URLLC"].popleft()
                self.forward_packet(pkt, r_id, routing_table)
                processing_budget -= 1
                urllc_served += 1
                
            # 2. Allocate remaining capacity between eMBB and mMTC based on slice QoS weight
            # eMBB gets a minimum guaranteed quota, mMTC takes remainder
            embb_served = 0
            embb_guarantee = int(processing_budget * (embb_config["allocated_bandwidth"] / 120.0)) if embb_config else 5
            embb_guarantee = max(1, min(embb_guarantee, processing_budget))
            
            while r_queues["eMBB"] and embb_served < embb_guarantee and processing_budget > 0:
                pkt = r_queues["eMBB"].popleft()
                self.forward_packet(pkt, r_id, routing_table)
                processing_budget -= 1
                embb_served += 1
                
            # 3. Drain remaining eMBB and mMTC packets on best effort basis
            while processing_budget > 0:
                if r_queues["eMBB"]:
                    pkt = r_queues["eMBB"].popleft()
                    self.forward_packet(pkt, r_id, routing_table)
                elif r_queues["mMTC"]:
                    pkt = r_queues["mMTC"].popleft()
                    self.forward_packet(pkt, r_id, routing_table)
                else:
                    break # No more packets in queues
                processing_budget -= 1

    def forward_packet(self, pkt: Packet, current_router: str, routing_table: Dict[str, str]):
        """Advance a packet multi-hop towards the Core using the dynamic routing table."""
        next_hop = routing_table.get(current_router)
        
        if not next_hop:
            # Routing blackhole (e.g. node offline, route failed)
            self.tick_stats[pkt.slice_type]["dropped"] += 1
            return
            
        # Get link connecting to next hop to calculate dynamic delay and packet success
        link = next((l for l in self.links if 
                     ((l["source_id"] == current_router and l["target_id"] == next_hop) or 
                      (l["source_id"] == next_hop and l["target_id"] == current_router)) and
                     l["status"] == "online"), None)
                     
        if not link:
            # Physical Link severed
            self.tick_stats[pkt.slice_type]["dropped"] += 1
            return
            
        # Accumulate hop delay = propagation delay + queue delay penalty
        snr = self.get_snr(current_router, next_hop)
        
        # Link bit-error-rate packet drop simulation
        # High SNR -> near 100% success; low SNR -> random packet drop
        drop_probability = 0.0
        if snr < 15.0:
            drop_probability = 0.25
        elif snr < 10.0:
            drop_probability = 0.60
            
        if random.random() < drop_probability:
            self.tick_stats[pkt.slice_type]["dropped"] += 1
            return

        # Calculate packet hop delay (ms)
        propagation_delay = link["latency"]
        # Queuing delay: longer queues at next node add processing delay
        next_node_queues = self.queues.get(next_hop)
        queuing_delay = 0.0
        if next_node_queues:
            total_next_queue_len = sum(len(q) for q in next_node_queues.values())
            queuing_delay = (total_next_queue_len / 5.0)  # 0.2ms per packet waiting
            
        pkt.latency_accumulated += (propagation_delay + queuing_delay)
        
        if next_hop == "Core":
            # Packet successfully delivered!
            self.tick_stats[pkt.slice_type]["delivered"] += 1
            self.tick_stats[pkt.slice_type]["total_latency"] += pkt.latency_accumulated
        else:
            # Push into next hop queue
            next_queues = self.queues.get(next_hop)
            if next_queues:
                q = next_queues[pkt.slice_type]
                if len(q) < self.queue_limit:
                    pkt.current_node = next_hop
                    pkt.hops.append(next_hop)
                    q.append(pkt)
                else:
                    # Buffer overflow at next hop!
                    self.tick_stats[pkt.slice_type]["dropped"] += 1
            else:
                self.tick_stats[pkt.slice_type]["dropped"] += 1

    def step(self):
        """Advance the simulated network by a single discrete time tick."""
        self.current_tick += 1
        
        # Reset current tick statistics
        for s_type in ["eMBB", "URLLC", "mMTC"]:
            self.tick_stats[s_type] = {"generated": 0, "delivered": 0, "dropped": 0, "total_latency": 0.0}
            
        # 1. Compute dynamic routing paths
        routing_table = self.calculate_routing_table()
        
        # 2. Active clients generate traffic into mesh edges
        self.generate_traffic()
        
        # 3. Process routing nodes queues and forward packets
        self.process_node_queues(routing_table)
        
        # 4. Compile metrics for this tick
        self.compile_tick_metrics()

    def compile_tick_metrics(self):
        """Aggregate data from current tick and compute active 5G slicing telemetry."""
        for s_type in ["eMBB", "URLLC", "mMTC"]:
            stats = self.tick_stats[s_type]
            slice_cfg = self.slices[s_type]
            
            # Throughput = delivered packets count * average packet size in Mb * conversion
            # We scale this to simulate realistic Mbps:
            # eMBB baseline ~ 60-120 Mbps, URLLC ~ 10-25 Mbps, mMTC ~ 1-5 Mbps
            delivered = stats["delivered"]
            generated = stats["generated"]
            dropped = stats["dropped"]
            
            # Calculate throughput in Mbps
            # Packet size is in Mb, let's treat 1 tick as 100 milliseconds. 
            # 1 tick throughput in Mbps = delivered size in Mb / 0.1s
            delivered_size = delivered * (3.0 if s_type == "eMBB" else 0.2 if s_type == "URLLC" else 0.03)
            throughput = round(delivered_size / 0.1, 2)
            
            # If slice is inactive or disabled, clamp throughput to zero
            if slice_cfg["status"] != "active":
                throughput = 0.0
                
            # Latency (ms) = average latency of delivered packets
            if delivered > 0:
                avg_latency = round(stats["total_latency"] / delivered, 2)
            else:
                avg_latency = 0.0 if generated == 0 else slice_cfg["latency_limit"] * 1.5
                
            # Packet Delivery Ratio (%)
            total_handled = delivered + dropped
            if total_handled > 0:
                pdr = round((delivered / total_handled) * 100.0, 2)
            else:
                pdr = 100.0
                
            # Dynamic QoS Priority Adjustment based on database priority configurations
            # If priority has been lowered, latency suffers under load
            priority_delay_penalty = max(0.0, (slice_cfg["priority"] - 1) * 3.0)
            avg_latency = round(avg_latency + priority_delay_penalty, 2)
            
            active_users = sum(1 for n in self.nodes.values() if n["type"] == "Client" and n["slice_type"] == s_type and n["status"] == "online")
            
            # Save latest metrics
            self.latest_metrics[s_type] = {
                "throughput": throughput,
                "latency": avg_latency,
                "pdr": pdr,
                "active_users": active_users
            }
            
            # Push into historical window for graphs
            hist = self.metrics_history[s_type]
            hist.append({
                "tick": self.current_tick,
                "throughput": throughput,
                "latency": avg_latency,
                "pdr": pdr
            })
            # Keep history capped at 30 entries
            if len(hist) > 30:
                hist.pop(0)

    def trigger_congestion(self, status: bool):
        """Simulate high network-level congestion by increasing eMBB data volumes."""
        self.congestion_multiplier = 4.0 if status else 1.0

    def get_simulation_payload(self) -> Dict[str, Any]:
        """Format complete live simulation payload for WebSocket stream and charts."""
        # Calculate active routing links for UI visualization
        routing_table = self.calculate_routing_table()
        
        # Calculate queue utilization statistics per node
        queue_stats = {}
        for n_id, q_dict in self.queues.items():
            queue_stats[n_id] = {
                s_type: len(q) for s_type, q in q_dict.items()
            }
            
        # Get dynamic link load and status
        active_links = []
        for l in self.links:
            snr = self.get_snr(l["source_id"], l["target_id"])
            capacity = self.get_link_capacity(l)
            load = self.get_link_load(l["source_id"], l["target_id"])
            
            active_links.append({
                "id": l["id"],
                "source_id": l["source_id"],
                "target_id": l["target_id"],
                "capacity": round(capacity, 1),
                "latency": round(l["latency"], 1),
                "snr": round(snr, 1),
                "load": load,
                "status": l["status"]
            })
            
        return {
            "tick": self.current_tick,
            "routing_policy": self.routing_policy,
            "congestion": self.congestion_multiplier > 1.0,
            "metrics": self.latest_metrics,
            "history": self.metrics_history,
            "nodes": list(self.nodes.values()),
            "links": active_links,
            "routing_table": routing_table,
            "queues": queue_stats
        }
