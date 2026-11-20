"""
test_simulator.py — Comprehensive Unit Tests for 5G WMN Simulator Engine

Validates the following core physics and algorithms:
  1. Free-Space Path Loss SNR Model:  SNR(d) = 75 - 20·log₁₀(d)
  2. Shannon-Hartley Link Capacity:   C = BaseCapacity × min(1.0, SNR/35)
  3. Dijkstra Dynamic Routing with three policies (shortest_hop, snr_based, load_balanced)
  4. Self-healing multi-hop bypass after single and multi-node failures
  5. End-to-end multi-hop path tracing from any client to Core
  6. Traffic generation profiles per slice type
  7. Congestion multiplier effects
"""
import math
import pytest
from backend.app.simulator import WMNNetworkSimulator, Packet
from backend.app.database import SessionLocal, NodeModel, LinkModel, SliceModel


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def simulator():
    """Initializes a clean simulator synced from the seeded database."""
    sim = WMNNetworkSimulator()
    sim.routing_policy = "shortest_hop"
    sim.congestion_multiplier = 1.0
    # Ensure all nodes and links are online for a clean baseline
    for n in sim.nodes.values():
        n["status"] = "online"
    for l in sim.links:
        l["status"] = "online"
    return sim


# ============================================================
# 1. FREE-SPACE PATH LOSS SNR MODEL TESTS
# ============================================================

class TestSNRCalculation:
    """Verify the SNR model: SNR(d) = 75 - 20·log₁₀(d), clamped [5, 45] dB."""

    def test_snr_within_bounds(self, simulator):
        """All SNR values must be clamped between 5 dB and 45 dB."""
        for n1 in simulator.nodes:
            for n2 in simulator.nodes:
                snr = simulator.get_snr(n1, n2)
                assert 5.0 <= snr <= 45.0, f"SNR({n1},{n2})={snr} out of bounds"

    def test_snr_monotonic_distance_decay(self, simulator):
        """SNR must decrease monotonically with increasing Euclidean distance."""
        # Client-eMBB-1 (50,100) is closer to Router-D (150,300) than to Core (700,300)
        snr_near = simulator.get_snr("Client-eMBB-1", "Router-D")
        snr_far = simulator.get_snr("Client-eMBB-1", "Core")
        assert snr_near > snr_far, "Closer node must have higher SNR"

    def test_snr_self_distance_clamped(self, simulator):
        """Distance to self is 0, which clamps to 10m minimum. SNR should be high."""
        snr = simulator.get_snr("Core", "Core")
        assert snr >= 40.0, f"Self-SNR should be near ceiling but got {snr}"

    def test_snr_mathematical_accuracy(self, simulator):
        """Verify the path-loss formula output against manual calculation.

        Router-A (500,150) -> Core (700,300):
        distance = sqrt((700-500)² + (300-150)²) = sqrt(40000+22500) = sqrt(62500) = 250m
        Expected SNR ≈ 75 - 20·log₁₀(250) = 75 - 20·2.3979 = 75 - 47.96 ≈ 27.04
        But clamped to [5,45], so ≈ 27 ± 1.5 fading.
        """
        # We run multiple samples to average out the ±1.5 fading randomness
        samples = [simulator.get_snr("Router-A", "Core") for _ in range(50)]
        avg_snr = sum(samples) / len(samples)
        expected = 75.0 - 20.0 * math.log10(250.0)  # ≈ 27.04
        assert abs(avg_snr - expected) < 2.5, f"Average SNR {avg_snr:.2f} deviates from expected {expected:.2f}"

    def test_snr_invalid_node_returns_zero(self, simulator):
        """Non-existent node IDs must return 0.0 SNR."""
        assert simulator.get_snr("INVALID_NODE", "Core") == 0.0
        assert simulator.get_snr("Core", "NONEXISTENT") == 0.0


# ============================================================
# 2. SHANNON-HARTLEY LINK CAPACITY BUDGET TESTS
# ============================================================

