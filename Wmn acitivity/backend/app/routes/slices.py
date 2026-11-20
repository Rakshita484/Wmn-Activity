from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import SessionLocal, SliceModel
from ..schemas import SliceResponse, SliceUpdate, SliceCreate

router = APIRouter(prefix="/api/slices", tags=["slices"])

# DB Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=List[SliceResponse])
def get_slices(db: Session = Depends(get_db)):
    """Fetch all active 5G network slices."""
    return db.query(SliceModel).all()

@router.get("/{slice_type}", response_model=SliceResponse)
def get_slice(slice_type: str, db: Session = Depends(get_db)):
    """Fetch single slice details by its type (eMBB, URLLC, mMTC)."""
    s = db.query(SliceModel).filter(SliceModel.type == slice_type).first()
    if not s:
        raise HTTPException(status_code=404, detail=f"Slice type {slice_type} not found.")
    return s

@router.put("/{slice_type}", response_model=SliceResponse)
def update_slice_qos(slice_type: str, payload: SliceUpdate, db: Session = Depends(get_db)):
    """Update QoS SLA configurations for a specific slice."""
    s = db.query(SliceModel).filter(SliceModel.type == slice_type).first()
    if not s:
        raise HTTPException(status_code=404, detail=f"Slice type {slice_type} not found.")
        
    if payload.name is not None:
        s.name = payload.name
    if payload.allocated_bandwidth is not None:
        s.allocated_bandwidth = payload.allocated_bandwidth
    if payload.latency_limit is not None:
        s.latency_limit = payload.latency_limit
    if payload.priority is not None:
        s.priority = payload.priority
    if payload.status is not None:
        s.status = payload.status
    if payload.color is not None:
        s.color = payload.color
        
    db.commit()
    db.refresh(s)
    
    # Notify simulator to reload database configurations
    from ..main import simulator
    if simulator:
        simulator.load_from_db()
        
    return s
