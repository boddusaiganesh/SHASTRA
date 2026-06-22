import React from "react";
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { CHART_COLORS } from "../../constants/colorCodes";

interface Props { data: { type: string; count: number; percentage: number }[] }

const CrimeTypeChart: React.FC<Props> = ({ data }) => (
  <ResponsiveContainer width="100%" height={220}>
    <PieChart>
      <Pie data={data} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={3} dataKey="count" nameKey="type">
        {data.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
      </Pie>
      <Tooltip
        contentStyle={{ background: "#0f172a", border: "1px solid #334155", color: "#e2e8f0", borderRadius: "8px" }}
        formatter={(value, name) => [`${value} cases`, name]}
      />
      <Legend wrapperStyle={{ fontSize: "11px" }} formatter={(val) => <span style={{ color: "#94a3b8" }}>{val}</span>} />
    </PieChart>
  </ResponsiveContainer>
);

export default CrimeTypeChart;
