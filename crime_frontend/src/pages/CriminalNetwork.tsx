import React, { useEffect, useState, useMemo, useRef } from "react";
import { motion } from "framer-motion";
import { Network, AlertTriangle, Search, ChevronRight, Users, MapPin, Brain, ChevronLeft, Grid, Loader2, Map } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import AIMarkdown from "../components/common/AIMarkdown";
import { useDistricts } from "../hooks/useDistricts";
import { networkService } from "../services/networkService";
import { watchlistService } from "../services/watchlistService";
import { investigationService } from "../services/investigationService";
import NetworkGraph, { NetworkGraphHandle } from "../components/network/NetworkGraph";
import ConnectivityMatrix from "../components/network/ConnectivityMatrix";
import NetworkTimeline from "../components/network/NetworkTimeline";
import NetworkMap from "../components/network/NetworkMap";
import LoadingSpinner from "../components/common/LoadingSpinner";
import { NODE_COLORS } from "../constants/colorCodes";
import { CRIME_TYPES } from "../constants/crimeTypes";

interface NetworkNode {
  node_id: string; node_type: string; label: string; risk_score: number;
  crime_count: number; profile_data: Record<string, unknown>;
  ai_analysis?: string; is_fallback?: boolean; timeline?: any[];
}
interface NetworkEdge {
  edge_id?: string;
  source_node_id: string; target_node_id: string; relationship_type: string; strength_score: number;
  crime_types?: string[];
  crime_ids?: string[];
  confidence_level?: string;
  source?: string;
  target?: string;
}

const nodeTypeIcons: Record<string, React.FC<{ className?: string }>> = {
  criminal: Users,
  victim: Users,
  location: MapPin,
};

