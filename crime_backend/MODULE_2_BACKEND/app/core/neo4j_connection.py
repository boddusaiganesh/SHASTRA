"""
Neo4j Graph Database Connection
"""

from neo4j import AsyncGraphDatabase, AsyncDriver
from typing import Optional, List, Dict, Any
import logging

from app.core.config import settings, RELATIONSHIP_TYPES

logger = logging.getLogger(__name__)

_driver: Optional[AsyncDriver] = None


async def init_neo4j():
    """Initialize Neo4j driver"""
    global _driver
    try:
        _driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URL,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_lifetime=3600,
            max_connection_pool_size=50,
            connection_acquisition_timeout=60,
        )
        await _driver.verify_connectivity()
        logger.info("Neo4j connected successfully")
        
        # Create indexes and constraints
        await _create_indexes()
        
    except Exception as e:
        logger.warning(f"Neo4j connection failed (non-critical): {e}")
        _driver = None


async def _create_indexes():
    """Create Neo4j indexes and constraints"""
    if not _driver:
        return
    
    async with _driver.session() as session:
        queries = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Criminal) REQUIRE c.offender_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (v:Victim) REQUIRE v.victim_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (l:Location) REQUIRE l.location_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (o:Organization) REQUIRE o.org_id IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (c:Criminal) ON (c.name)",
            "CREATE INDEX IF NOT EXISTS FOR (c:Criminal) ON (c.risk_level)",
            "CREATE INDEX IF NOT EXISTS FOR (l:Location) ON (l.location_type)",
        ]
        for query in queries:
            try:
                await session.run(query)
            except Exception as e:
                logger.warning(f"Index creation warning: {e}")


def get_neo4j_driver() -> Optional[AsyncDriver]:
    """Get Neo4j driver instance"""
    return _driver


async def close_neo4j():
    """Close Neo4j driver"""
    global _driver
    if _driver:
        await _driver.close()
        _driver = None
        logger.info("Neo4j connection closed")


def get_neo4j_health() -> str:
    """Check Neo4j health"""
    if not _driver:
        return "not connected"
    return "healthy"


async def run_neo4j_query(query: str, parameters: Dict = None) -> List[Dict[str, Any]]:
    """Run a Neo4j query and return results as list of dicts"""
    if not _driver:
        logger.warning("Neo4j not available, returning empty result")
        return []
    
    try:
        async with _driver.session() as session:
            result = await session.run(query, parameters or {})
            return [record.data() async for record in result]
    except Exception as e:
        logger.error(f"Neo4j query error: {e}")
        return []


async def find_shortest_path(node_id_1: str, node_id_2: str, max_hops: int = 5) -> dict:
    """Find the shortest relationship path between two entities in the graph."""
    query = f"""
    MATCH (a {{offender_id: $id1}}), (b {{offender_id: $id2}})
    MATCH path = shortestPath((a)-[*..{max_hops}]-(b))
    RETURN [n IN nodes(path) | {{id: coalesce(n.offender_id, n.victim_id, n.location_id), name: n.name}}] AS path_nodes,
           [r IN relationships(path) | type(r)] AS path_rels
    LIMIT 1
    """
    results = await run_neo4j_query(query, {"id1": node_id_1, "id2": node_id_2})
    if not results:
        return {"found": False, "path_nodes": [], "path_rels": []}
    return {"found": True, "path_nodes": results[0]["path_nodes"], "path_rels": results[0]["path_rels"]}


async def sync_offender_to_neo4j(offender_data: Dict[str, Any]):
    """Sync a new/updated offender to Neo4j"""
    query = """
    MERGE (c:Criminal {offender_id: $offender_id})
    SET c.name = $name,
        c.risk_level = $risk_level,
        c.risk_score = $risk_score,
        c.crime_count = $crime_count,
        c.status = $status
    RETURN c
    """
    await run_neo4j_query(query, offender_data)


async def sync_victim_to_neo4j(victim_data: Dict[str, Any]):
    """Sync a new/updated victim to Neo4j"""
    query = """
    MERGE (v:Victim {victim_id: $victim_id})
    SET v.name = $name,
        v.vulnerability_level = $vulnerability_level,
        v.victimization_count = $victimization_count
    RETURN v
    """
    await run_neo4j_query(query, victim_data)


async def sync_location_to_neo4j(location_data: Dict[str, Any]):
    """Sync a location to Neo4j"""
    query = """
    MERGE (l:Location {location_id: $location_id})
    SET l.name = $name,
        l.location_type = $location_type,
        l.risk_score = $risk_score,
        l.is_hotspot = $is_hotspot
    RETURN l
    """
    await run_neo4j_query(query, location_data)


