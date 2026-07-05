import React from "react";
import { Info } from "lucide-react";

interface ExplainabilityPanelProps {
  points?: string[];
  score?: number;
}

const ExplainabilityPanel: React.FC<ExplainabilityPanelProps> = ({ points, score }) => {
  if (!points || points.length === 0) return null;
  return (
    <div className="mt-2 pl-3 border-l-2 border-blue-500/40 space-y-1">
      <div className="flex items-center gap-1 text-xs text-blue-400 font-medium">
        <Info className="h-3 w-3" /> Why this was flagged
        {score !== undefined && <span className="text-slate-500">(confidence: {(score * 100).toFixed(0)}%)</span>}
      </div>
      {points.map((p, i) => (
        <p key={i} className="text-xs text-slate-400">• {p}</p>
      ))}
    </div>
  );
};

export default ExplainabilityPanel;
