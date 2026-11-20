from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any
from ..main import mcp_server

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

@router.post("/rpc")
def handle_mcp_rpc(payload: Dict[str, Any] = Body(...)):
    """
    Direct endpoint to submit standard MCP JSON-RPC 2.0 requests.
    Enables frontend dashboard to simulate true AI client context tools calls.
    """
    if not mcp_server:
        raise HTTPException(status_code=500, detail="MCP Server inactive.")
        
    response = mcp_server.handle_request(payload)
    if response is None:
        return {"status": "success", "message": "Notification processed."}
        
    return response

@router.get("/tools")
def list_mcp_tools():
    """Retrieve list of all tools exposed by the MCP server."""
    if not mcp_server:
        raise HTTPException(status_code=500, detail="MCP Server inactive.")
    return mcp_server.tools

@router.get("/resources")
def list_mcp_resources():
    """Retrieve list of resources managed by the MCP server."""
    if not mcp_server:
        raise HTTPException(status_code=500, detail="MCP Server inactive.")
    return mcp_server.resources

@router.get("/prompts")
def list_mcp_prompts():
    """Retrieve list of prompt frameworks supported by the MCP server."""
    if not mcp_server:
        raise HTTPException(status_code=500, detail="MCP Server inactive.")
    return mcp_server.prompts
