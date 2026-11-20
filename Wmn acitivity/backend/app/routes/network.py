from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from ..database import SessionLocal, NodeModel, LinkModel
from ..schemas import NodeResponse, LinkResponse, NodeStatusUpdate, RoutingPolicyUpdate

router = APIRouter(prefix="/api/network", tags=["network"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/nodes", response_model=List[NodeResponse])
def get_nodes(db: Session = Depends(get_db)):
    """Retrieve all physical nodes (Routers, Clients, Gateway)."""
    return db.query(NodeModel).all()

@router.get("/links", response_model=List[LinkResponse])
def get_links(db: Session = Depends(get_db)):
    """Retrieve all backhaul and access links."""
    return db.query(LinkModel).all()

@router.put("/nodes/{node_id}/status", response_model=NodeResponse)
def toggle_node(node_id: str, payload: NodeStatusUpdate, db: Session = Depends(get_db)):
    """Power a router online/offline to trigger dynamic routing self-healing."""
    node = db.query(NodeModel).filter(NodeModel.id == node_id).first()
    if not node:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found.")
        
    status = payload.status.lower()
    if status not in ["online", "offline"]:
        raise HTTPException(status_code=400, detail="Status must be 'online' or 'offline'.")
        
    node.status = status
    
    # Cascade online/offline status to all links physically connected to this node
    links = db.query(LinkModel).filter((LinkModel.source_id == node_id) | (LinkModel.target_id == node_id)).all()
    for l in links:
        l.status = status
        
    db.commit()
    db.refresh(node)
    
    # Instruct simulator to sync settings immediately
    from ..main import simulator
    if simulator:
        simulator.load_from_db()
        
    return node

@router.post("/routing-policy")
def set_routing_policy(payload: RoutingPolicyUpdate):
    """Dynamically modify the mesh backhaul cost routing metrics."""
    from ..main import simulator
    if not simulator:
        raise HTTPException(status_code=500, detail="Simulator instance inactive.")
        
    policy = payload.policy.lower()
    if policy not in ["shortest_hop", "snr_based", "load_balanced"]:
        raise HTTPException(status_code=400, detail="Invalid routing policy.")
        
    simulator.routing_policy = policy
    return {"success": True, "policy": policy}

@router.get("/telemetry")
def get_telemetry():
    """Retrieve current, high-fidelity aggregate telemetry and metrics history."""
    from ..main import simulator
    if not simulator:
        raise HTTPException(status_code=500, detail="Simulator inactive.")
    return simulator.get_simulation_payload()
