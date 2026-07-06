import React, { useMemo, useState } from 'react';

// We define interfaces locally to match the ones in CriminalNetwork.tsx
// Note: Usually these would be in a shared types file.
interface NetworkNode {
  node_id: string; node_type: string; label: string; risk_score: number;
  crime_count: number; profile_data: Record<string, unknown>;
  ai_analysis?: string; timeline?: any[];
  centrality?: { betweenness: number; degree: number; pagerank: number };
  community_id?: number;
}

interface NetworkEdge {
  edge_id?: string;
  source_node_id?: string;
  target_node_id?: string;
  source?: string;
  target?: string;
  relationship_type: string;
  strength_score: number;
}

interface MatrixProps {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  onCellClick: (nodeA: string, nodeB: string) => void;
}

const ConnectivityMatrix: React.FC<MatrixProps> = ({ nodes, edges, onCellClick }) => {
  const [sortMode, setSortMode] = useState<'community' | 'degree' | 'risk'>('community');

  // Order nodes based on sort mode
  // Order nodes based on sort mode, cap at 200 to prevent React rendering death
  const MAX_MATRIX_NODES = 200;
  
  const ordered = useMemo(() => {
    const sorted = [...nodes].sort((a, b) => {
      if (sortMode === 'community') {
        const ca = a.community_id ?? 0, cb = b.community_id ?? 0;
        if (ca !== cb) return ca - cb;
        return (b.centrality?.degree ?? 0) - (a.centrality?.degree ?? 0);
      } else if (sortMode === 'degree') {
        return (b.centrality?.degree ?? 0) - (a.centrality?.degree ?? 0);
      } else if (sortMode === 'risk') {
        return (b.risk_score ?? 0) - (a.risk_score ?? 0);
      }
      return 0;
    });
    return sorted.slice(0, MAX_MATRIX_NODES);
  }, [nodes, sortMode]);

  // Build a fast lookup for edges
  const edgeMap = useMemo(() => {
    const m = new Map<string, NetworkEdge>();
    edges.forEach(e => {
      const src = e.source_node_id;
      const tgt = e.target_node_id;
      if (src && tgt) {
        m.set(`${src}_${tgt}`, e);
        m.set(`${tgt}_${src}`, e); // undirected lookup
      }
    });
    return m;
  }, [edges]);

  const cellSize = Math.max(8, Math.min(24, 800 / Math.max(1, ordered.length)));
  const offset = 180; // Space for labels

  return (
    <div className="w-full h-full flex flex-col bg-slate-900 overflow-hidden relative">
      <div className="absolute top-4 left-4 z-10 flex gap-2">
        <span className="text-xs text-slate-400 my-auto">Sort by:</span>
        {(['community', 'degree', 'risk'] as const).map(mode => (
          <button
            key={mode}
            onClick={() => setSortMode(mode)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border ${
              sortMode === mode
                ? "bg-blue-600 border-blue-500 text-white"
                : "bg-slate-800 border-slate-700 text-slate-400 hover:text-white"
            }`}
          >
            {mode.charAt(0).toUpperCase() + mode.slice(1)}
          </button>
        ))}
      </div>

      {nodes.length > MAX_MATRIX_NODES && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 px-4 py-2 bg-yellow-900/80 text-yellow-50 text-xs rounded-full shadow-lg">
          Showing top {MAX_MATRIX_NODES} of {nodes.length} nodes to maintain performance.
        </div>
      )}

      <div className="flex-1 overflow-auto custom-scrollbar p-6 pt-16">
        <svg
          width={ordered.length * cellSize + offset + 20}
          height={ordered.length * cellSize + offset + 20}
        >
          {/* Row labels */}
          {ordered.map((n, i) => (
            <text
              key={`r-${n.node_id}`}
              x={offset - 8}
              y={offset + i * cellSize + cellSize / 1.5}
              fontSize={Math.min(10, cellSize - 1)}
              textAnchor="end"
              fill="#94a3b8"
              className="pointer-events-none select-none"
            >
              {n.label.length > 25 ? n.label.slice(0, 25) + '...' : n.label}
            </text>
          ))}
          
          {/* Column labels (rotated) */}
          {ordered.map((n, i) => (
            <text
              key={`c-${n.node_id}`}
              x={offset + i * cellSize + cellSize / 2}
              y={offset - 8}
              fontSize={Math.min(10, cellSize - 1)}
              textAnchor="start"
              fill="#94a3b8"
              transform={`rotate(-45 ${offset + i * cellSize + cellSize / 2} ${offset - 8})`}
              className="pointer-events-none select-none"
            >
              {n.label.length > 25 ? n.label.slice(0, 25) + '...' : n.label}
            </text>
          ))}

          {/* Matrix cells */}
          {ordered.map((rowNode, i) =>
            ordered.map((colNode, j) => {
              const edge = i !== j ? edgeMap.get(`${rowNode.node_id}_${colNode.node_id}`) : null;
              
              let fill = "#1e293b"; // Default: no connection
              if (i === j) {
                fill = "#334155"; // Diagonal self
              } else if (edge) {
                const strength = edge.strength_score || 50;
                const t = Math.min(1, strength / 100);
                const r = Math.round(30 + t * 195);
                fill = `rgb(${r}, ${Math.round(41 - t * 20)}, ${Math.round(59 - t * 40)})`;
              }

              return (
                <rect
                  key={`${rowNode.node_id}-${colNode.node_id}`}
                  x={offset + j * cellSize}
                  y={offset + i * cellSize}
                  width={cellSize - 1}
                  height={cellSize - 1}
                  fill={fill}
                  rx={2}
                  className={edge ? "cursor-pointer hover:opacity-80 transition-opacity" : "cursor-default"}
                  onClick={() => {
                    if (edge && i !== j) {
                      onCellClick(rowNode.node_id, colNode.node_id);
                    }
                  }}
                >
                  {i !== j && (
                    <title>
                      {edge
                        ? `${rowNode.label} ↔ ${colNode.label}\nConnection: ${edge.relationship_type}\nStrength: ${edge.strength_score}%`
                        : `${rowNode.label} ↔ ${colNode.label}\nNo connection`}
                    </title>
                  )}
                </rect>
              );
            })
          )}
          
          {/* Community boundary lines */}
          {sortMode === 'community' && ordered.map((n, i) => {
            if (i === 0) return null;
            if (n.community_id !== ordered[i - 1].community_id) {
              return (
                <line
                  key={`comm-${i}`}
                  x1={offset}
                  y1={offset + i * cellSize}
                  x2={offset + ordered.length * cellSize}
                  y2={offset + i * cellSize}
                  stroke="#475569"
                  strokeWidth="1.5"
                  strokeDasharray="4,4"
                  opacity="0.5"
                />
              );
            }
            return null;
          })}
          {sortMode === 'community' && ordered.map((n, i) => {
            if (i === 0) return null;
            if (n.community_id !== ordered[i - 1].community_id) {
              return (
                <line
                  key={`comm-v-${i}`}
                  x1={offset + i * cellSize}
                  y1={offset}
                  x2={offset + i * cellSize}
                  y2={offset + ordered.length * cellSize}
                  stroke="#475569"
                  strokeWidth="1.5"
                  strokeDasharray="4,4"
                  opacity="0.5"
                />
              );
            }
            return null;
          })}
        </svg>
      </div>
    </div>
  );
};

export default ConnectivityMatrix;
