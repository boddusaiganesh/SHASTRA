import React, { useEffect, useRef } from "react";
import cytoscape from "cytoscape";
import { NODE_COLORS } from "../../constants/colorCodes";

interface NetworkNode {
  node_id: string; node_type: string; label: string; risk_score: number; crime_count: number; profile_data: Record<string, unknown>;
}
interface NetworkEdge {
  source: string; target: string; relationship_type: string; strength_score: number;
}
interface Props {
  nodes: NetworkNode[]; edges: NetworkEdge[];
  onNodeSelect?: (node: NetworkNode) => void;
  selectedNodeId?: string | null;
}

const NetworkGraph: React.FC<Props> = ({ nodes, edges, onNodeSelect, selectedNodeId }) => {
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
          },
        })),
        ...edges.map((e, i) => ({
          data: {
            id: `e${i}`,
            source: e.source,
            target: e.target,
            label: e.relationship_type,
            strength: e.strength_score,
          },
        })),
      ],
      style: [
        {
          selector: "node",
          style: {
            "background-color": (ele: cytoscape.NodeSingular) => NODE_COLORS[ele.data("type") as string] || "#6B7280",
            "border-color": "#1e293b",
            "border-width": 3,
            "label": "data(label)",
            "color": "#e2e8f0",
            "font-size": "10px",
            "text-valign": "bottom",
            "text-halign": "center",
            "text-margin-y": 4,
            "width": (ele: cytoscape.NodeSingular) => Math.max(30, Math.min(60, 20 + ele.data("crimes"))),
            "height": (ele: cytoscape.NodeSingular) => Math.max(30, Math.min(60, 20 + ele.data("crimes"))),
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
      ],
      layout: { name: "cose", animate: true, randomize: true, nodeRepulsion: () => 8000, idealEdgeLength: () => 100 },
      wheelSensitivity: 0.3,
    });

    cy.on("tap", "node", (evt) => {
      const nodeId = evt.target.id();
      const node = nodes.find((n) => n.node_id === nodeId);
      if (node) onNodeSelect?.(node);
    });

    cyRef.current = cy;
    return () => cy.destroy();
  }, [nodes, edges]);

  useEffect(() => {
    if (!cyRef.current || !selectedNodeId) return;
    cyRef.current.$(`#${selectedNodeId}`).select();
  }, [selectedNodeId]);

  return <div ref={containerRef} className="h-full w-full" style={{ background: "#0f172a" }} />;
};

export default NetworkGraph;
