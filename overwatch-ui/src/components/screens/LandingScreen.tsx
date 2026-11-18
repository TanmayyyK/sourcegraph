import React, { useEffect, useState, useRef } from "react";
import { motion, useInView } from "framer-motion";
import { Link } from "react-router-dom";

// ─── Data ─────────────────────────────────────────────────────────

const FLOW_NODES = [
  { id: 1, label: "Upload Assets",  sub: "Secure ingest pipeline", icon: "upload"  },
  { id: 2, label: "Fingerprint",    sub: "Hash & chain-of-custody", icon: "scan"    },
  { id: 3, label: "AI Analysis",    sub: "Parallel ML model execution", icon: "brain"   },
  { id: 4, label: "Risk Score",     sub: "Deterministic threat classification", icon: "zap"     },
  { id: 5, label: "Command Center", sub: "Live response dashboard", icon: "monitor" },
];

const FEATURES = [
  { tag: "Ingestion Engine",    title: "Drop anything.\nFingerprint everything.",  body: "PDFs, images, video, code — Overwatch fingerprints every byte and builds a tamper-evident chain of custody before the file lands on disk.", span: 7, icon: "upload"  },
  { tag: "AI Analysis",        title: "Patterns humans miss",                      body: "Seven parallel ML models scan simultaneously for plagiarism, deepfakes, and supply-chain anomalies.", span: 5, icon: "brain"   },
  { tag: "Command Center",     title: "One screen,\nevery signal",                 body: "Live risk feed, asset timeline, and one-click SIEM export — all in a single pane of glass.", span: 5, icon: "monitor" },
  { tag: "Trend Intelligence", title: "Act weeks before the threat lands",         body: "Rolling 30-day analytics surface emerging attack patterns and similarity clusters so your team is always a step ahead.", span: 7, icon: "chart"   },
];

const TEAM = [
  {
    name: "Tanmay Kumar",  role: "Creator & Principal Architect", init: "TK",
    bio: "Architected, integrated, and deployed the complete distributed microservice architecture and cloud infrastructure."
  },
  {
    name: "Yogesh Sharma", role: "Threat Intel Contributor", init: "YS",
    bio: "Provided specialized support for threat intelligence components and localized threat detection models."
  },
  {
    name: "Rohit Kumar",   role: "Text Engine Contributor", init: "RK",
    bio: "Delivered targeted infrastructural support for text processing and vector engine node operations."
  },
  {
    name: "Yug",           role: "OCR Contributor", init: "YG",
    bio: "Supported the OCR extraction pipeline and localized vision processing tasks."
  },
];

const STATS = [
  { value: "96.2%",   label: "Detection Precision" },
  { value: "<2min",   label: "Average Pipeline"    },
  { value: "AES-256", label: "Data Encryption"     },
  { value: "JSON-LD", label: "Structured Reports"  },
];

const NAV_LINKS = [
  { name: "Home",     type: "link",     to: "/" },
  { name: "Features", type: "scroll",   to: "features-section" },
  { name: "GitHub",   type: "external", to: "https://github.com/TanmayyyK/sourcegraph" },
  { name: "Docs",     type: "link",     to: "/docs" },
];

