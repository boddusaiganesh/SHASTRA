import React from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

interface Props { data: { month: string; crimes: number; solved: number }[] }

const CrimeTrendChart: React.FC<Props> = ({ data }) => (
  <ResponsiveContainer width="100%" height={220}>
    <LineChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
      <XAxis dataKey="month" tick={{ fill: "#94a3b8", fontSize: 11 }} />
      <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} />
      <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #334155", color: "#e2e8f0", borderRadius: "8px" }} />
      <Legend wrapperStyle={{ fontSize: "12px" }} />
      <Line type="monotone" dataKey="crimes" stroke="#ef4444" strokeWidth={2} dot={{ fill: "#ef4444", r: 3 }} name="Total Crimes" />
      <Line type="monotone" dataKey="solved" stroke="#22c55e" strokeWidth={2} dot={{ fill: "#22c55e", r: 3 }} name="Solved" />
    </LineChart>
  </ResponsiveContainer>
);

export default CrimeTrendChart;
