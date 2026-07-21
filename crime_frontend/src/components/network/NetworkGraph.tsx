import { useEffect, useRef, useImperativeHandle, forwardRef } from "react";
import cytoscape from "cytoscape";
import fcose from "cytoscape-fcose";
import { NODE_COLORS } from "../../constants/colorCodes";

cytoscape.use(fcose);

interface NetworkNode {
  node_id: string; node_type: string; label: string; risk_score: number; crime_count: number; profile_data: Record<string, unknown>;
  centrality?: { betweenness: number; degree: number; pagerank: number };
  community_id?: number;
}
interface NetworkEdge {
  source?: string; target?: string; source_node_id?: string; target_node_id?: string; relationship_type: string; strength_score: number;
  crime_types?: string[];
  crime_ids?: string[];
  confidence_level?: string;
  edge_id?: string;
}
interface Props {
  nodes: NetworkNode[]; edges: NetworkEdge[];
  onNodeSelect?: (node: NetworkNode) => void;
  onNodeExpand?: (node: NetworkNode) => void;
  onNodeCompare?: (node: NetworkNode) => void;
  onEdgeSelect?: (sourceId: string, targetId: string, edgeData: any) => void;
  selectedNodeId?: string | null;
  highlightPath?: string[];
  showClusters?: boolean;
  clusterSummary?: Record<string, { size: number; dominant_crime_type?: string; dominant_district?: string }>;
  replaceKey?: string | number;
  colorBy?: "type" | "cluster";
  watchedNodeIds?: Set<string>;
}

export interface NetworkGraphHandle {
  focusOnNode: (nodeId: string) => void;
  clearFocus: () => void;
  highlightKeyPlayers: (nodeIds: string[]) => void;
  fitGraph: () => void;
  zoomIn: () => void;
  zoomOut: () => void;
  highlightByCrimeIds: (crimeIds: Set<string>) => void;
}

const getDynamicLayoutOptions = (nodeCount: number, edgeCount: number) => {
  const scale = 1 + Math.sqrt(Math.max(nodeCount, 1)) / 5;
  const avgDegree = nodeCount > 0 ? (edgeCount * 2) / nodeCount : 0;
  const densityFactor = 1 + Math.min(avgDegree / 6, 1) * 0.5;
  const isLarge = nodeCount > 100;

  return {
    name: "fcose",
    quality: isLarge ? "draft" : "default",
    animate: !isLarge,
    randomize: true,
    nodeDimensionsIncludeLabels: true,
    packComponents: true,
    nodeSeparation: Math.min(900, Math.round(220 * scale)),
    idealEdgeLength: Math.min(700, Math.round(300 * scale * densityFactor)),
    nodeRepulsion: Math.min(120000, Math.round(15000 * scale * scale)),
    edgeElasticity: 0.35,
    gravity: Math.max(0.01, 0.1 / scale),
    numIter: isLarge ? 1500 : 2500,
    tile: true,
    nestingFactor: 1.2,
    gravityRangeCompound: 1.5,
    gravityCompound: 1.0,
  } as any;
};

const getEdgeId = (e: NetworkEdge, i?: number) => {
  if (e.edge_id) return e.edge_id;
  const s = e.source || e.source_node_id || "";
  const t = e.target || e.target_node_id || "";
  return i !== undefined ? `e${i}_${s}_${t}` : `${s}_${t}`;
};

