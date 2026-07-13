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
  crimeTypeLens?: string | null;
  showClusters?: boolean;
  clusterSummary?: Record<string, { size: number; dominant_crime_type?: string; dominant_district?: string }>;
  replaceKey?: string | number;
  colorBy?: "type" | "cluster";
}

export interface NetworkGraphHandle {
  focusOnNode: (nodeId: string) => void;
  clearFocus: () => void;
  highlightKeyPlayers: (nodeIds: string[]) => void;
}

const getDynamicLayoutOptions = (nodeCount: number, edgeCount: number) => {
  const scale = 1 + Math.sqrt(Math.max(nodeCount, 1)) / 6;
  const avgDegree = nodeCount > 0 ? (edgeCount * 2) / nodeCount : 0;
  const densityFactor = 1 + Math.min(avgDegree / 6, 1) * 0.4;
  const isLarge = nodeCount > 150;

  return {
    name: "fcose",
    quality: isLarge ? "draft" : "default",
    animate: !isLarge,
    randomize: true,
    nodeDimensionsIncludeLabels: true,
    packComponents: true,
    nodeSeparation: Math.min(600, Math.round(160 * scale)),
    idealEdgeLength: Math.min(520, Math.round(220 * scale * densityFactor)),
    nodeRepulsion: Math.min(60000, Math.round(9000 * scale * scale)),
    edgeElasticity: 0.35,
    gravity: Math.max(0.02, 0.15 / scale),
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
      "font-size": "10px",
      "text-valign": "bottom",
      "text-halign": "center",
      "text-margin-y": 4,
      "width": (ele: cytoscape.NodeSingular) => {
        if (ele.isParent() || ele.data("isCluster")) return "auto";
        const crimes = Number(ele.data("crimes")) || 0;
        const btw = Number(ele.data("betweenness")) || 0;
        return Math.max(30, Math.min(80, 20 + crimes * 2 + btw * 100));
      },
      "height": (ele: cytoscape.NodeSingular) => {
        if (ele.isParent() || ele.data("isCluster")) return "auto";
        const crimes = Number(ele.data("crimes")) || 0;
        const btw = Number(ele.data("betweenness")) || 0;
        return Math.max(30, Math.min(80, 20 + crimes * 2 + btw * 100));
      },
      "text-wrap": "wrap",
      "text-max-width": "80px",
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
    selector: "edge",
    style: {
      "width": (ele: cytoscape.EdgeSingular) => 1 + (Number(ele.data("strength")) || 50) / 30,
      "line-color": "#334155",
      "target-arrow-color": "#334155",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      "label": "data(label)",
      "font-size": "8px",
      "color": "#64748b",
      "text-rotation": "autorotate",
      // @ts-ignore
      "line-style": (ele: cytoscape.EdgeSingular) => ele.data("confidence") === "SUSPECTED" ? "dashed" : "solid",
    },
  },
  {
    selector: "edge:selected",
    style: { "line-color": "#3b82f6", "target-arrow-color": "#3b82f6" },
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

const NetworkGraph = forwardRef<NetworkGraphHandle, Props>(({ nodes, edges, onNodeSelect, onNodeExpand, onNodeCompare, onEdgeSelect, selectedNodeId, highlightPath, crimeTypeLens, showClusters = true, clusterSummary, replaceKey, colorBy = "type" }, ref) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const prevIdsRef = useRef<Set<string>>(new Set());
  const lastReplaceKeyRef = useRef(replaceKey);
  const crimeTypeLensRef = useRef(crimeTypeLens);
  const propsRef = useRef({ nodes, edges, onNodeSelect, onNodeExpand, onNodeCompare, onEdgeSelect });

  useEffect(() => {
    propsRef.current = { nodes, edges, onNodeSelect, onNodeExpand, onNodeCompare, onEdgeSelect };
    crimeTypeLensRef.current = crimeTypeLens;
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
    if (!containerRef.current) return;
    const currentIds = new Set(nodes.map(n => n.node_id));
    console.log('[NetworkGraph] useEffect[nodes,edges] fired — nodes:', nodes.length, 'edges:', edges.length, 'replaceKey:', replaceKey, 'showClusters:', showClusters);

    if (!cyRef.current) {
      console.log('[NetworkGraph] Initialising new Cytoscape instance with', nodes.length, 'nodes,', edges.length, 'edges');
      const elements = buildElements(nodes, edges, showClusters, clusterSummary);
      console.log('[NetworkGraph] buildElements result:', elements.length, 'elements (nodes+edges+parents)');
      const cy = cytoscape({
        container: containerRef.current,
        elements,
        style: getStyleSheet(colorBy),
        layout: getDynamicLayoutOptions(nodes.length, edges.length),
        minZoom: 0.2,
        maxZoom: 3,
      });

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
    console.log('[NetworkGraph] cy already exists — isReplace:', isReplace, 'cy nodes:', cy.nodes().length, 'cy edges:', cy.edges().length);
    console.log('[NetworkGraph] classes on cy nodes sample:', cy.nodes().slice(0, 3).map(n => n.id() + ':' + n.classes().join(',')));
    lastReplaceKeyRef.current = replaceKey;

    if (isReplace) {
      // Full wipe + re-add on every server-side filter change.
      // This is the only safe way to guarantee no stale 'dimmed'/'lens-dimmed'
      // classes survive from previous interactions (Highlight Key Players, focus, lens).
      console.log('[NetworkGraph] isReplace=true — full wipe and rebuild');
      cy.elements().remove();
      const freshElements = buildElements(nodes, edges, showClusters, clusterSummary);
      console.log('[NetworkGraph] freshElements count:', freshElements.length);
      cy.add(freshElements);
      console.log('[NetworkGraph] after full re-add: cy nodes:', cy.nodes().length, 'cy edges:', cy.edges().length);
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

      if (newNodes.length === 0 && newEdges.length === 0 && !hasRemovedNodes && !hasRemovedEdges) return;

      if (hasRemovedNodes || hasRemovedEdges || currentIds.size < existingIds.size) {
        cy.elements().remove();
        cy.add(buildElements(nodes, edges, showClusters, clusterSummary));
        cy.layout(getDynamicLayoutOptions(nodes.length, edges.length)).run();
      } else {
        cy.add(buildElements(newNodes, newEdges, showClusters, clusterSummary));
        const totalNodes = cy.nodes().length;
        const totalEdges = cy.edges().length;
        cy.layout({ ...getDynamicLayoutOptions(totalNodes, totalEdges), randomize: false, fit: false, numIter: 150, animationDuration: 300 } as any).run();
      }
    }

    prevIdsRef.current = currentIds;
  }, [nodes, edges, showClusters, clusterSummary, replaceKey]);

  useEffect(() => {
    if (!cyRef.current) return;
    cyRef.current.edges().removeClass("lens-dimmed");
    cyRef.current.nodes().removeClass("lens-dimmed");
    console.log('[NetworkGraph] crimeTypeLens changed to:', crimeTypeLens, '| cy nodes:', cyRef.current.nodes().length, 'cy edges:', cyRef.current.edges().length);
    if (!crimeTypeLens) {
      console.log('[NetworkGraph] lens is null — all lens-dimmed cleared, nodes should be visible');
      return;
    }

    const matchingEdges = cyRef.current.edges().filter(
      (e) => (e.data("crimeTypes") || []).includes(crimeTypeLens)
    );
    console.log('[NetworkGraph] lens matchingEdges:', matchingEdges.length, '/ total edges:', cyRef.current.edges().length);
    console.log('[NetworkGraph] sample edge crimeTypes:', cyRef.current.edges().slice(0,3).map(e => e.data('crimeTypes')));
    const nonMatching = cyRef.current.edges().not(matchingEdges);
    nonMatching.addClass("lens-dimmed");

    const connectedNodeIds = new Set(matchingEdges.map((e) => [(e as cytoscape.EdgeSingular).source().id(), (e as cytoscape.EdgeSingular).target().id()]).flat());
    console.log('[NetworkGraph] lens connectedNodeIds:', connectedNodeIds.size, '/ total nodes:', cyRef.current.nodes().length);
    cyRef.current.nodes().forEach((n) => {
      if (!connectedNodeIds.has(n.id())) n.addClass("lens-dimmed");
    });
  }, [crimeTypeLens]);

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
      neighborhood.removeClass("lens-dimmed");

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

      cy.edges().removeClass("lens-dimmed");
      cy.nodes().removeClass("lens-dimmed");
      if (crimeTypeLensRef.current) {
        const matchingEdges = cy.edges().filter((e) => (e.data("crimeTypes") || []).includes(crimeTypeLensRef.current!));
        cy.edges().not(matchingEdges).addClass("lens-dimmed");
        const connectedIds = new Set(matchingEdges.map((e) => [(e as cytoscape.EdgeSingular).source().id(), (e as cytoscape.EdgeSingular).target().id()]).flat());
        cy.nodes().forEach((n) => { if (!connectedIds.has(n.id())) n.addClass("lens-dimmed"); });
      }

      cy.animate({
        fit: { eles: cy.elements(), padding: 50 },
        duration: 500,
        easing: "ease-in-out-cubic",
      });
    },
    highlightKeyPlayers: (nodeIds: string[]) => {
      const cy = cyRef.current;
      if (!cy) return;
      cy.elements().removeClass("dimmed focus-active focus-neighbor focus-edge");
      cy.elements().removeClass("key-player");
      const keyEls = cy.collection();
      nodeIds.forEach((id) => keyEls.merge(cy.getElementById(id)));
      cy.elements().not(keyEls).addClass("dimmed");
      keyEls.addClass("key-player");
      cy.animate({ fit: { eles: keyEls, padding: 80 }, duration: 500, easing: "ease-in-out-cubic" });
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
