import React from "react";
import { formatDateTime } from "../../utils/dateFormatter";
import { CRIME_TYPE_COLORS } from "../../constants/crimeTypes";

interface Crime {
  crime_id: string; crime_type: string; date_time: string; location: string;
  district: string; status: string;
}

interface Props { crimes: Crime[]; compact?: boolean }

const statusColor: Record<string, string> = {
  "Under Investigation": "bg-yellow-900/40 text-yellow-400",
  "FIR Filed": "bg-blue-900/40 text-blue-400",
  "Arrested": "bg-green-900/40 text-green-400",
  "Solved": "bg-green-900/60 text-green-300",
  "Active Search": "bg-red-900/40 text-red-400",
};

const CrimesTable: React.FC<Props> = ({ crimes, compact }) => (
  <div className="overflow-x-auto">
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-slate-700/50">
          <th className="text-left py-2 px-3 text-xs text-slate-500 font-medium">Crime ID</th>
          <th className="text-left py-2 px-3 text-xs text-slate-500 font-medium">Type</th>
          {!compact && <th className="text-left py-2 px-3 text-xs text-slate-500 font-medium">Location</th>}
          <th className="text-left py-2 px-3 text-xs text-slate-500 font-medium">District</th>
          <th className="text-left py-2 px-3 text-xs text-slate-500 font-medium">Date/Time</th>
          <th className="text-left py-2 px-3 text-xs text-slate-500 font-medium">Status</th>
        </tr>
      </thead>
      <tbody>
        {crimes.map((c) => (
          <tr key={c.crime_id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
            <td className="py-2 px-3 text-xs text-blue-400 font-mono">{c.crime_id}</td>
            <td className="py-2 px-3">
              <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                style={{ background: (CRIME_TYPE_COLORS[c.crime_type] || "#6366f1") + "30", color: CRIME_TYPE_COLORS[c.crime_type] || "#818cf8" }}>
                {c.crime_type}
              </span>
            </td>
            {!compact && <td className="py-2 px-3 text-xs text-slate-300">{c.location}</td>}
            <td className="py-2 px-3 text-xs text-slate-400">{c.district}</td>
            <td className="py-2 px-3 text-xs text-slate-400">{formatDateTime(c.date_time)}</td>
            <td className="py-2 px-3">
              <span className={`text-xs px-2 py-0.5 rounded-full ${statusColor[c.status] || "bg-slate-700 text-slate-400"}`}>{c.status}</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

export default CrimesTable;