class TestLinkCapacity:
    """Verify: C = BaseCapacity × min(1.0, SNR/35), with offline = 0."""

    def test_online_link_positive_capacity(self, simulator):
        """All online links must yield capacity > 0."""
        for link in simulator.links:
            if link["status"] == "online":
                cap = simulator.get_link_capacity(link)
                assert cap > 0, f"Link {link['source_id']}->{link['target_id']} capacity must be > 0"

    def test_offline_link_zero_capacity(self, simulator):
        """Offline links must return exactly 0.0 capacity."""
        link = simulator.links[0].copy()
        link["status"] = "offline"
        assert simulator.get_link_capacity(link) == 0.0

    def test_capacity_bounded_by_base(self, simulator):
        """Dynamic capacity must never exceed the configured base capacity."""
        for link in simulator.links:
            cap = simulator.get_link_capacity(link)
            assert cap <= link["capacity"], (
                f"Link {link['source_id']}->{link['target_id']}: "
                f"dynamic capacity {cap} > base capacity {link['capacity']}"
            )

    def test_capacity_scales_with_snr(self, simulator):
        """Higher SNR links should yield higher capacity (same base)."""
        # Router-A->Core is at distance 250m, Router-D->Router-B is at distance ~354m
        link_close = next(l for l in simulator.links
                         if l["source_id"] == "Router-A" and l["target_id"] == "Core")
        link_far = next(l for l in simulator.links
                        if l["source_id"] == "Router-D" and l["target_id"] == "Router-B")
        # Normalize for different base capacities
        eff_close = simulator.get_link_capacity(link_close) / link_close["capacity"]
        eff_far = simulator.get_link_capacity(link_far) / link_far["capacity"]
        assert eff_close >= eff_far, "Closer link should have higher SNR efficiency"


# ============================================================
# 3. DIJKSTRA ROUTING CONVERGENCE TESTS
# ============================================================

class TestDijkstraRouting:
    """Verify Dijkstra convergence with three routing policies."""

    def test_shortest_hop_direct_routers_reach_core(self, simulator):
        """Router-A and Router-B are directly connected to Core with 1 hop."""
        simulator.routing_policy = "shortest_hop"
        rt = simulator.calculate_routing_table()
        assert rt["Router-A"] == "Core"
        assert rt["Router-B"] == "Core"

    def test_shortest_hop_inner_routers(self, simulator):
        """Router-C and Router-D must find a 2-hop path to Core."""
        simulator.routing_policy = "shortest_hop"
        rt = simulator.calculate_routing_table()
        # Router-C connects to Router-A and Router-B (both 1 hop to Core)
        assert rt["Router-C"] in ["Router-A", "Router-B"]
        # Router-D has direct links to Router-A, Router-B, Router-C
        assert rt["Router-D"] in ["Router-A", "Router-B", "Router-C"]

    def test_snr_based_routing_converges(self, simulator):
        """SNR-based routing must produce a valid routing table for all online nodes."""
        simulator.routing_policy = "snr_based"
        rt = simulator.calculate_routing_table()
        for nid, node in simulator.nodes.items():
            if node["status"] == "online" and nid != "Core":
                assert rt.get(nid) is not None, f"Node {nid} unreachable under snr_based"

    def test_load_balanced_routing_converges(self, simulator):
        """Load-balanced routing must produce a valid routing table for all online nodes."""
        simulator.routing_policy = "load_balanced"
        rt = simulator.calculate_routing_table()
        for nid, node in simulator.nodes.items():
            if node["status"] == "online" and nid != "Core":
                assert rt.get(nid) is not None, f"Node {nid} unreachable under load_balanced"

    def test_all_clients_have_path_to_core(self, simulator):
        """Every online client must have a valid multi-hop path ending at Core."""
        simulator.routing_policy = "shortest_hop"
        rt = simulator.calculate_routing_table()
        clients = [nid for nid, n in simulator.nodes.items()
                    if n["type"] == "Client" and n["status"] == "online"]
        for c in clients:
            # Trace path from client to Core
            path, curr = [c], c
            while curr != "Core":
                nxt = rt.get(curr)
                assert nxt is not None, f"Path from {c} broken at {curr}"
                assert nxt not in path, f"Routing loop detected for {c} at {curr}"
                path.append(nxt)
                curr = nxt
            assert path[-1] == "Core", f"Client {c} path does not end at Core"


