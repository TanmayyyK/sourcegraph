// ============================================================
//  App.jsx  —  SourceGraph Overwatch  v3.0  "Production Overhaul"
// ============================================================
//  Stack: React 18 · Tailwind CSS · Framer Motion · React Flow · Lucide React
//
//  Install deps before use:
//    npm i framer-motion reactflow lucide-react
//  Tailwind must be configured in your project.
// ============================================================

import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
  MarkerType,
} from "reactflow";
import "reactflow/dist/style.css";
import {
  Shield, UploadCloud, X, Eye, AlertTriangle, CheckCircle2,
  Clock, Activity, Lock, User, Network, FileVideo, FileText,
  Search, LogOut, ChevronRight, ChevronDown, Layers, Cpu,
  Database, ArrowRight, BarChart2, ShieldCheck,
} from "lucide-react";


// ─── GLOBAL STYLES ───────────────────────────────────────────
function GlobalStyles() {
  return (
    <style>{`
      @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap');
      *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
      html, body {
        background: #09090b; color: #f0ede8;
        font-family: 'DM Sans', -apple-system, sans-serif;
        -webkit-font-smoothing: antialiased;
      }
      ::-webkit-scrollbar { width: 4px; }
      ::-webkit-scrollbar-track { background: transparent; }
      ::-webkit-scrollbar-thumb { background: rgba(240,237,232,0.08); border-radius: 4px; }
      #grain {
        position: fixed; inset: 0; pointer-events: none; z-index: 9999; opacity: 0.028;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
        background-size: 160px;
      }
      @keyframes pulse-dot { 0%,100% { opacity:1; } 50% { opacity:0.18; } }
      .pulse-dot { animation: pulse-dot 2.4s ease-in-out infinite; }
      @keyframes amber-pulse {
        0%,100% { box-shadow: 0 0 0 0 rgba(251,191,36,0.35); }
        50%      { box-shadow: 0 0 0 5px rgba(251,191,36,0); }
      }
      .badge-processing { animation: amber-pulse 1.9s ease-in-out infinite; }
      .react-flow__attribution { display: none !important; }
      .react-flow__controls {
        background: rgba(12,12,15,0.95) !important;
        border: 1px solid rgba(255,255,255,0.07) !important;
        border-radius: 10px !important; box-shadow: none !important;
      }
      .react-flow__controls-button {
        background: transparent !important; border: none !important;
        color: rgba(240,237,232,0.4) !important; border-bottom: 1px solid rgba(255,255,255,0.05) !important;
      }
      .react-flow__controls-button:hover {
        background: rgba(255,255,255,0.05) !important; color: #f0ede8 !important;
      }
      .react-flow__controls-button:last-child { border-bottom: none !important; }
    `}</style>
  );
}


// ─── DESIGN TOKENS ───────────────────────────────────────────
const ACCENT        = "#7c6cf5";
const ACCENT_DIM    = "rgba(124,108,245,0.09)";
const ACCENT_BORDER = "rgba(124,108,245,0.24)";
const AMBER         = "#f59e0b";
const GREEN         = "#34d399";
const RED           = "#f87171";


// ─── MOCK DATA ────────────────────────────────────────────────
const MOCK_DETECTIONS = [
  { id:"DET-8821", asset:"Oppenheimer_FinalCut_4K.mp4",   score:0.947, visual:0.961, text:0.924, status:"Completed",  time:"2m",  stream:"Stream α", type:"video" },
  { id:"DET-8822", asset:"Inception_Scene12_suspect.mp4", score:0,     visual:0,     text:0,     status:"Processing", time:"1m",  stream:"Stream β", type:"video" },
  { id:"DET-8820", asset:"podcast_ep44_unedited.mp3",     score:0.823, visual:null,  text:0.823, status:"Completed",  time:"7m",  stream:"Text Feed", type:"audio"},
  { id:"DET-8819", asset:"tutorial_screenrecord_hd.mp4",  score:0.541, visual:0.612, text:0.421, status:"Completed",  time:"12m", stream:"Stream β", type:"video" },
  { id:"DET-8823", asset:"documentary_seg03_raw.mp4",     score:0,     visual:0,     text:0,     status:"Failed",     time:"15m", stream:"Stream α", type:"video" },
  { id:"DET-8818", asset:"documentary_seg02_master.mp4",  score:0.991, visual:0.994, text:0.988, status:"Completed",  time:"23m", stream:"Stream α", type:"video" },
];


// ─── ANIMATION VARIANTS ───────────────────────────────────────
const fadeUp = {
  initial: { opacity:0, y:14 },
  animate: { opacity:1, y:0,  transition:{ duration:0.46, ease:[0.4,0,0.2,1] } },
  exit:    { opacity:0, y:-8, transition:{ duration:0.22 } },
};
const fadeIn = {
  initial: { opacity:0 },
  animate: { opacity:1, transition:{ duration:0.32 } },
  exit:    { opacity:0, transition:{ duration:0.2 } },
};
const stagger = {
  animate: { transition:{ staggerChildren:0.07, delayChildren:0.08 } },
};
const staggerItem = {
  initial: { opacity:0, y:10 },
  animate: { opacity:1, y:0, transition:{ duration:0.4, ease:[0.4,0,0.2,1] } },
};
const drawerVariants = {
  hidden:  { x:"100%", opacity:0 },
  visible: { x:0, opacity:1, transition:{ type:"spring", damping:28, stiffness:280 } },
  exit:    { x:"100%", opacity:0, transition:{ duration:0.26, ease:[0.4,0,1,1] } },
};
const modalVariants = {
  hidden:  { scale:0.94, opacity:0, y:12 },
  visible: { scale:1, opacity:1, y:0, transition:{ type:"spring", damping:24, stiffness:300 } },
  exit:    { scale:0.97, opacity:0, y:6, transition:{ duration:0.2 } },
};


// ─── UTILITY COMPONENTS ───────────────────────────────────────

function StatusBadge({ status }) {
  const cfg = {
    Completed:  { cls:"bg-emerald-500/10 text-emerald-400 border-emerald-500/20",  dot:"bg-emerald-400", extra:"" },
    Processing: { cls:"bg-amber-500/10  text-amber-400  border-amber-500/20",      dot:"bg-amber-400",   extra:"badge-processing" },
    Failed:     { cls:"bg-red-500/10    text-red-400    border-red-500/20",         dot:"bg-red-400",     extra:"" },
  }[status] || {};
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[11px] font-medium border ${cfg.cls} ${cfg.extra}`}>
      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${cfg.dot}`}/>
      {status}
    </span>
  );
}

function ScoreBar({ label, value, color, delay = 0.2 }) {
  return (
    <div>
      <div className="flex justify-between items-center mb-1.5">
        <span className="text-[11.5px] text-white/38">{label}</span>
        <span className="text-[12px] font-medium" style={{ color }}>
          {value != null && value > 0 ? `${(value * 100).toFixed(1)}%` : "N/A"}
        </span>
      </div>
      <div className="h-[3px] bg-white/[0.05] rounded-full overflow-hidden">
        <motion.div
          className="h-full rounded-full"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: value != null && value > 0 ? `${value * 100}%` : 0 }}
          transition={{ duration: 0.95, ease: [0.4, 0, 0.2, 1], delay }}
        />
      </div>
    </div>
  );
}

function ScoreRing({ score }) {
  const pct = Math.round(score * 100);
  const color = score >= 0.85 ? RED : score >= 0.65 ? AMBER : GREEN;
  const r = 30, circ = 2 * Math.PI * r;
  return (
    <div className="relative flex items-center justify-center" style={{ width: 76, height: 76 }}>
      <svg width="76" height="76" style={{ transform: "rotate(-90deg)" }}>
        <circle cx="38" cy="38" r={r} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="4" />
        <motion.circle
          cx="38" cy="38" r={r} fill="none"
          stroke={color} strokeWidth="4" strokeLinecap="round"
          strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: circ - (circ * pct / 100) }}
          transition={{ duration: 1.2, ease: [0.4, 0, 0.2, 1], delay: 0.3 }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-[17px] leading-none font-['Instrument_Serif']" style={{ color }}>{pct}%</span>
        <span className="text-[9px] text-white/22 mt-0.5 tracking-widest uppercase">Fused</span>
      </div>
    </div>
  );
}


// ─── REACT FLOW: CUSTOM NODES ─────────────────────────────────

