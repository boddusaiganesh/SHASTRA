import React from "react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine } from "recharts";

interface Props { data: { day: number; date: string; predicted: number; upper_bound: number; lower_bound: number; historical: number | null }[] }

const ForecastChart: React.FC<Props> = ({ data }) => {
  const safeData = Array.isArray(data) ? data : [];
  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={safeData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
        <defs>
          <linearGradient id="predGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="boundsGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#6366f1" stopOpacity={0.15} />
            <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="date" tick={{ fill: "#64748b", fontSize: 9 }} interval={4} />
        <YAxis tick={{ fill: "#64748b", fontSize: 10 }} />
        <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", color: "#e2e8f0", borderRadius: "8px", fontSize: "12px" }} />
        <ReferenceLine x={safeData[9]?.date} stroke="#f59e0b" strokeDasharray="5 5" label={{ value: "Today", fill: "#f59e0b", fontSize: 10 }} />
        <Area type="monotone" dataKey="upper_bound" stroke="#6366f1" strokeWidth={0} fill="url(#boundsGrad)" name="Upper Bound" />
        <Area type="monotone" dataKey="lower_bound" stroke="#6366f1" strokeWidth={0} fill="#0f172a" name="Lower Bound" />
        <Area type="monotone" dataKey="predicted" stroke="#3b82f6" strokeWidth={2} fill="url(#predGrad)" name="Predicted Crimes" dot={false} />
        <Area type="monotone" dataKey="historical" stroke="#22c55e" strokeWidth={2} fill="none" name="Historical" dot={false} connectNulls={false} />
        <Legend wrapperStyle={{ fontSize: "11px" }} />
      </AreaChart>
    </ResponsiveContainer>
  );
};

export default ForecastChart;
