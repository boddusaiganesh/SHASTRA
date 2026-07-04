"""
Network Analysis Service - Criminal network and link analysis
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import logging

from app.core.neo4j_connection import get_network_graph, run_neo4j_query
from app.models.database_models.offender_model import Offender
from app.core.redis_connection import cache_get, cache_set

logger = logging.getLogger(__name__)


async def get_network_graph_data(
    db: AsyncSession,
    search_query: Optional[str] = None,
    crime_type: Optional[str] = None,
    district_id: Optional[str] = None,
    depth: int = 2,
    node_limit: int = 100,
) -> Dict[str, Any]:
    """Get criminal network graph data"""
    
    cache_key = f"network_graph:{search_query}:{crime_type}:{district_id}:{depth}:{node_limit}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    # Try Neo4j first
    graph_data = await get_network_graph(
        search_query=search_query,
        crime_type=crime_type,
        district_id=district_id,
        depth=depth,
        node_limit=node_limit,
    )
    
    # If Neo4j is offline, return the status explicitly
    if graph_data.get("status") == "offline":
        return graph_data
    
    # If Neo4j is available but there is no data
    if not graph_data.get("nodes"):
        graph_data["status"] = "no_data"
        
    await cache_set(cache_key, graph_data, expiry=600)
    return graph_data


async def build_network_from_postgres(
    db: AsyncSession,
    search_query: Optional[str] = None,
    district_id: Optional[str] = None,
    node_limit: int = 100,
) -> Dict[str, Any]:
    """Build network graph from PostgreSQL data when Neo4j is unavailable"""
    from app.models.database_models.crime_model import CrimeOffenderLink, Crime
    
    # Get offenders
    query = select(Offender).limit(node_limit)
    
    if district_id:
        query = query.where(Offender.district_id == district_id)
    if search_query:
        query = query.where(
            (Offender.first_name.ilike(f"%{search_query}%")) |
            (Offender.last_name.ilike(f"%{search_query}%"))
        )
    
    result = await db.execute(query)
    offenders = result.scalars().all()
    
    nodes = []
    edges = []
    node_id_map = {}
    
    for offender in offenders:
        node_id = str(offender.offender_id)
        
        # Risk-based color
        color_map = {"HIGH": "#ef4444", "MEDIUM": "#f97316", "LOW": "#22c55e"}
        color = color_map.get(offender.risk_level, "#6b7280")
        
        nodes.append({
            "node_id": node_id,
            "node_type": "criminal",
            "label": f"{offender.first_name} {offender.last_name}",
            "risk_score": offender.risk_score or 0,
            "crime_count": offender.total_crimes or 0,
            "size": 15 + (offender.total_crimes or 0) * 3,
            "color": color,
            "profile_data": {
                "offender_reference": offender.offender_reference,
                "status": offender.status,
                "risk_level": offender.risk_level,
                "district_id": offender.district_id,
            },
        })
        node_id_map[node_id] = offender
    
    # Build edges from known_associates
    for offender in offenders:
        if offender.known_associates:
            for associate_id in offender.known_associates:
                source_id = str(offender.offender_id)
                target_id = associate_id
                
                # Only add edge if target node exists
                if any(n["node_id"] == target_id for n in nodes):
                    edges.append({
                        "edge_id": f"{source_id}_{target_id}",
                        "source_node_id": source_id,
                        "target_node_id": target_id,
                        "relationship_type": "KNOWS",
                        "strength_score": 60,
                        "confidence_level": "SUSPECTED",
                        "crime_count": 1,
                    })
    
    return {
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "network_density": round(len(edges) / max(len(nodes), 1), 2),
        "key_players": [
            n["node_id"]
            for n in sorted(nodes, key=lambda x: x["crime_count"], reverse=True)[:5]
        ],
    }


async def get_node_detail(
    db: AsyncSession,
    node_id: str,
) -> Optional[Dict[str, Any]]:
    """Get detailed information about a specific network node"""
    from app.services.gemini_service import get_offender_ai_analysis
    
    try:
        import uuid
        offender_uuid = uuid.UUID(node_id)
        
        result = await db.execute(
            select(Offender).where(Offender.offender_id == offender_uuid)
        )
        offender = result.scalar_one_or_none()
        
        if not offender:
            return None
        
        # Get crime history
        from app.models.database_models.crime_model import CrimeOffenderLink, Crime
        link_result = await db.execute(
            select(CrimeOffenderLink).where(CrimeOffenderLink.offender_id == offender_uuid)
        )
        links = link_result.scalars().all()
        
        crime_ids = [link.crime_id for link in links]
        crimes = []
        for cid in crime_ids[:10]:
            cr = await db.execute(select(Crime).where(Crime.crime_id == cid))
            crime = cr.scalar_one_or_none()
            if crime:
                crimes.append({
                    "crime_id": str(crime.crime_id),
                    "crime_type": crime.crime_type,
                    "date": str(crime.date_of_occurrence),
                    "status": crime.status,
                    "severity": crime.severity,
                })
        
        # Get AI analysis
        ai_analysis = await get_offender_ai_analysis(offender.to_dict(), crimes)
        
        return {
            "node_id": node_id,
            "node_type": "criminal",
            "label": f"{offender.first_name} {offender.last_name}",
            "risk_score": offender.risk_score,
            "crime_count": offender.total_crimes,
            "direct_connections": len(offender.known_associates or []),
            "profile_data": offender.to_dict(),
            "connected_nodes": offender.known_associates or [],
            "timeline": crimes,
            "ai_analysis": ai_analysis,
        }
        
    except (ValueError, Exception) as e:
        logger.error(f"Error getting node detail: {e}")
        return None


async def get_network_ai_summary(
    db: AsyncSession,
    district_id: Optional[str] = None,
    focus_area: Optional[str] = None,
) -> Dict[str, Any]:
    """Get AI-powered network analysis summary"""
    from app.services.gemini_service import get_network_analysis_summary
    
    cache_key = f"network_ai_summary:{district_id}:{focus_area}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    # Get network statistics
    offender_query = select(Offender).where(Offender.total_crimes > 1)
    if district_id:
        offender_query = offender_query.where(Offender.district_id == district_id)
    
    result = await db.execute(offender_query.limit(50))
    high_activity_offenders = result.scalars().all()
    
    # Find suspicious pairs (shared known associates)
    suspicious_pairs = []
    all_offenders = [o.to_dict() for o in high_activity_offenders]
    
    for i, o1 in enumerate(all_offenders[:10]):
        for o2 in all_offenders[i+1:i+6]:
            common = set(o1.get("known_associates", [])) & set(o2.get("known_associates", []))
            if common:
                suspicious_pairs.append({
                    "offender_1": o1["full_name"],
                    "offender_2": o2["full_name"],
                    "connection_type": "SHARED_ASSOCIATE",
                    "confidence": "SUSPECTED",
                })
    
    # Network stats
    network_stats = {
        "total_criminals": len(all_offenders),
        "high_risk_count": sum(1 for o in all_offenders if o.get("risk_level") == "HIGH"),
        "active_count": sum(1 for o in all_offenders if o.get("status") == "ACTIVE"),
        "network_density": round(len(suspicious_pairs) / max(len(all_offenders), 1), 2),
    }
    
    # Get AI summary
    summary_text = await get_network_analysis_summary(
        all_offenders[:20], suspicious_pairs, network_stats, focus_area
    )
    
    # Extract key findings
    key_findings = [
        f"Identified {network_stats['total_criminals']} repeat offenders in the network",
        f"{network_stats['high_risk_count']} individuals classified as HIGH risk",
        f"{network_stats['active_count']} offenders currently active",
        f"Detected {len(suspicious_pairs)} suspicious associations",
        "Network analysis reveals organized crime patterns requiring investigation",
    ]
    
    recommended_actions = [
        "Prioritize surveillance of HIGH risk individuals",
        "Investigate identified suspicious pairs for coordinated activity",
        "Coordinate inter-district intelligence sharing",
        "Deploy undercover assets in identified criminal network areas",
        "Issue lookout notices for absconding network members",
    ]
    
    response = {
        "summary_text": summary_text,
        "key_findings": key_findings,
        "suspicious_pairs": suspicious_pairs[:10],
        "recommended_actions": recommended_actions,
        "network_stats": network_stats,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await cache_set(cache_key, response, expiry=1800)
    return response
