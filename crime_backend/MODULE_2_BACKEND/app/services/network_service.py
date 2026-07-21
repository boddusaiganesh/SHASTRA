"""
Network Analysis Service - Criminal network and link analysis
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import logging

from app.core.neo4j_connection import get_network_graph
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
    if graph_data.get("status") == "offline" or not graph_data.get("nodes"):
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
        
        # Build cluster summaries
        from collections import Counter
        groups = {}
        for n in graph_data["nodes"]:
            cid = n.get("community_id", 0)
            groups.setdefault(cid, []).append(n)
        
        summaries = {}
        for cid, members in groups.items():
            if len(members) < 2:
                continue
            crime_types = Counter(
                ct for m in members for ct in (m.get("preferred_crime_types") or m.get("crime_types") or [])
            )
            districts = Counter(m.get("district_id") for m in members if m.get("district_id"))
            summaries[cid] = {
                "size": len(members),
                "dominant_crime_type": crime_types.most_common(1)[0][0] if crime_types else None,
                "dominant_district": districts.most_common(1)[0][0] if districts else None,
            }
        graph_data["cluster_summary"] = summaries
        
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
                "status": "no_data",
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
                    "known_associates": offender.known_associates or [],
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
                        "crime_types": [crime_type] if crime_type else [],
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
            if not victim_ids_for_crime_type:
                victims = []
            else:
                vq = vq.where(Victim.victim_id.in_(victim_ids_for_crime_type))
                v_result = await db.execute(vq)
                victims = v_result.scalars().all()
        else:
            v_result = await db.execute(vq)
            victims = v_result.scalars().all()
        for v in victims:
            nodes.append({
                "node_id": str(v.victim_id),
                "node_type": "victim",
                "label": f"{v.first_name} {v.last_name}",
                "risk_score": len(v.vulnerability_factors) * 10 if v.vulnerability_factors else 0,
                "crime_count": 1,
                "size": 20,
                "color": "#3b82f6",
                "profile_data": {"district_id": v.district_id},
            })

        link_q = select(CrimeVictimLink)
        if district_id:
            # Explicit join condition to avoid SQLAlchemy auto-join ambiguity
            link_q = link_q.join(Crime, Crime.crime_id == CrimeVictimLink.crime_id).where(Crime.district_id == district_id)
        if matching_crime_ids is not None:
            link_q = link_q.where(CrimeVictimLink.crime_id.in_(matching_crime_ids))
        cv_links = (await db.execute(link_q)).scalars().all()
        
        cv_crime_ids = {cvl.crime_id for cvl in cv_links}
        off_links_by_crime = {}
        crimes_by_id = {}
        if cv_crime_ids:
            all_off_links = (await db.execute(
                select(CrimeOffenderLink).where(CrimeOffenderLink.crime_id.in_(cv_crime_ids))
            )).scalars().all()
            for ol in all_off_links:
                off_links_by_crime.setdefault(ol.crime_id, []).append(ol)
            all_crimes = (await db.execute(
                select(Crime).where(Crime.crime_id.in_(cv_crime_ids))
            )).scalars().all()
            crimes_by_id = {c.crime_id: c for c in all_crimes}

        for cvl in cv_links:
            off_links = off_links_by_crime.get(cvl.crime_id, [])
            crime = crimes_by_id.get(cvl.crime_id)
            for ol in off_links:
                # When node_type=="victim", offenders were not loaded into nodes,
                # so we only draw edges between entities that are actually in the graph.
                # Both sides must be present — but skip the check if node_type forces only one type.
                source_present = node_type == "victim" or any(n["node_id"] == str(ol.offender_id) for n in nodes)
                target_present = any(n["node_id"] == str(cvl.victim_id) for n in nodes)
                if source_present and target_present and node_type != "victim":
                    edges.append({
                        "edge_id": f"{ol.offender_id}_{cvl.victim_id}",
                        "source_node_id": str(ol.offender_id),
                        "target_node_id": str(cvl.victim_id),
                        "relationship_type": "VICTIMIZED_AT",
                        "strength_score": 70,
                        "confidence_level": "CONFIRMED",
                        "crime_types": [crime.crime_type] if crime else [],
                        "crime_id": str(crime.crime_id) if crime else None,
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
            lq = lq.where(
                (Location.address.ilike(f"%{search_query}%")) |
                (Location.location_name.ilike(f"%{search_query}%"))
            )
        if location_ids_for_crime_type is not None:
            if not location_ids_for_crime_type:
                locations = []
            else:
                lq = lq.where(Location.location_id.in_(location_ids_for_crime_type))
                l_result = await db.execute(lq)
                locations = l_result.scalars().all()
        else:
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
                "color": "#22c55e",
                "profile_data": {
                    "district_id": l.district_id,
                    "latitude": l.latitude,
                    "longitude": l.longitude
                },
            })
            location_ids_in_graph.add(str(l.location_id))

        if location_ids_in_graph:
            try:
                import uuid
                crime_q = select(Crime).where(Crime.location_id.in_([uuid.UUID(lid) for lid in location_ids_in_graph]))
                if matching_crime_ids is not None:
                    crime_q = crime_q.where(Crime.crime_id.in_(matching_crime_ids))
                crimes_at_locations = (await db.execute(crime_q)).scalars().all()
                crime_ids_by_location = {}
                for c in crimes_at_locations:
                    if c.location_id:
                        crime_ids_by_location.setdefault(str(c.location_id), []).append(c.crime_id)

                existing_offender_ids = {n["node_id"] for n in nodes if n["node_type"] == "criminal"}
                all_loc_crime_ids = {cid for cids in crime_ids_by_location.values() for cid in cids}
                loc_offender_links_by_crime = {}
                if all_loc_crime_ids:
                    all_loc_off_links = (await db.execute(
                        select(CrimeOffenderLink).where(CrimeOffenderLink.crime_id.in_(all_loc_crime_ids))
                    )).scalars().all()
                    for ol in all_loc_off_links:
                        loc_offender_links_by_crime.setdefault(ol.crime_id, []).append(ol)

                for loc_id, crime_ids in crime_ids_by_location.items():
                    if not crime_ids:
                        continue
                    for cid in crime_ids:
                        for ol in loc_offender_links_by_crime.get(cid, []):
                            offender_id = str(ol.offender_id)
                            # Only draw edge when offender is present in graph
                            # (skip this check only when node_type=="location" since
                            # offenders are not loaded in that mode)
                            if node_type == "location" or offender_id in existing_offender_ids:
                                if node_type != "location":  # don't add edges to absent offenders
                                    edges.append({
                                        "edge_id": f"{offender_id}_{loc_id}",
                                        "source_node_id": offender_id,
                                        "target_node_id": loc_id,
                                        "relationship_type": "FREQUENTED",
                                        "strength_score": 55,
                                        "confidence_level": "SUSPECTED",
                                        "crime_types": [crime_type] if crime_type else [],
                                        "crime_id": str(cid),
                                    })
            except Exception as e:
                logger.warning(f"Failed to link locations to crimes/offenders in fallback: {e}")

    
    import asyncio
    from functools import partial
    
    # Merge duplicate edges
    merged_edges = {}
    for e in edges:
        eid = e["edge_id"]
        cid = e.pop("crime_id", None)
        if eid not in merged_edges:
            e["crime_ids"] = [cid] if cid else []
            merged_edges[eid] = e
        else:
            existing = merged_edges[eid]
            if cid and cid not in existing["crime_ids"]:
                existing["crime_ids"].append(cid)
            for ct in e.get("crime_types", []):
                if ct not in existing["crime_types"]:
                    existing["crime_types"].append(ct)
            existing["strength_score"] = min(100, existing["strength_score"] + 10)
    
    edges = list(merged_edges.values())
    
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
    try:
        import uuid
        parsed_id = uuid.UUID(node_id)
    except ValueError:
        from app.core.neo4j_connection import run_neo4j_query, get_neo4j_driver
        if get_neo4j_driver() is None:
            return {"error": "neo4j_offline"}
        query = "MATCH (n) WHERE elementId(n) = $node_id RETURN labels(n)[0] AS label, properties(n) AS props"
        res = await run_neo4j_query(query, {"node_id": node_id})
        if res and res[0]:
            label = res[0].get("label", "Unknown")
            props = res[0].get("props", {})
            return {
                "node_id": node_id,
                "label": props.get("name", "Unknown Node"),
                "title": props.get("name", "Unknown Node"),
                "type": label.upper(),
                "details": {k: v for k, v in props.items() if k not in ["name", "offender_id", "victim_id", "location_id"]},
                "recent_activity": []
            }
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
            if crime_ids:
                cr_result = await db.execute(select(Crime).where(Crime.crime_id.in_(crime_ids[:10])))
                crimes_list = cr_result.scalars().all()
                crimes = [{
                    "crime_id": str(crime.crime_id),
                    "crime_type": crime.crime_type,
                    "date": str(crime.date_of_occurrence),
                    "status": crime.status,
                    "severity": crime.severity,
                } for crime in crimes_list]
            
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
                "ai_analysis": None,
            }

        # Try Victim next
        from app.models.database_models.victim_model import Victim
        result = await db.execute(select(Victim).where(Victim.victim_id == parsed_id))
        victim = result.scalar_one_or_none()
        if victim:
            return {
                "node_id": str(victim.victim_id),
                "node_type": "victim",
                "label": f"{victim.first_name} {victim.last_name}",
                "risk_score": len(victim.vulnerability_factors) * 10 if victim.vulnerability_factors else 0,
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


async def get_node_ai_analysis(db: AsyncSession, node_id: str) -> Dict[str, Any]:
    from app.services.gemini_service import get_offender_ai_analysis
    
    cache_key = f"node_ai:{node_id}"
    cached = await cache_get(cache_key)
    if cached: return cached
    
    try:
        import uuid
        parsed_id = uuid.UUID(node_id)
    except ValueError:
        from app.core.neo4j_connection import run_neo4j_query
        query = "MATCH (n) WHERE elementId(n) = $node_id RETURN properties(n) AS props"
        res = await run_neo4j_query(query, {"node_id": node_id})
        if res and res[0]:
            return {
                "ai_analysis": "This entity was sourced directly from the graph database and does not have a detailed PostgreSQL record available for deep AI analysis."
            }
        return {"ai_analysis": None}
        
    try:
        result = await db.execute(select(Offender).where(Offender.offender_id == parsed_id))
        offender = result.scalar_one_or_none()
        if not offender: return {"ai_analysis": None}
        
        from app.models.database_models.crime_model import CrimeOffenderLink, Crime
        links = await db.execute(select(CrimeOffenderLink).where(CrimeOffenderLink.offender_id == parsed_id))
        crime_ids = [l.crime_id for l in links.scalars().all()]
        crimes = []
        if crime_ids:
            cr = await db.execute(select(Crime).where(Crime.crime_id.in_(crime_ids[:10])))
            crimes = [{"crime_type": c.crime_type, "status": c.status} for c in cr.scalars().all()]
            
        analysis = await get_offender_ai_analysis(offender.to_dict(), crimes)
        res = {"ai_analysis": analysis.get("text", ""), "is_fallback": analysis.get("is_fallback", False)}
        await cache_set(cache_key, res, expiry=3600)
        return res
    except Exception as e:
        logger.error(f"Error generating AI analysis: {e}", exc_info=True)
        return {"ai_analysis": None}


async def get_network_ai_summary(
    db: AsyncSession,
    district_id: Optional[str] = None,
    focus_area: Optional[str] = None,
    search_query: Optional[str] = None,
    node_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Get AI-powered network analysis summary perfectly synced with the graph"""
    from app.services.gemini_service import get_network_analysis_summary
    import itertools
    
    cache_key = f"network_ai_summary:{district_id}:{focus_area}:{search_query}:{node_type}"
    cached = await cache_get(cache_key)
    if cached:
        return cached
    
    # Get EXACT same network graph data that the frontend sees
    graph_data = await get_network_graph_data(
        db, 
        search_query=search_query, 
        crime_type=focus_area, 
        district_id=district_id, 
        node_type=node_type
    )
    
    # Extract offenders from the graph nodes
    all_offenders = []
    for node in graph_data.get("nodes", []):
        if node.get("node_type") == "criminal" or node.get("node_type") == "Offender":
            props = dict(node.get("profile_data", {}) or {})
            if props:
                # Add full_name if missing but label exists
                if "full_name" not in props and "label" in node:
                    props["full_name"] = node["label"]
                if "risk_score" not in props and "risk_score" in node:
                    props["risk_score"] = node["risk_score"]
                all_offenders.append(props)
    
    # Find suspicious pairs (shared known associates) by checking all combinations
    suspicious_pairs = []
    
    for o1, o2 in itertools.combinations(all_offenders, 2):
        common = set(o1.get("known_associates", [])) & set(o2.get("known_associates", []))
        if common:
            suspicious_pairs.append({
                "offender_1": o1.get("full_name", "Unknown"),
                "offender_2": o2.get("full_name", "Unknown"),
                "connection_type": "SHARED_ASSOCIATE",
                "confidence": "SUSPECTED",
            })
    
    # Network stats
    network_stats = {
        "total_criminals": len(all_offenders),
        "high_risk_count": sum(1 for o in all_offenders if o.get("risk_level") == "HIGH" or o.get("risk_score", 0) >= 70),
        "active_count": sum(1 for o in all_offenders if o.get("status") == "ACTIVE"),
        "network_density": round(len(suspicious_pairs) / max(len(all_offenders), 1), 2),
    }
    
    # Get AI summary
    ai_data = await get_network_analysis_summary(
        all_offenders[:20], suspicious_pairs, network_stats, focus_area
    )
    
    # Extract AI findings or fallback to defaults
    summary_text = ai_data.get("summary_text", "Network analysis temporarily unavailable.")
    key_findings = ai_data.get("key_findings", [])
    if not key_findings:
        key_findings = [
            f"Identified {network_stats['total_criminals']} repeat offenders in the network",
            f"{network_stats['high_risk_count']} individuals classified as HIGH risk",
            f"{network_stats['active_count']} offenders currently active",
            f"Detected {len(suspicious_pairs)} suspicious associations",
            "Network analysis reveals organized crime patterns requiring investigation",
        ]
        
    recommended_actions = ai_data.get("recommended_actions", [])
    if not recommended_actions:
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
        "is_fallback": ai_data.get("is_fallback", False),
    }
    
    await cache_set(cache_key, response, expiry=1800)
    return response
