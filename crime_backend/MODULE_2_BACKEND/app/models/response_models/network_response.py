"""
Network Analysis Response Models
"""

from pydantic import BaseModel
from typing import List


class NetworkNode(BaseModel):
    node_id: str
    node_type: str
    label: str
    risk_score: float = 0
    crime_count: int = 0
    size: float = 20
    color: str = "#ef4444"
    profile_data: dict = {}


class NetworkEdge(BaseModel):
    edge_id: str
    source_node_id: str
    target_node_id: str
    relationship_type: str
    strength_score: float = 50
    confidence_level: str = "SUSPECTED"
    crime_count: int = 0
    crime_types: List[str] = []


class NetworkGraphResponse(BaseModel):
    nodes: List[NetworkNode]
    edges: List[NetworkEdge]
    total_nodes: int
    total_edges: int
    network_density: float
    key_players: List[str]


class NetworkAISummaryResponse(BaseModel):
    summary_text: str
    key_findings: List[str]
    suspicious_pairs: List[dict]
    recommended_actions: List[str]
    network_stats: dict
    generated_at: str