// ─── Icons ────────────────────────────────────────────────────────
function Icon({ name, size = 18, className = "" }: { name: string; size?: number; className?: string }) {
  const p = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.5, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, className };
  if (name === "upload")  return <svg {...p}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>;
  if (name === "scan")    return <svg {...p}><path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/><circle cx="12" cy="12" r="3"/></svg>;
  if (name === "brain")   return <svg {...p}><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"/></svg>;
  if (name === "zap")     return <svg {...p}><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>;
  if (name === "monitor") return <svg {...p}><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4"/></svg>;
  if (name === "chart")   return <svg {...p}><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>;
  if (name === "shield")  return <svg {...p}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>;
  if (name === "sun")     return <svg {...p}><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>;
  if (name === "moon")    return <svg {...p}><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>;
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
function Navbar({ dark, onToggleDark, onLoginClick, onSignupClick }: any) {
  const [scrolled, setScrolled] = useState(false);
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

  return (
    <nav className={navClass}>
      <div className="flex items-center gap-3">
        <div className={`w-7 h-7 rounded flex items-center justify-center ${dark ? 'bg-gray-100 text-gray-900' : 'bg-gray-900 text-white'}`}>
          <Icon name="shield" size={14} />
        </div>
        <span className={`font-semibold text-sm tracking-tight ${dark ? 'text-gray-100' : 'text-gray-900'}`}>OVERWATCH</span>
      </div>

      <div className="hidden md:flex items-center gap-1">
        {NAV_LINKS.map((l) => (
          <div key={l.name}>
            {l.type === "link" && <Link to={l.to!} className={`px-4 py-2 text-xs font-medium transition-colors ${dark ? 'text-gray-400 hover:text-gray-100' : 'text-gray-500 hover:text-gray-900'}`}>{l.name}</Link>}
            {l.type === "external" && <a href={l.to!} target="_blank" rel="noreferrer" className={`px-4 py-2 text-xs font-medium transition-colors ${dark ? 'text-gray-400 hover:text-gray-100' : 'text-gray-500 hover:text-gray-900'}`}>{l.name}</a>}
            {l.type === "scroll" && <button onClick={() => document.getElementById(l.to!)?.scrollIntoView({ behavior: "smooth" })} className={`px-4 py-2 text-xs font-medium transition-colors ${dark ? 'text-gray-400 hover:text-gray-100' : 'text-gray-500 hover:text-gray-900'}`}>{l.name}</button>}
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3">
        <button onClick={onToggleDark} className={`p-2 rounded-md transition-colors ${dark ? 'text-gray-400 hover:text-gray-100 hover:bg-gray-800' : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'}`}>
          <Icon name={dark ? "sun" : "moon"} size={14} />
        </button>
        <button onClick={onLoginClick} className={`px-4 py-2 text-xs font-medium transition-colors ${dark ? 'text-gray-300 hover:text-white' : 'text-gray-600 hover:text-gray-900'}`}>Log in</button>
        <button onClick={onSignupClick} className={`px-4 py-2 text-xs font-medium rounded-md transition-all ${dark ? 'bg-gray-100 text-gray-900 hover:bg-white' : 'bg-gray-900 text-white hover:bg-gray-800'}`}>Sign up</button>
      </div>
    </nav>
  );
}

function HeroSection({ dark, onSignupClick }: any) {
  return (
    <section className={`min-h-screen flex flex-col justify-center px-6 md:px-12 pt-32 pb-24 relative overflow-hidden ${dark ? 'bg-[#030712]' : 'bg-[#F9FAFB]'}`}>
      <div className="absolute inset-0 pointer-events-none" style={{ backgroundImage: `linear-gradient(${dark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)'} 1px, transparent 1px), linear-gradient(90deg, ${dark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)'} 1px, transparent 1px)`, backgroundSize: '64px 64px' }} />
      
      <div className="max-w-4xl relative z-10">
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-2 mb-8">
          <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-pulse" />
          <span className={`text-[10px] font-mono uppercase tracking-widest ${dark ? 'text-gray-500' : 'text-gray-400'}`}>System Operational v2.4</span>
        </motion.div>

        <motion.h1 initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1, duration: 0.5 }} className={`text-5xl md:text-7xl font-semibold tracking-tight leading-[1.05] mb-6 ${dark ? 'text-gray-100' : 'text-gray-900'}`}>
          Asset intelligence<br />
          <span className={dark ? 'text-gray-500' : 'text-gray-400'}>without blind spots.</span>
        </motion.h1>

        <motion.p initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.5 }} className={`text-sm md:text-base max-w-lg leading-relaxed mb-10 ${dark ? 'text-gray-400' : 'text-gray-500'}`}>
          Fingerprint, analyze, and act on every digital asset in your pipeline. Deterministic threat scoring and strict VRAM governance for enterprise teams.
        </motion.p>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3, duration: 0.5 }} className="flex gap-4">
          <button onClick={onSignupClick} className={`px-6 py-3 text-sm font-medium rounded-lg transition-all ${dark ? 'bg-gray-100 text-gray-900 hover:bg-white shadow-[0_0_20px_rgba(255,255,255,0.1)]' : 'bg-gray-900 text-white hover:bg-gray-800 shadow-[0_4px_14px_rgba(0,0,0,0.1)]'}`}>
            Deploy Platform
          </button>
          <button className={`px-6 py-3 text-sm font-medium rounded-lg border transition-all ${dark ? 'border-gray-800 text-gray-300 hover:bg-gray-900' : 'border-gray-200 text-gray-600 hover:bg-gray-50'}`}>
            Read Documentation
          </button>
        </motion.div>

        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5, duration: 0.5 }} className={`mt-24 pt-8 border-t flex flex-wrap gap-12 md:gap-24 ${dark ? 'border-gray-800' : 'border-gray-200'}`}>
          {STATS.map((s, i) => (
            <div key={i}>
              <p className={`text-2xl font-semibold mb-1 ${dark ? 'text-gray-100' : 'text-gray-900'}`}>{s.value}</p>
              <p className={`text-[10px] font-mono uppercase tracking-widest ${dark ? 'text-gray-500' : 'text-gray-400'}`}>{s.label}</p>
            </div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

function FlowchartSection({ dark }: any) {
  return (
    <section className={`py-24 md:py-32 px-6 md:px-12 border-t ${dark ? 'bg-[#030712] border-gray-800' : 'bg-white border-gray-100'}`}>
      <FadeUp>
        <h2 className={`text-2xl md:text-3xl font-semibold tracking-tight mb-16 ${dark ? 'text-gray-100' : 'text-gray-900'}`}>Execution Pipeline</h2>
      </FadeUp>
      <div className="flex overflow-x-auto pb-8 hide-scrollbar gap-4">
        {FLOW_NODES.map((node, i) => (
          <FadeUp key={node.id} delay={i * 0.1} className={`min-w-[240px] flex-1 p-6 border rounded-xl relative ${dark ? 'bg-[#0A0A0A] border-gray-800' : 'bg-[#F9FAFB] border-gray-100'}`}>
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center mb-6 ${dark ? 'bg-gray-900 text-gray-100 border border-gray-800' : 'bg-white text-gray-900 border border-gray-200 shadow-sm'}`}>
              <Icon name={node.icon} size={14} />
            </div>
            <p className={`text-[10px] font-mono uppercase tracking-widest mb-3 ${dark ? 'text-gray-600' : 'text-gray-400'}`}>Phase 0{node.id}</p>
            <p className={`text-sm font-semibold mb-1 ${dark ? 'text-gray-100' : 'text-gray-900'}`}>{node.label}</p>
            <p className={`text-xs ${dark ? 'text-gray-500' : 'text-gray-500'}`}>{node.sub}</p>
          </FadeUp>
        ))}
      </div>
    </section>
  );
}

function FeaturesSection({ dark }: any) {
  return (
    <section id="features-section" className={`py-24 md:py-32 px-6 md:px-12 border-t ${dark ? 'bg-[#030712] border-gray-800' : 'bg-[#F9FAFB] border-gray-200'}`}>
      <div className="max-w-6xl mx-auto">
        <FadeUp className="mb-16">
          <h2 className={`text-2xl md:text-3xl font-semibold tracking-tight ${dark ? 'text-gray-100' : 'text-gray-900'}`}>Architecture Overview</h2>
        </FadeUp>
        <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
          {FEATURES.map((f, i) => (
            <FadeUp key={i} delay={i * 0.1} className={`col-span-1 p-8 rounded-2xl border ${f.span === 7 ? 'md:col-span-7' : 'md:col-span-5'} ${dark ? 'bg-[#0A0A0A] border-gray-800' : 'bg-white border-gray-100 shadow-[0_8px_30px_rgb(0,0,0,0.04)]'}`}>
              <div className={`w-10 h-10 rounded-lg flex items-center justify-center mb-8 ${dark ? 'bg-gray-900 text-gray-100 border border-gray-800' : 'bg-gray-50 text-gray-900 border border-gray-200'}`}>
                <Icon name={f.icon} size={16} />
              </div>
              <h3 className={`text-lg font-semibold mb-3 tracking-tight whitespace-pre-line ${dark ? 'text-gray-100' : 'text-gray-900'}`}>{f.title}</h3>
              <p className={`text-sm leading-relaxed max-w-sm ${dark ? 'text-gray-400' : 'text-gray-500'}`}>{f.body}</p>
            </FadeUp>
          ))}
        </div>
      </div>
    </section>
  );
}

function TeamSection({ dark }: any) {
  return (
    <section id="team" className={`py-24 md:py-32 px-6 md:px-12 border-t ${dark ? 'bg-[#030712] border-gray-800' : 'bg-white border-gray-100'}`}>
      <div className="max-w-6xl mx-auto">
        <FadeUp className="mb-16">
          <h2 className={`text-2xl md:text-3xl font-semibold tracking-tight ${dark ? 'text-gray-100' : 'text-gray-900'}`}>Engineering Team</h2>
        </FadeUp>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {TEAM.map((member, i) => (
            <FadeUp key={i} delay={i * 0.1} className={`p-6 rounded-xl border ${dark ? 'bg-[#0A0A0A] border-gray-800' : 'bg-[#F9FAFB] border-gray-100'}`}>
              <div className={`w-8 h-8 rounded-md flex items-center justify-center text-xs font-mono font-semibold mb-6 ${dark ? 'bg-gray-800 text-gray-300' : 'bg-gray-200 text-gray-700'}`}>
                {member.init}
              </div>
              <p className={`text-sm font-semibold mb-1 ${dark ? 'text-gray-100' : 'text-gray-900'}`}>{member.name}</p>
              <p className={`text-[10px] font-mono uppercase tracking-widest mb-4 ${dark ? 'text-gray-500' : 'text-gray-400'}`}>{member.role}</p>
              <p className={`text-xs leading-relaxed ${dark ? 'text-gray-400' : 'text-gray-500'}`}>{member.bio}</p>
            </FadeUp>
          ))}
        </div>
      </div>
    </section>
  );
}

function Footer({ dark }: any) {
  return (
    <footer className={`py-12 px-6 md:px-12 border-t flex flex-col md:flex-row justify-between items-start md:items-center gap-6 ${dark ? 'bg-[#030712] border-gray-800 text-gray-500' : 'bg-white border-gray-200 text-gray-400'}`}>
      <div className="flex items-center gap-2">
        <Icon name="shield" size={16} />
        <span className="text-xs font-semibold tracking-tight">OVERWATCH SYSTEMS</span>
      </div>
      <div className="text-xs">
        &copy; {new Date().getFullYear()} Overwatch. All rights reserved.
      </div>
    </footer>
  );
}

export default function LandingScreen({ onLoginClick, onSignupClick }: { onLoginClick: () => void; onSignupClick: () => void }) {
  const [dark, setDark] = useState(() => {
    if (typeof window !== "undefined") return window.matchMedia("(prefers-color-scheme: dark)").matches;
    return false;
  });

  return (
    <div className={`min-h-screen font-sans selection:bg-gray-300 dark:selection:bg-gray-700 ${dark ? 'dark' : ''}`}>
      <Navbar dark={dark} onToggleDark={() => setDark(!dark)} onLoginClick={onLoginClick} onSignupClick={onSignupClick} />
      <HeroSection dark={dark} onSignupClick={onSignupClick} />
      <FlowchartSection dark={dark} />
      <FeaturesSection dark={dark} />
      <TeamSection dark={dark} />
      <Footer dark={dark} />
    </div>
  );
}
