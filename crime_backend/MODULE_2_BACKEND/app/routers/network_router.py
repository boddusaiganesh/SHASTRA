from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
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

@router.get("/graph-data", response_model=None)
@limiter.limit("30/minute")
async def fetch_network_graph(
    request: Request,
    search_query: Optional[str] = Query(None),
    crime_type: Optional[str] = Query(None),
    district_id: Optional[str] = Query(None),
    node_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    resolved_id = scope_district_param(resolved_id, current_user)
    data = await get_network_graph_data(db, search_query, crime_type, resolved_id, node_type=node_type)
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
    if data and isinstance(data, dict) and data.get("error") == "neo4j_offline":
        raise HTTPException(status_code=503, detail="Node detail is temporarily unavailable (graph database offline).")
    if not data:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"success": True, "data": data}

@router.get("/node-detail/{node_id}/ai-analysis")
@limiter.limit("20/minute")
async def fetch_node_ai_analysis(
    request: Request,
    node_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.services.network_service import get_node_ai_analysis
    data = await get_node_ai_analysis(db, node_id)
    return {"success": True, "data": data}

@router.get("/ai-summary")
@limiter.limit("20/minute")
async def fetch_ai_summary(
    request: Request,
    district_id: Optional[str] = Query(None),
    crime_type: Optional[str] = Query(None),
    search_query: Optional[str] = Query(None),
    node_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    resolved_id = await resolve_district_id(db, district_id)
    resolved_id = scope_district_param(resolved_id, current_user)
    data = await get_network_ai_summary(
        db, 
        district_id=resolved_id, 
        focus_area=crime_type,
        search_query=search_query,
        node_type=node_type
    )
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
@limiter.limit("50/minute")
async def expand_node(
    request: Request,
    node_id: str,
    node_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Return only the immediate neighbors of one node — for incremental graph expansion."""
    from app.core.neo4j_connection import run_neo4j_query, normalize_node
    
    root_where = "n.offender_id = $id OR n.victim_id = $id OR n.location_id = $id OR n.org_id = $id OR elementId(n) = $id OR toLower(coalesce(n.offender_id, '')) = toLower($id) OR toLower(coalesce(n.victim_id, '')) = toLower($id)"
    if node_type == "criminal":
        match_clause = f"MATCH (n)-[r]-(connected:Criminal) WHERE ({root_where})"
    elif node_type == "victim":
        match_clause = f"MATCH (n)-[r]-(connected:Victim) WHERE ({root_where})"
    elif node_type == "location":
        match_clause = f"MATCH (n)-[r]-(connected:Location) WHERE ({root_where})"
    elif node_type == "organization":
        match_clause = f"MATCH (n)-[r]-(connected:Organization) WHERE ({root_where})"
    else:
        match_clause = f"MATCH (n)-[r]-(connected) WHERE ({root_where})"

    query = f"""
    {match_clause}
    WITH n, r, connected, coalesce(r.strength_score, 0) AS s
    ORDER BY s DESC
    LIMIT 25
    RETURN n, elementId(n) AS n_eid, labels(n) AS labels_n,
           connected, elementId(connected) AS connected_eid, labels(connected) AS labels_connected,
           type(r) AS rel_type, properties(r) AS r_props
    """
    try:
        results = await run_neo4j_query(query, {"id": node_id})
        if not results:
            return {"success": True, "data": {"nodes": [], "edges": []}}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail="Node expansion is currently not available in fallback mode (Neo4j is offline)."
        )
    
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
            "strength_score": rel_props.get("strength", 50),
            "confidence_level": rel_props.get("confidence", "SUSPECTED"),
            "crime_types": rel_props.get("crime_types", []),
            "crime_count": len(rel_props.get("crime_ids", [])),
            "crime_ids": rel_props.get("crime_ids", [])
        })
        
    data = {
        "nodes": list(nodes_map.values()),
        "edges": edges
    }
    
    return {"success": True, "data": data}

from pydantic import BaseModel

class EdgeInsightRequest(BaseModel):
    node_a: dict
    node_b: dict
    edge: dict

@router.post("/edge-insight")
@limiter.limit("15/minute")
async def edge_insight(
    request: Request,
    payload: EdgeInsightRequest,
    current_user=Depends(get_current_user),
):
    from app.services.gemini_service import get_edge_connection_insight
    res = await get_edge_connection_insight(payload.node_a, payload.node_b, payload.edge)
    return {"success": True, "data": {"insight": res.get("text", ""), "is_fallback": res.get("is_fallback", False)}}


class TimelineRequest(BaseModel):
    crime_ids: list[str]

@router.post("/timeline")
@limiter.limit("30/minute")
async def network_timeline(
    request: Request,
    payload: TimelineRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Given the crime_ids currently shown on the network graph (pulled from each
    edge's crime_ids property), return them ordered by date for the timeline strip."""
    import uuid as uuid_lib
    from sqlalchemy import select
    from app.core.security import scope_district_filter
    from app.models.database_models.crime_model import Crime

    valid_ids = []
    for cid in payload.crime_ids:
        try:
            valid_ids.append(uuid_lib.UUID(cid))
        except ValueError:
            continue

    if not valid_ids:
        return {"success": True, "data": {"events": []}}

    stmt = select(Crime).where(Crime.crime_id.in_(valid_ids))
    stmt = scope_district_filter(stmt, current_user, Crime.district_id)
    result = await db.execute(stmt)
    crimes = result.scalars().all()

    events = sorted([
        {
            "crime_id": str(c.crime_id),
            "date": c.date_of_occurrence.isoformat() if c.date_of_occurrence else None,
            "crime_type": c.crime_type,
            "district_id": c.district_id,
            "status": c.status,
        }
        for c in crimes if c.date_of_occurrence
    ], key=lambda e: e["date"])

    return {"success": True, "data": {"events": events}}
