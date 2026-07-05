from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.database import get_db
from app.core.security import get_current_user, scope_district_param
from app.utils.district_resolver import resolve_district_id
from app.services.network_service import get_network_graph_data, get_node_detail, get_network_ai_summary

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

@router.get("/graph")            
@router.get("/graph-data")
@limiter.limit("30/minute")
async def fetch_network_graph(
    request: Request,
    search_query: Optional[str] = Query(None),
    crime_type: Optional[str] = Query(None),
    district_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    resolved_id = scope_district_param(resolved_id, current_user)
    data = await get_network_graph_data(db, search_query, crime_type, resolved_id)
    return {"success": True, "data": data}

@router.get("/node-detail/{node_id}")
@limiter.limit("30/minute")
async def fetch_node_detail(
    request: Request,
    node_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    data = await get_node_detail(db, node_id)
    if not data:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"success": True, "data": data}

@router.get("/ai-summary")
@limiter.limit("5/minute")
async def fetch_ai_summary(
    request: Request,
    district_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    resolved_id = scope_district_param(resolved_id, current_user)
    data = await get_network_ai_summary(db, resolved_id)
    return {"success": True, "data": data}

@router.get("/shortest-path")
@limiter.limit("10/minute")
async def shortest_path(
    request: Request,
    node_a: str = Query(...),
    node_b: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.core.neo4j_connection import find_shortest_path
    data = await find_shortest_path(node_a, node_b)
    return {"success": True, "data": data}

@router.get("/expand/{node_id}")
@limiter.limit("20/minute")
async def expand_node(
    request: Request,
    node_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return only the immediate neighbors of one node — for incremental graph expansion."""
    from app.core.neo4j_connection import run_neo4j_query, normalize_node
    
    query = """
    MATCH (n)-[r]-(connected)
    WHERE n.offender_id = $id OR n.victim_id = $id OR n.location_id = $id OR n.org_id = $id OR elementId(n) = $id
    RETURN n, elementId(n) AS n_eid, labels(n) AS labels_n,
           connected, elementId(connected) AS connected_eid, labels(connected) AS labels_connected,
           type(r) AS rel_type, properties(r) AS r_props
    LIMIT 25
    """
    results = await run_neo4j_query(query, {"id": node_id})
    
    nodes_map = {}
    edges = []
    
    for record in results:
        # Source node
        node = record["n"]
        n_eid = record["n_eid"]
        labels_n = record["labels_n"]
        norm_n = normalize_node(node, labels_n, n_eid)
        src_id = norm_n["node_id"]
        
        if src_id not in nodes_map:
            nodes_map[src_id] = norm_n
            
        # Connected node
        connected = record["connected"]
        conn_eid = record["connected_eid"]
        labels_conn = record["labels_connected"]
        norm_conn = normalize_node(connected, labels_conn, conn_eid)
        norm_conn["size"] = 15
        tgt_id = norm_conn["node_id"]
        
        if tgt_id not in nodes_map:
            nodes_map[tgt_id] = norm_conn
            
        # Edge
        rel_props = record["r_props"] or {}
        edges.append({
            "edge_id": f"{src_id}_{tgt_id}",
            "source_node_id": src_id,
            "target_node_id": tgt_id,
            "relationship_type": record["rel_type"],
            "strength_score": rel_props.get("strength_score", 50),
            "confidence_level": rel_props.get("confidence_level", "SUSPECTED"),
            "crime_count": len(rel_props.get("crime_ids", []))
        })
        
    data = {
        "nodes": list(nodes_map.values()),
        "edges": edges
    }
    
    return {"success": True, "data": data}

