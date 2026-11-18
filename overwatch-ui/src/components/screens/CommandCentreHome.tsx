import React, { useEffect, useState, useRef } from "react";
import { motion, useInView } from "framer-motion";
import { apiFetch, HealthResponse } from "@/lib/api";

// ─── API & Data Types ──────────────────────────────────────────
interface DashboardStats {
  totalAssets:  number;
  goldenAssets: number;
  isOffline:    boolean;
  isLoading:    boolean;
  nodes:        Record<string, string>;
}

function useDashboardStats(): DashboardStats {
  const [stats, setStats] = useState<DashboardStats>({
    totalAssets:  0, goldenAssets: 0, isOffline: false, isLoading: true, nodes: {},
  });

  useEffect(() => {
    let cancelled = false;
    async function fetchHealth() {
      try {
        const res = await apiFetch<HealthResponse>("/");
        if (cancelled) return;
        if (res.ok) {
          setStats({ totalAssets: res.data.total_assets, goldenAssets: res.data.golden_assets, isOffline: false, isLoading: false, nodes: res.data.nodes || {} });
        } else {
          throw new Error(res.error);
        }
      } catch (err) {
        if (cancelled) return;
        setStats((prev) => ({ ...prev, isOffline: true, isLoading: false }));
      }
    }
    fetchHealth();
    const intervalId = setInterval(fetchHealth, 5000);
    return () => { cancelled = true; clearInterval(intervalId); };
  }, []);

  return stats;
}

// ─── Icons ────────────────────────────────────────────────────────
function Icon({ name, size = 18, className = "" }: { name: string; size?: number; className?: string }) {
  const p = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.5, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, className };
  if (name === "shield")   return <svg {...p}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>;
  if (name === "zap")      return <svg {...p}><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>;
  if (name === "activity") return <svg {...p}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>;
  if (name === "chevron")  return <svg {...p}><polyline points="6 9 12 15 18 9"/></svg>;
  if (name === "settings") return <svg {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>;
  if (name === "logout")   return <svg {...p}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>;
  if (name === "sun")      return <svg {...p}><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>;
  if (name === "moon")     return <svg {...p}><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>;
  return null;
}

// ─── Helpers ──────────────────────────────────────────────────────
function FadeUp({ children, delay = 0, className = "" }: { children: React.ReactNode; delay?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  return (
    <motion.div ref={ref} initial={{ opacity: 0, y: 16 }} animate={inView ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.5, delay, ease: [0.22, 1, 0.36, 1] }} className={className}>
      {children}
    </motion.div>
  );
}