function PirateNode({ data }) {
  return (
    <div
      className="rounded-xl border px-4 py-3.5 min-w-[210px]"
      style={{
        background: "rgba(248,113,113,0.07)",
        borderColor: "rgba(248,113,113,0.32)",
        boxShadow: "0 0 28px rgba(248,113,113,0.1), inset 0 1px 0 rgba(248,113,113,0.1)",
      }}
    >
      <div className="flex items-center gap-1.5 mb-2.5">
        <AlertTriangle size={11} color={RED} />
        <span className="text-[9.5px] font-bold tracking-widest uppercase" style={{ color: RED }}>Pirate Node</span>
      </div>
      <div className="text-[13px] font-medium text-[#f0ede8] leading-snug truncate max-w-[182px]">{data.label}</div>
      <div className="text-[11px] mt-1" style={{ color: "rgba(248,113,113,0.6)" }}>Suspect Asset</div>
      <Handle type="source" position={Position.Right}
        style={{ background: RED, border: "none", width: 8, height: 8, boxShadow: `0 0 8px ${RED}` }} />
    </div>
  );
}

function SourceNode({ data }) {
  return (
    <div
      className="rounded-xl border px-4 py-3.5 min-w-[210px]"
      style={{
        background: "rgba(124,108,245,0.07)",
        borderColor: "rgba(124,108,245,0.32)",
        boxShadow: "0 0 28px rgba(124,108,245,0.1), inset 0 1px 0 rgba(124,108,245,0.1)",
      }}
    >
      <div className="flex items-center gap-1.5 mb-2.5">
        <ShieldCheck size={11} color={ACCENT} />
        <span className="text-[9.5px] font-bold tracking-widest uppercase" style={{ color: ACCENT }}>Golden Master</span>
      </div>
      <div className="text-[13px] font-medium text-[#f0ede8] leading-snug truncate max-w-[182px]">{data.label}</div>
      <div className="text-[11px] mt-1" style={{ color: "rgba(124,108,245,0.6)" }}>Primary Source · Verified ✓</div>
      <Handle type="target" position={Position.Left}
        style={{ background: ACCENT, border: "none", width: 8, height: 8, boxShadow: `0 0 8px ${ACCENT}` }} />
    </div>
  );
}

function ConfidenceNode({ data }) {
  const color = data.score >= 0.85 ? RED : data.score >= 0.65 ? AMBER : GREEN;
  return (
    <div
      className="rounded-xl border px-4 py-3.5 text-center min-w-[155px]"
      style={{
        background: "rgba(15,15,18,0.97)",
        borderColor: "rgba(255,255,255,0.09)",
        boxShadow: "0 4px 32px rgba(0,0,0,0.6)",
      }}
    >
      <div className="text-[9.5px] font-bold tracking-widest uppercase text-white/25 mb-1.5">Fusion Score</div>
      <div className="text-[26px] font-['Instrument_Serif'] leading-none" style={{ color }}>
        {(data.score * 100).toFixed(1)}%
      </div>
      <div className="text-[10px] text-white/20 mt-1.5">
        V·{data.visual != null ? (data.visual * 100).toFixed(0) : "N/A"}% + T·{data.text != null ? (data.text * 100).toFixed(0) : "N/A"}%
      </div>
      <Handle type="target" position={Position.Left}
        style={{ background: "rgba(255,255,255,0.2)", border: "none", width: 6, height: 6 }} />
      <Handle type="source" position={Position.Right}
        style={{ background: "rgba(255,255,255,0.2)", border: "none", width: 6, height: 6 }} />
    </div>
  );
}

const NODE_TYPES = {
  pirateNode:     PirateNode,
  sourceNode:     SourceNode,
  confidenceNode: ConfidenceNode,
};


// ─── NEXUS GRAPH ──────────────────────────────────────────────

function NexusGraph({ detection }) {
  const initialNodes = [
    {
      id: "pirate", type: "pirateNode",
      position: { x: 40, y: 160 },
      data: { label: detection.asset },
    },
    {
      id: "confidence", type: "confidenceNode",
      position: { x: 320, y: 168 },
      data: { score: detection.score, visual: detection.visual, text: detection.text },
    },
    {
      id: "golden", type: "sourceNode",
      position: { x: 570, y: 160 },
      data: { label: "Oppenheimer_GoldenMaster_4K.mp4" },
    },
  ];
  const initialEdges = [
    {
      id: "e-pirate-conf", source: "pirate", target: "confidence",
      type: "smoothstep", animated: true,
      style: { stroke: RED, strokeWidth: 2.5 },
      markerEnd: { type: MarkerType.ArrowClosed, color: RED, width: 16, height: 16 },
    },
    {
      id: "e-conf-golden", source: "confidence", target: "golden",
      type: "smoothstep", animated: true,
      style: { stroke: ACCENT, strokeWidth: 2.5 },
      markerEnd: { type: MarkerType.ArrowClosed, color: ACCENT, width: 16, height: 16 },
    },
  ];

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  return (
    <ReactFlow
      nodes={nodes} edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      nodeTypes={NODE_TYPES}
      fitView fitViewOptions={{ padding: 0.35 }}
      minZoom={0.4} maxZoom={2.5}
      proOptions={{ hideAttribution: true }}
      style={{ background: "transparent" }}
    >
      <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="rgba(255,255,255,0.035)" />
      <Controls position="bottom-right" />
    </ReactFlow>
  );
}


// ─── NEXUS MODAL ──────────────────────────────────────────────

function NexusModal({ detection, onClose }) {
  return (
    <motion.div
      className="fixed inset-0 z-[70] flex flex-col"
      style={{ background: "rgba(9,9,11,0.97)", backdropFilter: "blur(32px)" }}
      variants={fadeIn} initial="initial" animate="animate" exit="exit"
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-7 py-4 flex-shrink-0"
        style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-xl flex items-center justify-center"
            style={{ background: ACCENT_DIM, border: `1px solid ${ACCENT_BORDER}` }}
          >
            <Network size={14} style={{ color: ACCENT }} />
          </div>
          <div>
            <div className="text-[14px] font-medium text-[#f0ede8]">Nexus Attribution Graph</div>
            <div className="text-[11px] text-white/30 font-mono truncate max-w-[460px]">{detection.asset}</div>
          </div>
        </div>
        <motion.button
          onClick={onClose}
          className="flex items-center gap-2 px-3 py-1.5 rounded-xl text-[12px] text-white/38 border border-white/[0.07] hover:text-white/65 hover:bg-white/[0.04] transition-all"
          whileHover={{ y: -1 }} whileTap={{ scale: 0.97 }}
        >
          <X size={12} /> Close Graph
        </motion.button>
      </div>

      {/* Graph canvas */}
      <div className="flex-1">
        <NexusGraph detection={detection} />
      </div>

      {/* Legend */}
      <div
        className="px-7 py-3 flex items-center gap-8 text-[11px] text-white/28 flex-shrink-0"
        style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}
      >
        <span className="text-white/18 font-medium tracking-wider uppercase text-[10px]">Legend</span>
        {[
          { color: RED,    label: "Suspect → Confidence Score" },
          { color: ACCENT, label: "Confidence Score → Golden Master" },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-2">
            <span className="w-5 h-0.5 rounded-full" style={{ background: color }} />
            <span>{label}</span>
          </div>
        ))}
        <div className="flex items-center gap-2 ml-auto">
          <span className="w-3 h-3 rounded" style={{ background: `${ACCENT}22`, border: `1px solid ${ACCENT}44` }} />
          <span>Verified Source</span>
          <span className="w-3 h-3 rounded ml-3" style={{ background: `${RED}22`, border: `1px solid ${RED}44` }} />
          <span>Pirate Asset</span>
        </div>
      </div>
    </motion.div>
  );
}


// ─── DEEP INSIGHTS DRAWER ─────────────────────────────────────

