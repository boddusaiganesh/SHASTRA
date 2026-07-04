import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Play, Pause, FastForward, SkipBack, Info, Network, AlertTriangle, Search, Filter, ShieldAlert, Zap, Layers, RefreshCw, ChevronRight, Users, MapPin, Building, Brain } from "lucide-react";
import ReactMarkdown from 'react-markdown';
import { networkService } from "../services/networkService";
import NetworkGraph from "../components/network/NetworkGraph";
import LoadingSpinner from "../components/common/LoadingSpinner";
import { NODE_COLORS } from "../constants/colorCodes";

interface NetworkNode {
  node_id: string; node_type: string; label: string; risk_score: number;
  crime_count: number; profile_data: Record<string, unknown>;
}
interface NetworkEdge {
  source: string; target: string; relationship_type: string; strength_score: number;
}

const nodeTypeIcons: Record<string, React.FC<{ className?: string }>> = {
  criminal: Users,
  victim: Users,
  location: MapPin,
  organization: Building,
};

const CriminalNetwork: React.FC = () => {
  const [nodes, setNodes] = useState<NetworkNode[]>([]);
  const [edges, setEdges] = useState<NetworkEdge[]>([]);
  const [aiSummary, setAiSummary] = useState<{ summary: string; suspicious_associations: { entities: string[]; reason: string; severity: string }[]; investigation_priorities: string[] } | null>(null);
  const [selectedNode, setSelectedNode] = useState<NetworkNode | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [nodeTypeFilter, setNodeTypeFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<"ok" | "offline" | "no_data">("ok");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    const fetch = async () => {
      setLoading(true);
      try {
        const [g, ai] = await Promise.all([
          networkService.getGraphData(),
          networkService.getAiSummary(),
        ]);
        
        if (g.status === "offline") {
          setStatus("offline");
          setErrorMessage(g.error || "Graph database is disconnected");
        } else if (g.status === "no_data") {
          setStatus("no_data");
          setErrorMessage("No graph data available");
        } else {
          setStatus("ok");
          setNodes(g.nodes as NetworkNode[]);
          setEdges(g.edges as NetworkEdge[]);
          setAiSummary(ai as typeof aiSummary);
        }
      } catch (e: any) {
        setStatus("offline");
        setErrorMessage(e.response?.data?.detail || "Failed to connect to backend");
      }
      setLoading(false);
    };
    fetch();
  }, []);

  const filteredNodes = nodes.filter((n) => {
    if (nodeTypeFilter !== "all" && n.node_type !== nodeTypeFilter) return false;
    if (searchQuery && !n.label.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const nodeTypeCounts = nodes.reduce((acc, n) => { acc[n.node_type] = (acc[n.node_type] || 0) + 1; return acc; }, {} as Record<string, number>);

  if (loading) return <div className="flex-1 flex items-center justify-center"><LoadingSpinner size="lg" text="Building criminal network..." /></div>;

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
            {[["all", "All Nodes"], ["criminal", "Criminals"], ["victim", "Victims"], ["location", "Locations"], ["organization", "Orgs"]].map(([val, label]) => (
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
          <div className="ml-auto flex items-center gap-3">
            {[["criminal", "Criminals"], ["victim", "Victims"], ["location", "Locations"], ["organization", "Organizations"]].map(([type, label]) => (
              <div key={type} className="flex items-center gap-1.5">
                <div className="h-3 w-3 rounded-full" style={{ background: NODE_COLORS[type] }} />
                <span className="text-xs text-slate-400">{label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

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
              <h2 className="text-xl font-bold text-white mb-2">No Graph Data</h2>
              <p className="text-sm max-w-md text-center">There are no records in the Graph Database to visualize. Please ingest data first.</p>
            </div>
          ) : (
            <>
              <NetworkGraph nodes={filteredNodes} edges={edges} onNodeSelect={setSelectedNode} selectedNodeId={selectedNode?.node_id} />
              <div className="absolute bottom-4 left-4 bg-slate-900/90 backdrop-blur border border-slate-700/50 rounded-lg p-2">
                <p className="text-xs text-slate-400">Click nodes to explore • Drag to rearrange • Scroll to zoom</p>
              </div>
            </>
          )}
        </div>

        {/* Right Panel */}
        <div className="w-80 bg-slate-900/95 border-l border-slate-700/50 flex flex-col overflow-y-auto custom-scrollbar">
          {/* Node Detail */}
          {selectedNode ? (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-4 border-b border-slate-700/50">
              <div className="flex items-center gap-3 mb-4">
                <div className="h-10 w-10 rounded-xl flex items-center justify-center" style={{ background: NODE_COLORS[selectedNode.node_type] + "30" }}>
                  <NodeIcon className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm font-bold text-white">{selectedNode.label}</p>
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
              <div className="mt-3">
                <p className="text-xs text-slate-400 mb-2">Connected Edges ({edges.filter(e => e.source === selectedNode.node_id || e.target === selectedNode.node_id).length})</p>
                <div className="space-y-1">
                  {edges.filter(e => e.source === selectedNode.node_id || e.target === selectedNode.node_id).map((e, i) => {
                    const otherId = e.source === selectedNode.node_id ? e.target : e.source;
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
              <p className="text-xs text-slate-500">Click a node in the network to view details</p>
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
                <ReactMarkdown
                  components={{
                    strong: ({node, ...props}) => <span className="font-bold text-blue-100" {...props} />,
                    h1: ({node, ...props}) => <h1 className="font-bold text-sm text-white mb-2 mt-4" {...props} />,
                    h2: ({node, ...props}) => <h2 className="font-bold text-sm text-white mb-2 mt-3" {...props} />,
                    h3: ({node, ...props}) => <h3 className="font-semibold text-white mb-1 mt-2" {...props} />,
                    ul: ({node, ...props}) => <ul className="list-disc pl-4 space-y-1 my-2" {...props} />,
                    ol: ({node, ...props}) => <ol className="list-decimal pl-4 space-y-1 my-2" {...props} />,
                    p: ({node, ...props}) => <p className="mb-2 last:mb-0" {...props} />
                  }}
                >
                  {aiSummary.summary}
                </ReactMarkdown>
              </div>

              <h4 className="text-xs font-semibold text-orange-400 mb-2 flex items-center gap-1">
                <AlertTriangle className="h-3 w-3" />Suspicious Associations
              </h4>
              <div className="space-y-2 mb-3">
                {(Array.isArray(aiSummary?.suspicious_associations) ? aiSummary.suspicious_associations : []).map((s, i) => (
                  <div key={i} className="p-2 bg-orange-950/20 border border-orange-500/20 rounded-lg">
                    <div className="flex items-center gap-1 mb-1">
                      <span className={`text-xs font-bold ${s.severity === "Critical" ? "text-red-400" : "text-orange-400"}`}>{s.severity}</span>
                    </div>
                    <p className="text-xs text-slate-300">{s.reason}</p>
                    <div className="flex gap-1 mt-1">
                      {(Array.isArray(s?.entities) ? s.entities : []).map((e) => <span key={e} className="text-xs text-slate-500 font-mono">{e}</span>)}
                    </div>
                  </div>
                ))}
              </div>

              <h4 className="text-xs font-semibold text-green-400 mb-2 flex items-center gap-1">
                <ChevronRight className="h-3 w-3" />Investigation Priorities
              </h4>
              <div className="space-y-1">
                {(Array.isArray(aiSummary?.investigation_priorities) ? aiSummary.investigation_priorities : []).map((p, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-slate-300">
                    <span className="text-green-400 font-bold mt-0.5">{i + 1}.</span>
                    <span>{p}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CriminalNetwork;
