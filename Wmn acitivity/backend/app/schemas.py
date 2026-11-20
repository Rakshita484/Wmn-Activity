from pydantic import BaseModel, Field
from typing import Optional, List

class SliceBase(BaseModel):
    id: str = Field(..., description="Unique slice identifier (e.g., slice-embb)")
    name: str = Field(..., description="Human-readable name of the network slice")
    type: str = Field(..., description="QoS Slicing class: eMBB, URLLC, or mMTC")
    allocated_bandwidth: float = Field(..., description="Bandwidth allocation in Mbps")
    latency_limit: float = Field(..., description="Maximum acceptable delay in ms")
    priority: int = Field(..., description="Scheduling priority (1 = Highest, 3 = Lowest)")
    status: str = Field("active", description="Status of the slice: active or inactive")
    color: str = Field("#ffffff", description="Hex color value for UI representation")

class SliceCreate(SliceBase):
    pass

class SliceUpdate(BaseModel):
    name: Optional[str] = None
    allocated_bandwidth: Optional[float] = None
    latency_limit: Optional[float] = None
    priority: Optional[int] = None
    status: Optional[str] = None
    color: Optional[str] = None

class SliceResponse(SliceBase):
    class Config:
        from_attributes = True

class NodeResponse(BaseModel):
    id: str
    name: str
    type: str
    x: float
    y: float
    status: str
    slice_type: Optional[str] = None

    class Config:
        from_attributes = True

class LinkResponse(BaseModel):
    id: int
    source_id: str
    target_id: str
    capacity: float
    latency: float
    status: str

    class Config:
        from_attributes = True

class NodeStatusUpdate(BaseModel):
    status: str = Field(..., description="Status string: online or offline")

class RoutingPolicyUpdate(BaseModel):
    policy: str = Field(..., description="Routing strategy: shortest_hop, snr_based, or load_balanced")
