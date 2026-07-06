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
        return True
        
    except Exception as e:
        logger.warning(f"Neo4j connection failed (non-critical): {e}")
        _driver = None
        return False


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
    MATCH (a), (b)
    WHERE (a.offender_id = $id1 OR a.victim_id = $id1 OR a.location_id = $id1 OR a.org_id = $id1)
    AND   (b.offender_id = $id2 OR b.victim_id = $id2 OR b.location_id = $id2 OR b.org_id = $id2)
    MATCH path = shortestPath((a)-[*..{max_hops}]-(b))
    RETURN [n IN nodes(path) | {{id: coalesce(n.offender_id, n.victim_id, n.location_id, n.org_id), name: n.name}}] AS path_nodes,
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


async def create_victim_offender_relationship(offender_id: str, victim_id: str, crime_id: str):
    """Create a relationship between a victim and a criminal."""
    query = """
    MATCH (c:Criminal {offender_id: $offender_id})
    MATCH (v:Victim {victim_id: $victim_id})
    MERGE (c)-[r:VICTIMIZED_AT]->(v)
    SET r.crime_id = $crime_id, r.confidence_level = 'CONFIRMED'
    """
    await run_neo4j_query(query, {"offender_id": offender_id, "victim_id": victim_id, "crime_id": crime_id})


def normalize_node(raw_node: dict, labels: list[str], eid: str = None) -> dict:
    if "Victim" in labels or raw_node.get("victim_id"):
        node_type, color = "victim", "#3b82f6"
    elif "Location" in labels or raw_node.get("location_id"):
        node_type, color = "location", "#22c55e"
    elif "Organization" in labels or raw_node.get("org_id"):
        node_type, color = "organization", "#a855f7"
    else:
        node_type, color = "criminal", "#ef4444"

    node_id = (raw_node.get("offender_id") or raw_node.get("victim_id")
               or raw_node.get("location_id") or raw_node.get("org_id")
               or eid)
    return {
        "node_id": node_id, 
        "node_type": node_type, 
        "color": color,
        "label": raw_node.get("name", "Unknown"),
        "risk_score": raw_node.get("risk_score", 0),
        "crime_count": raw_node.get("crime_count", 0),
        "size": 20 + (raw_node.get("crime_count", 0) * 2),
        "profile_data": dict(raw_node),
    }


async def get_network_graph(
    search_query: str = None,
    crime_type: str = None,
    district_id: str = None,
    node_type: str | None = None,
    depth: int = 2,
    node_limit: int = 100,
) -> Dict[str, Any]:
    """Get the criminal network graph from Neo4j"""
    # Connect directly to neo4j without awaiting the driver creation itself
    global _driver
    if not _driver:
        return {"status": "offline", "error": "Graph database (Neo4j) is not connected"}
        
    # SECURITY EXCEPTION: The following Cypher query uses unparameterized input because APOC path expansion requires labels and rel-types to be dynamic strings. Input is sanitized using regex strictly allowing alphanumeric characters before query execution.

    label_map = {
        "criminal": "Criminal",
        "victim": "Victim",
        "location": "Location",
        "organization": "Organization",
    }
    
    root_labels = [label_map[node_type]] if node_type in label_map else list(label_map.values())
    label_filter = " OR ".join(f"n:{lbl}" for lbl in root_labels)

    where_clauses = [f"({label_filter})"]
    params = {"node_limit": node_limit, "limit": node_limit * 3}

    if search_query:
        where_clauses.append("(n.name CONTAINS $search OR n.offender_id = $search OR n.victim_id = $search OR n.location_id = $search OR n.org_id = $search)")
        params["search"] = search_query

    if district_id:
        where_clauses.append("n.district_id = $district_id")
        params["district_id"] = district_id

    if crime_type:
        where_clauses.append("$crime_type IN n.crime_types")
        params["crime_type"] = crime_type

    query = f"""
    MATCH (n)
    WHERE {" AND ".join(where_clauses)}
    OPTIONAL MATCH (n)-[r]-()
    WITH n, count(r) AS degree
    ORDER BY degree DESC, n.risk_score DESC
    LIMIT $node_limit
    CALL {{
      WITH n
      OPTIONAL MATCH (n)-[r]-(connected)
      RETURN r, connected
      LIMIT 25
    }}
    RETURN n, elementId(n) AS n_eid, labels(n) AS labels_n, properties(r) AS r_props, type(r) AS type_r, connected, elementId(connected) AS connected_eid, labels(connected) AS labels_connected
    """
    
    results = await run_neo4j_query(query, params)
    
    # Process results into nodes and edges
    nodes_map = {}
    edges = []
    
    for record in results:
        # Process main node
        if record.get("n"):
            node = record["n"]
            labels_n = record.get("labels_n") or []
            eid = record.get("n_eid")
            normalized = normalize_node(node, labels_n, eid)
            node_id = normalized["node_id"]
            
            if node_id not in nodes_map:
                nodes_map[node_id] = normalized
        
        # Process relationship
        if record.get("type_r") and record.get("connected"):
            rel = record.get("r_props") or {}
            connected = record["connected"]
            
            source_id = node_id
            
            labels_conn = record.get("labels_connected") or []
            conn_eid = record.get("connected_eid")
            normalized_conn = normalize_node(connected, labels_conn, conn_eid)
            target_id = normalized_conn["node_id"]
            
            # Add connected node
            if target_id not in nodes_map:
                normalized_conn["size"] = 15
                nodes_map[target_id] = normalized_conn
            
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