const buildElements = (nodes: NetworkNode[], edges: NetworkEdge[], showClusters: boolean, clusterSummary?: Record<string, any>) => {
  const communityCounts: Record<number, number> = {};
  nodes.forEach((n) => {
    const c = n.community_id ?? 0;
    communityCounts[c] = (communityCounts[c] || 0) + 1;
  });

  const clusterableCommunities = new Set(
    Object.entries(communityCounts).filter(([, count]) => count >= 2).map(([id]) => Number(id))
  );

  const clusterParents = showClusters
    ? Array.from(clusterableCommunities).map((cId) => ({
        data: {
          id: `cluster-${cId}`,
          label: clusterSummary && clusterSummary[cId]?.dominant_crime_type
            ? `${clusterSummary[cId].dominant_crime_type} · ${communityCounts[cId]} members`
            : `Cluster ${cId + 1} · ${communityCounts[cId]} members`,
          isCluster: true,
        },
      }))
    : [];

  const memberNodes = nodes.map((n) => {
    const cId = n.community_id ?? 0;
    const parent = showClusters && clusterableCommunities.has(cId) ? `cluster-${cId}` : undefined;
    return {
      data: {
        id: n.node_id,
        label: n.label,
        type: n.node_type,
        risk: n.risk_score,
        crimes: n.crime_count,
        betweenness: n.centrality?.betweenness || 0,
        community: cId,
        ...(parent ? { parent } : {}),
      },
    };
  });

  const edgeEls = edges
    .filter((e) => {
      const s = e.source || e.source_node_id || "";
      const t = e.target || e.target_node_id || "";
      return nodes.some((n) => n.node_id === s) && nodes.some((n) => n.node_id === t);
    })
    .map((e, i) => ({
      data: {
        id: getEdgeId(e, i),
        source: e.source || e.source_node_id || "",
        target: e.target || e.target_node_id || "",
        label: e.relationship_type,
        strength: e.strength_score,
        crimeTypes: e.crime_types || [],
        crimeIds: (e as any).crime_ids || [],
        confidence: e.confidence_level || "SUSPECTED",
      },
    }));

  return [...clusterParents, ...memberNodes, ...edgeEls];
};

const getStyleSheet = (colorBy: "type" | "cluster" = "type"): any[] => [
  {
    selector: "node",
    style: {
      "background-color": (ele: cytoscape.NodeSingular) => {
        if (colorBy === "type") {
          return NODE_COLORS[ele.data("type") as string] || "#6B7280";
        }
        const commColors = ["#ef4444", "#3b82f6", "#22c55e", "#f59e0b", "#a855f7", "#ec4899", "#14b8a6", "#f97316"];
        const cId = ele.data("community") as number;
        return commColors[cId % commColors.length] || NODE_COLORS[ele.data("type") as string] || "#6B7280";
      },
      "border-color": "#1e293b",
      "border-width": 3,
      "label": "data(label)",
      "color": "#e2e8f0",
      "font-size": "11px",
      "font-weight": 600,
      "text-valign": "bottom",
      "text-halign": "center",
      "text-margin-y": 5,
      "width": (ele: cytoscape.NodeSingular) => {
        if (ele.isParent() || ele.data("isCluster")) return 50;
        const crimes = Number(ele.data("crimes")) || 0;
        const btw = Number(ele.data("betweenness")) || 0;
        return Math.max(38, Math.min(100, 28 + crimes * 3 + btw * 120));
      },
      "height": (ele: cytoscape.NodeSingular) => {
        if (ele.isParent() || ele.data("isCluster")) return 50;
        const crimes = Number(ele.data("crimes")) || 0;
        const btw = Number(ele.data("betweenness")) || 0;
        return Math.max(38, Math.min(100, 28 + crimes * 3 + btw * 120));
      },
      "text-wrap": "wrap",
      "text-max-width": "100px",
    },
  },
  {
    selector: "node:parent",
    style: {
      "background-color": "#1e293b",
      "background-opacity": 0.35,
      "border-color": "#475569",
      "border-width": 1.5,
      "border-style": "dashed",
      "shape": "round-rectangle",
      "label": "data(label)",
      "color": "#94a3b8",
      "font-size": "11px",
      "font-weight": 600,
      "text-valign": "top",
      "text-halign": "center",
      "text-margin-y": -6,
      "padding": "28px",
    } as any,
  },
  {
    selector: "node:selected",
    style: {
      "border-color": "#3b82f6",
      "border-width": 4,
    },
  },
  {
    selector: "node.focus-active",
    style: {
      "border-color": "#22d3ee",
      "border-width": 5,
      "overlay-color": "#22d3ee",
      "overlay-opacity": 0.18,
      "overlay-padding": 8,
      "z-index": 999,
    } as any,
  },
  {
    selector: "node.focus-neighbor",
    style: {
      "border-color": "#38bdf8",
      "border-width": 4,
      "z-index": 998,
    },
  },
  {
    selector: "node.watched",
    style: {
      "background-image": "url('data:image/svg+xml;utf8,<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 24 24\" fill=\"%23eab308\" stroke=\"white\" stroke-width=\"1\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><polygon points=\"12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2\"></polygon></svg>')",
      "background-fit": "cover",
      "background-clip": "none",
      "border-color": "#eab308",
      "border-width": 4,
    } as any,
  },
  {
    selector: "edge",
    style: {
      "width": (ele: cytoscape.EdgeSingular) => 1 + (Number(ele.data("strength")) || 50) / 30,
      "line-color": "#475569",
      "target-arrow-color": "#475569",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      "label": "",  // hide edge labels by default — too cluttered at scale
      "font-size": "0px",
      "color": "#64748b",
      "text-rotation": "autorotate",
      // @ts-ignore
      "line-style": (ele: cytoscape.EdgeSingular) => ele.data("confidence") === "SUSPECTED" ? "dashed" : "solid",
    },
  },
  {
    selector: "edge:selected",
    style: {
      "line-color": "#3b82f6",
      "target-arrow-color": "#3b82f6",
      "label": "data(label)",
      "font-size": "9px",
    },
  },
  {
    selector: "edge.focus-edge",
    style: {
      "line-color": "#38bdf8",
      "target-arrow-color": "#38bdf8",
      "width": (ele: cytoscape.EdgeSingular) => 2 + (Number(ele.data("strength")) || 50) / 25,
      "z-index": 997,
    } as any,
  },
  {
    selector: ".dimmed",
    style: { "opacity": 0.2 },
  },
  {
    selector: ".lens-dimmed",
    style: { "opacity": 0.12 },
  },
  {
    selector: "node.lens-dimmed",
    style: { "font-size": "8px" },
  },
  {
    selector: ".key-player",
    // @ts-ignore
    style: { "border-color": "#f59e0b", "border-width": 6, "border-style": "double" },
  },
];

