import { useEffect, useState } from "react";
import { useSelector } from "react-redux";
import { useNavigate, Link } from "react-router-dom";
import { RootState } from "../store/store";
import {
  MapPin,
  Building,
  Clock,
  Map,
  Share2,
  Brain,
  AlertOctagon,
  TrendingUp,
  FileText,
  ChevronRight,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  Radar,
} from "recharts";

// High-fidelity mock data for the charts matching the screenshot style
const crimeTrendData = [
  { month: "Jan", metricA: 80, metricB: 60, metricC: 110 },
  { month: "Feb", metricA: 110, metricB: 85, metricC: 95 },
  { month: "Mar", metricA: 95, metricB: 150, metricC: 120 },
  { month: "Apr", metricA: 155, metricB: 120, metricC: 140 },
  { month: "May", metricA: 140, metricB: 200, metricC: 115 },
  { month: "Jun", metricA: 180, metricB: 130, metricC: 210 },
  { month: "Jul", metricA: 160, metricB: 175, metricC: 180 },
  { month: "Aug", metricA: 200, metricB: 150, metricC: 195 },
  { month: "Sep", metricA: 220, metricB: 190, metricC: 235 },
];

const alertRadarData = [
  { subject: "NS", value: 120 },
  { subject: "ATT", value: 98 },
  { subject: "DET", value: 86 },
  { subject: "CEN", value: 99 },
  { subject: "LYW", value: 85 },
];

// District details for hotspots on the Karnataka SVG map
const mapHotspots = [
  { name: "Bengaluru Urban", x: 240, y: 350, intensity: 24, color: "#EF4444" },
  { name: "Mysuru", x: 205, y: 380, intensity: 16, color: "#F97316" },
  { name: "Belagavi", x: 120, y: 130, intensity: 14, color: "#F97316" },
  { name: "Kalaburagi", x: 230, y: 80, intensity: 10, color: "#F59E0B" },
  { name: "Mangaluru", x: 135, y: 330, intensity: 12, color: "#EF4444" },
  { name: "Ballari", x: 210, y: 200, intensity: 18, color: "#EF4444" },
];

