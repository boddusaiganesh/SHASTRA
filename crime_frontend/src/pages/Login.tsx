import React, { useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Shield, Lock, User, AlertCircle, Eye, EyeOff, ChevronDown,
} from 'lucide-react';
import { loginStart, loginSuccess, loginFailure } from '../store/authSlice';
import { authService } from '../services/authService';
import { RootState } from '../store/store';

const USER_ROLES = ["SCRB Officer", "District Officer", "Investigator", "Analyst"];

const inputClass =
  "w-full pl-10 pr-4 py-3 bg-slate-900/70 border border-slate-600/50 text-slate-200 " +
  "placeholder-slate-500 rounded-xl focus:outline-none focus:border-blue-500 " +
  "focus:ring-1 focus:ring-blue-500/30 transition-all text-sm";

export default function Login() {
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('Admin@1234');
  const [role, setRole] = useState(USER_ROLES[0]);
  const [showPassword, setShowPassword] = useState(false);
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { isLoading: loading, error } = useSelector((state: RootState) => state.auth);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    dispatch(loginStart());
    try {
      const response = await authService.login({ username, password });
      dispatch(loginSuccess({ ...response, isAuthenticated: true, isLoading: false, error: null }));
      navigate('/');
    } catch (err: unknown) {
      dispatch(loginFailure((err as Error).message || 'Login failed'));
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 relative overflow-hidden">
      <div className="absolute inset-0 z-0">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-blue-900/20 via-slate-900 to-slate-900" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md z-10"
      >
        <div className="bg-slate-800/50 backdrop-blur-xl border border-slate-700/50 rounded-3xl p-8 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 to-indigo-600" />

          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center h-16 w-16 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 mb-4 shadow-lg shadow-blue-500/30">
              <Shield className="h-8 w-8 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight">Karnataka State Police</h1>
            <p className="text-blue-400 text-sm font-semibold tracking-wide mt-1">SHASTRA Platform</p>
            <p className="text-slate-500 text-xs mt-1">Authorized Personnel Only — Secure Access</p>
          </div>

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
              <Shield className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className={`${inputClass} appearance-none cursor-pointer`}
              >
                {USER_ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
              <ChevronDown className="absolute right-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500 pointer-events-none" />
            </div>

            {/* Error */}
            {error && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                className="flex items-center gap-2 p-3 bg-red-900/30 border border-red-500/30 rounded-lg">
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

          <div className="text-center mt-4">
            <button className="text-xs text-slate-500 hover:text-blue-400 transition-colors">
              Forgot password? Contact SCRB Administrator
            </button>
          </div>

          <div className="mt-6 p-3 bg-blue-950/40 border border-blue-500/20 rounded-lg">
            <p className="text-xs text-blue-400 text-center">
              <span className="font-semibold">Demo Access:</span> Any username &amp; password will work
            </p>
          </div>
        </div>

        <div className="mt-8 text-center">
          <p className="text-xs text-slate-500 font-medium">
            © 2024 Karnataka State Police · SHASTRA Intelligence Platform v1.0
          </p>
        </div>
      </motion.div>
    </div>
  );
}