# ============================================================
# 4. SELF-HEALING BYPASS TESTS
# ============================================================

class TestSelfHealing:
    """Verify dynamic routing self-heals when nodes go offline."""

    def test_single_router_failure_bypass(self, simulator):
        """After Router-A goes offline, all nodes must still route to Core via Router-B."""
        simulator.routing_policy = "shortest_hop"
        # Disable Router-A
        simulator.nodes["Router-A"]["status"] = "offline"
        for l in simulator.links:
            if l["source_id"] == "Router-A" or l["target_id"] == "Router-A":
                l["status"] = "offline"

        rt = simulator.calculate_routing_table()
        # Router-B should still route directly to Core
        assert rt["Router-B"] == "Core"
        # Router-C must use Router-B now
        assert rt["Router-C"] == "Router-B"
        # Router-D must find a path through Router-B or Router-C
        assert rt["Router-D"] in ["Router-B", "Router-C"]

    def test_double_router_failure(self, simulator):
        """After Router-A and Router-C go offline, traffic must reroute via Router-B/D path."""
        simulator.routing_policy = "shortest_hop"
        for rid in ["Router-A", "Router-C"]:
            simulator.nodes[rid]["status"] = "offline"
            for l in simulator.links:
                if l["source_id"] == rid or l["target_id"] == rid:
                    l["status"] = "offline"

        rt = simulator.calculate_routing_table()
        assert rt["Router-B"] == "Core"
        assert rt["Router-D"] == "Router-B"

    def test_core_offline_produces_empty_routes(self, simulator):
        """If the Core gateway goes offline, routing table must be empty (no destination)."""
        simulator.nodes["Core"]["status"] = "offline"
        rt = simulator.calculate_routing_table()
        assert rt == {}, "With Core offline, no routes should exist"


# ============================================================
# 5. TRAFFIC GENERATION & CONGESTION MULTIPLIER TESTS
# ============================================================

class TestTrafficGeneration:
    """Verify traffic profiles and congestion knobs."""

    def test_congestion_multiplier_toggle(self, simulator):
        """Congestion multiplier should toggle between 1.0 and 4.0."""
        assert simulator.congestion_multiplier == 1.0
        simulator.trigger_congestion(True)
        assert simulator.congestion_multiplier == 4.0
        simulator.trigger_congestion(False)
        assert simulator.congestion_multiplier == 1.0

    def test_simulation_step_advances_tick(self, simulator):
        """Each call to step() must increment the current_tick counter."""
        t0 = simulator.current_tick
        simulator.step()
        assert simulator.current_tick == t0 + 1
        simulator.step()
        assert simulator.current_tick == t0 + 2

    def test_simulation_step_produces_metrics(self, simulator):
        """After stepping, latest_metrics must contain throughput/latency/pdr for all slices."""
        simulator.step()
        for s_type in ["eMBB", "URLLC", "mMTC"]:
            m = simulator.latest_metrics[s_type]
            assert "throughput" in m
            assert "latency" in m
            assert "pdr" in m
            assert "active_users" in m

    def test_simulation_payload_structure(self, simulator):
        """get_simulation_payload() must return all required keys for frontend consumption."""
        simulator.step()
        payload = simulator.get_simulation_payload()
        required_keys = ["tick", "routing_policy", "congestion", "metrics",
                         "history", "nodes", "links", "routing_table", "queues"]
        for key in required_keys:
            assert key in payload, f"Payload missing key: {key}"
        assert isinstance(payload["nodes"], list)
        assert isinstance(payload["links"], list)
        assert len(payload["nodes"]) >= 11