export default function LandingPage() {
  const { isAuthenticated, user_name } = useSelector((state: RootState) => state.auth);
  const navigate = useNavigate();
  const [pulseScale, setPulseScale] = useState(1);

  // Simple pulsing effect for hotspots
  useEffect(() => {
    const interval = setInterval(() => {
      setPulseScale((prev) => (prev === 1 ? 1.25 : 1));
    }, 1200);
    return () => clearInterval(interval);
  }, []);

  const handleLaunch = () => {
    if (isAuthenticated) {
      navigate("/dashboard");
    } else {
      navigate("/login");
    }
  };

  return (
    <div className="min-h-screen bg-[#F5F2EB] text-[#2D2922] font-sans selection:bg-[#8E4A35]/20 selection:text-[#8E4A35] relative overflow-x-hidden">
      {/* Subtle paper/grain overlay */}
      <div 
        className="absolute inset-0 pointer-events-none opacity-[0.015]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/4000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`
        }}
      />

      {/* Header */}
      <header className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between z-20 relative">
        <div className="flex items-center gap-3">
          <div className="h-11 w-11 rounded-xl flex items-center justify-center overflow-hidden">
            <img src={`${import.meta.env.BASE_URL}shastra_logo.png`} alt="SHASTRA Logo" className="w-full h-full object-contain" />
          </div>
          <div>
            <h2 className="text-xs font-bold tracking-widest text-[#1C1917] uppercase">KARNATAKA STATE POLICE</h2>
            <p className="text-[10px] font-semibold text-stone-500 tracking-wider">State Crime Records Bureau</p>
          </div>
        </div>

        <div className="flex items-center gap-8">
          <nav className="hidden md:flex items-center gap-6 text-xs font-semibold text-stone-600 tracking-wider">
            <span>Intelligence</span>
            <span className="h-1 w-1 rounded-full bg-stone-400" />
            <span>Integrity</span>
            <span className="h-1 w-1 rounded-full bg-stone-400" />
            <span>Safety</span>
          </nav>

          {isAuthenticated ? (
            <button
              onClick={() => navigate("/dashboard")}
              className="px-5 py-2 bg-white border border-[#E4DFD5] text-[#1C1917] font-semibold text-xs rounded-full shadow-sm hover:bg-[#FAF8F5] transition-all flex items-center gap-1.5 flex-row"
            >
              <span>Hi, {user_name || "Officer"}</span>
              <ArrowRight className="h-3 w-3 text-stone-500" />
            </button>
          ) : (
            <button
              onClick={() => navigate("/login")}
              className="px-6 py-2 bg-white text-[#1C1917] font-bold text-xs rounded-full shadow-md shadow-stone-200 hover:shadow-lg transition-all"
            >
              Login
            </button>
          )}
        </div>
      </header>

      {/* Hero & Visualizer Grid */}
      <section className="max-w-7xl mx-auto px-6 pt-8 pb-12 grid grid-cols-1 lg:grid-cols-12 gap-8 relative z-10">
        
        {/* Left Column: Hero Text & Stats */}
        <div className="lg:col-span-5 flex flex-col justify-center">
          <h1 className="text-4xl md:text-5xl font-extrabold text-[#1C1917] tracking-tight leading-[1.1] mb-2 font-serif">
            WELCOME TO SHASTRA
          </h1>
          <p className="text-xs font-bold text-stone-500 tracking-widest uppercase mb-6 leading-relaxed">
            SPATIAL HOTSPOT & ADVANCED SOCIETAL THREAT RECOGNITION ARCHITECTURE
          </p>

          <p className="text-sm md:text-base text-stone-600 leading-relaxed mb-8 max-w-lg">
            Highly sophisticated and integrated spatial threat intelligence, hotspot detection, and anomaly forecasting platform for the Karnataka State Police. Designed for advanced predictive policing and data-driven law enforcement.
          </p>

          {/* Stats Cards Row */}
          <div className="grid grid-cols-3 gap-4 mb-8">
            <div className="bg-white/40 border border-white/60 backdrop-blur-md rounded-2xl p-4 shadow-sm flex flex-col justify-between">
              <div className="h-8 w-8 rounded-lg bg-[#FAF8F5]/80 border border-stone-200/50 flex items-center justify-center mb-3">
                <MapPin className="h-4.5 w-4.5 text-[#A16244]" />
              </div>
              <div>
                <h4 className="text-2xl font-extrabold text-[#1C1917]">32</h4>
                <p className="text-[9px] font-bold text-stone-500 tracking-wider uppercase">Districts</p>
              </div>
            </div>

            <div className="bg-white/40 border border-white/60 backdrop-blur-md rounded-2xl p-4 shadow-sm flex flex-col justify-between">
              <div className="h-8 w-8 rounded-lg bg-[#FAF8F5]/80 border border-stone-200/50 flex items-center justify-center mb-3">
                <Building className="h-4.5 w-4.5 text-[#A16244]" />
              </div>
              <div>
                <h4 className="text-2xl font-extrabold text-[#1C1917]">1,245+</h4>
                <p className="text-[9px] font-bold text-stone-500 tracking-wider uppercase">Police Stations</p>
              </div>
            </div>

            <div className="bg-white/40 border border-white/60 backdrop-blur-md rounded-2xl p-4 shadow-sm flex flex-col justify-between">
              <div className="h-8 w-8 rounded-lg bg-[#FAF8F5]/80 border border-stone-200/50 flex items-center justify-center mb-3">
                <Clock className="h-4.5 w-4.5 text-[#A16244]" />
              </div>
              <div>
                <h4 className="text-2xl font-extrabold text-[#1C1917]">24/7</h4>
                <p className="text-[9px] font-bold text-stone-500 tracking-wider uppercase">Intelligence</p>
              </div>
            </div>
          </div>

          {/* Launch Dashboard Button */}
          <div>
            <button
              onClick={handleLaunch}
              className="relative px-8 py-3.5 bg-gradient-to-r from-[#8E4A35] via-[#A65B43] to-[#8E4A35] text-white font-extrabold text-xs tracking-widest uppercase rounded-xl shadow-lg shadow-[#8E4A35]/35 hover:shadow-xl hover:shadow-[#8E4A35]/50 transition-all active:scale-[0.98] group overflow-hidden border-b-4 border-[#6C3423] cursor-pointer"
            >
              <span className="absolute inset-0 bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />
              <span className="flex items-center gap-2">
                Launch Dashboard
                <Sparkles className="h-4 w-4 text-amber-200 group-hover:animate-spin" />
              </span>
            </button>
          </div>
        </div>

        {/* Center: Karnataka Map & Vidhana Soudha Backdrop */}
        <div className="lg:col-span-4 flex items-center justify-center relative min-h-[400px]">
          {/* Vidhana Soudha Graphic - Custom Architectural SVG Backdrop */}
          <div className="absolute inset-0 opacity-30 pointer-events-none flex items-center justify-center">
            <svg 
              viewBox="0 0 400 300" 
              className="w-full h-full text-[#C8C2B3] stroke-current fill-none"
              style={{
                maskImage: "radial-gradient(circle, rgba(0,0,0,1) 30%, rgba(0,0,0,0) 80%)",
                WebkitMaskImage: "radial-gradient(circle, rgba(0,0,0,1) 30%, rgba(0,0,0,0) 80%)"
              }}
            >
              {/* Ground line */}
              <line x1="10" y1="250" x2="390" y2="250" strokeWidth="1.5"/>
              
              {/* Steps */}
              <line x1="120" y1="250" x2="280" y2="250" strokeWidth="2"/>
              <line x1="125" y1="246" x2="275" y2="246" strokeWidth="1.5"/>
              <line x1="130" y1="242" x2="270" y2="242" strokeWidth="1"/>
              
              {/* Main building base */}
              <rect x="30" y="170" width="340" height="72" strokeWidth="1.2"/>
              
              {/* Portico / Pillars */}
              <rect x="135" y="160" width="130" height="82" strokeWidth="1.2"/>
              {/* Columns */}
              <line x1="145" y1="160" x2="145" y2="242" strokeWidth="1.5"/>
              <line x1="165" y1="160" x2="165" y2="242" strokeWidth="1.5"/>
              <line x1="185" y1="160" x2="185" y2="242" strokeWidth="1.5"/>
              <line x1="200" y1="160" x2="200" y2="242" strokeWidth="1.5"/>
              <line x1="215" y1="160" x2="215" y2="242" strokeWidth="1.5"/>
              <line x1="235" y1="160" x2="235" y2="242" strokeWidth="1.5"/>
              <line x1="255" y1="160" x2="255" y2="242" strokeWidth="1.5"/>
              
              {/* Pediment (triangle over columns) */}
              <polygon points="130,160 270,160 200,135" strokeWidth="1.2"/>
              
              {/* Central Dome base */}
              <rect x="175" y="115" width="50" height="20" strokeWidth="1.2"/>
              {/* Central Dome */}
              <path d="M 175,115 C 175,90 225,90 225,115 Z" strokeWidth="1.2"/>
              {/* Finial / Spire */}
              <line x1="200" y1="95" x2="200" y2="70" strokeWidth="1.2"/>
              <circle cx="200" cy="68" r="2" fill="currentColor" />
              
              {/* Left Dome */}
              <rect x="50" y="155" width="20" height="15" strokeWidth="1.2"/>
              <path d="M 50,155 C 50,145 70,145 70,155 Z" strokeWidth="1.2"/>
              <line x1="60" y1="145" x2="60" y2="135" strokeWidth="1"/>

              {/* Right Dome */}
              <rect x="330" y="155" width="20" height="15" strokeWidth="1.2"/>
              <path d="M 330,155 C 330,145 350,145 350,155 Z" strokeWidth="1.2"/>
              <line x1="340" y1="145" x2="340" y2="135" strokeWidth="1"/>
              
              {/* Decorative windows grid */}
              <line x1="40" y1="190" x2="120" y2="190" strokeWidth="0.8" strokeDasharray="2 2" />
              <line x1="40" y1="210" x2="120" y2="210" strokeWidth="0.8" strokeDasharray="2 2" />
              <line x1="280" y1="190" x2="360" y2="190" strokeWidth="0.8" strokeDasharray="2 2" />
              <line x1="280" y1="210" x2="360" y2="210" strokeWidth="0.8" strokeDasharray="2 2" />
            </svg>
          </div>

          {/* Karnataka Map SVG Outline */}
          <div className="relative z-10 w-full max-w-[320px] aspect-[3/4]">
            <svg 
              viewBox="0 0 300 400" 
              className="w-full h-full drop-shadow-md select-none"
            >
              {/* Karnataka State Borders Path */}
              <path
                d="M 120,40 C 130,35 150,20 160,10 C 170,5 180,5 190,10 C 200,15 210,30 220,45 C 230,55 240,60 250,65 C 260,70 280,75 285,85 C 290,95 280,120 290,130 C 300,140 320,180 330,200 C 340,220 350,240 350,260 C 350,285 340,300 335,320 C 325,350 290,410 280,430 C 275,440 270,450 260,455 C 250,460 230,440 215,430 C 200,420 190,430 180,415 C 170,400 160,380 155,360 C 150,340 155,320 150,300 C 145,280 125,260 120,240 C 115,220 120,200 115,180 C 110,160 95,150 100,130 C 105,110 120,95 130,85 C 140,75 135,55 120,40 Z"
                stroke="#D1CFC7"
                strokeWidth={1.5}
                fill="#FCFAF5"
                fillOpacity={0.7}
                strokeLinecap="round"
                strokeLinejoin="round"
              />

              {/* District grid line approximations */}
              <path d="M120,130 Q160,140 240,110" stroke="#E5E3DB" strokeWidth={1} fill="none" strokeDasharray="3 3" />
              <path d="M115,180 Q170,210 280,160" stroke="#E5E3DB" strokeWidth={1} fill="none" strokeDasharray="3 3" />
              <path d="M125,260 Q200,250 300,240" stroke="#E5E3DB" strokeWidth={1} fill="none" strokeDasharray="3 3" />
              <path d="M150,300 Q200,320 280,310" stroke="#E5E3DB" strokeWidth={1} fill="none" strokeDasharray="3 3" />
              <path d="M155,360 Q210,360 260,370" stroke="#E5E3DB" strokeWidth={1} fill="none" strokeDasharray="3 3" />

              {/* Glowing Interactive Hotspots */}
              {mapHotspots.map((hs, i) => (
                <g key={i}>
                  {/* Pulse Ring */}
                  <circle
                    cx={hs.x}
                    cy={hs.y}
                    r={hs.intensity * pulseScale}
                    fill={hs.color}
                    fillOpacity={0.15}
                    className="transition-all duration-1000 ease-in-out"
                  />
                  {/* Hotspot Core */}
                  <circle
                    cx={hs.x}
                    cy={hs.y}
                    r={6}
                    fill={hs.color}
                    className="cursor-pointer"
                  >
                    <title>{hs.name}: High Risk Zone</title>
                  </circle>
                  {/* Subtle Inner Dot */}
                  <circle cx={hs.x} cy={hs.y} r={2} fill="white" />
                </g>
              ))}
            </svg>
          </div>
        </div>

        {/* Right Column: Visualizations & Widgets */}
        <div className="lg:col-span-3 flex flex-col gap-6">
          
          {/* Crime Trend Widget */}
          <div className="bg-white/40 border border-white/60 backdrop-blur-md rounded-2xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-extrabold tracking-wider text-[#1C1917] uppercase">Crime Trend</h3>
              <div className="flex items-center gap-1.5 text-[8px] font-bold text-stone-500 uppercase">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#3B82F6]" /> Metrics
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#EF4444]" /> Metrics
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#10B981]" /> Metrics
              </div>
            </div>

            <div className="h-36 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={crimeTrendData} margin={{ top: 5, right: 0, left: -25, bottom: 0 }}>
                  <defs>
                    <linearGradient id="colorA" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3B82F6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#3B82F6" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorB" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#EF4444" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#EF4444" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorC" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10B981" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#10B981" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="month" tickLine={false} axisLine={false} tick={{ fontSize: 9, fill: "#78716c" }} />
                  <YAxis domain={[0, 250]} tickLine={false} axisLine={false} tick={{ fontSize: 9, fill: "#78716c" }} />
                  <Tooltip 
                    contentStyle={{ background: "#FAF8F5", border: "1px solid #E4DFD5", borderRadius: "12px", fontSize: "10px" }}
                  />
                  <Area type="monotone" dataKey="metricA" stroke="#3B82F6" strokeWidth={1.5} fillOpacity={1} fill="url(#colorA)" />
                  <Area type="monotone" dataKey="metricB" stroke="#EF4444" strokeWidth={1.5} fillOpacity={1} fill="url(#colorB)" />
                  <Area type="monotone" dataKey="metricC" stroke="#10B981" strokeWidth={1.5} fillOpacity={1} fill="url(#colorC)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Active Alerts Widget */}
          <div className="bg-white/40 border border-white/60 backdrop-blur-md rounded-2xl p-5 shadow-sm">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xs font-extrabold tracking-wider text-[#1C1917] uppercase">Active Alerts</h3>
              <div className="text-right">
                <span className="text-xs font-extrabold text-[#15803D] flex items-center gap-0.5 justify-end">
                  ▲ +18.6%
                </span>
                <p className="text-[9px] font-bold text-stone-500 uppercase">23 High Priority</p>
              </div>
            </div>

            <div className="flex gap-4 items-center">
              {/* Radar Chart */}
              <div className="h-28 w-28 flex-shrink-0">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart cx="50%" cy="50%" outerRadius="80%" data={alertRadarData}>
                    <PolarGrid stroke="#E5E3DB" />
                    <PolarAngleAxis dataKey="subject" tick={{ fontSize: 8, fill: "#57534e", fontWeight: "bold" }} />
                    <Radar
                      name="Alerts"
                      dataKey="value"
                      stroke="#A65B43"
                      fill="#A65B43"
                      fillOpacity={0.4}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              </div>

              {/* Legend with Metrics Counts */}
              <div className="flex-1 space-y-1 text-[9px] font-bold text-stone-600">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#EF4444]" /> High Priority
                  </span>
                  <span className="text-stone-800">143</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#3B82F6]" /> High Priority
                  </span>
                  <span className="text-stone-800">53</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#F59E0B]" /> High Priority
                  </span>
                  <span className="text-stone-800">83</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-[#10B981]" /> High Priority
                  </span>
                  <span className="text-stone-800">23</span>
                </div>
                <div className="flex items-center justify-between text-stone-400">
                  <span className="flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-stone-300" /> Low Priority
                  </span>
                  <span>37</span>
                </div>
              </div>
            </div>
          </div>

        </div>

      </section>

      {/* Bottom Row Navigation Modules - 6 premium cards */}
      <section className="max-w-7xl mx-auto px-6 pb-16 relative z-10">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-5">
          
          {/* Card 1: Advanced Visualization */}
          <Link
            to={isAuthenticated ? "/map" : "/login"}
            className="group bg-white border border-[#E4DFD5] rounded-3xl overflow-hidden shadow-sm hover:shadow-md transition-all flex flex-col min-h-[170px]"
          >
            {/* Wooden/beige warm header */}
            <div className="h-16 bg-[#E6DFD3]/80 group-hover:bg-[#E6DFD3] transition-colors flex items-center justify-center text-stone-700">
              <Map className="h-7 w-7 stroke-[1.5]" />
            </div>
            <div className="p-4 flex-1 flex flex-col justify-between">
              <div>
                <h3 className="text-[11px] font-extrabold tracking-wider uppercase text-stone-800 mb-1.5">
                  Advanced Visualization
                </h3>
                <p className="text-[10px] text-stone-500 leading-normal">
                  Interactive map, spatial crime density, and live hotspot tracking across jurisdictions.
                </p>
              </div>
              <div className="mt-3 flex items-center justify-end text-[#8E4A35] opacity-0 group-hover:opacity-100 transition-opacity">
                <ChevronRight className="h-4 w-4" />
              </div>
            </div>
          </Link>

          {/* Card 2: Network & Link Analysis */}
          <Link
            to={isAuthenticated ? "/network" : "/login"}
            className="group bg-white border border-[#E4DFD5] rounded-3xl overflow-hidden shadow-sm hover:shadow-md transition-all flex flex-col min-h-[170px]"
          >
            {/* Dark steel blue header */}
            <div className="h-16 bg-[#2E3A46] text-white flex items-center justify-center">
              <Share2 className="h-7 w-7 stroke-[1.5]" />
            </div>
            <div className="p-4 flex-1 flex flex-col justify-between">
              <div>
                <h3 className="text-[11px] font-extrabold tracking-wider uppercase text-stone-800 mb-1.5">
                  Network & Link Analysis
                </h3>
                <p className="text-[10px] text-stone-500 leading-normal">
                  Deconstruct criminal associations, visualize hierarchies, and track suspect connections.
                </p>
              </div>
              <div className="mt-3 flex items-center justify-end text-[#8E4A35] opacity-0 group-hover:opacity-100 transition-opacity">
                <ChevronRight className="h-4 w-4" />
              </div>
            </div>
          </Link>

          {/* Card 3: AI Prediction & Risk Scoring */}
          <Link
            to={isAuthenticated ? "/predictions" : "/login"}
            className="group bg-white border border-[#E4DFD5] rounded-3xl overflow-hidden shadow-sm hover:shadow-md transition-all flex flex-col min-h-[170px]"
          >
            {/* Metallic bronze/copper header */}
            <div className="h-16 bg-gradient-to-r from-[#A0522D] to-[#CD853F] text-white flex items-center justify-center">
              <Brain className="h-7 w-7 stroke-[1.5]" />
            </div>
            <div className="p-4 flex-1 flex flex-col justify-between">
              <div>
                <h3 className="text-[11px] font-extrabold tracking-wider uppercase text-stone-800 mb-1.5">
                  AI Prediction & Risk Scoring
                </h3>
                <p className="text-[10px] text-stone-500 leading-normal">
                  Predictive threat assessment, safety index scoring, and recidivism likelihood forecasting.
                </p>
              </div>
              <div className="mt-3 flex items-center justify-end text-[#8E4A35] opacity-0 group-hover:opacity-100 transition-opacity">
                <ChevronRight className="h-4 w-4" />
              </div>
            </div>
          </Link>

          {/* Card 4: Anomaly Detection */}
          <Link
            to={isAuthenticated ? "/anomalies" : "/login"}
            className="group bg-white border border-[#E4DFD5] rounded-3xl overflow-hidden shadow-sm hover:shadow-md transition-all flex flex-col min-h-[170px]"
          >
            {/* Wood texture/dark brown header */}
            <div className="h-16 bg-[#5D4037] text-white flex items-center justify-center">
              <AlertOctagon className="h-7 w-7 stroke-[1.5]" />
            </div>
            <div className="p-4 flex-1 flex flex-col justify-between">
              <div>
                <h3 className="text-[11px] font-extrabold tracking-wider uppercase text-stone-800 mb-1.5">
                  Anomaly Detection
                </h3>
                <p className="text-[10px] text-stone-500 leading-normal">
                  Auto-detect irregular crime spikes, temporal anomalies, and unusual behavior patterns.
                </p>
              </div>
              <div className="mt-3 flex items-center justify-end text-[#8E4A35] opacity-0 group-hover:opacity-100 transition-opacity">
                <ChevronRight className="h-4 w-4" />
              </div>
            </div>
          </Link>

          {/* Card 5: Socio-economic Insights */}
          <Link
            to={isAuthenticated ? "/dashboard" : "/login"}
            className="group bg-white border border-[#E4DFD5] rounded-3xl overflow-hidden shadow-sm hover:shadow-md transition-all flex flex-col min-h-[170px]"
          >
            {/* Forest green header */}
            <div className="h-16 bg-[#3E5C54] text-white flex items-center justify-center">
              <TrendingUp className="h-7 w-7 stroke-[1.5]" />
            </div>
            <div className="p-4 flex-1 flex flex-col justify-between">
              <div>
                <h3 className="text-[11px] font-extrabold tracking-wider uppercase text-stone-800 mb-1.5">
                  Socio-economic Insights
                </h3>
                <p className="text-[10px] text-stone-500 leading-normal">
                  Correlate crime patterns with local economic indices, demographics, and literacy rates.
                </p>
              </div>
              <div className="mt-3 flex items-center justify-end text-[#8E4A35] opacity-0 group-hover:opacity-100 transition-opacity">
                <ChevronRight className="h-4 w-4" />
              </div>
            </div>
          </Link>

          {/* Card 6: Intelligence Reports */}
          <Link
            to={isAuthenticated ? "/reports" : "/login"}
            className="group bg-white border border-[#E4DFD5] rounded-3xl overflow-hidden shadow-sm hover:shadow-md transition-all flex flex-col min-h-[170px]"
          >
            {/* Dark Slate header */}
            <div className="h-16 bg-[#374151] text-white flex items-center justify-center">
              <FileText className="h-7 w-7 stroke-[1.5]" />
            </div>
            <div className="p-4 flex-1 flex flex-col justify-between">
              <div>
                <h3 className="text-[11px] font-extrabold tracking-wider uppercase text-stone-800 mb-1.5">
                  Intelligence Reports
                </h3>
                <p className="text-[10px] text-stone-500 leading-normal">
                  Automated executive briefs, formal case reports, and strategic intelligence dossiers.
                </p>
              </div>
              <div className="mt-3 flex items-center justify-end text-[#8E4A35] opacity-0 group-hover:opacity-100 transition-opacity">
                <ChevronRight className="h-4 w-4" />
              </div>
            </div>
          </Link>

        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[#E4DFD5] bg-[#EFEBDE]/50 py-8 relative z-10">
        <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          {/* Tags / Chips */}
          <div className="flex flex-wrap gap-2">
            {["shastra", "intelligence", "analytics", "security", "karnataka police"].map((tag, i) => (
              <span
                key={i}
                className="px-3 py-1 bg-white/70 border border-[#E4DFD5] text-[10px] font-bold text-stone-500 rounded-full tracking-wider uppercase"
              >
                {tag}
              </span>
            ))}
          </div>

          {/* Bureau Info */}
          <div className="text-[10px] font-bold text-stone-500 tracking-wider uppercase text-center sm:text-right">
            SHASTRA State Crime Records Bureau · © 2026
          </div>
        </div>
      </footer>
    </div>
  );
}
