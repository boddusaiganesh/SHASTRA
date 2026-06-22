import React, { useEffect, useState } from "react";
import { Users, Bell, Database, Plus, Save } from "lucide-react";
import { settingsService } from "../services/alertService";
import LoadingSpinner from "../components/common/LoadingSpinner";

interface User { user_id: string; username: string; full_name: string; role: string; district?: string; is_active: boolean; }
interface AlertThresholds { crime_spike_percent: number; anomaly_confidence: number; high_risk_score: number; }

const SettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState("users");
  const [users, setUsers] = useState<User[]>([]);
  const [thresholds, setThresholds] = useState<AlertThresholds | null>(null);
  const [dataSources, setDataSources] = useState<unknown[]>([]);
  const [loading, setLoading] = useState(true);
  const [saveMsg, setSaveMsg] = useState("");
  const [newUser, setNewUser] = useState({ username: "", full_name: "", role: "INVESTIGATOR", password: "" });

  useEffect(() => {
    Promise.all([
      settingsService.getUsers(),
      settingsService.getAlertThresholds(),
      settingsService.getDataSources(),
    ]).then(([u, t, d]) => {
      setUsers(u as unknown as User[]);
      setThresholds(t as unknown as AlertThresholds);
      setDataSources(d as unknown[]);
      setLoading(false);
    });
  }, []);

  const handleSaveThresholds = async () => {
    if (!thresholds) return;
    await settingsService.updateAlertThresholds(thresholds as any);
    setSaveMsg("Thresholds saved!");
    setTimeout(() => setSaveMsg(""), 2500);
  };

  const handleAddUser = async () => {
    if (!newUser.username || !newUser.full_name) return;
    const result = await settingsService.addUser(newUser);
    setUsers((prev) => [...prev, result.user as unknown as User]);
    setNewUser({ username: "", full_name: "", role: "INVESTIGATOR", password: "" });
  };

  if (loading) return <div className="flex-1 flex items-center justify-center"><LoadingSpinner size="lg" text="Loading settings..." /></div>;

  const inputCls = "w-full bg-slate-900 border border-slate-600 text-slate-200 text-sm rounded-lg px-3 py-2.5 focus:outline-none focus:border-blue-500";

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6">
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
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
              <input placeholder="Username" value={newUser.username} onChange={(e) => setNewUser({ ...newUser, username: e.target.value })} className={inputCls} />
              <input placeholder="Full Name" value={newUser.full_name} onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })} className={inputCls} />
              <select value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })} className={inputCls}>
                {["SCRB_OFFICER", "DISTRICT_OFFICER", "INVESTIGATOR"].map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
              <input type="password" placeholder="Password" value={newUser.password} onChange={(e) => setNewUser({ ...newUser, password: e.target.value })} className={inputCls} />
            </div>
            <button onClick={handleAddUser} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors">Add User</button>
          </div>
          {/* Users List */}
          <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead><tr className="border-b border-slate-700/50">
                {["User", "Username", "Role", "District", "Status"].map((h) => (
                  <th key={h} className="text-left py-3 px-4 text-xs text-slate-500">{h}</th>
                ))}
              </tr></thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.user_id} className="border-b border-slate-800/50 hover:bg-slate-800/30">
                    <td className="py-3 px-4 text-white font-medium">{u.full_name || (u as any).user_name}</td>
                    <td className="py-3 px-4 text-slate-400 font-mono text-xs">{u.username || (u as any).email}</td>
                    <td className="py-3 px-4"><span className="text-xs bg-blue-900/40 text-blue-400 px-2 py-0.5 rounded-full">{u.role}</span></td>
                    <td className="py-3 px-4 text-slate-400 text-xs">{u.district || "State-Wide"}</td>
                    <td className="py-3 px-4"><span className={`text-xs px-2 py-0.5 rounded-full ${u.is_active || (u as any).status === 'Active' ? "bg-green-900/40 text-green-400" : "bg-slate-700 text-slate-400"}`}>{u.is_active || (u as any).status === 'Active' ? "Active" : "Inactive"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Thresholds Tab */}
      {activeTab === "thresholds" && thresholds && (
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-5">
          <h3 className="text-sm font-semibold text-white mb-4">Alert Trigger Thresholds</h3>
          <div className="space-y-5 max-w-md">
            {[
              { key: "crime_spike_percent", label: "Crime Spike Alert (%)", min: 10, max: 500 },
              { key: "anomaly_confidence", label: "Anomaly Confidence Threshold (%)", min: 50, max: 99 },
              { key: "high_risk_score", label: "High Risk Score Threshold", min: 50, max: 100 },
            ].map(({ key, label, min, max }) => (
              <div key={key}>
                <div className="flex justify-between text-xs mb-2">
                  <span className="text-slate-300">{label}</span>
                  <span className="text-blue-400 font-bold">{thresholds[key as keyof AlertThresholds] || 0}</span>
                </div>
                <input type="range" min={min} max={max}
                  value={thresholds[key as keyof AlertThresholds] || 0}
                  onChange={(e) => setThresholds({ ...thresholds, [key]: Number(e.target.value) })}
                  className="w-full accent-blue-500"
                />
              </div>
            ))}
            <button onClick={handleSaveThresholds}
              className="flex items-center gap-2 px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors">
              <Save className="h-4 w-4" /> Save Thresholds
            </button>
            {saveMsg && <p className="text-xs text-green-400">{saveMsg}</p>}
          </div>
        </div>
      )}

      {/* Data Sources Tab */}
      {activeTab === "datasources" && (
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-4">
          <h3 className="text-sm font-semibold text-white mb-4">Connected Data Sources</h3>
          <div className="space-y-3">
            {(dataSources as { name: string; source_name?: string; type: string; status: string; last_sync: string }[]).map((ds, i) => (
              <div key={i} className="flex items-center justify-between p-3 bg-slate-900/60 rounded-lg border border-slate-700/50">
                <div>
                  <p className="text-sm text-white">{ds.name || ds.source_name}</p>
                  <p className="text-xs text-slate-400">{ds.type || 'Database'} · Last sync: {ds.last_sync}</p>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full ${ds.status === "Active" || ds.status === "Connected" ? "bg-green-900/40 text-green-400" : "bg-red-900/40 text-red-400"}`}>
                  {ds.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default SettingsPage;
