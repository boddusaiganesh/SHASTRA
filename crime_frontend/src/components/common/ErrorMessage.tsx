import React from "react";
import { AlertTriangle } from "lucide-react";

interface Props { message: string; onRetry?: () => void; }

const ErrorMessage: React.FC<Props> = ({ message, onRetry }) => (
  <div className="flex flex-col items-center justify-center gap-3 py-8">
    <AlertTriangle className="h-10 w-10 text-red-400" />
    <p className="text-sm text-red-400">{message}</p>
    {onRetry && (
      <button onClick={onRetry} className="rounded bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700">
        Retry
      </button>
    )}
  </div>
);

export default ErrorMessage;