const NetworkGraph = forwardRef<NetworkGraphHandle, Props>(({ nodes, edges, onNodeSelect, onNodeExpand, onNodeCompare, onEdgeSelect, selectedNodeId, highlightPath, showClusters = true, clusterSummary, replaceKey, colorBy = "type", watchedNodeIds }, ref) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const prevIdsRef = useRef<Set<string>>(new Set());
  const lastReplaceKeyRef = useRef<string | number | undefined>(undefined);
  const propsRef = useRef({ nodes, edges, onNodeSelect, onNodeExpand, onNodeCompare, onEdgeSelect });

  useEffect(() => {
    propsRef.current = { nodes, edges, onNodeSelect, onNodeExpand, onNodeCompare, onEdgeSelect };
  });

  useEffect(() => {
    if (!containerRef.current) return;
    const el = containerRef.current;
    const ro = new ResizeObserver(() => {
      if (cyRef.current) {
        cyRef.current.resize();
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    return () => {
      cyRef.current?.destroy();
      cyRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (cyRef.current) {
      cyRef.current.style(getStyleSheet(colorBy));
    }
  }, [colorBy]);

  useEffect(() => {
    if (!cyRef.current) return;
    cyRef.current.nodes().forEach(n => {
      if (watchedNodeIds?.has(n.id())) {
        n.addClass("watched");
      } else {
        n.removeClass("watched");
      }
    });
  }, [watchedNodeIds]);

  useEffect(() => {
    if (!containerRef.current) return;
    const currentIds = new Set(nodes.map(n => n.node_id));

    if (!cyRef.current) {
      const elements = buildElements(nodes, edges, showClusters, clusterSummary);
      const cy = cytoscape({
        container: containerRef.current,
        elements,
        style: getStyleSheet(colorBy),
        layout: getDynamicLayoutOptions(nodes.length, edges.length),
        minZoom: 0.05,
        maxZoom: 4,
        // wheelSensitivity: 0.3,  // removed — caused Cytoscape warning about non-standard zoom
      });
      // Fit graph to viewport with padding once layout settles
      cy.one("layoutstop", () => { cy.fit(undefined, 60); });

      cy.on("tap", "node", (evt: cytoscape.EventObject) => {
        const nodeId = evt.target.id();
        const node = propsRef.current.nodes.find((n) => n.node_id === nodeId);
        if (node) {
          if ((evt.originalEvent as MouseEvent).shiftKey) {
            propsRef.current.onNodeCompare?.(node);
          } else {
            propsRef.current.onNodeSelect?.(node);
          }
        }
      });

      cy.on("dblclick", "node", (evt: cytoscape.EventObject) => {
        const nodeId = evt.target.id();
        const node = propsRef.current.nodes.find((n) => n.node_id === nodeId);
        if (node) propsRef.current.onNodeExpand?.(node);
      });

      cy.on("tap", "edge", (evt: cytoscape.EventObject) => {
        const edgeData = evt.target.data();
        propsRef.current.onEdgeSelect?.(edgeData.source, edgeData.target, edgeData);
      });

      cyRef.current = cy;
      prevIdsRef.current = currentIds;
      lastReplaceKeyRef.current = replaceKey;
      return;
    }

    const cy = cyRef.current;
    const isReplace = replaceKey !== lastReplaceKeyRef.current;
    lastReplaceKeyRef.current = replaceKey;

    if (isReplace) {
      // Full wipe + re-add on every server-side filter change.
      // This is the only safe way to guarantee no stale 'dimmed'
      // classes survive from previous interactions (Highlight Key Players, focus).
      cy.elements().remove();
      const freshElements = buildElements(nodes, edges, showClusters, clusterSummary);
      cy.add(freshElements);
      
      // re-apply watched classes after rebuilding elements
      if (watchedNodeIds) {
        cy.nodes().forEach(n => {
          if (watchedNodeIds.has(n.id())) n.addClass("watched");
        });
      }

      cy.layout(getDynamicLayoutOptions(nodes.length, edges.length)).run();
    } else {
      const existingIds = new Set(cy.nodes().map(n => n.id()));
      let hasRemovedNodes = false;
      cy.nodes().forEach(n => {
        if (!currentIds.has(n.id())) hasRemovedNodes = true;
      });

      const currentEdgeIds = new Set(edges.map((e, i) => getEdgeId(e, i)));
      let hasRemovedEdges = false;
      cy.edges().forEach(e => {
        if (!currentEdgeIds.has(e.id())) hasRemovedEdges = true;
      });

      const newNodes = nodes.filter(n => !existingIds.has(n.node_id));
      const newEdges = edges.filter((e, i) => {
        const eid = getEdgeId(e, i);
        return cy.getElementById(eid).empty();
      });

      if (newNodes.length === 0 && newEdges.length === 0 && !hasRemovedNodes && !hasRemovedEdges) {
        // Just update classes for watched nodes even if no structural change
        cy.nodes().forEach(n => {
          if (watchedNodeIds?.has(n.id())) n.addClass("watched");
          else n.removeClass("watched");
        });
        return;
      }

      if (hasRemovedNodes || hasRemovedEdges || currentIds.size < existingIds.size) {
        cy.elements().remove();
        const freshElements = buildElements(nodes, edges, showClusters, clusterSummary);
        cy.add(freshElements);
        if (watchedNodeIds) {
          cy.nodes().forEach(n => {
            if (watchedNodeIds.has(n.id())) n.addClass("watched");
          });
        }
        cy.layout(getDynamicLayoutOptions(nodes.length, edges.length)).run();
      } else {
        cy.add(buildElements(newNodes, newEdges, showClusters, clusterSummary));
        cy.nodes().forEach(n => {
          if (watchedNodeIds?.has(n.id())) n.addClass("watched");
          else n.removeClass("watched");
        });
        const totalNodes = cy.nodes().length;
        const totalEdges = cy.edges().length;
        cy.layout({ ...getDynamicLayoutOptions(totalNodes, totalEdges), randomize: false, fit: false, numIter: 150, animationDuration: 300 } as any).run();
      }
    }

    prevIdsRef.current = currentIds;
  }, [nodes, edges, showClusters, clusterSummary, replaceKey]);


  useImperativeHandle(ref, () => ({
    focusOnNode: (nodeId: string) => {
      const cy = cyRef.current;
      if (!cy) return;
      const node = cy.getElementById(nodeId);
      if (node.empty()) return;
      
      const neighborEdges = node.connectedEdges();
      const neighborNodes = node.neighborhood().nodes();
      const neighborhood = node.closedNeighborhood();

      cy.elements().removeClass("focus-active focus-neighbor focus-edge dimmed");

      cy.elements().addClass("dimmed");
      neighborhood.removeClass("dimmed");

      node.addClass("focus-active");
      neighborNodes.addClass("focus-neighbor");
      neighborEdges.addClass("focus-edge");

      neighborhood.forEach((ele) => {
        const parent = ele.isChild() ? ele.parent() : null;
        if (parent && !parent.empty()) parent.removeClass("dimmed");
      });

      cy.animate({
        fit: { eles: neighborhood, padding: 60 },
        duration: 500,
        easing: "ease-in-out-cubic",
      });
    },
    clearFocus: () => {
      const cy = cyRef.current;
      if (!cy) return;
      cy.elements().removeClass("dimmed focus-active focus-neighbor focus-edge");

      cy.animate({
        fit: { eles: cy.elements(), padding: 50 },
        duration: 500,
        easing: "ease-in-out-cubic",
      });
    },
    highlightKeyPlayers: (nodeIds: string[]) => {
      const cy = cyRef.current;
      if (!cy) return;
      cy.elements().removeClass("dimmed focus-active focus-neighbor focus-edge key-player");
      if (nodeIds.length === 0) return;
      const keyEls = cy.collection();
      nodeIds.forEach((id) => keyEls.merge(cy.getElementById(id)));
      cy.elements().not(keyEls).addClass("dimmed");
      keyEls.addClass("key-player");
      cy.animate({ fit: { eles: keyEls, padding: 80 }, duration: 500, easing: "ease-in-out-cubic" });
    },
    highlightByCrimeIds: (crimeIds: Set<string>) => {
      const cy = cyRef.current;
      if (!cy) return;
      cy.elements().removeClass("dimmed focus-active focus-neighbor focus-edge key-player");
      if (crimeIds.size === 0) return;

      const matchingEdges = cy.edges().filter(ele => {
        const ids = ele.data("crimeIds") || [];
        return ids.some((id: string) => crimeIds.has(id));
      });
      if (matchingEdges.empty()) {
        cy.elements().addClass("dimmed");
        return;
      }
      
      const matchingNodes = matchingEdges.connectedNodes();
      cy.elements().not(matchingEdges).not(matchingNodes).addClass("dimmed");
      matchingEdges.addClass("focus-edge");
      matchingNodes.addClass("focus-neighbor");
    },
    fitGraph: () => {
      const cy = cyRef.current;
      if (!cy) return;
      cy.animate({ fit: { eles: cy.elements(), padding: 60 }, duration: 400, easing: "ease-in-out-cubic" });
    },
    zoomIn: () => {
      const cy = cyRef.current;
      if (!cy) return;
      cy.animate({ zoom: Math.min(cy.zoom() * 1.35, cy.maxZoom()), duration: 200 });
    },
    zoomOut: () => {
      const cy = cyRef.current;
      if (!cy) return;
      cy.animate({ zoom: Math.max(cy.zoom() / 1.35, cy.minZoom()), duration: 200 });
    },
  }));

  useEffect(() => {
    if (!cyRef.current) return;
    cyRef.current.elements(":selected").unselect();
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
});

export default NetworkGraph;
