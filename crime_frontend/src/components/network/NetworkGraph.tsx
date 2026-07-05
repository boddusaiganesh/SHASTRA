import React, { useEffect, useRef } from "react";
import cytoscape from "cytoscape";
import { NODE_COLORS } from "../../constants/colorCodes";

interface NetworkNode {
  node_id: string; node_type: string; label: string; risk_score: number; crime_count: number; profile_data: Record<string, unknown>;
  centrality?: { betweenness: number; degree: number; pagerank: number };
  community_id?: number;
}
interface NetworkEdge {
  source?: string; target?: string; source_node_id?: string; target_node_id?: string; relationship_type: string; strength_score: number;
}
interface Props {
  nodes: NetworkNode[]; edges: NetworkEdge[];
  onNodeSelect?: (node: NetworkNode) => void;
  onNodeExpand?: (node: NetworkNode) => void;
  onNodeCompare?: (node: NetworkNode) => void;
  selectedNodeId?: string | null;
  highlightPath?: string[];
}

const NetworkGraph: React.FC<Props> = ({ nodes, edges, onNodeSelect, onNodeExpand, onNodeCompare, selectedNodeId, highlightPath }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  useEffect(() => {
    if (!containerRef.current || !nodes.length) return;

    const cy = cytoscape({
      container: containerRef.current,
      elements: [
        ...nodes.map((n) => ({
          data: {
            id: n.node_id,
            label: n.label,
            type: n.node_type,
            risk: n.risk_score,
            crimes: n.crime_count,
            betweenness: n.centrality?.betweenness || 0,
            community: n.community_id || 0,
          },
        })),
        ...edges.map((e, i) => ({
          data: {
            id: `e${i}`,
            source: e.source || e.source_node_id || "",
            target: e.target || e.target_node_id || "",
            label: e.relationship_type,
            strength: e.strength_score,
          },
        })),
      ],
      style: [
        {
          selector: "node",
          style: {
            "background-color": (ele: cytoscape.NodeSingular) => {
              const commColors = ["#ef4444", "#3b82f6", "#22c55e", "#f59e0b", "#a855f7", "#ec4899", "#14b8a6", "#f97316"];
              const cId = ele.data("community") as number;
              return commColors[cId % commColors.length] || NODE_COLORS[ele.data("type") as string] || "#6B7280";
            },
            "border-color": "#1e293b",
            "border-width": 3,
            "label": "data(label)",
            "color": "#e2e8f0",
            "font-size": "10px",
            "text-valign": "bottom",
            "text-halign": "center",
            "text-margin-y": 4,
            "width": (ele: cytoscape.NodeSingular) => Math.max(30, Math.min(80, 20 + ele.data("crimes") * 2 + ele.data("betweenness") * 100)),
            "height": (ele: cytoscape.NodeSingular) => Math.max(30, Math.min(80, 20 + ele.data("crimes") * 2 + ele.data("betweenness") * 100)),
            "text-wrap": "wrap",
            "text-max-width": "80px",
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-color": "#3b82f6",
            "border-width": 4,
          },
        },
        {
          selector: "edge",
          style: {
            "width": (ele: cytoscape.EdgeSingular) => 1 + ele.data("strength") / 30,
            "line-color": "#334155",
            "target-arrow-color": "#334155",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            "label": "data(label)",
            "font-size": "8px",
            "color": "#64748b",
            "text-rotation": "autorotate",
          },
        },
        {
          selector: "edge:selected",
          style: { "line-color": "#3b82f6", "target-arrow-color": "#3b82f6" },
        },
        {
          selector: ".dimmed",
          style: { "opacity": 0.2 },
        },
      ],
      layout: { name: "cose", animate: true, randomize: true, nodeRepulsion: () => 8000, idealEdgeLength: () => 100 },
      wheelSensitivity: 0.3,
    });

    cy.on("tap", "node", (evt: cytoscape.EventObject) => {
      const nodeId = evt.target.id();
      const node = nodes.find((n) => n.node_id === nodeId);
      if (node) {
        if ((evt.originalEvent as MouseEvent).shiftKey) {
          onNodeCompare?.(node);
        } else {
          onNodeSelect?.(node);
        }
      }
    });

    cy.on("dblclick", "node", (evt: cytoscape.EventObject) => {
      const nodeId = evt.target.id();
      const node = nodes.find((n) => n.node_id === nodeId);
      if (node) onNodeExpand?.(node);
    });

    cyRef.current = cy;
    return () => cy.destroy();
  }, [nodes, edges]);

  useEffect(() => {
    if (!cyRef.current) return;
    if (selectedNodeId) {
      cyRef.current.getElementById(selectedNodeId).select();
    }
  }, [selectedNodeId]);

  useEffect(() => {
    if (!cyRef.current) return;
    cyRef.current.elements().removeClass("dimmed");
    if (highlightPath && highlightPath.length > 0) {
      const pathSelectors = highlightPath.map(id => `#${id}`).join(", ");
      cyRef.current.elements().not(pathSelectors).addClass("dimmed");
    }
  }, [highlightPath]);

  return <div ref={containerRef} className="h-full w-full" style={{ background: "#0f172a" }} />;
};

export default NetworkGraph;
