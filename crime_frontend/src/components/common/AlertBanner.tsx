import React from "react";
import { AlertTriangle, X } from "lucide-react";

interface Props { count: number; critical: number; onDismiss?: () => void; }

const AlertBanner: React.FC<Props> = ({ count, critical, onDismiss }) => {
  if (count === 0) return null;
  return (
    <div className="flex items-center justify-between bg-red-900/80 border border-red-500 px-4 py-2 rounded-lg text-sm">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-red-400 animate-pulse" />
        <span className="text-red-200">
          <strong className="text-red-400">{count} active alerts</strong>
          {critical > 0 && <> — <strong className="text-red-300">{critical} CRITICAL</strong> require immediate attention</>}
        </span>
      </div>
      {onDismiss && <button onClick={onDismiss}><X className="h-4 w-4 text-red-400" /></button>}
    </div>
  );
};

export default AlertBanner;
