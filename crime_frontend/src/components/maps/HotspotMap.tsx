import React, { useEffect } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import { karnatakaCenter } from "../../utils/mapHelpers";

interface Hotspot {
  hotspot_id: string; location: string; district: string; center_latitude: number; center_longitude: number;
  intensity: number; risk_level: string; crime_count: number; most_common_crime: string; trend: string;
}

interface Props { hotspots: Hotspot[] }

const FitBounds = () => {
  const map = useMap();
  useEffect(() => { map.setView(karnatakaCenter, 7); }, [map]);
  return null;
};

const getHotspotColor = (intensity: number) => {
  if (intensity >= 80) return "#991B1B";
  if (intensity >= 60) return "#EF4444";
  if (intensity >= 40) return "#F97316";
  return "#F59E0B";
};

const HotspotMap: React.FC<Props> = ({ hotspots }) => (
  <MapContainer center={karnatakaCenter} zoom={7} className="h-full w-full">
    <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; OpenStreetMap contributors' />
    <FitBounds />
    {hotspots.map((h) => (
      <CircleMarker
        key={h.hotspot_id}
        center={[h.center_latitude, h.center_longitude]}
        radius={10 + h.intensity / 8}
        fillColor={getHotspotColor(h.intensity)}
        color={getHotspotColor(h.intensity)}
        weight={2}
        fillOpacity={0.6}
        opacity={0.9}
      >
        <Popup>
          <div className="bg-slate-900 text-white rounded-lg p-3 min-w-[180px]">
            <p className="font-bold text-sm mb-1">{h.location}</p>
            <p className="text-xs text-slate-400 mb-2">{h.district}</p>
            <div className="space-y-1 text-xs">
              <div className="flex justify-between"><span className="text-slate-400">Intensity</span><span className="text-red-400 font-bold">{h.intensity}%</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Crimes</span><span className="text-white">{h.crime_count}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Top Crime</span><span className="text-orange-400">{h.most_common_crime}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Trend</span>
                <span className={h.trend === "Increasing" ? "text-red-400" : h.trend === "Decreasing" ? "text-green-400" : "text-yellow-400"}>{h.trend}</span>
              </div>
            </div>
          </div>
        </Popup>
      </CircleMarker>
    ))}
  </MapContainer>
);

export default HotspotMap;