function Drawer({ detection, onClose, onNexus }) {
  const scoreColor = detection.score >= 0.85 ? RED : detection.score >= 0.65 ? AMBER : GREEN;

  return (
    <motion.div
      className="fixed top-0 right-0 h-full z-50 flex flex-col overflow-hidden"
      style={{
        width: "min(490px, 100vw)",
        background: "rgba(10,10,13,0.98)",
        borderLeft: "1px solid rgba(255,255,255,0.07)",
        backdropFilter: "blur(30px)",
      }}
      variants={drawerVariants} initial="hidden" animate="visible" exit="exit"
    >
      {/* Header */}
      <div className="flex items-start justify-between p-6 flex-shrink-0" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
        <div className="flex-1 min-w-0 pr-4">
          <div className="text-[10px] uppercase tracking-[0.1em] text-white/22 mb-1.5">Deep Insights Panel</div>
          <div className="text-[14.5px] font-medium text-[#f0ede8] truncate">{detection.asset}</div>
          <div className="text-[11px] text-white/28 mt-1 font-mono">{detection.id}</div>
        </div>
        <motion.button
          onClick={onClose}
          className="w-8 h-8 rounded-xl flex items-center justify-center text-white/28 border border-white/[0.07] hover:text-white/65 hover:bg-white/[0.04] transition-all flex-shrink-0"
          whileTap={{ scale: 0.94 }}
        >
          <X size={14} />
        </motion.button>
      </div>

      {/* Scrollable body */}
      <div className="flex-1 overflow-y-auto p-6 space-y-7">

        {/* Score Ring + Status */}
        <div className="flex items-center gap-6">
          <ScoreRing score={detection.score} />
          <div>
            <div className="mb-2.5"><StatusBadge status={detection.status} /></div>
            <div className="text-[12.5px] text-white/32 leading-relaxed max-w-[260px]">
              Fused match confidence across visual & text modalities, weighted via adaptive α coefficient.
            </div>
          </div>
        </div>

        {/* Fused Score Formula */}
        <div>
          <div className="text-[10px] uppercase tracking-[0.1em] text-white/22 mb-3">Fused Scoring Model</div>
          <div
            className="rounded-xl p-4 font-mono text-[12px] space-y-2 mb-4"
            style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.06)" }}
          >
            <div style={{ color: GREEN }}>S_fused = α · S_visual + (1−α) · S_text</div>
            <div className="text-white/22 text-[10.5px] pt-1">α = 0.65 (video)&nbsp;·&nbsp;threshold = 0.80 (confirmation)</div>
          </div>
          <div className="space-y-4">
            <ScoreBar label="Visual Score  (α = 65%)"  value={detection.visual} color={ACCENT} delay={0.15} />
            <ScoreBar label="Text Score  (1−α = 35%)"  value={detection.text}   color={AMBER}  delay={0.25} />
            <ScoreBar label="Fused Confidence"          value={detection.score}  color={scoreColor} delay={0.35} />
          </div>
        </div>

        {/* Vector Math */}
        <div>
          <div className="text-[10px] uppercase tracking-[0.1em] text-white/22 mb-3">Vector Mathematics</div>
          <div
            className="rounded-xl p-4 font-mono text-[12px] space-y-2"
            style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.06)" }}
          >
            <div className="text-white/22 text-[10.5px]">// Cosine similarity (semantic alignment)</div>
            <div style={{ color: AMBER }}>cosine(A, B) = (A · B) / (‖A‖ × ‖B‖)</div>
            <div className="text-white/22 text-[10.5px] pt-2">// Euclidean distance (structural proximity)</div>
            <div style={{ color: ACCENT }}>euclidean(A, B) = √Σ(Aᵢ − Bᵢ)²</div>
          </div>
        </div>

        {/* Asset Metadata Grid */}
        <div>
          <div className="text-[10px] uppercase tracking-[0.1em] text-white/22 mb-3">Asset Metadata</div>
          <div className="grid grid-cols-2 gap-2.5">
            {[
              { label: "Detection ID",  value: detection.id },
              { label: "Stream",        value: detection.stream },
              { label: "Ingested",      value: `${detection.time} ago` },
              { label: "Asset Type",    value: detection.type === "video" ? "Video (MP4)" : detection.type === "audio" ? "Audio (MP3)" : "Document" },
              { label: "Vector Space",  value: detection.visual != null ? "512-D Visual" : "384-D Text" },
              { label: "Confidence",    value: detection.score > 0 ? `${(detection.score * 100).toFixed(1)}%` : "—" },
            ].map(({ label, value }) => (
              <div
                key={label}
                className="rounded-xl p-3"
                style={{ background: "rgba(255,255,255,0.022)", border: "1px solid rgba(255,255,255,0.055)" }}
              >
                <div className="text-[9.5px] text-white/22 uppercase tracking-wider mb-1">{label}</div>
                <div className="text-[12.5px] text-[#f0ede8] font-mono">{value}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer CTA */}
      <div className="p-5 flex-shrink-0" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
        <motion.button
          onClick={onNexus}
          className="w-full flex items-center justify-center gap-2.5 py-3 rounded-xl text-[13.5px] font-medium text-[#f0ede8] border transition-all"
          style={{ borderColor: ACCENT_BORDER, background: ACCENT_DIM }}
          whileHover={{ y: -1, background: "rgba(124,108,245,0.14)" }}
          whileTap={{ scale: 0.98 }}
        >
          <Network size={14} style={{ color: ACCENT }} />
          View Nexus Lineage Graph
          <ChevronRight size={12} className="text-white/30" />
        </motion.button>
      </div>
    </motion.div>
  );
}


// ─── NAVBAR ───────────────────────────────────────────────────

function Navbar({ page, nav, user, onLogout }) {
  const isDash = ["dashboard", "insights"].includes(page);

  return (
    <nav
      className="fixed top-0 left-0 right-0 z-40 h-[54px] flex items-center px-7"
      style={{ background: "rgba(9,9,11,0.86)", backdropFilter: "blur(16px)", borderBottom: "1px solid rgba(255,255,255,0.055)" }}
    >
      <div className="flex items-center justify-between w-full max-w-[1220px] mx-auto">

        {/* Logo */}
        <button
          onClick={() => nav("landing")}
          className="flex items-center gap-2.5 transition-opacity hover:opacity-80"
        >
          <div
            className="w-[22px] h-[22px] rounded-[6px] flex items-center justify-center"
            style={{ background: ACCENT }}
          >
            <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
              <circle cx="5" cy="5" r="1.65" fill="white" />
              <circle cx="5" cy="5" r="4" stroke="white" strokeWidth="1.1" fill="none" />
            </svg>
          </div>
          <span className="text-[14px] font-semibold text-[#f0ede8] tracking-tight">Overwatch</span>
        </button>

        {/* Nav links */}
        <div className="flex items-center gap-7">
          {isDash ? (
            <>
              <button
                onClick={() => nav("dashboard")}
                className={`text-[13.5px] transition-colors ${page === "dashboard" ? "text-[#f0ede8]" : "text-white/38 hover:text-white/65"}`}
              >
                Command Center
              </button>
              <button
                onClick={() => nav("insights")}
                className={`text-[13.5px] transition-colors ${page === "insights" ? "text-[#f0ede8]" : "text-white/38 hover:text-white/65"}`}
              >
                Insights
              </button>
            </>
          ) : (
            <>
              <button onClick={() => nav("landing")}    className="text-[13.5px] text-white/38 hover:text-white/65 transition-colors">Overview</button>
              <button onClick={() => nav("dashboard")}  className="text-[13.5px] text-white/38 hover:text-white/65 transition-colors">Dashboard</button>
            </>
          )}
        </div>

        {/* Right cluster */}
        <div className="flex items-center gap-3">
          {isDash && (
            <div className="flex items-center gap-1.5 text-[11px] text-white/28">
              <span className="w-1.5 h-1.5 rounded-full pulse-dot" style={{ background: GREEN }} />
              Live
            </div>
          )}

          {user && (
            <>
              <div
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-[12px] text-white/45"
                style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.07)" }}
              >
                <User size={11} /> {user.name}
              </div>
              <motion.button
                onClick={onLogout}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-[12px] text-white/30 hover:text-white/55 transition-all"
                style={{ border: "1px solid rgba(255,255,255,0.06)" }}
                whileTap={{ scale: 0.96 }}
              >
                <LogOut size={11} />
              </motion.button>
            </>
          )}

          <motion.button
            onClick={() => nav("ingestion")}
            className="flex items-center gap-2 px-4 py-[7px] rounded-xl text-[13px] font-medium text-[#09090b]"
            style={{ background: "#f0ede8" }}
            whileHover={{ opacity: 0.88, y: -1 }}
            whileTap={{ scale: 0.97 }}
          >
            + Ingest
          </motion.button>
        </div>
      </div>
    </nav>
  );
}


// ─── ROLE SELECT MODAL ────────────────────────────────────────

