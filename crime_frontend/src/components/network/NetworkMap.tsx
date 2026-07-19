import React, { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap, Polyline } from "react-leaflet";
import { karnatakaCenter } from "../../utils/mapHelpers";
import { NODE_COLORS } from "../../constants/colorCodes";

interface NetworkNode {
  node_id: string; node_type: string; label: string; risk_score: number; crime_count: number; profile_data: Record<string, any>;
}
interface NetworkEdge {
  source?: string; target?: string; source_node_id?: string; target_node_id?: string; relationship_type: string; strength_score: number;
}
interface Props {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  onNodeSelect?: (node: NetworkNode) => void;
  selectedNodeId?: string | null;
  watchedNodeIds?: Set<string>;
  isFallbackMode?: boolean;
}

const FitBounds = () => {
  const map = useMap();
  useEffect(() => { map.setView(karnatakaCenter, 7); }, [map]);
  return null;
};

const InvalidateOnResize = () => {
  const map = useMap();
  useEffect(() => {
    const container = map.getContainer();
    const ro = new ResizeObserver(() => { map.invalidateSize(); });
    ro.observe(container);
    return () => ro.disconnect();
  }, [map]);
  return null;
};

const NetworkMap: React.FC<Props> = ({ nodes, edges, onNodeSelect, selectedNodeId, watchedNodeIds, isFallbackMode }) => {
  // Find nodes with lat/lng in their profile_data
  const mappableNodes = useMemo(() => {
    return nodes.filter(n => n.profile_data && n.profile_data.latitude && n.profile_data.longitude);
  }, [nodes]);

  // Find edges where BOTH source and target have lat/lng
  const mappableEdges = useMemo(() => {
    return edges.map(e => {
      const srcId = e.source || e.source_node_id;
      const tgtId = e.target || e.target_node_id;
      const srcNode = mappableNodes.find(n => n.node_id === srcId);
      const tgtNode = mappableNodes.find(n => n.node_id === tgtId);
      if (srcNode && tgtNode) {
        return {
          edge: e,
          positions: [
            [Number(srcNode.profile_data.latitude), Number(srcNode.profile_data.longitude)] as [number, number],
            [Number(tgtNode.profile_data.latitude), Number(tgtNode.profile_data.longitude)] as [number, number]
          ]
        };
      }
      return null;
    }).filter(Boolean) as { edge: NetworkEdge, positions: [number, number][] }[];
  }, [edges, mappableNodes]);

  return (
    <div className="w-full h-full relative" style={{ background: "#0f172a" }}>
      {mappableNodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center z-[400] bg-slate-900/80 backdrop-blur-sm">
          <div className="text-center">
            <p className="text-slate-400 mb-2">No geo-tagged nodes in the current network.</p>
            <p className="text-xs text-slate-500">Only nodes with latitude/longitude coordinates can be mapped.</p>
          </div>
        </div>
      )}
      
      {isFallbackMode && (
        <div className="absolute top-4 left-1/2 transform -translate-x-1/2 z-[500] bg-amber-500/10 border border-amber-500/50 text-amber-500 px-4 py-2 rounded-md shadow-lg flex items-center gap-2 backdrop-blur-md">
          <svg className="w-5 h-5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <div>
            <p className="text-sm font-medium">Degraded Graph Mode</p>
            <p className="text-xs opacity-80">Geospatial accuracy may be reduced. Showing PostgreSQL fallback data.</p>
          </div>
        </div>
      )}
      
      <MapContainer
        center={karnatakaCenter}
        zoom={7}
        className="h-full w-full"
        style={{ background: "#0f172a" }}
        preferCanvas={true}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
          className="map-tiles grayscale"
        />
        <FitBounds />
        <InvalidateOnResize />

        {mappableEdges.map((e, i) => (
          <Polyline
            key={i}
            positions={e.positions}
            color="#475569"
            weight={1 + (e.edge.strength_score || 50) / 40}
            opacity={0.4}
            dashArray={e.edge.relationship_type.includes("SUSPECTED") ? "5, 5" : undefined}
          />
        ))}

        {mappableNodes.map((node) => {
          const lat = Number(node.profile_data.latitude);
          const lng = Number(node.profile_data.longitude);
          const isSelected = selectedNodeId === node.node_id;
          const isWatched = watchedNodeIds?.has(node.node_id);
          const color = (NODE_COLORS as any)[node.node_type] || "#94a3b8";

          return (
            <CircleMarker
              key={node.node_id}
              center={[lat, lng]}
              radius={isSelected ? 10 : isWatched ? 8 : 6}
              fillColor={color}
              color={isSelected ? "#3b82f6" : isWatched ? "#eab308" : "#1e293b"}
              weight={isSelected || isWatched ? 3 : 1}
              opacity={1}
              fillOpacity={isSelected ? 1 : 0.8}
              eventHandlers={{
                click: () => onNodeSelect?.(node),
              }}
            >
              <Popup className="custom-popup">
                <div className="p-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs px-2 py-0.5 rounded-full capitalize" style={{ backgroundColor: color + "40", color: color }}>
                      {node.node_type}
                    </span>
                    {isWatched && <span className="text-[10px] bg-yellow-900/40 text-yellow-400 px-1.5 rounded">Watched</span>}
                  </div>
                  <h3 className="font-bold text-sm text-slate-800">{node.label}</h3>
                  {node.crime_count > 0 && <p className="text-xs text-slate-600 mt-1">Crimes: {node.crime_count}</p>}
                </div>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
    </div>
  );
};

export default NetworkMap;