// ─── Components ───────────────────────────────────────────────────
function AppNavbar({ dark, setDark, userName, userRole, onNavigate, onLogout }: any) {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const h = () => setScrolled(window.scrollY > 10);
    window.addEventListener("scroll", h, { passive: true });
    return () => window.removeEventListener("scroll", h);
  }, []);

  const navClass = `fixed top-0 left-0 right-0 z-[200] h-14 flex items-center justify-between px-6 md:px-12 transition-all duration-300 ${
    scrolled 
      ? (dark ? 'bg-[#030712]/90 backdrop-blur-md border-b border-gray-800' : 'bg-white/90 backdrop-blur-md border-b border-gray-200')
      : 'bg-transparent border-b border-transparent'
  }`;

  const initials = userName.split(" ").map((w: string) => w[0]).join("").slice(0, 2).toUpperCase();

  return (
    <nav className={navClass}>
      <div className="flex items-center gap-3 cursor-pointer" onClick={() => onNavigate("HOME")}>
        <div className={`w-7 h-7 rounded flex items-center justify-center ${dark ? 'bg-gray-100 text-gray-900' : 'bg-gray-900 text-white'}`}>
          <Icon name="shield" size={14} />
        </div>
        <span className={`font-semibold text-sm tracking-tight ${dark ? 'text-gray-100' : 'text-gray-900'}`}>OVERWATCH</span>
      </div>

      <div className="hidden md:flex items-center gap-1">
        {[{l: "Home", a: "HOME"}, {l: "Features", a: "HOME"}, {l: "GitHub", href: "https://github.com/TanmayyyK/sourcegraph"}, {l: "Docs", href: "/docs"}].map((n) => (
          <button key={n.l} onClick={() => n.href ? window.location.assign(n.href) : onNavigate(n.a)} className={`px-4 py-2 text-xs font-medium transition-colors ${dark ? 'text-gray-400 hover:text-gray-100' : 'text-gray-500 hover:text-gray-900'}`}>
            {n.l}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-4">
        <button onClick={() => setDark(!dark)} className={`p-2 rounded-md transition-colors ${dark ? 'text-gray-400 hover:text-gray-100 hover:bg-gray-800' : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'}`}>
          <Icon name={dark ? "sun" : "moon"} size={14} />
        </button>

        <div className="relative">
          <button onClick={() => setMenuOpen(!menuOpen)} className={`flex items-center gap-2 p-1 pl-2 pr-3 rounded-lg border transition-colors ${dark ? 'border-gray-800 bg-[#0A0A0A] hover:border-gray-700' : 'border-gray-200 bg-white hover:border-gray-300 shadow-sm'}`}>
            <div className={`w-6 h-6 rounded flex items-center justify-center text-[10px] font-mono font-bold ${dark ? 'bg-gray-800 text-gray-300' : 'bg-gray-100 text-gray-700'}`}>
              {initials}
            </div>
            <div className="text-left leading-tight hidden sm:block">
              <p className={`text-[11px] font-semibold ${dark ? 'text-gray-100' : 'text-gray-900'}`}>{userName}</p>
              <p className={`text-[9px] font-mono uppercase tracking-widest ${dark ? 'text-gray-500' : 'text-gray-400'}`}>{userRole}</p>
            </div>
            <Icon name="chevron" size={12} className={dark ? 'text-gray-500' : 'text-gray-400'} />
          </button>

          {menuOpen && (
            <div className={`absolute top-full right-0 mt-2 w-48 rounded-xl border p-1 shadow-lg ${dark ? 'bg-[#0A0A0A] border-gray-800' : 'bg-white border-gray-200'}`}>
              <button className={`w-full flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg transition-colors ${dark ? 'text-gray-300 hover:bg-gray-800' : 'text-gray-600 hover:bg-gray-50'}`}>
                <Icon name="settings" size={14} /> Account Settings
              </button>
              <div className={`h-px w-full my-1 ${dark ? 'bg-gray-800' : 'bg-gray-100'}`} />
              <button onClick={onLogout} className={`w-full flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg transition-colors ${dark ? 'text-red-400 hover:bg-red-900/20' : 'text-red-600 hover:bg-red-50'}`}>
                <Icon name="logout" size={14} /> Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}

const ThreatTimeline = ({ dark }: any) => {
  const items = [
    { label: "New asset uploaded",   time: "2m ago" },
    { label: "System health check passed",   time: "41m ago" },
    { label: "Routine maintenance completed",    time: "3h ago" },
    { label: "Security patch deployed",  time: "Yesterday" },
  ];

  return (
    <div className="flex flex-col gap-2">
      {items.map((item, i) => (
        <FadeUp key={i} delay={i * 0.1} className={`flex items-center justify-between p-3 rounded-lg border ${dark ? 'bg-[#0A0A0A] border-gray-800' : 'bg-gray-50 border-gray-100'}`}>
          <div className="flex items-center gap-3">
            <div className={`w-1.5 h-1.5 rounded-full ${i < 2 ? 'bg-red-500' : (i === 2 ? 'bg-amber-500' : 'bg-gray-400')}`} />
            <span className={`text-xs font-medium ${dark ? 'text-gray-300' : 'text-gray-700'}`}>{item.label}</span>
          </div>
          <span className={`text-[10px] font-mono tracking-widest ${dark ? 'text-gray-500' : 'text-gray-400'}`}>{item.time}</span>
        </FadeUp>
      ))}
    </div>
  );
};

const NodeRoster = ({ statsData, dark }: any) => {
  const nodes = [
    { name: "Node A",  id: "atlas",         role: "Data Processing" },
    { name: "Node B",  id: "hermes",        role: "Storage Cluster" },
    { name: "Node C",  id: "argus",         role: "Monitoring" },
  ];

  return (
    <div className="flex flex-col gap-2">
      {nodes.map((n, i) => {
        const isOk = statsData.nodes[n.id] === "OK";
        return (
          <FadeUp key={n.name} delay={i * 0.1} className={`flex items-center justify-between p-3 rounded-lg border ${dark ? 'bg-[#0A0A0A] border-gray-800' : 'bg-gray-50 border-gray-100'}`}>
            <div className="flex items-center gap-3">
              <div className={`w-6 h-6 rounded flex items-center justify-center text-[10px] font-mono font-bold ${dark ? 'bg-gray-800 text-gray-300' : 'bg-white border border-gray-200 text-gray-700 shadow-sm'}`}>
                {n.name[0]}
              </div>
              <div className="flex flex-col">
                <span className={`text-xs font-medium leading-tight ${dark ? 'text-gray-300' : 'text-gray-700'}`}>{n.name}</span>
                <span className={`text-[9px] font-mono uppercase tracking-widest ${dark ? 'text-gray-500' : 'text-gray-400'}`}>{n.role}</span>
              </div>
            </div>
            <div className={`px-2 py-1 flex items-center gap-1.5 rounded-md border ${isOk ? (dark ? 'bg-green-950/30 border-green-900/50 text-green-400' : 'bg-green-50 border-green-200 text-green-600') : (dark ? 'bg-red-950/30 border-red-900/50 text-red-400' : 'bg-red-50 border-red-200 text-red-600')}`}>
              <div className={`w-1.5 h-1.5 rounded-full ${isOk ? 'bg-current' : 'bg-current animate-pulse'}`} />
              <span className="text-[9px] font-mono uppercase tracking-widest">{isOk ? 'ONLINE' : 'ERR'}</span>
            </div>
          </FadeUp>
        );
      })}
    </div>
  );
};

export interface CommandCenterHomeProps {
  userName:   string;
  userRole:   string;
  onNavigate: (destination: "INGEST" | "ASSETS" | "LOGS" | string) => void;
  onLogout?:  () => void;
}

export default function CommandCentreHome({ userName, userRole, onNavigate, onLogout }: CommandCenterHomeProps) {
  const [dark, setDark] = useState(() => {
    if (typeof window !== "undefined") return window.matchMedia("(prefers-color-scheme: dark)").matches;
    return false;
  });
  const statsData = useDashboardStats();
  const firstName = userName.split(" ")[0];

  return (
    <div className={`min-h-screen font-sans selection:bg-gray-300 dark:selection:bg-gray-700 ${dark ? 'dark bg-[#030712]' : 'bg-[#F9FAFB]'}`}>
      <AppNavbar dark={dark} setDark={setDark} userName={userName} userRole={userRole} onNavigate={onNavigate} onLogout={onLogout} />
      
      <main className="pt-24 pb-20 px-6 md:px-12 max-w-7xl mx-auto">
        <div className="mb-12">
          <FadeUp>
            <div className="flex items-center gap-2 mb-4">
              <span className={`w-1.5 h-1.5 rounded-full bg-gray-400 ${!statsData.isOffline && 'animate-pulse'}`} />
              <span className={`text-[10px] font-mono uppercase tracking-widest ${dark ? 'text-gray-500' : 'text-gray-400'}`}>
                {statsData.isOffline ? 'System Offline' : 'Live Dashboard'}
              </span>
            </div>
            <h1 className={`text-4xl md:text-5xl font-semibold tracking-tight mb-2 ${dark ? 'text-gray-100' : 'text-gray-900'}`}>
              Welcome back, {firstName}.
            </h1>
            <p className={`text-sm ${dark ? 'text-gray-400' : 'text-gray-500'}`}>
              Pipeline operational. Monitoring {statsData.totalAssets || 0} active assets.
            </p>
          </FadeUp>

          <FadeUp delay={0.1} className="mt-8 flex gap-4">
            <button onClick={() => onNavigate("INGEST")} className={`px-5 py-2.5 text-sm font-medium rounded-lg flex items-center gap-2 transition-all ${dark ? 'bg-gray-100 text-gray-900 hover:bg-white' : 'bg-gray-900 text-white hover:bg-gray-800'}`}>
              <Icon name="zap" size={14} /> Launch Portal
            </button>
            <button onClick={() => onNavigate("LOGS")} className={`px-5 py-2.5 text-sm font-medium rounded-lg border flex items-center gap-2 transition-all ${dark ? 'border-gray-800 text-gray-300 hover:bg-[#0A0A0A]' : 'border-gray-200 text-gray-600 bg-white hover:bg-gray-50'}`}>
              <Icon name="activity" size={14} /> System Logs
            </button>
          </FadeUp>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-6">
            <FadeUp delay={0.2} className={`col-span-1 md:col-span-2 p-6 md:p-8 rounded-2xl border ${dark ? 'bg-[#0A0A0A] border-gray-800' : 'bg-white border-gray-100 shadow-[0_8px_30px_rgb(0,0,0,0.04)]'}`}>
              <p className={`text-[10px] font-mono uppercase tracking-widest mb-6 ${dark ? 'text-gray-500' : 'text-gray-400'}`}>System Metrics</p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                {[
                  { label: "Total Assets", value: statsData.totalAssets },
                  { label: "Golden Refs", value: statsData.goldenAssets },
                  { label: "Avg Latency", value: "< 2.1s" },
                  { label: "Uptime", value: "99.99%" },
                ].map((s, i) => (
                  <div key={i}>
                    <p className={`text-2xl font-semibold mb-1 ${dark ? 'text-gray-100' : 'text-gray-900'}`}>{s.value}</p>
                    <p className={`text-xs ${dark ? 'text-gray-500' : 'text-gray-400'}`}>{s.label}</p>
                  </div>
                ))}
              </div>
            </FadeUp>

            <FadeUp delay={0.3} className={`p-6 rounded-2xl border ${dark ? 'bg-[#0A0A0A] border-gray-800' : 'bg-white border-gray-100 shadow-[0_8px_30px_rgb(0,0,0,0.04)]'}`}>
              <p className={`text-[10px] font-mono uppercase tracking-widest mb-4 ${dark ? 'text-gray-500' : 'text-gray-400'}`}>Node Topology</p>
              <NodeRoster statsData={statsData} dark={dark} />
            </FadeUp>

            <FadeUp delay={0.4} className={`p-6 rounded-2xl border ${dark ? 'bg-[#0A0A0A] border-gray-800' : 'bg-white border-gray-100 shadow-[0_8px_30px_rgb(0,0,0,0.04)]'}`}>
              <p className={`text-[10px] font-mono uppercase tracking-widest mb-4 ${dark ? 'text-gray-500' : 'text-gray-400'}`}>Threat Timeline</p>
              <ThreatTimeline dark={dark} />
            </FadeUp>
          </div>

          <div className="lg:col-span-1 flex flex-col gap-6">
            <FadeUp delay={0.5} className={`flex-1 p-6 rounded-2xl border ${dark ? 'bg-[#0A0A0A] border-gray-800' : 'bg-white border-gray-100 shadow-[0_8px_30px_rgb(0,0,0,0.04)]'}`}>
               <p className={`text-[10px] font-mono uppercase tracking-widest mb-4 ${dark ? 'text-gray-500' : 'text-gray-400'}`}>Intelligence Brief</p>
               <div className="space-y-4">
                 <div className={`p-4 rounded-xl border ${dark ? 'border-gray-800' : 'border-gray-100 bg-gray-50'}`}>
                   <h4 className={`text-sm font-semibold mb-2 ${dark ? 'text-gray-100' : 'text-gray-900'}`}>System Orchestrator</h4>
                   <p className={`text-xs leading-relaxed ${dark ? 'text-gray-400' : 'text-gray-500'}`}>All components are running smoothly. System latency is within optimal range.</p>
                 </div>
                 <div className={`p-4 rounded-xl border ${dark ? 'border-gray-800' : 'border-gray-100 bg-gray-50'}`}>
                   <h4 className={`text-sm font-semibold mb-2 ${dark ? 'text-gray-100' : 'text-gray-900'}`}>Resource Management</h4>
                   <p className={`text-xs leading-relaxed ${dark ? 'text-gray-400' : 'text-gray-500'}`}>Memory and compute resources are allocated efficiently. System is healthy.</p>
                 </div>
               </div>
            </FadeUp>
          </div>
        </div>
      </main>
    </div>
  );
}
