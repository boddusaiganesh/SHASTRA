import React, { useEffect } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import { karnatakaCenter } from "../../utils/mapHelpers";

interface DistrictRisk {
  district: string; risk_score: number; risk_level: string; latitude: number; longitude: number;
}

interface Props { districts: DistrictRisk[] }

const FitBounds = () => {
  const map = useMap();
  useEffect(() => { map.setView(karnatakaCenter, 7); }, [map]);
  return null;
};

const getRiskColor = (score: number) => {
  if (score >= 75) return "#EF4444";
  if (score >= 60) return "#F97316";
  if (score >= 45) return "#F59E0B";
  return "#22C55E";
};

const RiskMap: React.FC<Props> = ({ districts }) => (
  <MapContainer center={karnatakaCenter} zoom={7} className="h-full w-full">
    <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; OpenStreetMap contributors' />
    <FitBounds />
    {districts.map((d) => (
      <CircleMarker
        key={d.district}
        center={[d.latitude, d.longitude]}
        radius={20}
        fillColor={getRiskColor(d.risk_score)}
        color={getRiskColor(d.risk_score)}
        weight={2}
        fillOpacity={0.5}
        opacity={0.9}
      >
        <Popup>
          <div className="bg-slate-900 text-white rounded-lg p-3">
            <p className="font-bold text-sm">{d.district}</p>
            <p className="text-xs text-slate-400">Risk Score: <span className="font-bold" style={{ color: getRiskColor(d.risk_score) }}>{d.risk_score}</span></p>
            <p className="text-xs text-slate-400">Level: <span className="font-bold" style={{ color: getRiskColor(d.risk_score) }}>{d.risk_level}</span></p>
          </div>
        </Popup>
      </CircleMarker>
    ))}
  </MapContainer>
);

export default RiskMap;
