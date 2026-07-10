import React, { useEffect, useState } from "react";
import { Users, Bell, Database, Plus, Save, ActivitySquare, ChevronLeft, ChevronRight } from "lucide-react";
import { settingsService } from "../services/settingsService";
import { useDistricts } from "../hooks/useDistricts";
import LoadingSpinner from "../components/common/LoadingSpinner";
import DataImport from "../components/settings/DataImport";
import { UploadCloud } from "lucide-react";

interface User { user_id: string; username: string; full_name: string; role: string; district?: string; district_id?: string; is_active: boolean; }
interface AlertThresholds { crime_spike_percent: number; anomaly_confidence: number; high_risk_score: number; }

const SettingsPage: React.FC = () => {
  const districts = useDistricts();
  const [activeTab, setActiveTab] = useState("users");
  const [users, setUsers] = useState<User[]>([]);
  const [thresholds, setThresholds] = useState<AlertThresholds | null>(null);
  const [dataSources, setDataSources] = useState<unknown[]>([]);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [usersPage, setUsersPage] = useState(1);
  const [usersTotalCount, setUsersTotalCount] = useState(0);
  const [logsPage, setLogsPage] = useState(1);
  const [logsTotalCount, setLogsTotalCount] = useState(0);
  const pageSize = 20;
  const [loading, setLoading] = useState(true);
  const [saveMsg, setSaveMsg] = useState("");
  const [newUser, setNewUser] = useState({ username: "", full_name: "", role: "INVESTIGATOR", password: "", district: "" });

  useEffect(() => {
    Promise.all([
      settingsService.getUsers(usersPage, pageSize),
      settingsService.getAlertThresholds(),
      settingsService.getDataSources(),
      settingsService.getAuditLogs(logsPage, pageSize),
    ]).then(([u, t, d, logs]: any[]) => {
      setUsers(Array.isArray(u) ? u : (u?.users || u?.data || []));
      setUsersTotalCount(u?.total_count || 0);
      setThresholds(t as unknown as AlertThresholds);
      setDataSources(Array.isArray(d) ? d : (d?.sources || d?.data || []));
      setAuditLogs(Array.isArray(logs) ? logs : (logs?.data || []));
      setLogsTotalCount(logs?.total_count || 0);
      setLoading(false);
    });
  }, [usersPage, logsPage]);

  const handleSaveThresholds = async () => {
    if (!thresholds) return;
    await settingsService.updateAlertThresholds(thresholds as any);
    setSaveMsg("Thresholds saved!");
    setTimeout(() => setSaveMsg(""), 2500);
  };

  const handleAddUser = async () => {
    if (!newUser.username || !newUser.full_name) return;
    const payload = {
      ...newUser,
      district_id: newUser.district || undefined
    };
    const result = await settingsService.addUser(payload as any);
    setUsers((prev) => [...prev, ((result as any).data || (result as any).user) as User]);
    setNewUser({ username: "", full_name: "", role: "INVESTIGATOR", password: "", district: "" });
  };

  if (loading) return <div className="flex-1 flex items-center justify-center"><LoadingSpinner size="lg" text="Loading settings..." /></div>;

  const inputCls = "w-full bg-slate-900 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-2.5 focus:outline-none focus:border-blue-500";

  return (
    <div className="flex-1 min-h-0 w-full overflow-y-auto custom-scrollbar p-6 space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">Platform Settings</h1>
        <p className="text-sm text-slate-400">System configuration and user management</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-slate-700/50 pb-0">
        {[
          { id: "users", label: "User Management", icon: Users },
          { id: "thresholds", label: "Alert Thresholds", icon: Bell },
          { id: "datasources", label: "Data Sources", icon: Database },
          { id: "auditlogs", label: "Activity Log", icon: ActivitySquare },
          { id: "import", label: "Import Data", icon: UploadCloud },
        ].map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => setActiveTab(id)}
            className={`flex items-center gap-2 px-4 py-2 text-sm border-b-2 transition-colors -mb-px ${
              activeTab === id ? "border-blue-500 text-blue-400" : "border-transparent text-slate-400 hover:text-white"
            }`}>
            <Icon className="h-4 w-4" />{label}
          </button>
        ))}
      </div>

      {/* Users Tab */}
      {activeTab === "users" && (
        <div className="space-y-4">
          {/* Add User Form */}
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2"><Plus className="h-4 w-4 text-blue-400" />Add New User</h3>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-3">
              <input placeholder="Username" value={newUser.username} onChange={(e) => setNewUser({ ...newUser, username: e.target.value })} className={inputCls} />
              <input placeholder="Full Name" value={newUser.full_name} onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })} className={inputCls} />
              <select value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })} className={inputCls}>
                {["SCRB_OFFICER", "DISTRICT_OFFICER", "INVESTIGATOR"].map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
              <select value={newUser.district} onChange={(e) => setNewUser({ ...newUser, district: e.target.value })} className={inputCls}>
                <option value="">State-Wide</option>
                {districts.map((d) => <option key={d.district_id} value={d.district_id}>{d.district_name}</option>)}
              </select>
              <input type="password" placeholder="Password" value={newUser.password} onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} className={inputCls} />
            </div>
            <button onClick={handleAddUser} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors">Add User</button>
          </div>
          {/* Users List */}
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl overflow-x-auto custom-scrollbar">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-slate-700/50">
                {["User", "Username", "Role", "District", "Status"].map((h) => (
                  <th key={h} className="text-left py-3 px-4 text-xs text-slate-500">{h}</th>
                ))}
              </tr></thead>
              <tbody>
                {(Array.isArray(users) ? users : []).map((u) => (
                  <tr key={u.user_id} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                    <td className="py-3 px-4 text-white font-medium">{u.full_name || (u as any).user_name}</td>
                    <td className="py-3 px-4 text-slate-400 font-mono text-xs">{u.username || (u as any).email}</td>
                    <td className="py-3 px-4"><span className="text-xs bg-blue-900/40 text-blue-400 px-2 py-0.5 rounded-full">{u.role}</span></td>
                    <td className="py-3 px-4 text-slate-400 text-xs">{u.district_id || "State-Wide"}</td>
                    <td className="py-3 px-4"><span className={`text-xs px-2 py-0.5 rounded-full ${u.is_active || (u as any).status === 'Active' ? "bg-green-900/40 text-green-400" : "bg-slate-700 text-slate-400"}`}>{u.is_active || (u as any).status === 'Active' ? "Active" : "Inactive"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
            
            {/* Users Pagination */}
            <div className="p-4 border-t border-slate-700/50 flex items-center justify-between bg-slate-800/80">
              <span className="text-sm text-slate-400">
                Showing {users.length} records {usersTotalCount > 0 && `of ${usersTotalCount} total`}
              </span>
              <div className="flex items-center gap-2">
                <button 
                  onClick={() => setUsersPage(p => Math.max(1, p - 1))}
                  disabled={usersPage === 1}
                  className="p-1 rounded bg-slate-700 text-white disabled:opacity-50 hover:bg-slate-600 transition-colors"
                >
                  <ChevronLeft className="h-5 w-5" />
                </button>
                <span className="text-sm text-white px-2">Page {usersPage} {usersTotalCount > 0 && `of ${Math.max(1, Math.ceil(usersTotalCount / pageSize))}`}</span>
                <button 
                  onClick={() => setUsersPage(p => p + 1)}
                  disabled={usersPage >= Math.max(1, Math.ceil(usersTotalCount / pageSize))}
                  className="p-1 rounded bg-slate-700 text-white disabled:opacity-50 hover:bg-slate-600 transition-colors"
                >
                  <ChevronRight className="h-5 w-5" />
                </button>
              </div>
            </div>
            
          </div>
        </div>
      )}

      {/* Thresholds Tab */}
      {activeTab === "thresholds" && thresholds && (
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-white mb-4">Alert Trigger Thresholds</h3>
          <div className="space-y-5 max-w-md">
            {Object.entries(thresholds).map(([k, v]) => (
              <div key={k}>
                <label className="block text-xs font-medium text-slate-400 mb-1 capitalize">{k.replace(/_/g, " ")}</label>
                <input type="number" value={v as number}
                  onChange={(e) => setThresholds({ ...thresholds, [k]: Number(e.target.value) })}
                  className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm" />
              </div>
            ))}
            <button onClick={handleSaveThresholds} className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors">
              <Save className="h-4 w-4" /> Save Changes
            </button>
            {saveMsg && <span className="text-xs text-green-400 ml-2">{saveMsg}</span>}
          </div>
        </div>
      )}

      {/* Data Sources Tab */}
      {activeTab === "datasources" && (
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-white mb-4">Connected Data Sources</h3>
          <div className="space-y-3">
            {(Array.isArray(dataSources) ? (dataSources as { name: string; source_name?: string; type: string; status: string; last_sync: string; source_id?: string }[]) : []).map((ds, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-slate-900/60 rounded-lg border border-slate-700/50">
                <div>
                  <p className="text-sm text-white">{ds.name || ds.source_name}</p>
                  <p className="text-xs text-slate-400">{ds.type || 'Database'} · Last sync: {ds.last_sync}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${ds.status === "Active" || ds.status === "Connected" ? "bg-green-900/40 text-green-400" : "bg-red-900/40 text-red-400"}`}>
                    {ds.status}
                  </span>
                  {ds.source_id && !['postgres', 'neo4j', 'redis', 'gemini'].includes(ds.source_id) && (
                    <button
                      onClick={async () => {
                        try {
                          await settingsService.syncDataSource(ds.source_id!);
                          alert(`Successfully synced ${ds.name || ds.source_name}`);
                        } catch (e: any) {
                          alert(`Failed to sync: ${e.message || "Unknown error"}`);
                        }
                      }}
                      className="px-2.5 py-1 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs transition-colors font-medium"
                    >
                      Sync
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Import Tab */}
      {activeTab === "import" && <DataImport />}

      {/* Audit Logs Tab */}
      {activeTab === "auditlogs" && (
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl overflow-x-auto custom-scrollbar">
          <h3 className="text-sm font-semibold text-white m-4">System Activity Log</h3>
          <table className="w-full text-sm">
            <thead><tr className="border-b border-slate-700/50">
              {["Timestamp", "User ID", "Action", "Resource", "Resource ID"].map((h) => (
                <th key={h} className="text-left py-3 px-4 text-xs text-slate-500">{h}</th>
              ))}
            </tr></thead>
            <tbody>
              {auditLogs.map((log) => (
                <tr key={log.log_id} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                  <td className="py-3 px-4 text-slate-400 font-mono text-xs">{new Date(log.timestamp).toLocaleString()}</td>
                  <td className="py-3 px-4 text-slate-300 text-xs">{log.user_id || 'System'}</td>
                  <td className="py-3 px-4"><span className="text-xs bg-purple-900/40 text-purple-400 px-2 py-0.5 rounded-full">{log.action}</span></td>
                  <td className="py-3 px-4 text-white text-xs">{log.resource_type}</td>
                  <td className="py-3 px-4 text-slate-500 font-mono text-xs truncate max-w-[150px]">{log.resource_id}</td>
                </tr>
              ))}
              {auditLogs.length === 0 && (
                <tr>
                  <td colSpan={5} className="py-4 text-center text-slate-500 text-sm">No recent activity.</td>
                </tr>
              )}
            </tbody>
          </table>
          
          {/* Audit Logs Pagination */}
          <div className="p-4 border-t border-slate-700/50 flex items-center justify-between bg-slate-800/80">
            <span className="text-sm text-slate-400">
              Showing {auditLogs.length} records {logsTotalCount > 0 && `of ${logsTotalCount} total`}
            </span>
            <div className="flex items-center gap-2">
              <button 
                onClick={() => setLogsPage(p => Math.max(1, p - 1))}
                disabled={logsPage === 1}
                className="p-1 rounded bg-slate-700 text-white disabled:opacity-50 hover:bg-slate-600 transition-colors"
              >
                <ChevronLeft className="h-5 w-5" />
              </button>
              <span className="text-sm text-white px-2">Page {logsPage} {logsTotalCount > 0 && `of ${Math.max(1, Math.ceil(logsTotalCount / pageSize))}`}</span>
              <button 
                onClick={() => setLogsPage(p => p + 1)}
                disabled={logsPage >= Math.max(1, Math.ceil(logsTotalCount / pageSize))}
                className="p-1 rounded bg-slate-700 text-white disabled:opacity-50 hover:bg-slate-600 transition-colors"
              >
                <ChevronRight className="h-5 w-5" />
              </button>
            </div>
          </div>
          
        </div>
      )}
    </div>
  );
};

export default SettingsPage;
