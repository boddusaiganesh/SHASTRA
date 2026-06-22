"""
Neo4j Graph Database Connection
"""

from neo4j import GraphDatabase, Driver
from typing import Optional, List, Dict, Any
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

_driver: Optional[Driver] = None


def init_neo4j():
    """Initialize Neo4j driver"""
    global _driver
    try:
        _driver = GraphDatabase.driver(
            settings.NEO4J_URL,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_lifetime=3600,
            max_connection_pool_size=50,
            connection_acquisition_timeout=60,
        )
        _driver.verify_connectivity()
        logger.info("Neo4j connected successfully")
        
        # Create indexes and constraints
        _create_indexes()
        
    except Exception as e:
        logger.warning(f"Neo4j connection failed (non-critical): {e}")
        _driver = None


def _create_indexes():
    """Create Neo4j indexes and constraints"""
    if not _driver:
        return
    
    with _driver.session() as session:
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
                session.run(query)
            except Exception as e:
                logger.warning(f"Index creation warning: {e}")


def get_neo4j_driver() -> Optional[Driver]:
    """Get Neo4j driver instance"""
    return _driver


def close_neo4j():
    """Close Neo4j driver"""
    global _driver
    if _driver:
        _driver.close()
        _driver = None
        logger.info("Neo4j connection closed")


def get_neo4j_health() -> str:
    """Check Neo4j health"""
    if not _driver:
        return "not connected"
    try:
        with _driver.session() as session:
            session.run("RETURN 1")
            return "healthy"
    except Exception as e:
        return f"unhealthy: {str(e)}"


def run_neo4j_query(query: str, parameters: Dict = None) -> List[Dict[str, Any]]:
    """Run a Neo4j query and return results as list of dicts"""
    if not _driver:
        logger.warning("Neo4j not available, returning empty result")
        return []
    
    try:
        with _driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]
    except Exception as e:
        logger.error(f"Neo4j query error: {e}")
        return []


def sync_offender_to_neo4j(offender_data: Dict[str, Any]):
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
    run_neo4j_query(query, offender_data)


def sync_victim_to_neo4j(victim_data: Dict[str, Any]):
    """Sync a new/updated victim to Neo4j"""
    query = """
    MERGE (v:Victim {victim_id: $victim_id})
    SET v.name = $name,
        v.vulnerability_level = $vulnerability_level,
        v.victimization_count = $victimization_count
    RETURN v
    """
    run_neo4j_query(query, victim_data)


def sync_location_to_neo4j(location_data: Dict[str, Any]):
    """Sync a location to Neo4j"""
    query = """
    MERGE (l:Location {location_id: $location_id})
    SET l.name = $name,
        l.location_type = $location_type,
        l.risk_score = $risk_score,
        l.is_hotspot = $is_hotspot
    RETURN l
    """
    run_neo4j_query(query, location_data)


def create_criminal_relationship(
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
    run_neo4j_query(query, {
        "id1": offender_id_1,
        "id2": offender_id_2,
        "strength_score": strength_score,
        "confidence_level": confidence_level,
        "crime_ids": crime_ids or [],
        "first_seen_date": first_seen_date,
        "last_seen_date": last_seen_date,
    })


def get_network_graph(
    search_query: str = None,
    crime_type: str = None,
    district_id: str = None,
    depth: int = 2,
    node_limit: int = 100,
) -> Dict[str, Any]:
    """Get the criminal network graph from Neo4j"""
    
    # Build the Cypher query dynamically
    if search_query:
        match_clause = "MATCH (n) WHERE n.name CONTAINS $search OR n.offender_id = $search"
    else:
        match_clause = "MATCH (n:Criminal)"
    
    query = f"""
    {match_clause}
    WITH n LIMIT $node_limit
    OPTIONAL MATCH (n)-[r]-(connected)
    RETURN n, r, connected
    LIMIT $limit
    """
    
    results = run_neo4j_query(query, {
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
                # Determine node type
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
                nodes_map[target_id] = {
                    "node_id": target_id,
                    "node_type": "criminal",
                    "label": connected.get("name", "Unknown"),
                    "risk_score": connected.get("risk_score", 0),
                    "crime_count": connected.get("crime_count", 0),
                    "size": 15,
                    "color": "#f97316",
                    "profile_data": dict(connected),
                }
            
            edges.append({
                "edge_id": f"{source_id}_{target_id}",
                "source_node_id": source_id,
                "target_node_id": target_id,
                "relationship_type": type(rel).__name__ if rel else "LINKED_TO",
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
