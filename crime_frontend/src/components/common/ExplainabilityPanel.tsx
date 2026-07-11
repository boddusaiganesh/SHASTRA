import React from "react";
import { Info } from "lucide-react";

interface ExplainabilityPanelProps {
  points?: string[];
  score?: number;
}

import AIMarkdown from "./AIMarkdown";

const ExplainabilityPanel: React.FC<ExplainabilityPanelProps> = ({ points, score }) => {
  if (!points || points.length === 0) return null;
  return (
    <div className="mt-2 pl-3 border-l-2 border-blue-500/40 space-y-1">
      <div className="flex items-center gap-1 text-xs text-blue-400 font-medium mb-2">
        <Info className="h-3 w-3" /> Why this was flagged
        {score != null && <span className="text-slate-500">(confidence: {(score * 100).toFixed(0)}%)</span>}
      </div>
      {points.map((p, i) => (
        <div key={i} className="flex items-start gap-1.5 text-xs text-slate-400">
          <span className="text-slate-500 mt-0.5">•</span>
          <div className="flex-1">
            <AIMarkdown text={p} />
          </div>
        </div>
      ))}
    </div>
  );
};

export default ExplainabilityPanel;