function RoleModal({ onSelect, onClose }) {
  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(9,9,11,0.82)", backdropFilter: "blur(22px)" }}
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      onClick={onClose}
    >
      <motion.div
        className="w-full max-w-[530px] rounded-2xl p-8"
        style={{ background: "rgba(13,13,16,0.99)", border: "1px solid rgba(255,255,255,0.08)", backdropFilter: "blur(40px)" }}
        variants={modalVariants} initial="hidden" animate="visible" exit="exit"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal header */}
        <div className="text-center mb-8">
          <div
            className="w-11 h-11 rounded-xl mx-auto mb-4 flex items-center justify-center"
            style={{ background: ACCENT_DIM, border: `1px solid ${ACCENT_BORDER}` }}
          >
            <Layers size={18} style={{ color: ACCENT }} />
          </div>
          <h2 className="font-['Instrument_Serif'] text-[27px] text-[#f0ede8] mb-2">Select Workflow</h2>
          <p className="text-[13px] text-white/35 leading-relaxed max-w-[300px] mx-auto">
            Choose your role to configure the ingestion engine and session context.
          </p>
        </div>

        {/* Role cards */}
        <div className="grid grid-cols-2 gap-3 mb-6">
          {/* PRODUCER */}
          <motion.button
            onClick={() => onSelect("PRODUCER")}
            className="rounded-xl p-5 text-left transition-all duration-200 group"
            style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.07)" }}
            whileHover={{ y: -2, borderColor: ACCENT_BORDER, background: ACCENT_DIM }}
            whileTap={{ scale: 0.98 }}
          >
            <div
              className="w-9 h-9 rounded-xl mb-4 flex items-center justify-center"
              style={{ background: ACCENT_DIM, border: `1px solid ${ACCENT_BORDER}` }}
            >
              <Shield size={16} style={{ color: ACCENT }} />
            </div>
            <div className="text-[14px] font-semibold text-[#f0ede8] mb-1.5 tracking-tight">PRODUCER</div>
            <div className="text-[11.5px] text-white/33 leading-relaxed">Ingest and protect Golden Master media assets into the secured library.</div>
          </motion.button>

          {/* AUDITOR */}
          <motion.button
            onClick={() => onSelect("AUDITOR")}
            className="rounded-xl p-5 text-left transition-all duration-200"
            style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.07)" }}
            whileHover={{ y: -2, borderColor: "rgba(245,158,11,0.28)", background: "rgba(245,158,11,0.06)" }}
            whileTap={{ scale: 0.98 }}
          >
            <div
              className="w-9 h-9 rounded-xl mb-4 flex items-center justify-center"
              style={{ background: "rgba(245,158,11,0.09)", border: "1px solid rgba(245,158,11,0.24)" }}
            >
              <Search size={16} style={{ color: AMBER }} />
            </div>
            <div className="text-[14px] font-semibold text-[#f0ede8] mb-1.5 tracking-tight">AUDITOR</div>
            <div className="text-[11.5px] text-white/33 leading-relaxed">Upload suspect clips for multi-modal piracy inference against the library.</div>
          </motion.button>
        </div>

        <button onClick={onClose} className="w-full text-center text-[12px] text-white/22 hover:text-white/42 transition-colors py-1">
          Cancel
        </button>
      </motion.div>
    </motion.div>
  );
}


// ─── LOGIN VIEW ───────────────────────────────────────────────

