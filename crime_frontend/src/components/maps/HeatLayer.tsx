import { useEffect } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet.heat";

interface Props {
  points: [number, number, number?][]; // [lat, lng, intensity?]
}

const HeatLayer: React.FC<Props> = ({ points }) => {
  const map = useMap();

  useEffect(() => {
    // @ts-ignore - leaflet.heat augments L at runtime
    const heat = L.heatLayer(points, {
      radius: 22,
      blur: 18,
      maxZoom: 12,
      gradient: { 0.2: "#3b82f6", 0.4: "#22c55e", 0.6: "#f59e0b", 0.8: "#ef4444", 1.0: "#991b1b" },
    }).addTo(map);

    return () => { map.removeLayer(heat); };
  }, [map, points]);

  return null;
};

export default HeatLayer;
