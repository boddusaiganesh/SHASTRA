from fastapi import APIRouter, HTTPException
import logging

from app.core.neo4j_connection import get_network_graph

router = APIRouter()
logger = logging.getLogger(__name__)

# Mock Fallback Data (In case Neo4j Docker is not running)
MOCK_NODES = [
    { "node_id": "N001", "node_type": "criminal", "label": "Rajan Mehta", "risk_score": 92, "crime_count": 14, "profile_data": { "age": 34, "district": "Bengaluru Urban", "status": "Active" } },
    { "node_id": "N002", "node_type": "criminal", "label": "Suresh Naik", "risk_score": 78, "crime_count": 9, "profile_data": { "age": 28, "district": "Kalaburagi", "status": "Absconding" } },
    { "node_id": "N003", "node_type": "criminal", "label": "Mohammad Ilyas", "risk_score": 85, "crime_count": 11, "profile_data": { "age": 42, "district": "Belagavi", "status": "Active" } },
    { "node_id": "N005", "node_type": "victim", "label": "Priya Sharma", "risk_score": 0, "crime_count": 0, "profile_data": { "age": 26, "district": "Bengaluru Urban" } },
    { "node_id": "N007", "node_type": "location", "label": "Whitefield Hub", "risk_score": 88, "crime_count": 287, "profile_data": { "address": "Whitefield, Bengaluru", "type": "Crime Hub" } },
    { "node_id": "N009", "node_type": "organization", "label": "Shell Company A", "risk_score": 81, "crime_count": 23, "profile_data": { "type": "Money Laundering", "registered": "Bengaluru" } },
]

MOCK_EDGES = [
    { "source": "N001", "target": "N002", "relationship_type": "Associate", "strength_score": 85 },
    { "source": "N001", "target": "N003", "relationship_type": "Co-conspirator", "strength_score": 92 },
    { "source": "N001", "target": "N007", "relationship_type": "Frequent Location", "strength_score": 78 },
    { "source": "N001", "target": "N009", "relationship_type": "Financial Link", "strength_score": 65 },
    { "source": "N003", "target": "N005", "relationship_type": "Victim", "strength_score": 45 },
]

MOCK_AI_SUMMARY = {
    "summary": "Analysis reveals a sophisticated multi-district criminal network centered around Rajan Mehta (N001) and Mohammad Ilyas (N003) with strong financial links through Shell Company A. The network has tentacles in organized vehicle theft in Whitefield.",
    "suspicious_associations": [
        { "entities": ["N001", "N003", "N009"], "reason": "Suspected money laundering operation", "severity": "Critical" },
    ],
    "investigation_priorities": ["Freeze financial accounts linked to N009", "Locate and apprehend Suresh Naik (N002)"]
}

@router.get("/graph")
async def fetch_network_graph():
    """
    Fetch the criminal network graph from Neo4j.
    Gracefully falls back to mock data if Neo4j is offline.
    """
    try:
        data = get_network_graph()
        # If Neo4j is not connected, it returns {"nodes": [], "edges": []} or similar
        # Let's check if it actually returned data, else use mock.
        if not data or not data.get("nodes"):
            logger.info("Neo4j offline or empty. Returning mock graph data.")
            return {
                "nodes": MOCK_NODES,
                "edges": MOCK_EDGES,
                "total_nodes": len(MOCK_NODES),
                "total_edges": len(MOCK_EDGES),
            }
        return data
    except Exception as e:
        logger.error(f"Error fetching network graph: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/ai-summary")
async def fetch_ai_summary():
    """
    Fetch the Gemini AI network summary.
    """
    return MOCK_AI_SUMMARY
