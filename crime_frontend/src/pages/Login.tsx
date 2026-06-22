import React, { useState } from "react";
import { useDispatch } from "react-redux";
import { useNavigate } from "react-router-dom";
import { Shield, Eye, EyeOff, Lock, User, ChevronDown, AlertCircle } from "lucide-react";
import { motion } from "framer-motion";
import { loginSuccess } from "../store/authSlice";
import { authService } from "../services/authService";
import { USER_ROLES } from "../constants/crimeTypes";

const Login: React.FC = () => {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState(USER_ROLES[0]);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await authService.login({ username, password, role });
      dispatch(loginSuccess(result as Parameters<typeof loginSuccess>[0]));
      navigate("/dashboard");
    } catch {
      setError("Invalid credentials. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const inputClass = "w-full bg-slate-800/60 border border-slate-600 text-white rounded-xl px-4 py-3 pl-11 text-sm focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50 placeholder-slate-500 transition-all";

  return (
    <div className="min-h-screen bg-[#020817] flex items-center justify-center relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-indigo-600/10 rounded-full blur-3xl" />
        <div className="absolute inset-0" style={{
          backgroundImage: "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.03) 1px, transparent 0)",
          backgroundSize: "40px 40px",
        }} />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="relative w-full max-w-md mx-4"
      >
        {/* Card */}
        <div className="bg-slate-900/80 backdrop-blur-xl border border-slate-700/50 rounded-2xl p-8 shadow-2xl">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 mb-4 shadow-lg shadow-blue-500/30">
              <Shield className="h-8 w-8 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Karnataka State Police</h1>
            <p className="text-blue-400 text-sm font-semibold tracking-wide mt-1">SHASTRA Platform</p>
            <p className="text-slate-500 text-xs mt-1">Authorized Personnel Only — Secure Access</p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Username */}
            <div className="relative">
              <User className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
              <input
                type="text"
                placeholder="Officer ID / Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className={inputClass}
                required
              />
            </div>

            {/* Password */}
            <div className="relative">
              <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
              <input
                type={showPassword ? "text" : "password"}
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputClass}
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>

            {/* Role Selector */}
            <div className="relative">
              <div className="absolute left-3.5 top-1/2 -translate-y-1/2">
                <Shield className="h-4 w-4 text-slate-500" />
              </div>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as typeof role)}
                className={`${inputClass} appearance-none cursor-pointer`}
              >
                {USER_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
              <ChevronDown className="absolute right-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 pointer-events-none" />
            </div>

            {/* Error */}
            {error && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-2 p-3 bg-red-900/30 border border-red-500/30 rounded-lg">
                <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0" />
                <p className="text-xs text-red-400">{error}</p>
              </motion.div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-semibold rounded-xl transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg shadow-blue-600/30"
            >
              {loading ? (
                <>
                  <div className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                  Authenticating...
                </>
              ) : "Login to Platform"}
            </button>
          </form>

          {/* Forgot Password */}
          <div className="text-center mt-4">
            <button className="text-xs text-slate-500 hover:text-blue-400 transition-colors">
              Forgot password? Contact SCRB Administrator
            </button>
          </div>

          {/* Demo hint */}
          <div className="mt-6 p-3 bg-blue-950/40 border border-blue-500/20 rounded-lg">
            <p className="text-xs text-blue-400 text-center">
              <span className="font-semibold">Demo Access:</span> Any username & password will work
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-8 text-center">
          <p className="text-xs text-slate-500 font-medium">
          © 2024 Karnataka State Police · SHASTRA Intelligence Platform v1.0
          </p>
        </div>
      </motion.div>
    </div>
  );
};

export default Login;
