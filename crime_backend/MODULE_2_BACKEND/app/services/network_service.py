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

def compute_graph_centrality(nodes: list, edges: list) -> dict:
    import networkx as nx

    G = nx.Graph()
    for n in nodes:
        G.add_node(n["node_id"])
    for e in edges:
        src = e.get("source_node_id") or e.get("source")
        tgt = e.get("target_node_id") or e.get("target")
        if src and tgt and src in G and tgt in G:
            weight = e.get("strength_score", 50)
            G.add_edge(src, tgt, weight=weight)

    if G.number_of_nodes() == 0:
        return {}

    betweenness = nx.betweenness_centrality(G, weight="weight")
    degree = dict(G.degree())
    try:
        pagerank = nx.pagerank(G, weight="weight")
    except Exception:
        pagerank = {n: 0.0 for n in G.nodes()}

    return {
        node_id: {
            "betweenness": round(betweenness.get(node_id, 0), 4),
            "degree": degree.get(node_id, 0),
            "pagerank": round(pagerank.get(node_id, 0), 4),
        }
        for node_id in G.nodes()
    }

def detect_communities(nodes: list, edges: list) -> dict:
    import networkx as nx
    from networkx.algorithms.community import louvain_communities

    G = nx.Graph()
    for n in nodes:
        G.add_node(n["node_id"])
    for e in edges:
        src = e.get("source_node_id") or e.get("source")
        tgt = e.get("target_node_id") or e.get("target")
        if src and tgt and src in G and tgt in G:
            G.add_edge(src, tgt, weight=e.get("strength_score", 50))

    if G.number_of_edges() == 0:
        return {n["node_id"]: 0 for n in nodes}

    communities = louvain_communities(G, weight="weight", seed=42)
    community_map = {}
    for idx, community in enumerate(communities):
        for node_id in community:
            community_map[node_id] = idx
    return community_map


async def get_network_graph_data(
    db: AsyncSession,
    search_query: Optional[str] = None,
    crime_type: Optional[str] = None,
    district_id: Optional[str] = None,
    node_type: Optional[str] = None,
    depth: int = 2,
    node_limit: int = 100,
) -> Dict[str, Any]:
    """Get criminal network graph data"""
    
    cache_key = f"network_graph:{search_query}:{crime_type}:{district_id}:{node_type}:{depth}:{node_limit}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    # Try Neo4j first
    graph_data = await get_network_graph(
        search_query=search_query,
        crime_type=crime_type,
        district_id=district_id,
        node_type=node_type,
        depth=depth,
        node_limit=node_limit,
    )
    
    # NEW: fall back to Postgres instead of just reporting "offline"
    if graph_data.get("status") == "offline":
        graph_data = await build_network_from_postgres(
            db, search_query=search_query, district_id=district_id, node_limit=node_limit, crime_type=crime_type, node_type=node_type
        )
        graph_data["source"] = "postgres_fallback"
    
    # If Neo4j is available but there is no data
    if not graph_data.get("nodes"):
        graph_data["status"] = "no_data"
    else:
        import asyncio
        from functools import partial
        loop = asyncio.get_running_loop()
        
        # Inject metrics using a thread pool to avoid blocking the event loop
        centrality, communities = await asyncio.gather(
            loop.run_in_executor(None, partial(compute_graph_centrality, graph_data["nodes"], graph_data["edges"])),
            loop.run_in_executor(None, partial(detect_communities, graph_data["nodes"], graph_data["edges"])),
        )
        
        for n in graph_data["nodes"]:
            n["centrality"] = centrality.get(n["node_id"], {"betweenness": 0, "degree": 0, "pagerank": 0})
            n["community_id"] = communities.get(n["node_id"], 0)
        
        graph_data["key_players"] = [
            n["node_id"] for n in
            sorted(graph_data["nodes"], key=lambda x: x.get("centrality", {}).get("betweenness", 0), reverse=True)[:5]
        ]
        
    await cache_set(cache_key, graph_data, expiry=600)
    return graph_data


