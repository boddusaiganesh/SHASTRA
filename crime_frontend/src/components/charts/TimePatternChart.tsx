import React from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface Props { data: { label: string; crimes: number }[]; title?: string; color?: string }

const TimePatternChart: React.FC<Props> = ({ data, title, color = "#3b82f6" }) => {
  const safeData = Array.isArray(data) ? data : [];
  const max = safeData.length > 0 ? Math.max(...safeData.map((d) => d?.crimes || 0)) : 1;
  return (
    <div>
      {title && <h4 className="text-xs text-slate-400 mb-2">{title}</h4>}
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={safeData} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="label" tick={{ fill: "#64748b", fontSize: 9 }} interval={2} />
          <YAxis tick={{ fill: "#64748b", fontSize: 10 }} />
          <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", color: "#e2e8f0", borderRadius: "8px", fontSize: "12px" }} />
          <Bar dataKey="crimes" radius={[2, 2, 0, 0]}>
            {safeData.map((entry, i) => (
              <Cell key={i} fill={entry.crimes === max ? "#ef4444" : color} opacity={0.7 + ((entry.crimes || 0) / max) * 0.3} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
};

export default TimePatternChart;
