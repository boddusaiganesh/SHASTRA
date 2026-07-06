import React, { useEffect } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import MarkerClusterGroup from 'react-leaflet-cluster';
import HeatLayer from "./HeatLayer";
import { CRIME_TYPE_COLORS } from "../../constants/crimeTypes";
import { karnatakaCenter } from "../../utils/mapHelpers";
import { formatDateTime } from "../../utils/dateFormatter";

interface Crime {
  crime_id: string; crime_type: string; date_time: string; location: string;
  district: string; police_station?: string; status: string; latitude: number; longitude: number;
  victim_id?: string; suspect_id?: string;
}

interface Props {
  crimes: Crime[];
  viewMode: "heatmap" | "cluster" | "pins";
  onCrimeSelect?: (crime: Crime) => void;
}

const FitBounds = () => {
  const map = useMap();
  useEffect(() => { map.setView(karnatakaCenter, 7); }, [map]);
  return null;
};

const CrimeMap: React.FC<Props> = ({ crimes, viewMode, onCrimeSelect }) => {
  const getRadius = () => viewMode === "heatmap" ? 20 : 7;
  const getOpacity = () => viewMode === "heatmap" ? 0.35 : 0.85;

  return (
    <MapContainer
      center={karnatakaCenter}
      zoom={7}
      className="h-full w-full"
      style={{ background: "#0f172a" }}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; OpenStreetMap contributors'
        className="map-tiles"
      />
      <FitBounds />
      {viewMode === "heatmap" ? (
        <HeatLayer points={crimes.map((c) => [c.latitude, c.longitude, 0.6])} />
      ) : viewMode === "cluster" ? (
        <MarkerClusterGroup>
          {crimes.map((crime) => (
            <CircleMarker
              key={crime.crime_id}
              center={[crime.latitude, crime.longitude]}
              radius={getRadius()}
              fillColor={CRIME_TYPE_COLORS[crime.crime_type] || "#6366f1"}
              color={CRIME_TYPE_COLORS[crime.crime_type] || "#6366f1"}
              weight={0}
              fillOpacity={getOpacity()}
              opacity={getOpacity()}
              className={crime.status === "REPORTED" || crime.status === "UNDER_INVESTIGATION" ? "red-zone-pulse" : ""}
              eventHandlers={{ click: () => onCrimeSelect?.(crime) }}
            >
              <Popup className="crime-popup">
                <div className="bg-slate-900 text-white rounded-lg p-3 min-w-[200px]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-blue-400">{crime.crime_id}</span>
                    <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: CRIME_TYPE_COLORS[crime.crime_type] + "40", color: CRIME_TYPE_COLORS[crime.crime_type] }}>
                      {crime.crime_type}
                    </span>
                  </div>
                  <p className="text-sm font-semibold mb-1">{crime.location}</p>
                  <p className="text-xs text-slate-400 mb-1">{crime.district} — {crime.police_station}</p>
                  <p className="text-xs text-slate-400 mb-2">{formatDateTime(crime.date_time)}</p>
                  <div className="flex items-center justify-between">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${crime.status === "CLOSED" || crime.status === "SOLVED" || crime.status === "ARCHIVED" ? "bg-green-900/50 text-green-400" : "bg-yellow-900/50 text-yellow-400"}`}>
                      {crime.status}
                    </span>
                    {crime.suspect_id && <span className="text-xs text-slate-500">Suspect: {crime.suspect_id}</span>}
                  </div>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MarkerClusterGroup>
      ) : (
        crimes.map((crime) => (
          <CircleMarker
            key={crime.crime_id}
            center={[crime.latitude, crime.longitude]}
            radius={getRadius()}
            fillColor={CRIME_TYPE_COLORS[crime.crime_type] || "#6366f1"}
            color={CRIME_TYPE_COLORS[crime.crime_type] || "#6366f1"}
            weight={viewMode === "pins" ? 2 : 0}
            fillOpacity={getOpacity()}
            opacity={getOpacity()}
            className={crime.status === "REPORTED" || crime.status === "UNDER_INVESTIGATION" ? "red-zone-pulse" : ""}
            eventHandlers={{ click: () => onCrimeSelect?.(crime) }}
          >
            <Popup className="crime-popup">
              <div className="bg-slate-900 text-white rounded-lg p-3 min-w-[200px]">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-blue-400">{crime.crime_id}</span>
                  <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: CRIME_TYPE_COLORS[crime.crime_type] + "40", color: CRIME_TYPE_COLORS[crime.crime_type] }}>
                    {crime.crime_type}
                  </span>
                </div>
                <p className="text-sm font-semibold mb-1">{crime.location}</p>
                <p className="text-xs text-slate-400 mb-1">{crime.district} — {crime.police_station}</p>
                <p className="text-xs text-slate-400 mb-2">{formatDateTime(crime.date_time)}</p>
                <div className="flex items-center justify-between">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${crime.status === "CLOSED" || crime.status === "SOLVED" || crime.status === "ARCHIVED" ? "bg-green-900/50 text-green-400" : "bg-yellow-900/50 text-yellow-400"}`}>
                    {crime.status}
                  </span>
                  {crime.suspect_id && <span className="text-xs text-slate-500">Suspect: {crime.suspect_id}</span>}
                </div>
              </div>
            </Popup>
          </CircleMarker>
        ))
      )}
    </MapContainer>
  );
};

export default CrimeMap;