async def build_network_from_postgres(
    db: AsyncSession,
    search_query: Optional[str] = None,
    district_id: Optional[str] = None,
    node_limit: int = 100,
    crime_type: Optional[str] = None,
    node_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Build network graph from PostgreSQL data when Neo4j is unavailable"""
    from app.models.database_models.crime_model import CrimeOffenderLink, Crime, CrimeVictimLink
    from app.models.database_models.victim_model import Victim
    from app.models.database_models.location_model import Location
    
    nodes: list[dict] = []
    edges: list[dict] = []
    per_type_limit = max(1, node_limit // (1 if node_type else 3))
    
    # --- Criminals ---
    if node_type in (None, "criminal"):
        q = select(Offender).limit(per_type_limit)
        if district_id:
            q = q.where(Offender.district_id == district_id)
        if search_query:
            q = q.where(
                (Offender.first_name.ilike(f"%{search_query}%")) |
                (Offender.last_name.ilike(f"%{search_query}%"))
            )
        if crime_type:
            q = q.join(CrimeOffenderLink).join(Crime).where(Crime.crime_type == crime_type).distinct()
        
        result = await db.execute(q)
        offenders = result.scalars().all()
        
        for offender in offenders:
            node_id = str(offender.offender_id)
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
            
            if offender.known_associates:
                for associate_id in offender.known_associates:
                    edges.append({
                        "edge_id": f"{node_id}_{associate_id}",
                        "source_node_id": node_id,
                        "target_node_id": associate_id,
                        "relationship_type": "KNOWS",
                        "strength_score": 60,
                    })

    # --- Victims ---
    if node_type in (None, "victim"):
        vq = select(Victim).limit(per_type_limit)
        if district_id:
            vq = vq.where(Victim.district_id == district_id)
        if search_query:
            vq = vq.where(
                (Victim.first_name.ilike(f"%{search_query}%")) |
                (Victim.last_name.ilike(f"%{search_query}%"))
            )
            
        v_result = await db.execute(vq)
        victims = v_result.scalars().all()
        for v in victims:
            nodes.append({
                "node_id": str(v.victim_id), 
                "node_type": "victim",
                "label": f"{v.first_name} {v.last_name}",
                "risk_score": v.vulnerability_level or 0,
                "crime_count": 1,
                "size": 20,
                "color": "#3b82f6", # blue for victims
                "profile_data": {"district_id": v.district_id},
            })
            
        link_q = select(CrimeVictimLink)
        if district_id:
            link_q = link_q.join(Crime).where(Crime.district_id == district_id)
        cv_links = (await db.execute(link_q)).scalars().all()
        for cvl in cv_links:
            off_links = (await db.execute(
                select(CrimeOffenderLink).where(CrimeOffenderLink.crime_id == cvl.crime_id)
            )).scalars().all()
            for ol in off_links:
                if any(n["node_id"] == str(ol.offender_id) for n in nodes) and \
                   any(n["node_id"] == str(cvl.victim_id) for n in nodes):
                    edges.append({
                        "edge_id": f"{ol.offender_id}_{cvl.victim_id}",
                        "source_node_id": str(ol.offender_id), 
                        "target_node_id": str(cvl.victim_id),
                        "relationship_type": "VICTIMIZED_AT", 
                        "strength_score": 70,
                    })

    # --- Locations ---
    if node_type in (None, "location"):
        lq = select(Location).limit(per_type_limit)
        if district_id:
            lq = lq.where(Location.district_id == district_id)
        if search_query:
            lq = lq.where(Location.address.ilike(f"%{search_query}%"))
            
        l_result = await db.execute(lq)
        locations = l_result.scalars().all()
        for l in locations:
            nodes.append({
                "node_id": str(l.location_id), 
                "node_type": "location",
                "label": l.address,
                "risk_score": 0,
                "crime_count": 0,
                "size": 25,
                "color": "#a855f7", # purple for locations
                "profile_data": {"district_id": l.district_id},
            })

    
    import asyncio
    from functools import partial
    loop = asyncio.get_running_loop()
    
    centrality, communities = await asyncio.gather(
        loop.run_in_executor(None, partial(compute_graph_centrality, nodes, edges)),
        loop.run_in_executor(None, partial(detect_communities, nodes, edges)),
    )
    for n in nodes:
        n["centrality"] = centrality.get(n["node_id"], {"betweenness": 0, "degree": 0, "pagerank": 0})
        n["community_id"] = communities.get(n["node_id"], 0)
        
    return {
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "network_density": round(len(edges) / max(len(nodes), 1), 2),
        "key_players": [
            n["node_id"]
            for n in sorted(nodes, key=lambda x: x.get("centrality", {}).get("betweenness", 0), reverse=True)[:5]
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
        
    except Exception as e:
        logger.error(f"Error getting node detail: {e}", exc_info=True)
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
