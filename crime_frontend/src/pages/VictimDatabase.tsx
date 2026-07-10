import { useState, useEffect } from 'react';
import { Search, UserPlus, FileText, User, ChevronLeft, ChevronRight } from 'lucide-react';
import { victimService } from '../services/victimService';
import { useSelector } from 'react-redux';
import { RootState } from '../store/store';
import { useDistricts } from '../hooks/useDistricts';

export default function VictimDatabase() {
  const [searchQuery, setSearchQuery] = useState('');
  const [victims, setVictims] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedVictim, setSelectedVictim] = useState<any>(null);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [totalCount, setTotalCount] = useState(0);
  const districts = useDistricts();
  
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [newVictim, setNewVictim] = useState({ first_name: "", last_name: "", age: "", gender: "", phone_number: "", district_id: "" });
  
  const handleRegisterVictim = async () => {
    try {
      await victimService.register(newVictim);
      setShowRegisterModal(false);
      setNewVictim({ first_name: "", last_name: "", age: "", gender: "", phone_number: "", district_id: "" });
      handleSearch();
    } catch (err) {
      console.error(err);
    }
  };
  
  const { user_role } = useSelector((state: RootState) => state.auth);
  const isScrbOrInvestigator = user_role === 'SCRB_OFFICER' || user_role === 'INVESTIGATOR';

  const handleSearch = async () => {
    setLoading(true);
    try {
      const data = await victimService.search(searchQuery, undefined, page, pageSize);
      setVictims(data.victims || data || []);
      setTotalCount(data.total_count || 0);
      setError(null);
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || "Failed to search victims");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    handleSearch();
  }, [page]);

  const viewProfile = async (id: string) => {
    try {
      const profile = await victimService.getProfile(id);
      setSelectedVictim(profile);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="flex h-full space-x-6">
      <div className="flex-1 bg-slate-900 rounded-xl border border-slate-800 p-6 flex flex-col">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <User className="h-6 w-6 text-emerald-500" />
            Victim Database
          </h1>
          {isScrbOrInvestigator && (
            <button onClick={() => setShowRegisterModal(true)} className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg transition-colors">
              <UserPlus className="h-4 w-4" />
              Register Victim
            </button>
          )}
        </div>

        <div className="flex gap-4 mb-6">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
            <input
              type="text"
              placeholder="Search victims by name or phone..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              className="w-full pl-10 pr-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-400 focus:outline-none focus:border-emerald-500"
            />
          </div>
          <button
            onClick={() => { setPage(1); handleSearch(); }}
            className="px-6 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
          >
            Search
          </button>
        </div>

        <div className="flex-1 overflow-auto rounded-lg border border-slate-800">
          <table className="w-full text-left border-collapse">
            <thead className="bg-slate-800 text-slate-300 sticky top-0">
              <tr>
                <th className="p-4 font-medium">Name</th>
                <th className="p-4 font-medium">Age/Gender</th>
                <th className="p-4 font-medium">Phone</th>
                <th className="p-4 font-medium">District</th>
                <th className="p-4 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 text-slate-300">
              {loading ? (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-slate-500">
                    Loading victims...
                  </td>
                </tr>
              ) : error ? (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-red-400">
                    {error}
                  </td>
                </tr>
              ) : victims.length === 0 ? (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-slate-500">
                    No victims found matching your search.
                  </td>
                </tr>
              ) : (
                victims.map((victim) => (
                  <tr key={victim.victim_id} className="hover:bg-slate-800/50 transition-colors">
                    <td className="p-4 font-medium text-slate-200">{victim.full_name}</td>
                    <td className="p-4">{victim.age || 'N/A'} / {victim.gender || 'N/A'}</td>
                    <td className="p-4">{victim.phone_number || 'N/A'}</td>
                    <td className="p-4">{districts.find(d => d.district_id === victim.district_id)?.district_name || victim.district_id}</td>
                    <td className="p-4">
                      <button
                        onClick={() => viewProfile(victim.victim_id)}
                        className="text-emerald-400 hover:text-emerald-300 px-3 py-1 rounded border border-emerald-500/30 hover:border-emerald-400 transition-colors"
                      >
                        View Profile
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          
          {/* Pagination Controls */}
          <div className="p-4 border-t border-slate-800 flex items-center justify-between bg-slate-900 sticky bottom-0">
            <span className="text-sm text-slate-400">
              Showing {victims.length} records {totalCount > 0 && `of ${totalCount} total`}
            </span>
            <div className="flex items-center gap-2">
              <button 
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1 rounded bg-slate-800 text-white disabled:opacity-50 hover:bg-slate-700 transition-colors"
              >
                <ChevronLeft className="h-5 w-5" />
              </button>
              <span className="text-sm text-white px-2">Page {page} {totalCount > 0 && `of ${Math.max(1, Math.ceil(totalCount / pageSize))}`}</span>
              <button 
                onClick={() => setPage(p => p + 1)}
                disabled={page >= Math.max(1, Math.ceil(totalCount / pageSize))}
                className="p-1 rounded bg-slate-800 text-white disabled:opacity-50 hover:bg-slate-700 transition-colors"
              >
                <ChevronRight className="h-5 w-5" />
              </button>
            </div>
          </div>
          
        </div>
      </div>

      {selectedVictim && (
        <div className="w-96 bg-slate-900 rounded-xl border border-slate-800 p-6 overflow-y-auto">
          <div className="flex justify-between items-start mb-6">
            <h2 className="text-xl font-bold text-slate-100">{selectedVictim.full_name}</h2>
            <button
              onClick={() => setSelectedVictim(null)}
              className="text-slate-400 hover:text-white"
            >
              ×
            </button>
          </div>
          
          <div className="space-y-6">
            <div>
              <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-2">Personal Details</h3>
              <div className="bg-slate-800 rounded-lg p-4 space-y-3">
                <div className="flex justify-between">
                  <span className="text-slate-400">Age</span>
                  <span className="text-slate-200">{selectedVictim.age || 'N/A'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Gender</span>
                  <span className="text-slate-200">{selectedVictim.gender || 'N/A'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Phone</span>
                  <span className="text-slate-200">{selectedVictim.phone_number || 'N/A'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Occupation</span>
                  <span className="text-slate-200">{selectedVictim.occupation || 'N/A'}</span>
                </div>
              </div>
            </div>

            {selectedVictim.linked_crimes && selectedVictim.linked_crimes.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-2">Linked Cases</h3>
                <div className="space-y-3">
                  {selectedVictim.linked_crimes.map((crime: any) => (
                    <div key={crime.crime_id} className="bg-slate-800 rounded-lg p-4 border border-slate-700">
                      <div className="flex items-center gap-2 text-slate-200 font-medium mb-1">
                        <FileText className="h-4 w-4 text-emerald-500" />
                        {crime.crime_reference_no}
                      </div>
                      <div className="text-sm text-slate-400 flex justify-between">
                        <span>{crime.crime_type}</span>
                        <span>{new Date(crime.date_of_occurrence).toLocaleDateString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {showRegisterModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl shadow-xl w-full max-w-md space-y-4">
            <h2 className="text-lg font-bold text-white mb-2">Register Victim</h2>
            <div className="grid grid-cols-2 gap-4">
              <input type="text" placeholder="First Name" value={newVictim.first_name} onChange={(e) => setNewVictim({...newVictim, first_name: e.target.value})} className="col-span-1 px-3 py-2 bg-slate-800 text-white rounded border border-slate-700 focus:border-emerald-500 outline-none" />
              <input type="text" placeholder="Last Name" value={newVictim.last_name} onChange={(e) => setNewVictim({...newVictim, last_name: e.target.value})} className="col-span-1 px-3 py-2 bg-slate-800 text-white rounded border border-slate-700 focus:border-emerald-500 outline-none" />
              <input type="number" placeholder="Age" value={newVictim.age} onChange={(e) => setNewVictim({...newVictim, age: e.target.value})} className="col-span-1 px-3 py-2 bg-slate-800 text-white rounded border border-slate-700 focus:border-emerald-500 outline-none" />
              <select value={newVictim.gender} onChange={(e) => setNewVictim({...newVictim, gender: e.target.value})} className="col-span-1 px-3 py-2 bg-slate-800 text-white rounded border border-slate-700 focus:border-emerald-500 outline-none">
                <option value="">Gender...</option>
                <option value="M">Male</option>
                <option value="F">Female</option>
                <option value="O">Other</option>
              </select>
              <input type="text" placeholder="Phone Number" value={newVictim.phone_number} onChange={(e) => setNewVictim({...newVictim, phone_number: e.target.value})} className="col-span-2 px-3 py-2 bg-slate-800 text-white rounded border border-slate-700 focus:border-emerald-500 outline-none" />
              <select value={newVictim.district_id} onChange={(e) => setNewVictim({...newVictim, district_id: e.target.value})} className="col-span-2 px-3 py-2 bg-slate-800 text-white rounded border border-slate-700 focus:border-emerald-500 outline-none">
                <option value="">Select District</option>
                {districts.map(d => <option key={d.district_id} value={d.district_id}>{d.district_name}</option>)}
              </select>
            </div>
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => setShowRegisterModal(false)} className="px-4 py-2 bg-slate-700 text-white rounded hover:bg-slate-600 transition-colors">Cancel</button>
              <button onClick={handleRegisterVictim} className="px-4 py-2 bg-emerald-600 text-white rounded hover:bg-emerald-500 transition-colors">Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