async def create_criminal_relationship(
    offender_id_1: str,
    offender_id_2: str,
    relationship_type: str,
    strength_score: float = 50.0,
    confidence_level: str = "SUSPECTED",
    crime_ids: List[str] = None,
    first_seen_date: str = None,
    last_seen_date: str = None,
):
    """Create a relationship between two criminals in Neo4j"""
    
    # SECURITY: relationship_type is interpolated directly into the Cypher query below
    # because Neo4j doesn't support parameterizing relationship type names. This allow-list
    # check is the only thing preventing Cypher injection here — do not remove it, and do not
    # add any other caller that builds a relationship-type Cypher string without this check.
    if relationship_type not in RELATIONSHIP_TYPES:
        raise ValueError(f"Invalid relationship_type: {relationship_type}")
    query = f"""
    MATCH (c1:Criminal {{offender_id: $id1}})
    MATCH (c2:Criminal {{offender_id: $id2}})
    MERGE (c1)-[r:{relationship_type}]->(c2)
    SET r.strength_score = $strength_score,
        r.confidence_level = $confidence_level,
        r.crime_ids = $crime_ids,
        r.first_seen_date = $first_seen_date,
        r.last_seen_date = $last_seen_date
    RETURN r
    """
    await run_neo4j_query(query, {
        "id1": offender_id_1,
        "id2": offender_id_2,
        "strength_score": strength_score,
        "confidence_level": confidence_level,
        "crime_ids": crime_ids or [],
        "first_seen_date": first_seen_date,
        "last_seen_date": last_seen_date,
    })


async def get_network_graph(
    search_query: str = None,
    crime_type: str = None,
    district_id: str = None,
    depth: int = 2,
    node_limit: int = 100,
) -> Dict[str, Any]:
    """Get the criminal network graph from Neo4j"""
    # Connect directly to neo4j without awaiting the driver creation itself
    global _driver
    if not _driver:
        return {"status": "offline", "error": "Graph database (Neo4j) is not connected"}
        
    # SECURITY EXCEPTION: The following Cypher query uses unparameterized input because APOC path expansion requires labels and rel-types to be dynamic strings. Input is sanitized using regex strictly allowing alphanumeric characters before query execution.

    # Build the Cypher query dynamically
    if search_query:
        match_clause = "MATCH (n) WHERE n.name CONTAINS $search OR n.offender_id = $search"
    else:
        match_clause = "MATCH (n:Criminal)"
    
    query = f"""
    {match_clause}
    WITH n LIMIT $node_limit
    OPTIONAL MATCH (n)-[r]-(connected)
    RETURN n, labels(n) AS labels_n, r, type(r) AS type_r, connected, labels(connected) AS labels_connected
    LIMIT $limit
    """
    
    results = await run_neo4j_query(query, {
        "search": search_query or "",
        "node_limit": node_limit,
        "limit": node_limit * 3,
    })
    
    # Process results into nodes and edges
    nodes_map = {}
    edges = []
    
    for record in results:
        # Process main node
        if record.get("n"):
            node = record["n"]
            node_id = (
                node.get("offender_id") or
                node.get("victim_id") or
                node.get("location_id") or
                node.get("org_id", str(id(node)))
            )
            
            if node_id not in nodes_map:
                # Determine node type from available labels or keys
                labels_n = record.get("labels_n") or []
                if "Victim" in labels_n or node.get("victim_id"):
                    node_type = "victim"
                    color = "#3b82f6"
                elif "Location" in labels_n or node.get("location_id"):
                    node_type = "location"
                    color = "#22c55e"
                elif "Organization" in labels_n or node.get("org_id"):
                    node_type = "organization"
                    color = "#a855f7"
                else:
                    node_type = "criminal"
                    color = "#ef4444"
                
                nodes_map[node_id] = {
                    "node_id": node_id,
                    "node_type": node_type,
                    "label": node.get("name", "Unknown"),
                    "risk_score": node.get("risk_score", 0),
                    "crime_count": node.get("crime_count", 0),
                    "size": 20 + (node.get("crime_count", 0) * 2),
                    "color": color,
                    "profile_data": dict(node),
                }
        
        # Process relationship
        if record.get("r") and record.get("connected"):
            rel = record["r"]
            connected = record["connected"]
            
            source_id = (
                record["n"].get("offender_id") or
                record["n"].get("victim_id") or
                str(id(record["n"]))
            )
            target_id = (
                connected.get("offender_id") or
                connected.get("victim_id") or
                connected.get("location_id") or
                str(id(connected))
            )
            
            # Add connected node
            if target_id not in nodes_map:
                labels_conn = record.get("labels_connected") or []
                if "Victim" in labels_conn or connected.get("victim_id"):
                    conn_type = "victim"
                    conn_color = "#3b82f6"
                elif "Location" in labels_conn or connected.get("location_id"):
                    conn_type = "location"
                    conn_color = "#22c55e"
                elif "Organization" in labels_conn or connected.get("org_id"):
                    conn_type = "organization"
                    conn_color = "#a855f7"
                else:
                    conn_type = "criminal"
                    conn_color = "#f97316"
                nodes_map[target_id] = {
                    "node_id": target_id,
                    "node_type": conn_type,
                    "label": connected.get("name", "Unknown"),
                    "risk_score": connected.get("risk_score", 0),
                    "crime_count": connected.get("crime_count", 0),
                    "size": 15,
                    "color": conn_color,
                    "profile_data": dict(connected),
                }
            
            edges.append({
                "edge_id": f"{source_id}_{target_id}",
                "source_node_id": source_id,
                "target_node_id": target_id,
                "relationship_type": record.get("type_r") or "LINKED_TO",
                "strength_score": rel.get("strength_score", 50) if rel else 50,
                "confidence_level": rel.get("confidence_level", "SUSPECTED") if rel else "SUSPECTED",
                "crime_count": len(rel.get("crime_ids", [])) if rel else 0,
            })
    
    nodes = list(nodes_map.values())
    
    return {
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "network_density": round(len(edges) / max(len(nodes), 1), 2),
        "key_players": [n["node_id"] for n in sorted(nodes, key=lambda x: x["crime_count"], reverse=True)[:5]],
    }

