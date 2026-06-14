from backend.core.schemas import SecurityValidateRequest, SecuritySimulateRequest
from typing import Optional, List, Dict, Any
from fastapi import Header, Query, APIRouter, Request, HTTPException
import backend.dependencies as deps
from backend.core.config import *
from backend.core.utils import *
router = APIRouter(tags=['Maintenance'])

# ---------------------------------------------------------------
# REST Endpoints — Road Maintenance
# ---------------------------------------------------------------
@router.get("/api/maintenance/orders")
async def maintenance_orders():
    if not deps.maintenance_ai:
        return []
    return deps.maintenance_ai.get_open_orders()



@router.get("/api/maintenance/geojson")
async def maintenance_geojson():
    orders = deps.maintenance_ai.get_open_orders() if deps.maintenance_ai else []
    features = []
    for idx, order in enumerate(orders):
        lat = float(order.get("lat", 28.6139))
        lon = float(order.get("lon", 77.2090))
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "id": order.get("id", f"road_{idx}"),
                    "severity": order.get("priority", "medium"),
                    "issue": order.get("issue", order.get("type", "road_anomaly")),
                    "junction": order.get("junction_id", "unknown"),
                },
            }
        )
    return {"type": "FeatureCollection", "features": features}



# ---------------------------------------------------------------
# REST Endpoints — Cybersecurity
# ---------------------------------------------------------------
@router.post("/api/security/validate")
async def security_validate(req: SecurityValidateRequest):
    if not deps.security_detector:
        return JSONResponse({"error": "Security module not available"}, status_code=503)
    return deps.security_detector.validate_command(req.junction_id, req.new_phase, source=req.source)



@router.post("/api/security/simulate")
async def security_simulate(req: SecuritySimulateRequest):
    if not deps.security_detector:
        return JSONResponse({"error": "Security module not available"}, status_code=503)
    return deps.security_detector.simulate_attack(req.attack_type, req.junction_id)



@router.get("/api/security/events")
async def security_events():
    if not deps.security_detector:
        return []
    return deps.security_detector.get_events(limit=50)