const CriminalNetwork: React.FC = () => {
  const [nodes, setNodes] = useState<NetworkNode[]>([]);
  const [edges, setEdges] = useState<NetworkEdge[]>([]);
  const [keyPlayers, setKeyPlayers] = useState<string[]>([]);
  const [aiSummary, setAiSummary] = useState<{
    summary_text: string;
    key_findings: string[];
    suspicious_pairs: { offender_1: string; offender_2: string; connection_type: string; confidence: string }[];
    recommended_actions: string[];
    network_stats: { total_criminals: number; high_risk_count: number; active_count: number; network_density: number };
    is_fallback?: boolean;
  } | null>(null);
  
  const [selectedNode, setSelectedNode] = useState<NetworkNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<any>(null);
  const [edgeInsight, setEdgeInsight] = useState<{ text: string; loading: boolean } | null>(null);
  const [nodeDetailLoading, setNodeDetailLoading] = useState(false);
  
  const [searchQuery, setSearchQuery] = useState("");
  const [nodeTypeFilter, setNodeTypeFilter] = useState("all");
  const [crimeTypeLens, setCrimeTypeLens] = useState("all");
  const [showIsolated, setShowIsolated] = useState(false);
  const [showClusters, setShowClusters] = useState(true);
  const [colorBy, setColorBy] = useState<"type" | "cluster">("type");
  const [replaceKey, setReplaceKey] = useState(0);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<"ok" | "offline" | "no_data">("ok");
  const [errorMessage, setErrorMessage] = useState("");
  const [compareNode1, setCompareNode1] = useState<NetworkNode | null>(null);
  const [compareNode2, setCompareNode2] = useState<NetworkNode | null>(null);
  const [highlightPath, setHighlightPath] = useState<string[]>([]);
  const [clusterSummary, setClusterSummary] = useState<Record<string, any>>({});
  const [isFallbackMode, setIsFallbackMode] = useState(false);
  const navigate = useNavigate();

  const [districtFilter, setDistrictFilter] = useState("all");
  const [warningMessage, setWarningMessage] = useState("");
  const [searchParams, setSearchParams] = useSearchParams();
  const districts = useDistricts();

  // New states for Ego-Network Navigation and Grid View
  const [viewMode, setViewMode] = useState<"graph" | "matrix" | "map">("graph");
  const [navHistory, setNavHistory] = useState<NetworkNode[]>([]);
  const [navIndex, setNavIndex] = useState(-1);
  const graphRef = useRef<NetworkGraphHandle>(null);

  const [isWatched, setIsWatched] = useState(false);
  const [watchedNodeIds, setWatchedNodeIds] = useState<Set<string>>(new Set());

  const fetchWatchlist = async () => {
    try {
      const w = await watchlistService.list();
      setWatchedNodeIds(new Set(w.map((item: any) => item.entity_id)));
    } catch (e) {
      console.warn("Could not fetch watchlist");
    }
  };

  useEffect(() => {
    fetchWatchlist();
  }, []);

  useEffect(() => {
    if (!selectedNode) return;
    watchlistService.status(selectedNode.node_id).then(setIsWatched).catch(() => {});
  }, [selectedNode?.node_id]);

  const toggleWatch = async () => {
    if (!selectedNode) return;
    try {
      if (isWatched) {
        await watchlistService.remove(selectedNode.node_id);
      } else {
        await watchlistService.add(selectedNode.node_id, selectedNode.node_type, selectedNode.label);
      }
      setIsWatched(!isWatched);
      fetchWatchlist(); // refresh stars in graph
    } catch (e) {
      console.error("Failed to toggle watch status", e);
    }
  };

  const [showSaveModal, setShowSaveModal] = useState(false);
  const [investigationTitle, setInvestigationTitle] = useState("");
  const [savedInvestigations, setSavedInvestigations] = useState<any[]>([]);
  const [showLoadPanel, setShowLoadPanel] = useState(false);

  const handleSaveInvestigation = async () => {
    if (!investigationTitle.trim()) return;
    try {
      await investigationService.save({
        title: investigationTitle,
        filters: { districtFilter, crimeTypeLens, nodeTypeFilter, searchQuery },
        board_state: {
          node_ids: nodes.map(n => n.node_id),
          edge_ids: edges.map(e => e.edge_id).filter(Boolean),
          node_notes: {},
        },
        district_id: districtFilter !== "all" ? districtFilter : undefined,
      });
      setShowSaveModal(false);
      setInvestigationTitle("");
      fetchInvestigations(); // Refresh the list
    } catch (e) {
      console.error("Failed to save investigation", e);
    }
  };

  const handleLoadInvestigation = async (id: string) => {
    try {
      const inv = await investigationService.get(id);
      if (!inv) return;
      const f = inv.filters || {};
      setDistrictFilter(f.districtFilter || "all");
      setCrimeTypeLens(f.crimeTypeLens || "all");
      setNodeTypeFilter(f.nodeTypeFilter || "all");
      setSearchQuery(f.searchQuery || "");
      setShowLoadPanel(false);
    } catch (e) {
      console.error("Failed to load investigation", e);
    }
  };

  const fetchInvestigations = async () => {
    try {
      const d = await investigationService.list();
      setSavedInvestigations(d?.investigations || []);
    } catch (e) {
      console.warn("Could not fetch investigations");
    }
  };

  useEffect(() => {
    if (showLoadPanel) fetchInvestigations();
  }, [showLoadPanel]);

  const [timelineEvents, setTimelineEvents] = useState<any[]>([]);
  const [selectedTimelineDate, setSelectedTimelineDate] = useState<string | null>(null);

  useEffect(() => {
    const allCrimeIds = Array.from(new Set(edges.flatMap((e: any) => e.crime_ids || [])));
    if (allCrimeIds.length === 0) { setTimelineEvents([]); return; }
    networkService.getTimeline(allCrimeIds).then(setTimelineEvents);
  }, [edges]);

  useEffect(() => {
    if (!selectedTimelineDate) { graphRef.current?.clearFocus(); return; }
    const matchingCrimeIds = new Set(
      timelineEvents.filter(e => e.date === selectedTimelineDate).map(e => e.crime_id)
    );
    graphRef.current?.highlightByCrimeIds?.(matchingCrimeIds);
  }, [selectedTimelineDate, timelineEvents]);


  useEffect(() => {
    const d = searchParams.get("district"); if (d) setDistrictFilter(d);
    const c = searchParams.get("crime_type"); if (c) setCrimeTypeLens(c);
    const n = searchParams.get("node_type"); if (n) setNodeTypeFilter(n);
  }, []); // hydrate on mount

  useEffect(() => {
    const params: Record<string, string> = {};
    if (districtFilter !== "all") params.district = districtFilter;
    if (crimeTypeLens !== "all") params.crime_type = crimeTypeLens;
    if (nodeTypeFilter !== "all") params.node_type = nodeTypeFilter;
    setSearchParams(params, { replace: true });
  }, [districtFilter, crimeTypeLens, nodeTypeFilter, setSearchParams]);

  useEffect(() => {
    const controller = new AbortController();
    const handle = setTimeout(async () => {
      setLoading(true);
      try {
        const [gResult, aiResult] = await Promise.allSettled([
          networkService.getGraphData(
            searchQuery || undefined,
            crimeTypeLens === "all" ? undefined : crimeTypeLens,
            districtFilter === "all" ? undefined : districtFilter,
            nodeTypeFilter === "all" ? undefined : nodeTypeFilter,
            { signal: controller.signal }
          ),
          networkService.getAiSummary(
            districtFilter === "all" ? undefined : districtFilter,
            crimeTypeLens === "all" ? undefined : crimeTypeLens,
            searchQuery || undefined,
            nodeTypeFilter === "all" ? undefined : nodeTypeFilter,
            { signal: controller.signal }
          ),
        ]);
        
        const g = gResult.status === "fulfilled" ? gResult.value : null;
        const ai = aiResult.status === "fulfilled" ? aiResult.value : null;
        
        if (g && g.status === "offline") {
          setStatus("offline");
          setErrorMessage(g.error || "Graph database is disconnected");
        } else if (g && (g.status === "no_data" || (g.nodes && g.nodes.length === 0))) {
          setStatus("no_data");
          setWarningMessage(g.warning || "No graph data available");
          setErrorMessage("No graph data available");
        } else if (g) {
          setStatus("ok");
          setNodes(g.nodes as NetworkNode[]);
          setEdges(g.edges as NetworkEdge[]);
          setReplaceKey((k) => k + 1);
          setKeyPlayers(g.key_players || []);
          setIsFallbackMode(g.source === "postgres_fallback");
          setClusterSummary(g.cluster_summary || {});
          setAiSummary(ai as typeof aiSummary);
          if (g.warning) {
            setWarningMessage(g.warning);
          } else if (g.nodes.length >= 100) {
            setWarningMessage(`Showing ${g.nodes.length} nodes (maximum reached). Please narrow your filters to see more specific results.`);
          } else {
            setWarningMessage("");
          }
        }
      } catch (e: any) {
        if (e.name !== "CanceledError") {
          setStatus("offline");
          setErrorMessage(e.response?.data?.detail || "Failed to connect to backend");
          console.error(e);
        }
      }
      setLoading(false);
    }, 400);

    return () => {
      clearTimeout(handle);
      controller.abort();
    };
  }, [searchQuery, nodeTypeFilter, crimeTypeLens, districtFilter]);

  const navigateToNode = async (node: NetworkNode, fromHistory = false) => {
    setViewMode("graph");
    
    if (!fromHistory) {
      const truncated = navHistory.slice(0, navIndex + 1);
      setNavHistory([...truncated, node]);
      setNavIndex(truncated.length);
    }
    
    setSelectedNode(node);
    setNodeDetailLoading(true);
    
    const alreadyLoaded = edges.some(e => e.source_node_id === node.node_id || e.target_node_id === node.node_id);
    
    const [detail] = await Promise.all([
      networkService.getNodeDetail(node.node_id).catch(() => null),
      !alreadyLoaded ? handleNodeExpand(node).catch(() => null) : Promise.resolve()
    ]);
    
    if (detail) {
      setSelectedNode(prev => prev && prev.node_id === node.node_id ? { ...prev, ...detail } : prev);
    }
    
    setNodeDetailLoading(false);
    graphRef.current?.focusOnNode(node.node_id);
    
    if (node.node_type === "criminal") {
      networkService.getNodeAiAnalysis(node.node_id).then(aiRes => {
         if (aiRes) {
            setSelectedNode(prev => prev && prev.node_id === node.node_id ? { ...prev, ai_analysis: aiRes.ai_analysis, is_fallback: aiRes.is_fallback } : prev);
         }
      });
    }
  };

  useEffect(() => {
    const focusId = searchParams.get("focus");
    if (focusId && nodes.length > 0) {
      const target = nodes.find(n => n.node_id === focusId);
      if (target) {
        navigateToNode(target);
      }
    }
  }, [nodes, searchParams]);

  const goBack = () => {
    if (navIndex <= 0) return;
    setNavIndex(navIndex - 1);
    navigateToNode(navHistory[navIndex - 1], true);
  };
  
  const goForward = () => {
    if (navIndex >= navHistory.length - 1) return;
    setNavIndex(navIndex + 1);
    navigateToNode(navHistory[navIndex + 1], true);
  };

  const clearNavigation = () => {
    setNavHistory([]);
    setNavIndex(-1);
    setSelectedNode(null);
    setSelectedEdge(null);
    setEdgeInsight(null);
    graphRef.current?.clearFocus();
  };

  const handleNodeSelect = async (node: NetworkNode) => {
    setSelectedEdge(null);
    setEdgeInsight(null);
    navigateToNode(node);
  };

  const handleEdgeSelect = async (sourceId: string, targetId: string, edgeData: any) => {
    setSelectedNode(null);
    setSelectedEdge(edgeData);
    
    const nodeA = nodes.find(n => n.node_id === sourceId);
    const nodeB = nodes.find(n => n.node_id === targetId);
    if (!nodeA || !nodeB) return;
    
    setEdgeInsight({ text: "", loading: true });
    const insight = await networkService.getEdgeInsight(nodeA, nodeB, edgeData);
    setEdgeInsight({ text: insight || "No insight available.", loading: false });
  };

  const handleNodeCompare = async (node: NetworkNode) => {
    if (isFallbackMode) {
      setWarningMessage("Shortest path comparison is not available in fallback mode (Neo4j is offline).");
      return;
    }
    
    if (!compareNode1) {
      setCompareNode1(node);
    } else if (!compareNode2) {
      setCompareNode2(node);
      const res = await networkService.getShortestPath(compareNode1.node_id, node.node_id);
      if (res && res.found) {
        const pathIds = res.path_nodes.map((n: any) => n.id);
        setHighlightPath(pathIds);
      } else {
        setWarningMessage("No path found between the selected nodes, or the graph database is offline.");
      }
    } else {
      setCompareNode1(node);
      setCompareNode2(null);
      setHighlightPath([]);
    }
  };

  const handleNodeExpand = async (node: NetworkNode) => {
    if (isFallbackMode) {
      setWarningMessage("Node expansion is not available in fallback mode (Neo4j is offline).");
      return;
    }
    try {
      const res = await networkService.expandNode(node.node_id);
      if (res && res.nodes && res.edges) {
        const newNodes = [...nodes];
        const newEdges = [...edges];
        let added = false;
        
        res.nodes.forEach((n: any) => {
          if (!newNodes.find(existing => existing.node_id === n.node_id)) {
            newNodes.push(n);
            added = true;
          }
        });
        
        const getEdgeKey = (edge: any) => edge.edge_id || `${edge.source_node_id || edge.source}_${edge.target_node_id || edge.target}`;
        res.edges.forEach((e: any) => {
          if (!newEdges.find(existing => getEdgeKey(existing) === getEdgeKey(e))) {
            newEdges.push(e);
            added = true;
          }
        });
        
        if (added) {
          setNodes(newNodes);
          setEdges(newEdges);
        } else {
          setWarningMessage("No additional connections found for this node.");
        }
      }
    } catch (e: any) {
      setWarningMessage(e.response?.data?.detail || "Node expansion failed.");
    }
  };

  const filteredNodes = useMemo(() => {
    let result = [...nodes];
    
    if (!showIsolated && edges.length > 0) {
      const connectedNodeIds = new Set(edges.flatMap(e => [e.source_node_id, e.target_node_id]));
      result = result.filter(n => connectedNodeIds.has(n.node_id));
    }
    
    return result;
    // Note: nodeTypeFilter and searchQuery filtering happens server-side via networkService.getGraphData
  }, [nodes, edges, showIsolated]);

  const nodeTypeCounts = nodes.reduce((acc, n) => { acc[n.node_type] = (acc[n.node_type] || 0) + 1; return acc; }, {} as Record<string, number>);


  if (loading) return <div className="flex-1 flex items-center justify-center"><LoadingSpinner size="lg" text="Building criminal network..." showProgress /></div>;

  const NodeIcon = selectedNode ? (nodeTypeIcons[selectedNode.node_type] || Users) : Users;

  return (
    <div className="flex-1 min-h-0 overflow-hidden flex flex-col w-full">
      {/* Header + Controls */}
      <div className="p-4 border-b border-slate-700/50 bg-slate-900/50">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Network className="h-5 w-5 text-blue-400" />
            <h1 className="text-lg font-bold text-white">Criminal Network & Link Analysis</h1>
          </div>
          <div className="flex items-center gap-2">
            {Object.entries(nodeTypeCounts).map(([type, count]) => (
              <span key={type} className="text-xs px-2 py-0.5 rounded-full border" style={{ borderColor: NODE_COLORS[type] + "60", color: NODE_COLORS[type], background: NODE_COLORS[type] + "20" }}>
                {type}: {count}
              </span>
            ))}
          </div>
        </div>
        
        {/* Navigation Toolbar */}
        <div className="flex items-center gap-4 mb-3 pb-3 border-b border-slate-700/50">
          <div className="flex items-center gap-1 bg-slate-800 p-1 rounded-lg">
            <button
              onClick={() => setViewMode("graph")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                viewMode === "graph" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              <Network className="h-3.5 w-3.5" /> Graph
            </button>
            <button
              onClick={() => setViewMode("matrix")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                viewMode === "matrix" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              <Grid className="h-3.5 w-3.5" /> Matrix
            </button>
            <button
              onClick={() => setViewMode("map")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                viewMode === "map" ? "bg-blue-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              <Map className="h-3.5 w-3.5" /> Map
            </button>
          </div>

          <div className="flex items-center gap-2 border-l border-slate-700 pl-4">
            <button onClick={() => setShowSaveModal(true)} className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 text-slate-300 hover:text-white border border-slate-700">
              💾 Save Investigation
            </button>
            <button onClick={() => setShowLoadPanel(true)} className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 text-slate-300 hover:text-white border border-slate-700">
              📂 My Investigations
            </button>
          </div>

          <div className="flex items-center gap-2 border-l border-slate-700 pl-4">
            <button 
              onClick={goBack} 
              disabled={navIndex <= 0} 
              className={`p-1.5 rounded-lg transition-colors ${navIndex <= 0 ? "text-slate-600 cursor-not-allowed" : "text-slate-300 hover:bg-slate-700 hover:text-white"}`}
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button 
              onClick={goForward} 
              disabled={navIndex >= navHistory.length - 1} 
              className={`p-1.5 rounded-lg transition-colors ${navIndex >= navHistory.length - 1 ? "text-slate-600 cursor-not-allowed" : "text-slate-300 hover:bg-slate-700 hover:text-white"}`}
            >
              <ChevronRight className="h-4 w-4" />
            </button>
            
            <div className="flex items-center gap-1 text-xs text-slate-400 ml-2">
              {navHistory.length === 0 ? (
                <span>No selection history</span>
              ) : (
                navHistory.slice(Math.max(0, navIndex - 3), navIndex + 1).map((n, i, arr) => (
                  <React.Fragment key={`${n.node_id}-${i}`}>
                    {i > 0 && <ChevronRight className="h-3 w-3 mx-1" />}
                    <button 
                      onClick={() => { 
                        const targetIdx = Math.max(0, navIndex - 3) + i;
                        setNavIndex(targetIdx); 
                        navigateToNode(n, true); 
                      }}
                      className={`hover:text-white hover:underline ${i === arr.length - 1 ? "text-blue-400 font-bold" : ""}`}
                    >
                      {n.label}
                    </button>
                  </React.Fragment>
                ))
              )}
              {navHistory.length > 0 && (
                <button onClick={clearNavigation} className="ml-3 text-[10px] uppercase tracking-wider text-slate-500 hover:text-red-400">Clear</button>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative flex-1 max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search nodes by name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
            />
          </div>
          <div className="flex items-center gap-1.5">
            {[["all", "All Nodes"], ["criminal", "Criminals"], ["victim", "Victims"], ["location", "Locations"]].map(([val, label]) => (
              <button
                key={val}
                onClick={() => setNodeTypeFilter(val)}
                className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                  nodeTypeFilter === val ? "bg-blue-600 text-white" : "bg-slate-800 text-slate-400 hover:text-white"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1.5 ml-3 pl-3 border-l border-slate-700">
            <select
              value={districtFilter}
              onChange={(e) => setDistrictFilter(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-slate-300 text-xs rounded-lg px-2 py-1 outline-none mr-1.5"
            >
              <option value="all">All Districts</option>
              {districts.map((d) => (
                <option key={d.district_id} value={d.district_id}>{d.district_name}</option>
              ))}
            </select>

            <select
              value={crimeTypeLens}
              onChange={(e) => setCrimeTypeLens(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-slate-300 text-xs rounded-lg px-2 py-1 outline-none"
            >
              <option value="all">All Crimes Lens</option>
              {CRIME_TYPES.filter(t => t !== "All").map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
            
            <button
              onClick={() => {
                if (keyPlayers.length > 0) {
                  graphRef.current?.highlightKeyPlayers(keyPlayers);
                }
              }}
              className="px-2.5 py-1 rounded-lg text-xs font-medium transition-colors bg-orange-900/40 text-orange-400 hover:bg-orange-900/60"
            >
              Highlight Key Players
            </button>

            <button
              onClick={() => setShowIsolated(!showIsolated)}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                showIsolated ? "bg-slate-700 text-white" : "bg-slate-800 text-slate-400 hover:text-white"
              }`}
            >
              {showIsolated ? "Hide Isolated" : "Show Isolated"}
            </button>

            <button
              onClick={() => setShowClusters(!showClusters)}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                showClusters ? "bg-purple-900/40 text-purple-400" : "bg-slate-800 text-slate-400 hover:text-white"
              }`}
            >
              {showClusters ? "Clusters: On" : "Clusters: Off"}
            </button>
            <button
              onClick={() => setColorBy(colorBy === "type" ? "cluster" : "type")}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                colorBy === "cluster" ? "bg-indigo-900/40 text-indigo-400" : "bg-slate-800 text-slate-400 hover:text-white"
              }`}
            >
              {colorBy === "type" ? "Color: Type" : "Color: Cluster"}
            </button>
            <span className="text-xs text-slate-500 ml-2">{filteredNodes.length} nodes • {edges.length} connections</span>
          </div>
          <div className="ml-auto flex items-center gap-3">
            {[["criminal", "Criminals"], ["victim", "Victims"], ["location", "Locations"]].map(([type, label]) => (
              <div key={type} className="flex items-center gap-1.5">
                <div className="h-3 w-3 rounded-full" style={{ background: NODE_COLORS[type] }} />
                <span className="text-xs text-slate-400">{label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {(districtFilter !== "all" || crimeTypeLens !== "all" || nodeTypeFilter !== "all") && (
        <div className="flex items-center gap-2 px-4 py-2 bg-slate-800/60 border-b border-slate-700/50">
          <span className="text-xs text-slate-400">Active filters:</span>
          {districtFilter !== "all" && (
            <span className="flex items-center gap-1 text-xs bg-blue-900/40 text-blue-300 px-2 py-1 rounded-full">
              District: {districts.find(d => d.district_id === districtFilter)?.district_name || districtFilter}
              <button onClick={() => setDistrictFilter("all")} className="hover:text-white">x</button>
            </span>
          )}
          {crimeTypeLens !== "all" && (
            <span className="flex items-center gap-1 text-xs bg-purple-900/40 text-purple-300 px-2 py-1 rounded-full">
              Crime Type: {crimeTypeLens}
              <button onClick={() => setCrimeTypeLens("all")} className="hover:text-white">x</button>
            </span>
          )}
          {nodeTypeFilter !== "all" && (
            <span className="flex items-center gap-1 text-xs bg-emerald-900/40 text-emerald-300 px-2 py-1 rounded-full">
              Type: {nodeTypeFilter}
              <button onClick={() => setNodeTypeFilter("all")} className="hover:text-white">x</button>
            </span>
          )}
          <button
            onClick={() => { setDistrictFilter("all"); setCrimeTypeLens("all"); setNodeTypeFilter("all"); setSearchQuery(""); }}
            className="ml-auto text-xs text-slate-400 hover:text-red-400 underline"
          >
            Clear all filters
          </button>
        </div>
      )}

      {warningMessage && (
        <div className="bg-amber-900/60 border-b border-amber-500/40 px-4 py-2 flex items-center gap-2 text-xs text-amber-200">
          <AlertTriangle className="h-4 w-4 text-amber-400 flex-shrink-0" />
          <span>{warningMessage}</span>
        </div>
      )}

      <div className="flex-1 min-h-0 flex overflow-hidden">
        {/* Network Graph */}
        <div className="flex-1 relative bg-slate-900/50">
          {status === "offline" ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400">
              <AlertTriangle className="h-12 w-12 text-red-500 mb-3 opacity-80" />
              <h2 className="text-xl font-bold text-white mb-2">Database Disconnected</h2>
              <p className="text-sm max-w-md text-center">{errorMessage}</p>
            </div>
          ) : status === "no_data" ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400">
              <Network className="h-12 w-12 text-slate-600 mb-3 opacity-50" />
              <h2 className="text-xl font-bold text-white mb-2">No Matches for This Filter Combination</h2>
              <p className="text-sm max-w-md text-center mb-4">
                {warningMessage || "There are no records matching the selected district and crime type."}
              </p>
              <button
                onClick={() => { setDistrictFilter("all"); setCrimeTypeLens("all"); setNodeTypeFilter("all"); setSearchQuery(""); }}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm"
              >
                Clear Filters
              </button>
            </div>
          ) : (
            <>
              {viewMode === "graph" ? (
                <NetworkGraph 
                  ref={graphRef}
                  nodes={filteredNodes} 
                  edges={edges} 
                  onNodeSelect={handleNodeSelect} 
                  onNodeCompare={handleNodeCompare}
                  onNodeExpand={handleNodeExpand}
                  onEdgeSelect={handleEdgeSelect}
                  selectedNodeId={selectedNode?.node_id} 
                  highlightPath={highlightPath}
                  showClusters={showClusters}
                  clusterSummary={clusterSummary}
                  replaceKey={replaceKey}
                  colorBy={colorBy}
                  watchedNodeIds={watchedNodeIds}
                />
              ) : viewMode === "matrix" ? (
                <ConnectivityMatrix 
                  nodes={filteredNodes}
                  edges={edges}
                  onCellClick={(nodeA, nodeB) => {
                    const edge = edges.find((e) => 
                      (e.source_node_id === nodeA && e.target_node_id === nodeB) ||
                      (e.source_node_id === nodeB && e.target_node_id === nodeA)
                    );
                    if (edge) {
                      const mappedEdgeData = {
                        strength: edge.strength_score,
                        crimeTypes: edge.crime_types || [],
                        confidence: edge.confidence_level,
                        label: edge.relationship_type,
                        ...edge
                      };
                      handleEdgeSelect(nodeA, nodeB, mappedEdgeData);
                    } else {
                      const targetNode = filteredNodes.find(n => n.node_id === nodeB) || filteredNodes.find(n => n.node_id === nodeA);
                      if (targetNode) navigateToNode(targetNode);
                    }
                  }}
                />
              ) : (
                <NetworkMap 
                  nodes={filteredNodes}
                  edges={edges}
                  onNodeSelect={navigateToNode}
                  selectedNodeId={selectedNode?.node_id}
                  watchedNodeIds={watchedNodeIds}
                  isFallbackMode={isFallbackMode}
                />
              )}
              
              {/* Floating zoom controls */}
              <div className="absolute bottom-24 left-4 flex flex-col gap-1 z-10">
                <button
                  onClick={() => graphRef.current?.zoomIn()}
                  title="Zoom In"
                  className="w-8 h-8 flex items-center justify-center bg-slate-800/95 border border-slate-600 rounded-lg text-slate-300 hover:text-white hover:bg-slate-700 text-base font-bold shadow transition-colors"
                >+</button>
                <button
                  onClick={() => graphRef.current?.zoomOut()}
                  title="Zoom Out"
                  className="w-8 h-8 flex items-center justify-center bg-slate-800/95 border border-slate-600 rounded-lg text-slate-300 hover:text-white hover:bg-slate-700 text-base font-bold shadow transition-colors"
                >−</button>
                <button
                  onClick={() => graphRef.current?.fitGraph()}
                  title="Fit to screen"
                  className="w-8 h-8 flex items-center justify-center bg-slate-800/95 border border-slate-600 rounded-lg text-slate-300 hover:text-white hover:bg-slate-700 text-sm shadow transition-colors"
                >⊡</button>
              </div>
              <div className="absolute bottom-24 left-14 bg-slate-900/80 backdrop-blur border border-slate-700/50 rounded-lg px-3 py-1.5 z-10">
                <p className="text-xs text-slate-500">Click node • Double-click expand • Shift-click compare • Scroll / ± to zoom</p>
              </div>
              
              {edgeInsight && (
                <div className="absolute bottom-32 left-4 right-4 max-w-md bg-blue-950/90 backdrop-blur border border-blue-500/30 rounded-lg p-3 z-10 shadow-lg shadow-blue-900/20">
                  <div className="flex items-center gap-2 mb-1">
                    <Brain className="h-3.5 w-3.5 text-blue-400" />
                    <span className="text-xs font-semibold text-white">Connection Insight</span>
                    <button onClick={() => setEdgeInsight(null)} className="ml-auto text-slate-500 hover:text-white text-xs">✕</button>
                  </div>
                  <p className="text-xs text-blue-200 leading-relaxed">
                    {edgeInsight.loading ? (
                      <span className="flex items-center gap-2">
                        <span className="h-3 w-3 rounded-full border-2 border-blue-400 border-t-transparent animate-spin inline-block"></span>
                        Analyzing connection…
                      </span>
                    ) : (
                      edgeInsight.text
                    )}
                  </p>
                </div>
              )}

              {(compareNode1 || compareNode2) && (
                <div className="absolute top-4 left-4 right-4 flex items-center justify-between bg-slate-900/90 backdrop-blur border border-slate-700/50 rounded-lg p-3">
                  <div className="flex items-center gap-4">
                    <div className="text-xs">
                      <span className="text-slate-400">Node A:</span> <span className="text-white font-bold">{compareNode1?.label || "Select..."}</span>
                    </div>
                    <div className="text-xs text-slate-500">↔</div>
                    <div className="text-xs">
                      <span className="text-slate-400">Node B:</span> <span className="text-white font-bold">{compareNode2?.label || "Select..."}</span>
                    </div>
                  </div>
                  <button 
                    onClick={() => { setCompareNode1(null); setCompareNode2(null); setHighlightPath([]); }}
                    className="text-xs px-2 py-1 bg-red-900/40 text-red-400 rounded-lg"
                  >
                    Clear Comparison
                  </button>
                </div>
              )}
            </>
          )}

          {/* Timeline Overlay */}
          <div className="absolute bottom-0 left-0 right-0 z-20">
            <NetworkTimeline 
              events={timelineEvents} 
              onSelectDate={setSelectedTimelineDate} 
              selectedDate={selectedTimelineDate}
              isFallbackMode={isFallbackMode}
            />
          </div>
        </div>

        {/* Right Panel */}
        <div className="w-80 bg-slate-900/95 border-l border-slate-700/50 flex flex-col overflow-y-auto custom-scrollbar">
          
          {/* Edge Detail */}
          {selectedEdge ? (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-4 border-b border-slate-700/50">
              <div className="flex items-center gap-3 mb-4">
                <div className="h-10 w-10 rounded-xl flex items-center justify-center bg-blue-500/20">
                  <Network className="h-5 w-5 text-blue-400" />
                </div>
                <div>
                  <p className="text-sm font-bold text-white">{selectedEdge.label}</p>
                  <span className="text-xs text-slate-400">Connection</span>
                </div>
              </div>
              
              <div className="space-y-3">
                <div className="flex justify-between text-xs pb-2 border-b border-slate-800">
                  <span className="text-slate-400">Confidence</span>
                  <span className={`font-bold ${selectedEdge.confidence === 'CONFIRMED' ? 'text-green-400' : 'text-orange-400'}`}>
                    {selectedEdge.confidence}
                  </span>
                </div>
                
                <div className="flex justify-between text-xs pb-2 border-b border-slate-800">
                  <span className="text-slate-400">Strength Score</span>
                  <span className="font-bold text-blue-400">{selectedEdge.strength}%</span>
                </div>
                
                {selectedEdge.crimeTypes && selectedEdge.crimeTypes.length > 0 && (
                  <div>
                    <span className="text-xs text-slate-400 block mb-2">Associated Crimes</span>
                    <div className="flex flex-wrap gap-1">
                      {selectedEdge.crimeTypes.map((t: string) => (
                        <span key={t} className="text-[10px] px-2 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                          {t}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </motion.div>
          ) : selectedNode ? (
            /* Node Detail */
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-4 border-b border-slate-700/50">
              <div className="flex items-center gap-3 mb-4">
                <div className="h-10 w-10 rounded-xl flex items-center justify-center" style={{ background: NODE_COLORS[selectedNode.node_type] + "30" }}>
                  <NodeIcon className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-bold text-white flex items-center gap-2">
                    {selectedNode.label}
                    {nodeDetailLoading && <Loader2 className="h-3 w-3 animate-spin text-slate-400" />}
                  </p>
                  <span className="text-xs capitalize" style={{ color: NODE_COLORS[selectedNode.node_type] }}>{selectedNode.node_type}</span>
                </div>
              </div>
              <div className="space-y-2">
                {selectedNode.risk_score > 0 && (
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-400">Risk Score</span>
                      <span className="font-bold text-red-400">{selectedNode.risk_score}/100</span>
                    </div>
                    <div className="h-1.5 bg-slate-700 rounded-full">
                      <div className="h-full rounded-full bg-gradient-to-r from-orange-500 to-red-500" style={{ width: `${selectedNode.risk_score}%` }} />
                    </div>
                  </div>
                )}
                {selectedNode.crime_count > 0 && (
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">Crime Count</span>
                    <span className="text-red-400 font-bold">{selectedNode.crime_count}</span>
                  </div>
                )}
                {Object.entries(selectedNode.profile_data).map(([k, v]) => (
                  <div key={k} className="flex justify-between text-xs">
                    <span className="text-slate-400 capitalize">{k.replace(/_/g, " ")}</span>
                    <span className="text-slate-200">{String(v)}</span>
                  </div>
                ))}
              </div>
              
              {selectedNode.ai_analysis && (
                <div className="mt-4 p-3 bg-blue-950/30 border border-blue-500/20 rounded-lg">
                  <div className="flex items-center gap-2 mb-2">
                    <Brain className="h-4 w-4 text-blue-400" />
                    <h3 className="text-sm font-semibold text-white">AI Profile Analysis</h3>
                  </div>
                  <div className="text-xs text-blue-200 leading-relaxed">
                    <AIMarkdown text={selectedNode.ai_analysis} isFallback={selectedNode.is_fallback} />
                  </div>
                </div>
              )}
              
              {selectedNode.node_type === "criminal" && (
                <button
                  onClick={() => navigate(`/offenders?offender_id=${selectedNode.node_id}`)}
                  className="mt-3 w-full text-xs px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium"
                >
                  Open Full Offender Record →
                </button>
              )}
              
              <button
                onClick={toggleWatch}
                className={`mt-2 w-full text-xs px-3 py-2 rounded-lg font-medium border ${
                  isWatched ? "bg-yellow-900/30 border-yellow-500/50 text-yellow-400" : "bg-slate-800 border-slate-700 text-slate-300 hover:text-white"
                }`}
              >
                {isWatched ? "⭐ Watching — you'll be alerted on new activity" : "☆ Add to Watchlist"}
              </button>
              
              <div className="mt-3">
                <p className="text-xs text-slate-400 mb-2">Connected Edges ({edges.filter(e => e.source_node_id === selectedNode.node_id || e.target_node_id === selectedNode.node_id).length})</p>
                <div className="space-y-1">
                  {edges.filter(e => e.source_node_id === selectedNode.node_id || e.target_node_id === selectedNode.node_id).map((e, i) => {
                    const otherId = e.source_node_id === selectedNode.node_id ? e.target_node_id : e.source_node_id;
                    const otherNode = nodes.find(n => n.node_id === otherId);
                    return (
                      <div key={i} className="flex items-center justify-between text-xs p-2 bg-slate-800/50 rounded">
                        <div className="flex items-center gap-2">
                          <div className="h-2 w-2 rounded-full" style={{ background: NODE_COLORS[otherNode?.node_type || "criminal"] }} />
                          <span className="text-slate-300">{otherNode?.label || otherId}</span>
                        </div>
                        <span className="text-slate-500">{e.relationship_type}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </motion.div>
          ) : (
            <div className="p-4 border-b border-slate-700/50 text-center">
              <Network className="h-8 w-8 text-slate-600 mx-auto mb-2" />
              <p className="text-xs text-slate-500">Click a node or edge in the network to view details</p>
            </div>
          )}

          {/* AI Summary */}
          {aiSummary && (
            <div className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <Brain className="h-4 w-4 text-blue-400" />
                <h3 className="text-sm font-semibold text-white">AI Network Analysis</h3>
                <span className="text-xs bg-blue-900/40 text-blue-400 px-1.5 py-0.5 rounded-full">Gemini</span>
              </div>
              <div className="bg-blue-950/30 border border-blue-500/20 rounded-lg p-3 mb-3 text-xs text-blue-200 leading-relaxed">
                <AIMarkdown text={aiSummary.summary_text} isFallback={aiSummary.is_fallback} />
              </div>

              <h4 className="text-xs font-semibold text-blue-400 mb-2 flex items-center gap-1">
                <Brain className="h-3 w-3" />Key Findings
              </h4>
              <div className="space-y-1 mb-3">
                {(Array.isArray(aiSummary?.key_findings) ? aiSummary.key_findings : []).map((kf, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-slate-300">
                    <span className="text-blue-400 font-bold mt-0.5">•</span>
                    <div className="flex-1"><AIMarkdown text={kf} /></div>
                  </div>
                ))}
              </div>

              <h4 className="text-xs font-semibold text-orange-400 mb-2 flex items-center gap-1">
                <AlertTriangle className="h-3 w-3" />Suspicious Associations
              </h4>
              <div className="space-y-2 mb-3">
                {(Array.isArray(aiSummary?.suspicious_pairs) ? aiSummary.suspicious_pairs : []).map((s, i) => (
                  <div key={i} className="p-2 bg-orange-950/20 border border-orange-500/20 rounded-lg">
                    <div className="text-xs text-slate-300"><AIMarkdown text={`${s.offender_1} ↔ ${s.offender_2} (${s.connection_type})`} /></div>
                    <div className="text-xs text-slate-500"><AIMarkdown text={s.confidence} /></div>
                  </div>
                ))}
              </div>

              <h4 className="text-xs font-semibold text-green-400 mb-2 flex items-center gap-1">
                <ChevronRight className="h-3 w-3" />Recommended Actions
              </h4>
              <div className="space-y-1">
                {(Array.isArray(aiSummary?.recommended_actions) ? aiSummary.recommended_actions : []).map((p, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-slate-300">
                    <span className="text-green-400 font-bold mt-0.5">{i + 1}.</span>
                    <div className="flex-1"><AIMarkdown text={p} /></div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
      
      {showSaveModal && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center" onClick={() => setShowSaveModal(false)}>
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-5 w-96" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-bold text-white mb-3">Save this investigation</h3>
            <input
              autoFocus
              placeholder="e.g. Kolar burglary ring — July 2026"
              value={investigationTitle}
              onChange={e => setInvestigationTitle(e.target.value)}
              className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white mb-3 focus:outline-none focus:border-blue-500"
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowSaveModal(false)} className="px-3 py-1.5 text-xs text-slate-400 hover:text-white">Cancel</button>
              <button onClick={handleSaveInvestigation} className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white rounded-lg">Save</button>
            </div>
          </div>
        </div>
      )}

      {showLoadPanel && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center" onClick={() => setShowLoadPanel(false)}>
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-5 w-[420px] max-h-[70vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-bold text-white mb-3">My Investigations</h3>
            {savedInvestigations.length === 0 && <p className="text-xs text-slate-500">No saved investigations yet.</p>}
            {savedInvestigations.map(inv => (
              <button
                key={inv.investigation_id}
                onClick={() => handleLoadInvestigation(inv.investigation_id)}
                className="w-full text-left p-3 mb-2 bg-slate-800/50 hover:bg-slate-800 rounded-lg border border-slate-700/50 transition-colors"
              >
                <p className="text-sm text-white font-medium">{inv.title}</p>
                <p className="text-xs text-slate-500 mt-1">Updated {new Date(inv.updated_at).toLocaleString()}</p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default CriminalNetwork;
