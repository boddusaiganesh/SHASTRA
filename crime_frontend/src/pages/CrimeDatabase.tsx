import React, { useEffect, useState } from "react";
import { Search, X, Upload, AlertTriangle, ChevronLeft, ChevronRight } from "lucide-react";
import { crimeService } from "../services/crimeService";
import CrimesTable from "../components/tables/CrimesTable";
import LoadingSpinner from "../components/common/LoadingSpinner";
import { useDistricts } from "../hooks/useDistricts";
import { CRIME_TYPES } from "../constants/crimeTypes";

export default function CrimeDatabase() {
  const [crimes, setCrimes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const districts = useDistricts();
  
  // Filters
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [district, setDistrict] = useState("All");
  const [crimeType, setCrimeType] = useState("All");
  const [status, setStatus] = useState("All");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [totalCount, setTotalCount] = useState(0);
  
  const [selectedCrime, setSelectedCrime] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<any[]>([]);
  const [uploading, setUploading] = useState(false);
  const [crimeToDelete, setCrimeToDelete] = useState<string | null>(null);

  // Added missing dispatch/navigate variables if needed, though they aren't used for logout here

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 500);
    return () => clearTimeout(timer);
  }, [search]);

  const loadCrimes = async () => {
    setLoading(true);
    try {
      const params: any = { page, page_size: pageSize };
      if (district !== "All") params.district_id = district;
      if (crimeType !== "All") params.crime_type = crimeType;
      if (status !== "All") params.status = status;
      if (debouncedSearch) params.q = debouncedSearch;

      // Use filter endpoint instead of map-data
      const response = await crimeService.filterCrimes(params); 
      // Handling Axios interceptor stripping off total_count: 
      // If the interceptor stripped total_count, it might just be the array. 
      // But we will fix the interceptor in D1. So response will have success, data, total_count.
      if (Array.isArray(response)) {
          setCrimes(response);
          setTotalCount(response.length); // Fallback if no pagination metadata
      } else {
          setCrimes(response.data || []);
          setTotalCount(response.total_count || 0);
      }
      setError(null);
    } catch (e: any) {
      console.error(e);
      setError(e.response?.data?.detail || "Failed to load crime data");
    }
    setLoading(false);
  };

  useEffect(() => {
    loadCrimes();
  }, [page, district, crimeType, status, debouncedSearch]); // Reload on filter or page change

  const handleStatusChange = async (id: string, newStatus: string) => {
    try {
      await crimeService.updateStatus(id, newStatus);
      await loadCrimes();
    } catch (e) {
      console.error(e);
    }
  };

  const handleDelete = async (id: string) => {
    setCrimeToDelete(id);
  };

  const confirmDelete = async () => {
    if (!crimeToDelete) return;
    try {
      await crimeService.remove(crimeToDelete);
      setCrimeToDelete(null);
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

  // Server-side filtering is now used via debouncedSearch
  
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
      <div className="flex flex-col md:flex-row items-start md:items-center justify-between mb-6 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white mb-1">Crime Database</h1>
          <p className="text-sm text-slate-400">Manage, update, and remove crime records.</p>
        </div>
        
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search database..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-48 pl-9 pr-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:border-blue-500 outline-none"
            />
          </div>
          
          <select 
            value={district} 
            onChange={(e) => { setDistrict(e.target.value); setPage(1); }}
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 outline-none"
          >
            <option value="All">All Districts</option>
            {districts.map(d => <option key={d.district_id} value={d.district_id}>{d.district_name}</option>)}
          </select>
          
          <select 
            value={crimeType} 
            onChange={(e) => { setCrimeType(e.target.value); setPage(1); }}
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 outline-none"
          >
            {CRIME_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          
          <select 
            value={status} 
            onChange={(e) => { setStatus(e.target.value); setPage(1); }}
            className="bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:border-blue-500 outline-none"
          >
            <option value="All">All Statuses</option>
            <option value="REPORTED">Reported</option>
            <option value="UNDER_INVESTIGATION">Under Investigation</option>
            <option value="SOLVED">Solved</option>
            <option value="CLOSED">Closed</option>
            <option value="ARCHIVED">Archived</option>
          </select>
        </div>
      </div>

      <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl overflow-hidden flex flex-col">
        {loading ? (
          <div className="p-8 flex justify-center"><LoadingSpinner /></div>
        ) : error ? (
          <div className="p-8 flex flex-col items-center text-red-400 gap-4"><AlertTriangle className="h-12 w-12" /><p>{error}</p></div>
        ) : (
          <>
            <CrimesTable 
              crimes={crimes} 
              compact={false} 
              onStatusChange={handleStatusChange} 
              onDelete={handleDelete} 
              onAttachments={handleOpenAttachments}
            />
            
            {/* Pagination Controls */}
            <div className="p-4 border-t border-slate-700/50 flex items-center justify-between bg-slate-800/80">
              <span className="text-sm text-slate-400">
                Showing {crimes.length} records {totalCount > 0 && `of ${totalCount} total`}
              </span>
              <div className="flex items-center gap-2">
                <button 
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="p-1 rounded bg-slate-700 text-white disabled:opacity-50 hover:bg-slate-600 transition-colors"
                >
                  <ChevronLeft className="h-5 w-5" />
                </button>
                <span className="text-sm text-white px-2">Page {page} {totalCount > 0 && `of ${totalPages}`}</span>
                <button 
                  onClick={() => setPage(p => p + 1)}
                  disabled={page >= totalPages && totalCount > 0}
                  className="p-1 rounded bg-slate-700 text-white disabled:opacity-50 hover:bg-slate-600 transition-colors"
                >
                  <ChevronRight className="h-5 w-5" />
                </button>
              </div>
            </div>
          </>
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
                        <button
                          onClick={async () => {
                            const { downloadAuthenticated } = await import("../utils/buildApiUrl");
                            await downloadAuthenticated(`/evidence/download/${ev.evidence_id}`);
                          }}
                          className="text-blue-400 hover:underline break-all text-left"
                        >
                          {ev.file_name || ev.description || "Attachment"}
                        </button>
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

      {crimeToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-slate-800 rounded-xl w-full max-w-sm shadow-2xl p-6 flex flex-col gap-4 text-center">
            <AlertTriangle className="h-12 w-12 text-red-500 mx-auto" />
            <h2 className="text-lg font-bold text-white">Delete Record?</h2>
            <p className="text-sm text-slate-400">Are you sure you want to permanently delete this crime record? This action cannot be undone.</p>
            <div className="flex justify-center gap-3 mt-2">
              <button onClick={() => setCrimeToDelete(null)} className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors text-sm">Cancel</button>
              <button onClick={confirmDelete} className="px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg transition-colors text-sm">Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
