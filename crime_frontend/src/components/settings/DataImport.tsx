import React, { useState } from 'react';
import { UploadCloud, FileText, AlertCircle, CheckCircle } from 'lucide-react';
import api from '../../services/api';
import { ENDPOINTS } from '../../constants/apiEndpoints';

export default function DataImport() {
  const [file, setFile] = useState<File | null>(null);
  const [modelType, setModelType] = useState('crimes');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please select a file first.");
      return;
    }
    
    setLoading(true);
    setError(null);
    setResult(null);
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('model_type', modelType);
    
    try {
      const response = await api.post(ENDPOINTS.IMPORT.BULK, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      setResult(response.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || "An error occurred during upload.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-6">
      <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
        <UploadCloud className="h-5 w-5 text-blue-400" />
        Bulk Data Import
      </h3>
      <p className="text-sm text-slate-400 mb-6">Upload CSV or JSON files to bulk import data into the system. Supported types are Crimes, Offenders, and Victims.</p>
      
      <div className="space-y-6 max-w-xl">
        <div>
          <label className="block text-xs font-medium text-slate-400 mb-2 uppercase tracking-wider">Target Data Model</label>
          <select 
            className="w-full bg-slate-900 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-2.5 focus:outline-none focus:border-blue-500"
            value={modelType}
            onChange={(e) => setModelType(e.target.value)}
          >
            <option value="crimes">Crimes Data</option>
            <option value="offenders">Offenders Data</option>
            <option value="victims">Victims Data</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-slate-400 mb-2 uppercase tracking-wider">Select File (.csv, .json)</label>
          <div className="flex items-center gap-4">
            <label className="flex-1 cursor-pointer flex items-center justify-center gap-2 bg-slate-900 border border-dashed border-slate-600 hover:border-blue-500 rounded-lg px-4 py-8 transition-colors">
              <FileText className="h-6 w-6 text-slate-500" />
              <span className="text-sm text-slate-300 font-medium">
                {file ? file.name : "Click to select a file"}
              </span>
              <input type="file" accept=".csv,.json" className="hidden" onChange={handleFileChange} />
            </label>
          </div>
        </div>

        <button 
          onClick={handleUpload} 
          disabled={loading || !file}
          className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          {loading ? "Importing Data..." : (
            <>
              <UploadCloud className="h-4 w-4" />
              Start Bulk Import
            </>
          )}
        </button>

        {error && (
          <div className="bg-red-900/20 border border-red-500/30 rounded-lg p-4 flex items-start gap-3 text-red-400 text-sm">
            <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
            <p>{error}</p>
          </div>
        )}

        {result && (
          <div className="bg-green-900/20 border border-green-500/30 rounded-lg p-4 space-y-3">
            <div className="flex items-center gap-2 text-green-400 font-medium mb-2">
              <CheckCircle className="h-5 w-5" />
              Import Completed
            </div>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div className="bg-slate-900/50 rounded p-2 text-center">
                <p className="text-slate-400 text-xs">Total Records</p>
                <p className="text-white font-mono text-lg">{result.total}</p>
              </div>
              <div className="bg-slate-900/50 rounded p-2 text-center">
                <p className="text-slate-400 text-xs">Successfully Imported</p>
                <p className="text-green-400 font-mono text-lg">{result.successful}</p>
              </div>
              <div className="bg-slate-900/50 rounded p-2 text-center">
                <p className="text-slate-400 text-xs">Failed / Skipped</p>
                <p className="text-red-400 font-mono text-lg">{result.failed}</p>
              </div>
            </div>
            {result.errors && result.errors.length > 0 && (
              <div className="mt-4">
                <p className="text-xs text-red-400 font-medium mb-1">Error Details (First 50)</p>
                <ul className="text-xs text-slate-400 max-h-32 overflow-y-auto custom-scrollbar space-y-1 bg-slate-900/80 p-2 rounded">
                  {result.errors.map((e: any, idx: number) => (
                    <li key={idx}>Row {e.row}: {e.error}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
