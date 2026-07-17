import React, { useState } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Shield, Lock, User, Eye, EyeOff, AlertCircle } from "lucide-react";
import { loginStart, loginSuccess, loginFailure } from '../store/authSlice';
import { authService } from '../services/authService';
import { RootState } from '../store/store';



const inputClass =
  "w-full pl-10 pr-4 py-3 bg-slate-900/70 border border-slate-600/50 text-slate-200 " +
  "placeholder-slate-500 rounded-xl focus:outline-none focus:border-blue-500 " +
  "focus:ring-1 focus:ring-blue-500/30 transition-all text-sm";

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showForgotMsg, setShowForgotMsg] = useState(false);
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { isLoading: loading, error } = useSelector((state: RootState) => state.auth);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    dispatch(loginStart());
    try {
      const response = await authService.login({ username, password });
      dispatch(loginSuccess({ ...response, isAuthenticated: true, isLoading: false, error: null }));
      navigate('/dashboard');
    } catch (err: unknown) {
      dispatch(loginFailure((err as Error).message || 'Login failed'));
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 relative overflow-y-auto custom-scrollbar">
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
            <div className="inline-flex items-center justify-center h-20 w-20 rounded-2xl bg-slate-900 border border-indigo-500/30 mb-4 shadow-[0_0_20px_rgba(79,70,229,0.4)] overflow-hidden">
              <img src="/shastra_logo.png" alt="SHASTRA Logo" className="h-full w-full object-cover scale-110" />
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

            <div className="flex items-center gap-2 text-xs text-slate-500">
              <Shield className="h-4 w-4" />
              <span>Your role and permissions are assigned by the SCRB Administrator</span>
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
            <button
              type="button"
              onClick={() => setShowForgotMsg(!showForgotMsg)}
              className="text-xs text-slate-500 hover:text-blue-400 transition-colors"
            >
              Forgot password? Contact SCRB Administrator
            </button>
            {showForgotMsg && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-3 p-3 bg-slate-900/60 border border-slate-700 rounded-lg text-xs text-slate-400 text-center"
              >
                Contact SCRB IT Helpdesk: <br />
                <a href="mailto:scrb-helpdesk@ksp.gov.in" className="text-blue-400 font-medium hover:underline">scrb-helpdesk@ksp.gov.in</a> or call{" "}
                <span className="text-blue-400 font-medium">080-2294-3000</span>
              </motion.div>
            )}
          </div>

          <div className="mt-6 p-3 bg-slate-900/60 border border-slate-700/50 rounded-lg">
            <p className="text-xs text-slate-500 text-center">
              This system is for authorized Karnataka State Police personnel only.
              Unauthorized access is a criminal offense.
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
