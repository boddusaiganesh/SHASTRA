import React from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface Hotspot {
  hotspot_id: string; location: string; district: string; crime_count: number;
  most_common_crime: string; risk_level: string; trend: string; intensity: number;
}

interface Props { hotspots: Hotspot[] }

const riskColors: Record<string, string> = { High: "bg-red-900/40 text-red-400", Medium: "bg-orange-900/40 text-orange-400", Low: "bg-green-900/40 text-green-400" };

const HotspotsTable: React.FC<Props> = ({ hotspots }) => (
  <div className="overflow-x-auto custom-scrollbar">
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-slate-700/50">
          {["Rank", "Location", "District", "Crimes", "Top Crime", "Risk", "Trend", "Intensity"].map((h) => (
            <th key={h} className="text-left py-2 px-3 text-xs text-slate-500 font-medium">{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {hotspots.map((h, i) => (
          <tr key={h.hotspot_id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
            <td className="py-2 px-3 text-xs text-slate-500 font-mono">#{i + 1}</td>
            <td className="py-2 px-3 text-xs text-white font-medium">{h.location}</td>
            <td className="py-2 px-3 text-xs text-slate-400">{h.district}</td>
            <td className="py-2 px-3 text-xs text-red-400 font-bold">{h.crime_count}</td>
            <td className="py-2 px-3 text-xs text-orange-400">{h.most_common_crime}</td>
            <td className="py-2 px-3">
              <span className={`text-xs px-2 py-0.5 rounded-full ${riskColors[h.risk_level] || ""}`}>{h.risk_level}</span>
            </td>
            <td className="py-2 px-3">
              <div className={`flex items-center gap-1 text-xs ${h.trend === "Increasing" ? "text-red-400" : h.trend === "Decreasing" ? "text-green-400" : "text-yellow-400"}`}>
                {h.trend === "Increasing" ? <TrendingUp className="h-3 w-3" /> : h.trend === "Decreasing" ? <TrendingDown className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
                {h.trend}
              </div>
            </td>
            <td className="py-2 px-3">
              <div className="flex items-center gap-2">
                <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                  <div className="h-full rounded-full bg-gradient-to-r from-yellow-500 to-red-500" style={{ width: `${h.intensity}%` }} />
                </div>
                <span className="text-xs text-slate-400">{h.intensity}%</span>
              </div>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

export default HotspotsTable;
