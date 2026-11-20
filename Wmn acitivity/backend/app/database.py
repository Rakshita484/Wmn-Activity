import os
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = "sqlite:///./wmn_slicing.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class SliceModel(Base):
    __tablename__ = "slices"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # eMBB, URLLC, mMTC
    allocated_bandwidth = Column(Float, nullable=False)  # in Mbps
    latency_limit = Column(Float, nullable=False)  # in ms
    priority = Column(Integer, nullable=False)  # 1 (Highest) to 3 (Lowest)
    status = Column(String, default="active")  # active, inactive
    color = Column(String, nullable=False)

class NodeModel(Base):
    __tablename__ = "nodes"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # Core, Router, Client
    x = Column(Float, nullable=False)  # Coordinates for frontend visualization
    y = Column(Float, nullable=False)
    status = Column(String, default="online")  # online, offline
    slice_type = Column(String, nullable=True)  # Only for Clients (e.g. eMBB)

class LinkModel(Base):
    __tablename__ = "links"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String, ForeignKey("nodes.id"), nullable=False)
    target_id = Column(String, ForeignKey("nodes.id"), nullable=False)
    capacity = Column(Float, nullable=False)  # Base bandwidth in Mbps
    latency = Column(Float, nullable=False)  # Base propagation delay in ms
    status = Column(String, default="online")  # online, offline

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Check if database is already seeded
    if db.query(SliceModel).count() > 0:
        db.close()
        return

    print("Seeding initial 5G network slicing and WMN topology...")

    # Seed Standard 5G Slices
    slices = [
        SliceModel(
            id="slice-embb",
            name="Enhanced Mobile Broadband (eMBB)",
            type="eMBB",
            allocated_bandwidth=100.0,
            latency_limit=50.0,
            priority=2,
            status="active",
            color="#00d2ff"  # Cyan/Blue
        ),
        SliceModel(
            id="slice-urllc",
            name="Ultra-Reliable Low-Latency (URLLC)",
            type="URLLC",
            allocated_bandwidth=20.0,
            latency_limit=5.0,
            priority=1,
            status="active",
            color="#ff3b30"  # Red
        ),
        SliceModel(
            id="slice-mmtc",
            name="Massive IoT (mMTC)",
            type="mMTC",
            allocated_bandwidth=10.0,
            latency_limit=200.0,
            priority=3,
            status="active",
            color="#4cd964"  # Green
        )
    ]
    for s in slices:
        db.add(s)

    # Seed 5G WMN Nodes (Positions mapped on a 800x600 grid)
    nodes = [
        # Core Network Gateway
        NodeModel(id="Core", name="5G UPF Core Gateway", type="Core", x=700, y=300, status="online"),
        
        # Mesh Routers (Backbone)
        NodeModel(id="Router-A", name="Mesh Backbone Router A", type="Router", x=500, y=150, status="online"),
        NodeModel(id="Router-B", name="Mesh Backbone Router B", type="Router", x=500, y=450, status="online"),
        NodeModel(id="Router-C", name="Mesh Backbone Router C", type="Router", x=300, y=300, status="online"),
        NodeModel(id="Router-D", name="Mesh Backbone Router D", type="Router", x=150, y=300, status="online"),
        
        # Mesh Clients (Devices bound to 5G Slices)
        NodeModel(id="Client-eMBB-1", name="AR Streamer (Client-eMBB-1)", type="Client", x=50, y=100, status="online", slice_type="eMBB"),
        NodeModel(id="Client-eMBB-2", name="4K Video Terminal (Client-eMBB-2)", type="Client", x=250, y=100, status="online", slice_type="eMBB"),
        
        NodeModel(id="Client-URLLC-1", name="Autonomous Vehicle (Client-URLLC-1)", type="Client", x=50, y=300, status="online", slice_type="URLLC"),
        NodeModel(id="Client-URLLC-2", name="Haptic Tele-surgery unit (Client-URLLC-2)", type="Client", x=450, y=550, status="online", slice_type="URLLC"),
        
        NodeModel(id="Client-mMTC-1", name="Smart Grid Sensor Array (Client-mMTC-1)", type="Client", x=50, y=500, status="online", slice_type="mMTC"),
        NodeModel(id="Client-mMTC-2", name="Agricultural Telemetry (Client-mMTC-2)", type="Client", x=250, y=500, status="online", slice_type="mMTC")
    ]
    for n in nodes:
        db.add(n)

    # Seed Mesh Links (Bidirectional connectivity)
    # We define physical coordinates that connect mesh routers in an dynamic multi-hop structure.
    links = [
        # Router to Core connections
        LinkModel(source_id="Router-A", target_id="Core", capacity=250.0, latency=2.0, status="online"),
        LinkModel(source_id="Router-B", target_id="Core", capacity=250.0, latency=2.0, status="online"),
        
        # Router to Router backhaul mesh links
        LinkModel(source_id="Router-C", target_id="Router-A", capacity=150.0, latency=4.0, status="online"),
        LinkModel(source_id="Router-C", target_id="Router-B", capacity=150.0, latency=4.0, status="online"),
        LinkModel(source_id="Router-D", target_id="Router-C", capacity=100.0, latency=5.0, status="online"),
        LinkModel(source_id="Router-A", target_id="Router-B", capacity=100.0, latency=6.0, status="online"),
        
        # Redundant mesh backhaul backup paths
        LinkModel(source_id="Router-D", target_id="Router-A", capacity=80.0, latency=8.0, status="online"),
        LinkModel(source_id="Router-D", target_id="Router-B", capacity=80.0, latency=8.0, status="online"),
        
        # Clients connecting to closest/primary Mesh Routers
        LinkModel(source_id="Client-eMBB-1", target_id="Router-D", capacity=80.0, latency=8.0, status="online"),
        LinkModel(source_id="Client-eMBB-2", target_id="Router-A", capacity=100.0, latency=5.0, status="online"),
        
        LinkModel(source_id="Client-URLLC-1", target_id="Router-D", capacity=30.0, latency=3.0, status="online"),
        LinkModel(source_id="Client-URLLC-2", target_id="Router-B", capacity=40.0, latency=2.0, status="online"),
        
        LinkModel(source_id="Client-mMTC-1", target_id="Router-D", capacity=15.0, latency=15.0, status="online"),
        LinkModel(source_id="Client-mMTC-2", target_id="Router-C", capacity=20.0, latency=10.0, status="online")
    ]
    for l in links:
        db.add(l)
        
    db.commit()
    db.close()
    print("Database seeded successfully.")
