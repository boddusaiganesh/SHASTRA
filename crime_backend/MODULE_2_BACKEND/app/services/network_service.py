"""
Network Analysis Service - Criminal network and link analysis
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import logging
import uuid

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
        
    expiry = 60 if graph_data.get("source") == "postgres_fallback" else 600
    await cache_set(cache_key, graph_data, expiry=expiry)
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

    if node_type == "organization":
        return {
            "nodes": [], "edges": [], "total_nodes": 0, "total_edges": 0,
            "network_density": 0, "key_players": [],
            "warning": "Organization entities are only available when Neo4j is connected.",
        }

    # --- Pre-resolve the set of crime_ids that match crime_type (+ district_id) ONCE ---
    # This becomes the single source of truth every entity type and edge filters against,
    # so Criminals / Victims / Locations / edges all agree on the same crime-type scope.
    matching_crime_ids = None
    if crime_type:
        crime_filter_q = select(Crime.crime_id).where(Crime.crime_type == crime_type)
        if district_id:
            crime_filter_q = crime_filter_q.where(Crime.district_id == district_id)
        matching_crime_ids = set((await db.execute(crime_filter_q)).scalars().all())
        if not matching_crime_ids:
            # No crimes at all match this district+type combo -- return an explicit empty
            # result instead of silently falling back to an unfiltered graph.
            return {
                "nodes": [], "edges": [], "total_nodes": 0, "total_edges": 0,
                "network_density": 0, "key_players": [],
                "warning": f"No records found for crime type '{crime_type}'"
                           + (" in the selected district." if district_id else "."),
            }

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
        if matching_crime_ids is not None:
            q = q.join(CrimeOffenderLink, CrimeOffenderLink.offender_id == Offender.offender_id) \
                 .where(CrimeOffenderLink.crime_id.in_(matching_crime_ids)).distinct()

        result = await db.execute(q)
        offenders = result.scalars().all()

        offender_node_ids = set()
        offender_associate_map = {}

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
            offender_node_ids.add(node_id)
            if offender.known_associates:
                offender_associate_map[node_id] = offender.known_associates

        seen_pairs = set()
        for node_id, associates in offender_associate_map.items():
            for associate_id in associates:
                if associate_id in offender_node_ids:
                    pair_key = tuple(sorted([node_id, associate_id]))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    edges.append({
                        "edge_id": f"{node_id}_{associate_id}",
                        "source_node_id": node_id,
                        "target_node_id": associate_id,
                        "relationship_type": "KNOWS",
                        "strength_score": 60,
                        "confidence_level": "SUSPECTED",
                        "crime_types": [],
                    })

    # --- Victims ---
    if node_type in (None, "victim"):
        # When a crime_type is selected, only pull victims linked to a matching crime
        victim_ids_for_crime_type = None
        if matching_crime_ids is not None:
            vlink_q = select(CrimeVictimLink.victim_id).where(CrimeVictimLink.crime_id.in_(matching_crime_ids))
            victim_ids_for_crime_type = set((await db.execute(vlink_q)).scalars().all())

        vq = select(Victim).limit(per_type_limit)
        if district_id:
            vq = vq.where(Victim.district_id == district_id)
        if search_query:
            vq = vq.where(
                (Victim.first_name.ilike(f"%{search_query}%")) |
                (Victim.last_name.ilike(f"%{search_query}%"))
            )
        if victim_ids_for_crime_type is not None:
            vq = vq.where(Victim.victim_id.in_(victim_ids_for_crime_type))

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
                "color": "#3b82f6",
                "profile_data": {"district_id": v.district_id},
            })

        link_q = select(CrimeVictimLink)
        if district_id:
            link_q = link_q.join(Crime).where(Crime.district_id == district_id)
        if matching_crime_ids is not None:
            link_q = link_q.where(CrimeVictimLink.crime_id.in_(matching_crime_ids))   # NEW
        cv_links = (await db.execute(link_q)).scalars().all()
        for cvl in cv_links:
            off_links = (await db.execute(
                select(CrimeOffenderLink).where(CrimeOffenderLink.crime_id == cvl.crime_id)
            )).scalars().all()
            crime = (await db.execute(select(Crime).where(Crime.crime_id == cvl.crime_id))).scalar_one_or_none()
            for ol in off_links:
                if any(n["node_id"] == str(ol.offender_id) for n in nodes) and \
                   any(n["node_id"] == str(cvl.victim_id) for n in nodes):
                    edges.append({
                        "edge_id": f"{ol.offender_id}_{cvl.victim_id}",
                        "source_node_id": str(ol.offender_id),
                        "target_node_id": str(cvl.victim_id),
                        "relationship_type": "VICTIMIZED_AT",
                        "strength_score": 70,
                        "confidence_level": "CONFIRMED",
                        "crime_types": [crime.crime_type] if crime else [],
                    })

    # --- Locations ---
    if node_type in (None, "location"):
        location_ids_for_crime_type = None
        if matching_crime_ids is not None:
            lloc_q = select(Crime.location_id).where(
                Crime.crime_id.in_(matching_crime_ids), Crime.location_id.isnot(None)
            )
            location_ids_for_crime_type = set((await db.execute(lloc_q)).scalars().all())

        lq = select(Location).limit(per_type_limit)
        if district_id:
            lq = lq.where(Location.district_id == district_id)
        if search_query:
            lq = lq.where(Location.address.ilike(f"%{search_query}%"))
        if location_ids_for_crime_type is not None:
            lq = lq.where(Location.location_id.in_(location_ids_for_crime_type))   # NEW

        l_result = await db.execute(lq)
        locations = l_result.scalars().all()
        location_ids_in_graph = set()
        for l in locations:
            nodes.append({
                "node_id": str(l.location_id),
                "node_type": "location",
                "label": l.address or l.location_name or "Unknown Address",
                "risk_score": l.risk_score or 0,
                "crime_count": l.total_crimes or 0,
                "size": 25,
                "color": "#a855f7",
                "profile_data": {"district_id": l.district_id},
            })
            location_ids_in_graph.add(str(l.location_id))

        if location_ids_in_graph:
            try:
                import uuid
                crime_q = select(Crime).where(Crime.location_id.in_([uuid.UUID(lid) for lid in location_ids_in_graph]))
                if matching_crime_ids is not None:
                    crime_q = crime_q.where(Crime.crime_id.in_(matching_crime_ids))   # NEW
                crimes_at_locations = (await db.execute(crime_q)).scalars().all()
                crime_ids_by_location = {}
                for c in crimes_at_locations:
                    if c.location_id:
                        crime_ids_by_location.setdefault(str(c.location_id), []).append(c.crime_id)

                existing_offender_ids = {n["node_id"] for n in nodes if n["node_type"] == "criminal"}
                for loc_id, crime_ids in crime_ids_by_location.items():
                    if not crime_ids:
                        continue
                    link_q = select(CrimeOffenderLink).where(CrimeOffenderLink.crime_id.in_(crime_ids))
                    offender_links = (await db.execute(link_q)).scalars().all()
                    for ol in offender_links:
                        offender_id = str(ol.offender_id)
                        if offender_id in existing_offender_ids:
                            edges.append({
                                "edge_id": f"{offender_id}_{loc_id}",
                                "source_node_id": offender_id,
                                "target_node_id": loc_id,
                                "relationship_type": "FREQUENTED",
                                "strength_score": 55,
                                "confidence_level": "SUSPECTED",
                                "crime_types": [],
                            })
            except Exception as e:
                logger.warning(f"Failed to link locations to crimes/offenders in fallback: {e}")

    
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
        parsed_id = uuid.UUID(node_id)
    except ValueError:
        return None
        
    try:
        # Try Offender first
        result = await db.execute(
            select(Offender).where(Offender.offender_id == parsed_id)
        )
        offender = result.scalar_one_or_none()
        
        if offender:
            # Get crime history
            from app.models.database_models.crime_model import CrimeOffenderLink, Crime
            link_result = await db.execute(
                select(CrimeOffenderLink).where(CrimeOffenderLink.offender_id == parsed_id)
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

        # Try Victim next
        from app.models.database_models.victim_model import Victim
        result = await db.execute(select(Victim).where(Victim.victim_id == parsed_id))
        victim = result.scalar_one_or_none()
        if victim:
            return {
                "node_id": node_id,
                "node_type": "victim",
                "label": f"{victim.first_name} {victim.last_name}",
                "risk_score": victim.vulnerability_level or 0,
                "crime_count": 1,
                "profile_data": victim.to_dict(),
                "timeline": [],
                "ai_analysis": None,
            }
            
        # Try Location next
        from app.models.database_models.location_model import Location
        result = await db.execute(select(Location).where(Location.location_id == parsed_id))
        location = result.scalar_one_or_none()
        if location:
            return {
                "node_id": node_id,
                "node_type": "location",
                "label": location.address or location.location_name or "Unknown Address",
                "risk_score": location.risk_score or 0,
                "crime_count": location.total_crimes or 0,
                "profile_data": location.to_dict(),
                "timeline": [],
                "ai_analysis": None,
            }
            
        return None
        
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
    if focus_area:
        from app.models.database_models.crime_model import CrimeOffenderLink, Crime
        offender_query = (
            offender_query.join(CrimeOffenderLink).join(Crime)
            .where(Crime.crime_type == focus_area).distinct()
        )
    
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
