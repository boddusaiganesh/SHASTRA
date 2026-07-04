import React, { useEffect, useState } from "react";
import { Search, X, Upload } from "lucide-react";
import { crimeService } from "../services/crimeService";
import CrimesTable from "../components/tables/CrimesTable";
import LoadingSpinner from "../components/common/LoadingSpinner";

export default function CrimeDatabase() {
  const [crimes, setCrimes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  
  const [selectedCrime, setSelectedCrime] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);

  const loadCrimes = async () => {
    setLoading(true);
    try {
      const data = await crimeService.getMapData(); 
      // Reuse mapData endpoint as it returns all crimes, or filter endpoint.
      setCrimes(data);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadCrimes();
  }, []);

  const handleStatusChange = async (id: string, status: string) => {
    try {
      await crimeService.updateStatus(id, status);
      await loadCrimes();
    } catch (e) {
      console.error(e);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm("Are you sure you want to delete this crime record?")) return;
    try {
      await crimeService.remove(id);
      await loadCrimes();
    } catch (e) {
      console.error(e);
    }
  };

  const handleOpenAttachments = async (id: string) => {
    setSelectedCrime(id);
    try {
      const data = await crimeService.getEvidence(id);
      setEvidence(data);
    } catch (e) {
      console.error(e);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || !e.target.files.length || !selectedCrime) return;
    setUploading(true);
    try {
      await crimeService.uploadEvidence(selectedCrime, e.target.files[0]);
      const data = await crimeService.getEvidence(selectedCrime);
      setEvidence(data);
    } catch (err) {
      console.error(err);
    }
    setUploading(false);
  };

  const filtered = crimes.filter(c => 
    c.crime_id.toLowerCase().includes(search.toLowerCase()) || 
    c.crime_type.toLowerCase().includes(search.toLowerCase()) ||
    c.district.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">Crime Database</h1>
          <p className="text-sm text-slate-400">Manage, update, and remove crime records.</p>
        </div>
        
        <div className="relative w-72">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search by ID, Type, or District..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:border-blue-500 outline-none"
          />
        </div>
      </div>

      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl overflow-hidden">
        {loading ? (
          <div className="p-8 flex justify-center"><LoadingSpinner /></div>
        ) : (
          <CrimesTable 
            crimes={filtered} 
            compact={false} 
            onStatusChange={handleStatusChange} 
            onDelete={handleDelete} 
            onAttachments={handleOpenAttachments}
          />
        )}
      </div>

      {selectedCrime && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-slate-800 rounded-xl w-full max-w-lg shadow-2xl flex flex-col max-h-full">
            <div className="p-4 border-b border-slate-700 flex justify-between items-center">
              <h2 className="text-lg font-semibold text-white">Attachments (Crime ID: {selectedCrime.substring(0,8)}...)</h2>
              <button onClick={() => setSelectedCrime(null)} className="text-slate-400 hover:text-white"><X className="h-5 w-5" /></button>
            </div>
            <div className="p-4 overflow-y-auto custom-scrollbar flex-1">
              {evidence.length === 0 ? (
                <p className="text-slate-400 text-sm text-center py-4">No attachments found.</p>
              ) : (
                <div className="space-y-3">
                  {evidence.map(ev => (
                    <div key={ev.evidence_id} className="bg-slate-700/50 p-3 rounded-lg flex items-center justify-between text-sm">
                      <div>
                        <a href={`http://localhost:8000${ev.file_url}`} target="_blank" rel="noreferrer" className="text-blue-400 hover:underline break-all">{ev.file_name}</a>
                        <p className="text-xs text-slate-400 mt-1">Uploaded: {new Date(ev.uploaded_at).toLocaleString()}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="p-4 border-t border-slate-700 bg-slate-900/30">
              <label className="flex items-center justify-center gap-2 w-full py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg cursor-pointer transition-colors text-sm font-medium">
                <Upload className="h-4 w-4" />
                {uploading ? "Uploading..." : "Upload File"}
                <input type="file" className="hidden" onChange={handleFileUpload} disabled={uploading} />
              </label>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