function LoginView({ role, onSuccess, onBack }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);

  const isProducer = role === "PRODUCER";
  const roleColor  = isProducer ? ACCENT : AMBER;
  const roleBg     = isProducer ? ACCENT_DIM : "rgba(245,158,11,0.09)";
  const roleBorder = isProducer ? ACCENT_BORDER : "rgba(245,158,11,0.24)";

  const handleLogin = async () => {
    setError(""); setLoading(true);
    await new Promise((r) => setTimeout(r, 950));
    if (username.trim() === "Tanmay" && password === "overwatch") {
      onSuccess({ name: "Tanmay" });
    } else {
      setError("Invalid credentials · Hint: username Tanmay, password overwatch");
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6" style={{ background: "#09090b" }}>
      {/* Ambient glow behind form */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div
          className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[680px] h-[480px] rounded-full"
          style={{ background: `radial-gradient(ellipse, ${roleColor}22 0%, transparent 68%)` }}
        />
      </div>

      <motion.div className="w-full max-w-[400px]" variants={fadeUp} initial="initial" animate="animate">
        {/* Back button */}
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-[12.5px] text-white/28 hover:text-white/52 transition-colors mb-9"
        >
          ← Back to role selection
        </button>

        {/* Role badge */}
        <span
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-bold tracking-widest uppercase border mb-6"
          style={{ color: roleColor, background: roleBg, borderColor: roleBorder }}
        >
          {isProducer ? <Shield size={9} /> : <Search size={9} />}
          {role} · Session
        </span>

        <h1 className="font-['Instrument_Serif'] text-[34px] text-[#f0ede8] mb-2 leading-tight tracking-tight">Authenticate</h1>
        <p className="text-[13.5px] text-white/33 mb-9 leading-relaxed">
          Access the SourceGraph Overwatch command interface.
        </p>

        <div className="space-y-3">
          {/* Username */}
          <div className="relative">
            <User size={12} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-white/22 pointer-events-none" />
            <input
              type="text" value={username} onChange={(e) => setUsername(e.target.value)}
              placeholder="Username"
              className="w-full pl-10 pr-4 py-3 rounded-xl text-[13.5px] text-[#f0ede8] placeholder-white/20 outline-none transition-all"
              style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)" }}
              onFocus={(e) => { e.target.style.borderColor = "rgba(255,255,255,0.18)"; }}
              onBlur={(e)  => { e.target.style.borderColor = "rgba(255,255,255,0.08)"; }}
              onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            />
          </div>

          {/* Password */}
          <div className="relative">
            <Lock size={12} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-white/22 pointer-events-none" />
            <input
              type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="Password"
              className="w-full pl-10 pr-4 py-3 rounded-xl text-[13.5px] text-[#f0ede8] placeholder-white/20 outline-none transition-all"
              style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)" }}
              onFocus={(e) => { e.target.style.borderColor = "rgba(255,255,255,0.18)"; }}
              onBlur={(e)  => { e.target.style.borderColor = "rgba(255,255,255,0.08)"; }}
              onKeyDown={(e) => e.key === "Enter" && handleLogin()}
            />
          </div>

          {/* Error */}
          <AnimatePresence>
            {error && (
              <motion.div
                className="flex items-start gap-2 text-[12px] text-red-400 px-3 py-2.5 rounded-xl"
                style={{ background: "rgba(248,113,113,0.06)", border: "1px solid rgba(248,113,113,0.18)" }}
                initial={{ opacity: 0, y: -5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
              >
                <AlertTriangle size={11} className="flex-shrink-0 mt-0.5" />
                {error}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Submit */}
          <motion.button
            onClick={handleLogin} disabled={loading}
            className="w-full py-3 rounded-xl text-[13.5px] font-medium text-[#09090b] flex items-center justify-center gap-2 transition-opacity"
            style={{ background: loading ? "rgba(240,237,232,0.55)" : "#f0ede8" }}
            whileHover={!loading ? { opacity: 0.88, y: -1 } : {}}
            whileTap={!loading ? { scale: 0.98 } : {}}
          >
            {loading ? (
              <>
                <span className="w-4 h-4 border-2 border-[#09090b]/25 border-t-[#09090b] rounded-full animate-spin" />
                Authenticating…
              </>
            ) : (
              <>
                <Shield size={13} />
                Access Command Center
              </>
            )}
          </motion.button>
        </div>
      </motion.div>
    </div>
  );
}


// ─── INGESTION VIEW ───────────────────────────────────────────

const INGESTION_STAGES = [
  "Extracting Frames…",
  "Vectorizing (512-D)…",
  "Synchronizing with Vector Store…",
  "Complete",
];

function IngestionView({ role, nav, onFileIngested }) {
  const [drag, setDrag]       = useState(false);
  const [stageIdx, setStageIdx] = useState(-1);  // -1 = idle
  const [progress, setProgress] = useState(0);
  const [fileName, setFileName] = useState("");

  const isProducer  = role === "PRODUCER";
  const roleColor   = isProducer ? ACCENT : AMBER;
  const roleBg      = isProducer ? ACCENT_DIM : "rgba(245,158,11,0.08)";
  const roleBorder  = isProducer ? ACCENT_BORDER : "rgba(245,158,11,0.22)";

  const simulate = useCallback((name) => {
    setFileName(name);
    setStageIdx(0);
    setProgress(0);

    const STAGE_THRESHOLDS = [0, 27, 64, 91, 100];
    let currentStage = 0;
    let prog = 0;

    const tick = setInterval(() => {
      prog += Math.random() * 3.2 + 1.2;
      if (prog >= STAGE_THRESHOLDS[currentStage + 1] && currentStage < 3) {
        currentStage += 1;
        setStageIdx(currentStage);
      }
      if (prog >= 100) {
        prog = 100;
        clearInterval(tick);
        setStageIdx(3);
        setTimeout(() => onFileIngested && onFileIngested(name), 500);
      }
      setProgress(Math.min(prog, 100));
    }, 115);
  }, [onFileIngested]);

  const onDrop = useCallback((e) => {
    e.preventDefault(); setDrag(false);
    const f = e.dataTransfer.files[0];
    if (f) simulate(f.name);
  }, [simulate]);

  const isDone = stageIdx === 3 && progress >= 99;

  return (
    <div className="min-h-screen pt-[54px] flex flex-col items-center justify-center p-10" style={{ background: "#09090b" }}>
      {/* Ambient glow */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div
          className="absolute top-[40%] left-1/2 -translate-x-1/2 -translate-y-1/2 w-[760px] h-[520px] rounded-full"
          style={{ background: `radial-gradient(ellipse, ${roleColor}18 0%, transparent 65%)` }}
        />
      </div>

      <div className="w-full max-w-[570px]">
        <motion.div variants={fadeUp} initial="initial" animate="animate">

          {/* Role badge */}
          <span
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-bold tracking-widest uppercase border mb-5"
            style={{ color: roleColor, background: roleBg, borderColor: roleBorder }}
          >
            {isProducer ? <Shield size={9} /> : <Search size={9} />}
            {role} Mode
          </span>

          <h1 className="font-['Instrument_Serif'] text-[33px] text-[#f0ede8] mb-2.5 leading-tight tracking-tight">
            {isProducer ? "Ingest Golden Master" : "Run Suspect Inference"}
          </h1>
          <p className="text-[13.5px] text-white/33 mb-9 leading-relaxed max-w-[420px]">
            {isProducer
              ? "Upload your protected master asset. Embeddings will be extracted and stored in the secured golden vector library."
              : "Upload a suspect clip for multi-modal piracy inference across 512-D visual and 384-D text embedding spaces."}
          </p>

          {/* ── Idle drop zone ── */}
          {stageIdx === -1 && (
            <motion.div
              className="relative rounded-2xl border-2 border-dashed flex flex-col items-center justify-center py-16 px-8 text-center cursor-pointer transition-all duration-200"
              style={{ borderColor: drag ? roleColor : "rgba(255,255,255,0.09)", background: drag ? roleBg : "rgba(255,255,255,0.012)" }}
              onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
              onDragLeave={() => setDrag(false)}
              onDrop={onDrop}
              onClick={() => simulate(`suspect_clip_${Date.now()}.mp4`)}
              whileHover={{ borderColor: "rgba(255,255,255,0.16)", background: "rgba(255,255,255,0.022)" }}
              whileTap={{ scale: 0.99 }}
            >
              <motion.div
                className="w-[72px] h-[72px] rounded-2xl flex items-center justify-center mb-5"
                style={{ background: roleBg, border: `1px solid ${roleBorder}` }}
                animate={{ scale: drag ? 1.1 : 1 }}
                transition={{ type: "spring", stiffness: 280 }}
              >
                <UploadCloud size={28} style={{ color: roleColor }} />
              </motion.div>
              <div className="text-[16px] font-medium text-[#f0ede8] mb-2">
                {drag ? "Release to ingest" : "Drop your file here"}
              </div>
              <div className="text-[13px] text-white/28 mb-5">or click to simulate an upload</div>
              <div
                className="text-[11px] text-white/20 px-4 py-1.5 rounded-full"
                style={{ border: "1px solid rgba(255,255,255,0.06)" }}
              >
                MP4 · MKV · MOV · MP3 · WAV · TXT · PDF
              </div>
            </motion.div>
          )}

          {/* ── In-progress ── */}
          {stageIdx >= 0 && !isDone && (
            <div className="py-6">
              <div className="text-[13px] text-white/40 text-center mb-6">
                Processing <span className="text-[#f0ede8]">{fileName}</span>
              </div>

              {/* Stage pills */}
              <div className="flex flex-wrap items-center gap-2 justify-center mb-8">
                {INGESTION_STAGES.slice(0, 3).map((s, i) => (
                  <div
                    key={i}
                    className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] border transition-all duration-400 ${
                      i < stageIdx
                        ? "text-white/20 border-white/[0.05]"
                        : i === stageIdx
                        ? "text-[#f0ede8] border-white/14 bg-white/[0.04]"
                        : "text-white/18 border-white/[0.04]"
                    }`}
                  >
                    {i < stageIdx
                      ? <CheckCircle2 size={9} color={GREEN} />
                      : i === stageIdx
                      ? <Cpu size={9} style={{ color: roleColor }} />
                      : <Clock size={9} />}
                    {s}
                  </div>
                ))}
              </div>

              {/* Progress bar */}
              <div className="space-y-2.5">
                <div className="flex justify-between text-[11px] text-white/25">
                  <span>{INGESTION_STAGES[Math.min(stageIdx, 3)]}</span>
                  <span>{Math.floor(progress)}%</span>
                </div>
                <div className="h-[3px] bg-white/[0.06] rounded-full overflow-hidden">
                  <motion.div
                    className="h-full rounded-full"
                    style={{ background: `linear-gradient(90deg, ${roleColor}88, ${roleColor})` }}
                    animate={{ width: `${progress}%` }}
                    transition={{ duration: 0.12, ease: "linear" }}
                  />
                </div>
              </div>
            </div>
          )}

          {/* ── Done ── */}
          {isDone && (
            <motion.div
              className="flex flex-col items-center text-center py-8"
              variants={fadeUp} initial="initial" animate="animate"
            >
              <motion.div
                className="w-[64px] h-[64px] rounded-full flex items-center justify-center mb-6"
                style={{ background: "rgba(52,211,153,0.09)", border: "1px solid rgba(52,211,153,0.24)" }}
                initial={{ scale: 0.4, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: "spring", stiffness: 240, damping: 18 }}
              >
                <CheckCircle2 size={28} color={GREEN} />
              </motion.div>
              <h2 className="font-['Instrument_Serif'] text-[30px] text-[#f0ede8] mb-2 tracking-tight">
                {isProducer ? "Master Ingested" : "Inference Complete"}
              </h2>
              <p className="text-[13.5px] text-white/33 mb-8 max-w-[340px] leading-relaxed">
                <span className="text-[#f0ede8]">{fileName}</span> has been processed and is now active in the analysis pipeline.
              </p>
              <div className="flex gap-3">
                <motion.button
                  onClick={() => nav("dashboard")}
                  className="px-5 py-2.5 rounded-xl text-[13.5px] font-medium text-[#09090b]"
                  style={{ background: "#f0ede8" }}
                  whileHover={{ opacity: 0.88, y: -1 }}
                  whileTap={{ scale: 0.97 }}
                >
                  View in Command Center
                </motion.button>
                <motion.button
                  onClick={() => { setStageIdx(-1); setProgress(0); setFileName(""); }}
                  className="px-5 py-2.5 rounded-xl text-[13.5px] text-white/42 transition-all"
                  style={{ border: "1px solid rgba(255,255,255,0.09)" }}
                  whileHover={{ y: -1, borderColor: "rgba(255,255,255,0.16)", color: "rgba(240,237,232,0.65)" }}
                  whileTap={{ scale: 0.97 }}
                >
                  Ingest Another
                </motion.button>
              </div>
            </motion.div>
          )}

        </motion.div>
      </div>
    </div>
  );
}


// ─── LANDING VIEW ─────────────────────────────────────────────

function LandingView({ nav, onLaunch }) {
  return (
    <div className="min-h-screen" style={{ background: "#09090b" }}>

      {/* Ambient glows */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div
          className="absolute top-[-8%] left-1/2 -translate-x-1/2 w-[950px] h-[650px] rounded-full"
          style={{ background: `radial-gradient(ellipse, ${ACCENT}1a 0%, transparent 63%)` }}
        />
        <div
          className="absolute top-[65%] left-[18%] w-[420px] h-[300px] rounded-full"
          style={{ background: `radial-gradient(ellipse, ${AMBER}0d 0%, transparent 70%)` }}
        />
      </div>

      {/* Hero */}
      <section className="relative max-w-[1220px] mx-auto px-7 pt-[130px] pb-[90px] text-center">
        <motion.div variants={stagger} initial="initial" animate="animate">

          {/* Pill badge */}
          <motion.div variants={staggerItem} className="flex justify-center mb-8">
            <span
              className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-[12px] font-medium"
              style={{ color: ACCENT, background: ACCENT_DIM, border: `1px solid ${ACCENT_BORDER}` }}
            >
              <span className="w-1.5 h-1.5 rounded-full" style={{ background: ACCENT }} />
              Distributed Anti-Piracy Intelligence Engine
            </span>
          </motion.div>

          {/* Headline */}
          <motion.h1
            variants={staggerItem}
            className="font-['Instrument_Serif'] leading-[1.05] tracking-[-0.026em] text-[#f0ede8] mb-6"
            style={{ fontSize: "clamp(46px, 7vw, 82px)" }}
          >
            Intelligence that watches<br />
            <em style={{ color: ACCENT }}>every copy.</em>
          </motion.h1>

          {/* Sub-headline */}
          <motion.p
            variants={staggerItem}
            className="text-[17px] text-white/42 max-w-[500px] mx-auto mb-10 leading-[1.74] font-light"
          >
            Multi-modal vector similarity across 512-D visual streams and 384-D text
            embeddings — detecting structural piracy the moment it surfaces.
          </motion.p>

          {/* CTAs */}
          <motion.div variants={staggerItem} className="flex gap-3 justify-center flex-wrap">
            <motion.button
              onClick={onLaunch}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-[14px] font-medium text-[#09090b]"
              style={{ background: "#f0ede8" }}
              whileHover={{ opacity: 0.88, y: -1 }} whileTap={{ scale: 0.97 }}
            >
              Launch Engine <ArrowRight size={14} />
            </motion.button>
            <motion.button
              onClick={() => nav("dashboard")}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-[14px] text-white/48 transition-all"
              style={{ border: "1px solid rgba(255,255,255,0.1)" }}
              whileHover={{ y: -1, borderColor: "rgba(255,255,255,0.18)", color: "rgba(240,237,232,0.72)" }}
              whileTap={{ scale: 0.97 }}
            >
              View Command Center
            </motion.button>
          </motion.div>
        </motion.div>
      </section>

      {/* Stats strip */}
      <div style={{ borderTop: "1px solid rgba(255,255,255,0.055)", borderBottom: "1px solid rgba(255,255,255,0.055)" }}>
        <div className="max-w-[1220px] mx-auto grid grid-cols-4">
          {[
            ["512-D",   "Visual vector space"],
            ["384-D",   "Text embedding space"],
            ["<50ms",   "Avg. match latency"],
            ["99.97%",  "Detection precision"],
          ].map(([v, l], i) => (
            <motion.div
              key={i}
              className={`px-8 py-7 ${i < 3 ? "border-r" : ""}`}
              style={{ borderColor: "rgba(255,255,255,0.055)" }}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 + i * 0.09, duration: 0.48 }}
            >
              <div className="font-['Instrument_Serif'] text-[30px] text-[#f0ede8] mb-1">{v}</div>
              <div className="text-[12px] text-white/30 font-light">{l}</div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* How it works */}
      <section className="max-w-[1220px] mx-auto px-7 py-[90px]">
        <div className="mb-12">
          <div className="text-[11px] tracking-[0.1em] uppercase font-semibold mb-3" style={{ color: ACCENT }}>How it works</div>
          <h2 className="font-['Instrument_Serif'] text-[38px] text-[#f0ede8] tracking-tight">Three phases. Zero gaps.</h2>
        </div>

        <div className="grid grid-cols-3 gap-4">
          {[
            { n:"01", title:"Ingest",   icon:<UploadCloud size={15} style={{ color:ACCENT }}/>,
              desc:"Upload video, audio, or transcript. The system extracts frame-level visual embeddings and text vectors asynchronously via isolated buffer workers." },
            { n:"02", title:"Analyze",  icon:<Cpu size={15} style={{ color:ACCENT }}/>,
              desc:"Dimensional reduction maps each asset into shared vector space. Cosine and Euclidean distances are computed against the protected golden source library." },
            { n:"03", title:"Surface",  icon:<Activity size={15} style={{ color:ACCENT }}/>,
              desc:"Fused similarity scores above the threshold trigger instant alerts. Attribution lineage traces each match back to its exact source frame with full confidence." },
          ].map((s, i) => (
            <motion.div
              key={i}
              className="rounded-2xl p-7 transition-all duration-200"
              style={{ background: "rgba(255,255,255,0.018)", border: "1px solid rgba(255,255,255,0.065)" }}
              initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.55 + i * 0.11, duration: 0.48 }}
              whileHover={{ y: -3, background: "rgba(255,255,255,0.026)", borderColor: "rgba(255,255,255,0.1)" }}
            >
              <div className="flex justify-between items-start mb-6">
                <span className="text-[11px] text-white/16 font-medium tracking-[0.05em]">{s.n}</span>
                {s.icon}
              </div>
              <h3 className="text-[16px] font-semibold text-[#f0ede8] mb-3 tracking-tight">{s.title}</h3>
              <p className="text-[13px] text-white/36 leading-relaxed font-light">{s.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CTA footer */}
      <div style={{ borderTop: "1px solid rgba(255,255,255,0.055)" }}>
        <div className="max-w-[440px] mx-auto text-center py-[82px] px-7">
          <h2 className="font-['Instrument_Serif'] text-[38px] text-[#f0ede8] mb-4 tracking-tight">Ready to deploy.</h2>
          <p className="text-[15px] text-white/36 mb-9 leading-[1.72] font-light">
            Connect your media pipeline and protect your assets in under five minutes.
          </p>
          <motion.button
            onClick={onLaunch}
            className="inline-flex items-center gap-2 px-7 py-3 rounded-xl text-[14px] font-medium text-[#09090b]"
            style={{ background: "#f0ede8" }}
            whileHover={{ opacity: 0.88, y: -1 }} whileTap={{ scale: 0.97 }}
          >
            Begin Ingestion <ArrowRight size={13} />
          </motion.button>
        </div>
      </div>
    </div>
  );
}


// ─── DASHBOARD VIEW ───────────────────────────────────────────

function DashboardView({ nav, detections, onRowClick }) {
  const scoreColor = (s) => s >= 0.85 ? RED : s >= 0.65 ? AMBER : "rgba(240,237,232,0.28)";

  return (
    <div className="min-h-screen pt-[54px]" style={{ background: "#09090b" }}>
      <div className="max-w-[1220px] mx-auto px-7 py-12">

        {/* Header row */}
        <motion.div
          className="flex justify-between items-end mb-10"
          variants={fadeUp} initial="initial" animate="animate"
        >
          <div>
            <div className="text-[10.5px] uppercase tracking-[0.1em] text-white/22 mb-2">Command Center</div>
            <h1 className="font-['Instrument_Serif'] text-[30px] text-[#f0ede8] tracking-tight">Detection Feed</h1>
          </div>
          <div className="flex items-center gap-1.5 text-[11px] text-white/28 pb-0.5">
            <span className="w-1.5 h-1.5 rounded-full pulse-dot" style={{ background: GREEN }} />
            2 active streams · Updated 4s ago
          </div>
        </motion.div>

        {/* Bento stat cards */}
        <motion.div className="grid grid-cols-4 gap-3 mb-8" variants={stagger} initial="initial" animate="animate">
          {[
            { label:"Active Streams",    value:"2",   sub:"α + β running",       icon:<Activity size={14} style={{ color:ACCENT }}/> },
            { label:"Detections Today",  value:"47",  sub:"+12 from yesterday",   icon:<Eye size={14} style={{ color:AMBER }}/> },
            { label:"Match Rate",        value:"68%", sub:"Of analyzed assets",   icon:<BarChart2 size={14} style={{ color:GREEN }}/> },
            { label:"Queue Depth",       value:"3",   sub:"Assets pending",       icon:<Database size={14} style={{ color:RED }}/> },
          ].map((c, i) => (
            <motion.div
              key={i}
              className="rounded-2xl p-5 hover:border-white/10 transition-all duration-200"
              style={{ background: "rgba(255,255,255,0.018)", border: "1px solid rgba(255,255,255,0.065)" }}
              variants={staggerItem}
              whileHover={{ y: -2 }}
            >
              <div className="flex items-center justify-between mb-4">
                <span className="text-[12px] text-white/28">{c.label}</span>
                {c.icon}
              </div>
              <div className="font-['Instrument_Serif'] text-[32px] text-[#f0ede8] leading-none mb-1">{c.value}</div>
              <div className="text-[11.5px] text-white/20">{c.sub}</div>
            </motion.div>
          ))}
        </motion.div>

        {/* Detection table */}
        <motion.div
          className="rounded-2xl overflow-hidden"
          style={{ background: "rgba(255,255,255,0.018)", border: "1px solid rgba(255,255,255,0.065)" }}
          initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.32, duration: 0.5 }}
        >
          {/* Table topbar */}
          <div
            className="flex items-center justify-between px-6 py-4"
            style={{ borderBottom: "1px solid rgba(255,255,255,0.055)" }}
          >
            <span className="text-[14px] font-medium text-[#f0ede8]">Recent Detections</span>
            <span className="text-[12px] text-white/24">Last {detections.length} events</span>
          </div>

          {/* Column headings */}
          <div
            className="grid px-6 py-2 text-[10px] uppercase tracking-[0.07em] text-white/20"
            style={{ gridTemplateColumns: "1fr 90px 115px 115px 72px 28px", borderBottom: "1px solid rgba(255,255,255,0.04)" }}
          >
            <span>Asset</span>
            <span>Score</span>
            <span>Status</span>
            <span>Stream</span>
            <span>Time</span>
            <span />
          </div>

          {/* Rows */}
          <motion.div variants={stagger} initial="initial" animate="animate">
            {detections.map((d) => {
              const clickable = d.status === "Completed";
              return (
                <motion.div
                  key={d.id}
                  className={`grid px-6 py-4 border-b border-white/[0.04] last:border-0 transition-all duration-150 group ${clickable ? "cursor-pointer hover:bg-white/[0.025]" : "opacity-60"}`}
                  style={{ gridTemplateColumns: "1fr 90px 115px 115px 72px 28px", alignItems: "center" }}
                  variants={staggerItem}
                  onClick={() => clickable && onRowClick(d)}
                >
                  {/* Asset name */}
                  <div>
                    <div className="flex items-center gap-2 mb-0.5">
                      {d.type === "video"
                        ? <FileVideo size={11} className="text-white/22 flex-shrink-0" />
                        : <FileText size={11} className="text-white/22 flex-shrink-0" />}
                      <span className="text-[13px] text-[#f0ede8] truncate max-w-[300px]">{d.asset}</span>
                    </div>
                    <span className="text-[10.5px] text-white/20 font-mono ml-[18px]">{d.id}</span>
                  </div>

                  {/* Score */}
                  <div
                    className="font-['Instrument_Serif'] text-[16px]"
                    style={{ color: d.score > 0 ? scoreColor(d.score) : "rgba(240,237,232,0.14)" }}
                  >
                    {d.score > 0 ? d.score.toFixed(3) : "—"}
                  </div>

                  {/* Status badge */}
                  <div><StatusBadge status={d.status} /></div>

                  {/* Stream */}
                  <div className="text-[12px] text-white/28">{d.stream}</div>

                  {/* Time */}
                  <div className="text-[12px] text-white/20">{d.time} ago</div>

                  {/* Expand indicator */}
                  <div className={`transition-opacity duration-150 ${clickable ? "opacity-0 group-hover:opacity-100" : "opacity-0"}`}>
                    <ChevronRight size={13} className="text-white/30" />
                  </div>
                </motion.div>
              );
            })}
          </motion.div>
        </motion.div>

        {/* Footer */}
        <div className="mt-6 text-center">
          <button
            onClick={() => nav("insights")}
            className="text-[13px] text-white/26 hover:text-white/48 transition-colors"
          >
            Explore Deep Insights →
          </button>
        </div>
      </div>
    </div>
  );
}


// ─── INSIGHTS VIEW ────────────────────────────────────────────

function InsightsView() {
  const [openKey, setOpenKey] = useState(null);
  const toggle = (k) => setOpenKey((p) => (p === k ? null : k));

  const sections = [
    {
      key: "math",
      title: "Vector Similarity Mathematics",
      preview: "Euclidean & Cosine distance across 512-D and 384-D spaces.",
      body: (
        <div className="text-[13.5px] text-white/48 leading-[1.8] font-light">
          <p className="mb-4">Each visual frame is encoded into a <strong className="text-[#f0ede8] font-medium">512-dimensional vector</strong> via a fine-tuned vision transformer. Text transcripts produce <strong className="text-[#f0ede8] font-medium">384-dimensional embeddings</strong> via a sentence-level language model.</p>
          <div className="rounded-xl p-4 font-mono text-[12px] space-y-2 mb-4" style={{ background:"rgba(255,255,255,0.025)", border:"1px solid rgba(255,255,255,0.06)" }}>
            <div className="text-white/22 text-[10.5px]">// Cosine similarity  (orientation-invariant · semantic matching)</div>
            <div style={{ color:AMBER }}>cosine(A, B) = (A · B) / (‖A‖ × ‖B‖)</div>
            <div className="text-white/22 text-[10.5px] pt-2">// Euclidean distance  (absolute spatial proximity · structural copies)</div>
            <div style={{ color:ACCENT }}>euclidean(A, B) = √Σ(Aᵢ − Bᵢ)²</div>
          </div>
          <p>Both metrics are computed per asset and fed into the fused scoring model. Cosine captures semantic alignment; Euclidean catches near-exact structural duplicates.</p>
        </div>
      ),
    },
    {
      key: "fused",
      title: "Fused Scoring Model",
      preview: "How visual and text scores are weighted into a single match confidence.",
      body: (
        <div className="text-[13.5px] text-white/48 leading-[1.8] font-light">
          <p className="mb-4">Final match confidence blends visual and text modalities via a weighted sum, with α tuned per asset type:</p>
          <div className="rounded-xl p-4 font-mono text-[12px] space-y-2 mb-5" style={{ background:"rgba(255,255,255,0.025)", border:"1px solid rgba(255,255,255,0.06)" }}>
            <div style={{ color:GREEN }}>S_fused = α · S_visual + (1−α) · S_text</div>
            <div className="text-white/22 text-[10.5px] pt-1">α = 0.65 for video · α = 0.0 for text-only assets · threshold = 0.80</div>
          </div>
          <div className="space-y-4">
            {[["Visual weight (α)", "65%", ACCENT], ["Text weight (1−α)", "35%", AMBER], ["Confirmation threshold", "80%", RED]].map(([l, p, c]) => (
              <div key={l}>
                <div className="flex justify-between text-[12px] mb-1.5">
                  <span className="text-white/36">{l}</span>
                  <span style={{ color:c }}>{p}</span>
                </div>
                <div className="h-[3px] bg-white/[0.05] rounded-full overflow-hidden">
                  <motion.div className="h-full rounded-full" style={{ background:c }} initial={{ width:0 }} animate={{ width:p }} transition={{ duration:0.9, ease:[0.4,0,0.2,1] }}/>
                </div>
              </div>
            ))}
          </div>
        </div>
      ),
    },
    {
      key: "buffer",
      title: "Stream Buffer Architecture",
      preview: "Async worker model isolating ML computation from the FastAPI event loop.",
      body: (
        <div className="text-[13.5px] text-white/48 leading-[1.8] font-light">
          <p className="mb-4"><code className="bg-white/[0.07] px-1.5 py-0.5 rounded text-[#f0ede8] text-[12px]">buffer_service.py</code> maintains isolated async worker queues per stream. Heavy ML inference is offloaded to a thread pool executor, keeping the FastAPI event loop fully non-blocking.</p>
          <div className="grid gap-2 mb-5 items-center" style={{ gridTemplateColumns:"1fr auto 1fr auto 1fr" }}>
            {["Ingest Queue", "→", "Worker Pool", "→", "Vector Store"].map((n, i) => (
              <div key={i} className={i % 2 === 0
                ? "text-center text-[12px] text-[#f0ede8] py-2 px-3 rounded-xl"
                : "text-center flex items-center justify-center text-[16px]"}
                style={i % 2 === 0
                  ? { background:"rgba(255,255,255,0.04)", border:"1px solid rgba(255,255,255,0.07)" }
                  : { color:ACCENT }}>
                {n}
              </div>
            ))}
          </div>
          <p>Streams α and β operate fully independently. Max buffer depth is configurable (default: 256 frames) with automatic backpressure signaling to the ingestion controller.</p>
        </div>
      ),
    },
    {
      key: "nexus",
      title: "Nexus Attribution Graph",
      preview: "Visual lineage connecting detected copies to exact golden source frames.",
      live: true,
      body: (
        <div className="text-center py-5 text-[13.5px] text-white/30 font-light">
          <div className="w-11 h-11 rounded-full mx-auto mb-4 flex items-center justify-center" style={{ background:ACCENT_DIM, border:`1px solid ${ACCENT_BORDER}` }}>
            <Network size={17} style={{ color:ACCENT }}/>
          </div>
          <p>The interactive Nexus Graph (powered by <strong className="text-white/48 font-medium">React Flow</strong>) is live in the Command Center.</p>
          <p className="mt-2">Click any <strong className="text-white/48 font-medium">Completed</strong> detection row, then press <em className="text-white/48">"View Nexus Lineage Graph"</em> in the panel.</p>
        </div>
      ),
    },
  ];

  return (
    <div className="min-h-screen pt-[54px]" style={{ background: "#09090b" }}>
      <div className="max-w-[760px] mx-auto px-7 py-14">
        <motion.div variants={fadeUp} initial="initial" animate="animate" className="mb-10">
          <div className="text-[10.5px] uppercase tracking-[0.1em] text-white/22 mb-2">Intelligence Layer</div>
          <h1 className="font-['Instrument_Serif'] text-[30px] text-[#f0ede8] mb-3 tracking-tight">System Insights</h1>
          <p className="text-[14px] text-white/30 font-light max-w-[460px] leading-relaxed">
            Technical breakdowns of the algorithms and architecture powering Overwatch.
          </p>
        </motion.div>

        <div className="space-y-2.5">
          {sections.map((s, i) => (
            <motion.div
              key={s.key}
              className="rounded-2xl overflow-hidden transition-all duration-200"
              style={{ background: "rgba(255,255,255,0.018)", border: "1px solid rgba(255,255,255,0.065)" }}
              initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 + i * 0.08, duration: 0.45 }}
              whileHover={{ borderColor: "rgba(255,255,255,0.1)" }}
            >
              <button
                onClick={() => toggle(s.key)}
                className="w-full px-6 py-5 flex items-center justify-between text-left hover:bg-white/[0.02] transition-all"
              >
                <div>
                  <div className="flex items-center gap-2.5 mb-1">
                    <span className="text-[14px] font-medium text-[#f0ede8]">{s.title}</span>
                    {s.live && (
                      <span
                        className="text-[9.5px] px-1.5 py-0.5 rounded border font-bold tracking-wider uppercase"
                        style={{ color: ACCENT, background: ACCENT_DIM, borderColor: ACCENT_BORDER }}
                      >
                        Live
                      </span>
                    )}
                  </div>
                  <div className="text-[12px] text-white/26">{s.preview}</div>
                </div>
                <motion.div
                  className="w-7 h-7 rounded-xl flex items-center justify-center text-white/28 flex-shrink-0 ml-4"
                  style={{ border: "1px solid rgba(255,255,255,0.08)" }}
                  animate={{ rotate: openKey === s.key ? 180 : 0 }}
                  transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
                >
                  <ChevronDown size={13} />
                </motion.div>
              </button>

              <AnimatePresence initial={false}>
                {openKey === s.key && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.26, ease: [0.4, 0, 0.2, 1] }}
                    className="overflow-hidden"
                  >
                    <div className="px-6 pb-6 pt-4" style={{ borderTop: "1px solid rgba(255,255,255,0.055)" }}>
                      {s.body}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}


// ─── APP ROOT ─────────────────────────────────────────────────

export default function App() {
  // Core state machine
  const [phase, setPhase]             = useState("landing");   // landing | login | ingestion | dashboard | insights
  const [role, setRole]               = useState(null);         // "PRODUCER" | "AUDITOR"
  const [user, setUser]               = useState(null);         // { name: "Tanmay" }
  const [showRoleModal, setShowRoleModal] = useState(false);

  // Asset feed
  const [detections, setDetections]   = useState(MOCK_DETECTIONS);

  // Drawer + Nexus
  const [selectedDetection, setSelectedDetection] = useState(null);
  const [drawerOpen, setDrawerOpen]   = useState(false);
  const [nexusOpen, setNexusOpen]     = useState(false);

  // Navigate — guard ingestion behind auth
  const nav = (p) => {
    if (p === "ingestion" && !user) {
      setShowRoleModal(true);
      return;
    }
    setPhase(p);
    setDrawerOpen(false);
    setNexusOpen(false);
  };

  const handleLaunch = () => setShowRoleModal(true);

  const handleRoleSelect = (r) => {
    setRole(r);
    setShowRoleModal(false);
    setPhase("login");
  };

  const handleLoginSuccess = (u) => {
    setUser(u);
    setPhase("ingestion");
  };

  const handleLogout = () => {
    setUser(null); setRole(null);
    setPhase("landing");
    setDrawerOpen(false); setNexusOpen(false);
  };

  const handleFileIngested = (fileName) => {
    const isVideo = /\.(mp4|mov|mkv|avi)$/i.test(fileName);
    const newItem = {
      id:     `DET-${8830 + detections.length}`,
      asset:  fileName,
      score: 0, visual: 0, text: 0,
      status: "Processing",
      time:   "just now",
      stream: role === "PRODUCER" ? "Stream α" : "Stream β",
      type:   isVideo ? "video" : "audio",
    };
    setDetections((prev) => [newItem, ...prev]);
  };

  const handleRowClick = (d) => {
    setSelectedDetection(d);
    setDrawerOpen(true);
  };

  const closeDrawer = () => { setDrawerOpen(false); setSelectedDetection(null); };

  const showNav = user && ["dashboard", "insights", "ingestion"].includes(phase);

  return (
    <div className="min-h-screen" style={{ background: "#09090b" }}>
      <GlobalStyles />
      <div id="grain" />

      {/* ── Navbar ── */}
      {showNav && (
        <Navbar page={phase} nav={nav} user={user} onLogout={handleLogout} />
      )}

      {/* ── Main page (with animated transitions) ── */}
      <AnimatePresence mode="wait">
        <motion.div key={phase} variants={fadeIn} initial="initial" animate="animate" exit="exit">
          {phase === "landing"   && <LandingView nav={nav} onLaunch={handleLaunch} />}
          {phase === "login"     && <LoginView role={role} onSuccess={handleLoginSuccess} onBack={() => { setPhase("landing"); setShowRoleModal(true); }} />}
          {phase === "ingestion" && <IngestionView role={role} nav={nav} onFileIngested={handleFileIngested} />}
          {phase === "dashboard" && <DashboardView nav={nav} detections={detections} onRowClick={handleRowClick} />}
          {phase === "insights"  && <InsightsView />}
        </motion.div>
      </AnimatePresence>

      {/* ── Role Select Modal ── */}
      <AnimatePresence>
        {showRoleModal && (
          <RoleModal
            onSelect={handleRoleSelect}
            onClose={() => setShowRoleModal(false)}
          />
        )}
      </AnimatePresence>

      {/* ── Drawer backdrop ── */}
      <AnimatePresence>
        {drawerOpen && (
          <motion.div
            className="fixed inset-0 z-40"
            style={{ background: "rgba(9,9,11,0.52)", backdropFilter: "blur(5px)" }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={closeDrawer}
          />
        )}
      </AnimatePresence>

      {/* ── Deep Insights Drawer ── */}
      <AnimatePresence>
        {drawerOpen && selectedDetection && (
          <Drawer
            detection={selectedDetection}
            onClose={closeDrawer}
            onNexus={() => setNexusOpen(true)}
          />
        )}
      </AnimatePresence>

      {/* ── Nexus Graph Modal ── */}
      <AnimatePresence>
        {nexusOpen && selectedDetection && (
          <NexusModal
            detection={selectedDetection}
            onClose={() => setNexusOpen(false)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}