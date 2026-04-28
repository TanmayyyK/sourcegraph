import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { apiFetch } from "@/lib/api";
import {
  ReactFlow,
  Controls,
  Background,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  MarkerType,
  Handle,
  Position,
  NodeProps,
  EdgeProps,
  BaseEdge,
  getBezierPath,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft,
  Activity,
  ShieldAlert,
  CheckCircle2,
  GitBranch,
  Database,
  Cpu,
  FileDown,
  Terminal,
  Shield,
  AlertTriangle,
} from "lucide-react";

// ─── CSS Keyframes & Global Overrides ────────────────────────────────────────

const GlobalStyles = () => (
  <style>{`
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=DM+Mono:wght@400;500;600&display=swap');

    @keyframes pulse-ring {
      0%   { transform: scale(1);    opacity: 0.55; }
      100% { transform: scale(1.12); opacity: 0; }
    }
    @keyframes pulse-dot {
      0%, 100% { opacity: 1;   transform: scale(1); }
      50%       { opacity: 0.3; transform: scale(0.7); }
    }
    @keyframes shimmer {
      0%   { background-position: -200% 0; }
      100% { background-position:  200% 0; }
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }

    /* ReactFlow canvas override */
    .nexus-canvas .react-flow__renderer { background: transparent !important; }

    /* Controls light theme */
    .nexus-canvas .react-flow__controls {
      background: #FFFFFF !important;
      border: 1px solid rgba(0,0,0,0.08) !important;
      border-radius: 10px !important;
      box-shadow: 0 2px 12px rgba(0,0,0,0.07) !important;
      overflow: hidden;
    }
    .nexus-canvas .react-flow__controls-button {
      background: transparent !important;
      border-bottom-color: rgba(0,0,0,0.07) !important;
      color: #64657A !important;
    }
    .nexus-canvas .react-flow__controls-button:hover {
      background: #F5F3EF !important;
    }

    /* Scrollbar */
    .nexus-log::-webkit-scrollbar        { width: 4px; }
    .nexus-log::-webkit-scrollbar-track  { background: transparent; }
    .nexus-log::-webkit-scrollbar-thumb  { background: rgba(0,0,0,0.11); border-radius: 2px; }
    .nexus-side::-webkit-scrollbar       { width: 4px; }
    .nexus-side::-webkit-scrollbar-track { background: transparent; }
    .nexus-side::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.08); border-radius: 2px; }

    /* Edge label */
    .nexus-canvas .react-flow__edge-text { font-family: 'DM Mono', monospace; font-size: 9px; fill: #9899AE; }
    .nexus-canvas .react-flow__edge-textbg { fill: transparent !important; }
  `}</style>
);

// ─── Design Tokens ────────────────────────────────────────────────────────────

const C = {
  bg:         "#F5F3EF",
  bgCard:     "#FFFFFF",
  bgMuted:    "#F0EEE9",
  bgDot:      "#E4E1DA",
  border:     "rgba(0,0,0,0.07)",
  borderMed:  "rgba(0,0,0,0.11)",
  text:       "#1C1C2E",
  textSub:    "#42435A",
  textMuted:  "#64657A",
  textFaint:  "#9899AE",
  accent:     "#4C63F7",   // Royal Blue
  violet:     "#7C5CF7",   // Violet
  coral:      "#F26B5B",   // Critical
  green:      "#2DA44E",   // Success
  amber:      "#D97706",   // Warning
  redTier:    "#EF4444",
  amberTier:  "#F59E0B",
  yellowTier: "#FACC15",
  emeraldTier:"#10B981",
  // Node palette
  colorAsset:   "#7C5CF7",
  colorEngine:  "#4C63F7",
  colorThreat:  "#F26B5B",
  colorVerdict: "#2DA44E",
};

// ─── Types ────────────────────────────────────────────────────────────────────

type NodeStatus = "processing" | "complete" | "idle" | "alert";

interface NodeData {
  label:        string;
  role?:        string;
  engine_type?: string;
  status?:      NodeStatus;
  score?:       number;
  nodeType?:    string;
}

interface ApiNode {
  id:   string;
  type: string;
  data: NodeData;
  position: { x: number; y: number };
}

interface ApiEdge {
  id:     string;
  source: string;
  target: string;
  label?: string;
}

interface AnalysisPayload {
  nodes:       ApiNode[];
  edges:       ApiEdge[];
  ingest_logs: string[];
  temporal_data?: Array<{ ts: number; val: number; type: string }>;
}

function normalizeConfidenceScore(score?: number): number {
  if (!Number.isFinite(score ?? NaN)) return 0;
  const rawScore = (score ?? 0) > 1 ? (score ?? 0) / 100 : (score ?? 0);
  return Math.max(0, Math.min(1, rawScore));
}

function getPiracyTier(score?: number) {
  const rawScore = normalizeConfidenceScore(score);
  if (rawScore >= 0.8) {
    return {
      label: "High Confidence (Piracy)",
      action: "Automated Takedown Initiated",
      color: C.redTier,
      textClass: "text-red-500",
      bgClass: "bg-red-500/20",
      borderClass: "border-red-500",
    };
  }
  if (rawScore >= 0.6) {
    return {
      label: "Suspicious",
      action: "Manual Review Required",
      color: C.amberTier,
      textClass: "text-amber-500",
      bgClass: "bg-amber-500/20",
      borderClass: "border-amber-500",
    };
  }
  if (rawScore >= 0.4) {
    return {
      label: "Low Confidence",
      action: "Flagged for Observation",
      color: C.yellowTier,
      textClass: "text-yellow-400",
      bgClass: "bg-yellow-400/20",
      borderClass: "border-yellow-400",
    };
  }
  return {
    label: "Clean",
    action: "Discarded",
    color: C.emeraldTier,
    textClass: "text-emerald-500",
    bgClass: "bg-emerald-500/20",
    borderClass: "border-emerald-500",
  };
}

// ─── Mock Data ────────────────────────────────────────────────────────────────

function generateMockPayload(assetId: string): AnalysisPayload {
  const tag = (assetId ?? "unknown").slice(-8);
  const ts  = (offset: number) => new Date(Date.now() - offset).toISOString();
  return {
    nodes: [
      { id: "asset_root",      type: "asset",
        data: { label: `${tag}.mp4`,     role: "Suspect Asset",       status: "processing", score: 0,  nodeType: "asset"   }, position: { x: 320, y: 60 }  },
      { id: "engine_audio",    type: "engine",
        data: { label: "Audio Engine",   role: "Spectral DTW",        engine_type: "AUDIO_DTW",  status: "processing", score: 87, nodeType: "engine"  }, position: { x: 60,  y: 260 } },
      { id: "engine_video",    type: "engine",
        data: { label: "Vision Engine",  role: "Frame Fingerprint",   engine_type: "VIDEO_HASH", status: "complete",   score: 92, nodeType: "engine"  }, position: { x: 320, y: 260 } },
      { id: "engine_meta",     type: "engine",
        data: { label: "Metadata Engine",role: "EXIF Analysis",       engine_type: "META_PARSE", status: "complete",   score: 71, nodeType: "engine"  }, position: { x: 580, y: 260 } },
      { id: "threat_deepfake", type: "threat",
        data: { label: "Deepfake Signal",role: "GAN Artifact Pattern",status: "alert",       score: 94, nodeType: "threat"  }, position: { x: 140, y: 460 } },
      { id: "verdict_final",   type: "verdict",
        data: { label: "High Confidence (Piracy)", role: "Automated Takedown Initiated", status: "alert", score: 91, nodeType: "verdict" }, position: { x: 430, y: 460 } },
    ],
    edges: [
      { id: "e1", source: "asset_root",      target: "engine_audio",    label: "Audio Stream"    },
      { id: "e2", source: "asset_root",      target: "engine_video",    label: "Video Stream"    },
      { id: "e3", source: "asset_root",      target: "engine_meta",     label: "Metadata"        },
      { id: "e4", source: "engine_audio",    target: "threat_deepfake", label: "Anomaly ↑94%"   },
      { id: "e5", source: "threat_deepfake", target: "verdict_final",   label: "Escalated"       },
      { id: "e6", source: "engine_video",    target: "verdict_final",   label: "High Confidence" },
      { id: "e7", source: "engine_meta",     target: "verdict_final",   label: "Correlated"      },
    ],
    ingest_logs: [
      `${ts(8200)} [INFO]  Asset ingested: ${tag}.mp4 — 342MB`,
      `${ts(7500)} [INFO]  Dispatching to 3 analysis engines`,
      `${ts(6800)} [INFO]  AudioEngine: Spectral analysis initializing`,
      `${ts(6100)} [INFO]  VideoEngine: Frame extraction started (1440p)`,
      `${ts(5300)} [OK]    MetadataEngine completed — score=71, no anomalies`,
      `${ts(4400)} [OK]    VideoEngine completed — score=92, 3 keyframes flagged`,
      `${ts(3600)} [WARN]  AudioEngine: Spectral anomaly at 2.31s–2.89s`,
      `${ts(2900)} [ALERT] GAN artifact pattern detected — confidence=94%`,
      `${ts(2200)} [OK]    AudioEngine completed — score=87`,
      `${ts(1500)} [ALERT] Threat escalation: Deepfake signal → VerdictEngine`,
      `${ts(800)}  [ALERT] VERDICT: FLAGGED — composite confidence=91%`,
    ],
  };
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function nodeColor(type: string, score?: number): string {
  switch (type) {
    case "asset":   return C.colorAsset;
    case "engine":  return C.colorEngine;
    case "threat":  return C.colorThreat;
    case "verdict": return getPiracyTier(score).color;
    default:        return C.accent;
  }
}

function parseLog(line: string) {
  const tsM   = line.match(/^(\d{4}-\d{2}-\d{2}T[\d:.]+Z)\s*/);
  const lvlM  = line.match(/\[(INFO|OK|WARN|ALERT|ERROR|DEBUG)\]/);
  const ts    = tsM   ? tsM[1]   : "";
  const level = lvlM  ? lvlM[1]  : "";
  const rest  = line.slice(tsM ? tsM[0].length : 0).replace(`[${level}]`, "").trim();
  const lc: Record<string,string> = {
    INFO: C.accent, OK: C.green, WARN: C.amber, ALERT: C.coral, ERROR: C.coral, DEBUG: C.textFaint,
  };
  return { ts: ts.slice(11, 23), level, rest, lc: lc[level] ?? C.textMuted };
}

// ─── Custom Node ──────────────────────────────────────────────────────────────

function NexusNode({ data, selected }: NodeProps) {
  const nodeData = data as unknown as NodeData;
  const type      = (nodeData.nodeType as string) ?? "engine";
  const status    = (nodeData.status   as string) ?? "idle";
  const score     = nodeData.score;
  const accentCol = nodeColor(type, score);
  const isProcess = status === "processing";
  const isAlert   = status === "alert";
  const isComplete= status === "complete";

  let Icon: React.ComponentType<{ size?: number; color?: string }>;
  switch (type) {
    case "asset":   Icon = Database;      break;
    case "threat":  Icon = ShieldAlert;   break;
    case "verdict": Icon = isAlert ? AlertTriangle : CheckCircle2; break;
    default:        Icon = Cpu;
  }

  const roleTag: Record<string,string> = {
    asset:   "SUSPECT ASSET",
    engine:  (data.engine_type as string) ?? "ENGINE",
    threat:  "THREAT VECTOR",
    verdict: "FINAL VERDICT",
  };

  return (
    <div style={{
      position:   "relative",
      background: C.bgCard,
      borderRadius: "12px",
      border:     `1px solid ${selected ? `${accentCol}55` : C.border}`,
      minWidth:   "188px",
      overflow:   "hidden",
      boxShadow:  selected
        ? `0 0 0 3px ${accentCol}1A, 0 8px 28px rgba(0,0,0,0.10)`
        : "0 2px 10px rgba(0,0,0,0.06), 0 1px 3px rgba(0,0,0,0.04)",
      fontFamily: "'DM Sans', sans-serif",
      cursor:     "pointer",
      transition: "box-shadow 0.25s ease, border-color 0.25s ease",
    }}>
      {/* Left gradient accent bar */}
      <div style={{
        position: "absolute", left: 0, top: 0, bottom: 0, width: "3px",
        background: `linear-gradient(180deg, ${accentCol} 0%, ${accentCol}44 100%)`,
      }}/>

      {/* Processing pulse rings */}
      {isProcess && <>
        <div style={{
          position: "absolute", inset: -3, borderRadius: "14px",
          border: `1.5px solid ${accentCol}`,
          animation: "pulse-ring 2s ease-out infinite",
          pointerEvents: "none",
        }}/>
        <div style={{
          position: "absolute", inset: -7, borderRadius: "17px",
          border: `1px solid ${accentCol}55`,
          animation: "pulse-ring 2s ease-out infinite",
          animationDelay: "0.35s",
          pointerEvents: "none",
        }}/>
      </>}

      <Handle type="target" position={Position.Top}    style={{ opacity: 0, pointerEvents: "none" }}/>
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0, pointerEvents: "none" }}/>
      <Handle type="source" position={Position.Right}  style={{ opacity: 0, pointerEvents: "none" }}/>
      <Handle type="target" position={Position.Left}   style={{ opacity: 0, pointerEvents: "none" }}/>

      <div style={{ padding: "11px 14px 12px 19px" }}>
        {/* Top row */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "7px" }}>
          <div style={{
            width: "30px", height: "30px", borderRadius: "8px",
            background: `${accentCol}12`,
            display: "flex", alignItems: "center", justifyContent: "center",
            flexShrink: 0,
          }}>
            <Icon size={14} color={accentCol}/>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontSize: "9px", fontWeight: 600, letterSpacing: "0.09em",
              textTransform: "uppercase", color: C.textFaint,
              fontFamily: "'DM Mono', monospace",
            }}>
              {roleTag[type] ?? "NODE"}
            </div>
          </div>
          {/* Status dot */}
          {isProcess  && <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: accentCol, animation: "pulse-dot 1.3s ease-in-out infinite", flexShrink: 0 }}/>}
          {isAlert    && <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: C.coral,    boxShadow: `0 0 7px ${C.coral}88`,                flexShrink: 0 }}/>}
          {isComplete && <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: C.green,                                                     flexShrink: 0 }}/>}
        </div>

        {/* Label */}
        <div style={{
          fontFamily: "'DM Mono', monospace", fontSize: "12px", fontWeight: 600,
          color: C.text, letterSpacing: "-0.01em",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          marginBottom: "2px",
        }}>
          {(data as unknown as NodeData).label}
        </div>

        {/* Role subtitle */}
        {(data as unknown as NodeData).role && (
          <div style={{ fontSize: "11px", color: C.textMuted, letterSpacing: "0.005em" }}>
            {(data as unknown as NodeData).role}
          </div>
        )}

        {/* Score bar */}
        {score != null && type !== "asset" && (
          <div style={{ marginTop: "9px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px" }}>
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "9px", color: C.textFaint, letterSpacing: "0.07em" }}>
                CONFIDENCE
              </span>
              <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "11px", fontWeight: 700, color: accentCol }}>
                {score}%
              </span>
            </div>
            <div style={{ height: "2px", background: C.bgMuted, borderRadius: "1px", overflow: "hidden" }}>
              <div style={{
                height: "100%", width: `${score}%`,
                background: `linear-gradient(90deg, ${accentCol}, ${accentCol}AA)`,
                borderRadius: "1px",
                transition: "width 0.5s ease",
              }}/>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Particle Edge ────────────────────────────────────────────────────────────

function ParticleEdge({
  sourceX, sourceY, targetX, targetY,
  sourcePosition, targetPosition,
  style = {}, markerEnd, data,
}: EdgeProps) {
  const [edgePath] = getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition });
  const highlighted = !!(data?.highlighted);
  const isThreat    = !!(data?.isThreat);
  const base        = isThreat ? C.coral : C.accent;
  const dur1        = `${1.9 + ((data?.durOffset as number) ?? 0)}s`;
  const dur2        = `${parseFloat(dur1) * 0.68}s`;
  const del2        = `${parseFloat(dur1) * 0.42}s`;

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          ...style,
          stroke:          highlighted ? base : `${base}40`,
          strokeWidth:     highlighted ? 2    : 1.5,
          strokeDasharray: highlighted ? undefined : "5 3",
          transition:      "stroke 0.3s ease, stroke-width 0.3s ease",
        }}
      />
      {/* Primary particle */}
      <circle r={highlighted ? 3.5 : 2.5} fill={base} opacity={highlighted ? 0.9 : 0.45}>
        <animateMotion dur={dur1} repeatCount="indefinite" path={edgePath}/>
      </circle>
      {/* Secondary particle (highlighted only) */}
      {highlighted && (
        <circle r={2} fill={base} opacity={0.5}>
          <animateMotion dur={dur2} repeatCount="indefinite" begin={del2} path={edgePath}/>
        </circle>
      )}
    </>
  );
}

const NODE_TYPES = {
  asset: NexusNode, engine: NexusNode, threat: NexusNode,
  verdict: NexusNode, custom: NexusNode,
};
const EDGE_TYPES = { particle: ParticleEdge };

// ─── Log Terminal ─────────────────────────────────────────────────────────────

function LogTerminal({ logs }: { logs: string[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [logs]);

  return (
    <div ref={ref} className="nexus-log" style={{
      height: "100%", overflowY: "auto",
      background: "#FAFAF8",
      border: `1px solid ${C.border}`,
      borderRadius: "10px",
      padding: "11px 12px",
      fontFamily: "'DM Mono', monospace",
      fontSize: "10.5px",
      lineHeight: "1.75",
    }}>
      {logs.length === 0 && (
        <div style={{ color: C.textFaint, fontStyle: "italic" }}>Awaiting events…</div>
      )}
      {logs.map((log, i) => {
        const { ts, level, rest, lc } = parseLog(log);
        return (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.028, duration: 0.18 }}
            style={{ display: "flex", gap: "7px", alignItems: "baseline", flexWrap: "wrap", marginBottom: "1px" }}
          >
            {ts && (
              <span style={{ color: C.violet, whiteSpace: "nowrap", flexShrink: 0 }}>{ts}</span>
            )}
            {level && (
              <span style={{
                color: lc, fontWeight: 600, flexShrink: 0,
                background: `${lc}18`, padding: "0 4px", borderRadius: "3px",
                letterSpacing: "0.03em",
              }}>
                {level}
              </span>
            )}
            <span style={{ color: C.textSub, wordBreak: "break-word", flex: 1 }}>{rest}</span>
          </motion.div>
        );
      })}
    </div>
  );
}

// ─── Temporal Chart ───────────────────────────────────────────────────────────

function TemporalChart({
  selectedNode,
  apiNodes,
  temporalData = []
}: {
  selectedNode: string | null;
  apiNodes: ApiNode[];
  temporalData?: Array<{ ts: number; val: number; type: string }>;
}) {
  const active = apiNodes.find(n => n.id === selectedNode);
  const score  = active?.data.score ?? 55;
  const isAlert = active?.type === "threat" || active?.data.status === "alert";
  const accent  = isAlert ? C.coral : C.accent;

  const bars = useMemo(() => {
    // If we have real temporal data from the backend, use it!
    if (temporalData && temporalData.length > 0) {
      // Sample or interpolate to 36 bars
      const barCount = 36;
      const maxVal = Math.max(...temporalData.map(d => d.val), 1);
      
      return Array.from({ length: barCount }, (_, i) => {
        const idx = Math.floor((i / barCount) * temporalData.length);
        const val = temporalData[idx]?.val ?? 0;
        // Normalize to 0.1 - 1.0 range for visibility
        return Math.max(0.08, val / maxVal);
      });
    }

    // Fallback: procedural wave based on score
    return Array.from({ length: 36 }, (_, i) => {
      const base = score / 100;
      const wave = 0.28 * Math.sin(i * 0.65 + score * 0.08)
                 + 0.12 * Math.cos(i * 1.4  + score * 0.05);
      return Math.max(0.05, Math.min(1, base + wave));
    });
  }, [score, temporalData]);

  return (
    <div style={{
      background: "#FAFAF8",
      border: `1px solid ${C.border}`,
      borderRadius: "10px",
      padding: "12px",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
          <Activity size={11} color={accent}/>
          <span style={{
            fontFamily: "'DM Mono', monospace", fontSize: "9.5px", fontWeight: 600,
            letterSpacing: "0.09em", textTransform: "uppercase", color: C.textMuted,
          }}>
            Temporal DTW
          </span>
        </div>
        {active ? (
          <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "12px", fontWeight: 700, color: accent }}>{score}%</span>
        ) : (
          <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "9.5px", color: C.textFaint, fontStyle: "italic" }}>
            select a node
          </span>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "flex-end", gap: "2px", height: "56px" }}>
        {bars.map((h, i) => (
          <motion.div
            key={i}
            initial={{ height: 0 }}
            animate={{ height: `${h * 100}%` }}
            transition={{ duration: 0.38, delay: i * 0.01, ease: "easeOut" }}
            style={{
              flex: 1, minHeight: "3px", borderRadius: "2px 2px 0 0",
              background: h > 0.72
                ? `${accent}EE`
                : h > 0.44
                ? `${accent}77`
                : `${accent}2E`,
            }}
          />
        ))}
      </div>

      <div style={{
        display: "flex", justifyContent: "space-between", marginTop: "7px",
        fontFamily: "'DM Mono', monospace", fontSize: "9px", color: C.textFaint,
      }}>
        <span>0s</span>
        <span style={{ maxWidth: "160px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {active ? active.data.label : "—"}
        </span>
        <span>36s</span>
      </div>
    </div>
  );
}

// ─── Forensic Sidebar ─────────────────────────────────────────────────────────

function ForensicSidebar({
  assetId, payload, selectedNode, apiNodes, onGenerateReport, isGenerating,
}: {
  assetId:          string;
  payload:          AnalysisPayload | null;
  selectedNode:     string | null;
  apiNodes:         ApiNode[];
  onGenerateReport: () => void;
  isGenerating:     boolean;
}) {
  const assetNode   = payload?.nodes.find(n => n.type === "asset");
  const filename    = assetNode?.data.label ?? assetId.slice(-12);
  const hasAlert    = payload?.nodes.some(n => n.data.status === "alert");
  const isVerifying = payload?.nodes.some(n => n.data.status === "processing");
  const statusLabel = isVerifying ? "Verifying…" : hasAlert ? "Threat Detected" : "Secured";
  const statusColor = isVerifying ? C.amber : hasAlert ? C.coral : C.green;

  const stats = payload ? [
    { label: "Engines", value: payload.nodes.filter(n => n.type === "engine").length, color: C.colorEngine },
    { label: "Threats", value: payload.nodes.filter(n => n.type === "threat").length, color: C.colorThreat },
    { label: "Events",  value: payload.ingest_logs.length,                            color: C.violet       },
  ] : [];

  const activeNode = apiNodes.find(n => n.id === selectedNode);
  const activeTier = activeNode?.type === "verdict" ? getPiracyTier(activeNode.data.score) : null;

  return (
    <div style={{
      width: "400px", height: "100vh", flexShrink: 0,
      background: C.bgCard,
      borderLeft: `1px solid ${C.border}`,
      display: "flex", flexDirection: "column",
      overflow: "hidden",
      fontFamily: "'DM Sans', sans-serif",
    }}>
      {/* ── Header ── */}
      <div style={{ padding: "22px 24px 18px", borderBottom: `1px solid ${C.border}` }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: "14px" }}>
          <div style={{ flex: 1, minWidth: 0, paddingRight: "12px" }}>
            <div style={{
              fontFamily: "'DM Mono', monospace", fontSize: "9.5px", fontWeight: 600,
              letterSpacing: "0.12em", textTransform: "uppercase", color: C.textFaint,
              marginBottom: "4px",
            }}>
              Forensic Analysis
            </div>
            <div style={{
              fontFamily: "'DM Mono', monospace", fontSize: "13.5px", fontWeight: 600,
              color: C.text, letterSpacing: "-0.02em",
              overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            }}>
              {filename}
            </div>
          </div>
          {/* Status badge */}
          <div style={{
            display: "flex", alignItems: "center", gap: "6px", flexShrink: 0,
            background: `${statusColor}0F`, padding: "5px 11px",
            borderRadius: "20px", border: `1px solid ${statusColor}30`,
          }}>
            <div style={{
              width: "6px", height: "6px", borderRadius: "50%",
              background: statusColor,
              animation: isVerifying ? "pulse-dot 1.3s ease-in-out infinite" : "none",
              boxShadow: !isVerifying ? `0 0 7px ${statusColor}88` : "none",
            }}/>
            <span style={{
              fontFamily: "'DM Mono', monospace", fontSize: "10.5px",
              fontWeight: 600, color: statusColor, letterSpacing: "0.02em",
              whiteSpace: "nowrap",
            }}>
              {statusLabel}
            </span>
          </div>
        </div>

        {/* Stats row */}
        {stats.length > 0 && (
          <div style={{ display: "flex", gap: "8px" }}>
            {stats.map(s => (
              <div key={s.label} style={{
                flex: 1, background: C.bgMuted, borderRadius: "8px",
                padding: "8px 10px", textAlign: "center",
              }}>
                <div style={{
                  fontFamily: "'DM Mono', monospace", fontSize: "18px",
                  fontWeight: 700, color: s.color, lineHeight: 1,
                }}>
                  {s.value}
                </div>
                <div style={{
                  fontSize: "9.5px", color: C.textFaint, textTransform: "uppercase",
                  letterSpacing: "0.07em", marginTop: "3px",
                }}>
                  {s.label}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Scrollable content ── */}
      <div className="nexus-side" style={{
        flex: 1, overflowY: "auto", padding: "18px 24px",
        display: "flex", flexDirection: "column", gap: "16px",
      }}>
        {/* Log terminal */}
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
            <Terminal size={11} color={C.textMuted}/>
            <span style={{
              fontFamily: "'DM Mono', monospace", fontSize: "9.5px", fontWeight: 600,
              letterSpacing: "0.1em", textTransform: "uppercase", color: C.textMuted,
            }}>
              Ingest Log
            </span>
          </div>
          <div style={{ height: "210px" }}>
            <LogTerminal logs={payload?.ingest_logs ?? []}/>
          </div>
        </div>

        {/* Temporal chart */}
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "8px" }}>
            <Activity size={11} color={C.textMuted}/>
            <span style={{
              fontFamily: "'DM Mono', monospace", fontSize: "9.5px", fontWeight: 600,
              letterSpacing: "0.1em", textTransform: "uppercase", color: C.textMuted,
            }}>
              Temporal Alignment
            </span>
          </div>
          <TemporalChart
            selectedNode={selectedNode}
            apiNodes={apiNodes}
            temporalData={payload?.temporal_data}
          />
        </div>

        {/* Selected node detail card */}
        <AnimatePresence>
          {activeNode && (
            <motion.div
              key={activeNode.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.22 }}
              className={activeTier ? `border ${activeTier.bgClass} ${activeTier.borderClass}` : undefined}
              style={{
                background: activeTier ? undefined : `${nodeColor(activeNode.type, activeNode.data.score)}08`,
                border: activeTier ? undefined : `1px solid ${nodeColor(activeNode.type, activeNode.data.score)}20`,
                borderRadius: "10px",
                padding: "14px",
              }}
            >
              <div style={{
                fontFamily: "'DM Mono', monospace", fontSize: "9.5px", fontWeight: 600,
                letterSpacing: "0.1em", textTransform: "uppercase",
                color: activeTier?.color ?? nodeColor(activeNode.type, activeNode.data.score),
                marginBottom: "10px",
              }}>
                Selected Node
              </div>
              {([
                ["ID",          activeNode.id],
                ["Label",       activeNode.data.label],
                ["Role",        activeNode.data.role],
                ["Status",      activeNode.data.status?.toUpperCase()],
                ["Score",       activeNode.data.score != null ? `${activeNode.data.score}%` : undefined],
                ["Engine Type", activeNode.data.engine_type],
              ] as [string, string | undefined][]).filter(([,v]) => !!v).map(([k, v]) => (
                <div key={k} style={{
                  display: "flex", justifyContent: "space-between", alignItems: "baseline",
                  marginBottom: "5px",
                }}>
                  <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "10px", color: C.textFaint }}>{k}</span>
                  <span style={{
                    fontFamily: "'DM Mono', monospace", fontSize: "10.5px",
                    fontWeight: 600, color: C.text,
                    maxWidth: "200px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  }}>
                    {v}
                  </span>
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* ── Footer: Generate Report ── */}
      <div style={{ padding: "14px 24px 22px", borderTop: `1px solid ${C.border}` }}>
        <motion.button
          whileHover={isGenerating ? {} : { scale: 1.015 }}
          whileTap={isGenerating  ? {} : { scale: 0.975 }}
          onClick={onGenerateReport}
          disabled={isGenerating}
          style={{
            width: "100%", padding: "13px",
            background: isGenerating
              ? C.bgMuted
              : `linear-gradient(135deg, ${C.accent} 0%, ${C.violet} 100%)`,
            color:  isGenerating ? C.textMuted : "#FFFFFF",
            border: isGenerating ? `1px solid ${C.border}` : "none",
            borderRadius: "10px",
            fontSize: "13px", fontWeight: 600,
            fontFamily: "'DM Sans', sans-serif",
            cursor:  isGenerating ? "not-allowed" : "pointer",
            display: "flex", alignItems: "center", justifyContent: "center", gap: "8px",
            letterSpacing: "0.01em",
            boxShadow: isGenerating ? "none" : `0 4px 16px ${C.accent}44`,
            transition: "background 0.3s, box-shadow 0.3s, color 0.3s",
          }}
        >
          {isGenerating ? (
            <>
              <div style={{
                width: "13px", height: "13px",
                border: `2px solid ${C.textFaint}`,
                borderTopColor: "transparent",
                borderRadius: "50%",
                animation: "spin 0.75s linear infinite",
              }}/>
              Compiling Report…
            </>
          ) : (
            <>
              <FileDown size={15}/>
              Generate Forensic Report
            </>
          )}
        </motion.button>
      </div>
    </div>
  );
}

// ─── Loading Skeleton ─────────────────────────────────────────────────────────

function LoadingSkeleton() {
  const shimmer: React.CSSProperties = {
    backgroundImage:    `linear-gradient(90deg, ${C.bgMuted} 25%, ${C.bgDot} 50%, ${C.bgMuted} 75%)`,
    backgroundSize:     "200% 100%",
    animation:          "shimmer 1.6s ease-in-out infinite",
  };
  return (
    <div style={{
      height: "100vh", width: "100vw",
      background: C.bg, display: "flex", overflow: "hidden",
      fontFamily: "'DM Sans', sans-serif",
    }}>
      {/* Canvas area */}
      <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", position: "relative" }}>
        <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%", opacity: 0.6 }}>
          <defs>
            <pattern id="sk-dots" width="24" height="24" patternUnits="userSpaceOnUse">
              <circle cx="12" cy="12" r="1" fill={C.bgDot}/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#sk-dots)"/>
        </svg>

        <div style={{ textAlign: "center", position: "relative", zIndex: 1 }}>
          {/* Concentric pulse rings */}
          <div style={{ position: "relative", width: "68px", height: "68px", margin: "0 auto 22px" }}>
            {[0,1,2].map(i => (
              <div key={i} style={{
                position: "absolute", inset: `-${i * 15}px`,
                borderRadius: "50%",
                border: `1.5px solid ${C.accent}`,
                opacity: 0,
                animation: "pulse-ring 2.2s ease-out infinite",
                animationDelay: `${i * 0.42}s`,
              }}/>
            ))}
            <div style={{
              width: "68px", height: "68px", borderRadius: "50%",
              background: `${C.accent}10`,
              border: `2px solid ${C.accent}33`,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              <GitBranch size={26} color={C.accent}/>
            </div>
          </div>
          <div style={{
            fontFamily: "'DM Mono', monospace", fontSize: "11px", fontWeight: 600,
            letterSpacing: "0.18em", color: C.textMuted, textTransform: "uppercase",
          }}>
            Initializing Nexus Graph
          </div>
          <div style={{
            fontFamily: "'DM Mono', monospace", fontSize: "10px", color: C.textFaint,
            marginTop: "7px", letterSpacing: "0.07em",
            animation: "pulse-dot 2s ease-in-out infinite",
          }}>
            Loading analysis payload…
          </div>
        </div>
      </div>

      {/* Sidebar skeleton */}
      <div style={{
        width: "400px", background: C.bgCard,
        borderLeft: `1px solid ${C.border}`,
        padding: "24px",
      }}>
        <div style={{ marginBottom: "20px" }}>
          <div style={{ height: "10px", width: "110px", borderRadius: "4px", ...shimmer, marginBottom: "10px" }}/>
          <div style={{ height: "18px", width: "190px", borderRadius: "5px", ...shimmer }}/>
        </div>
        <div style={{ display: "flex", gap: "8px", marginBottom: "24px" }}>
          {[1,2,3].map(i => (
            <div key={i} style={{ flex: 1, height: "54px", borderRadius: "8px", ...shimmer, animationDelay: `${i * 0.12}s` }}/>
          ))}
        </div>
        <div style={{ height: "14px", width: "80px", borderRadius: "4px", ...shimmer, marginBottom: "10px" }}/>
        <div style={{ height: "210px", borderRadius: "10px", ...shimmer, marginBottom: "20px" }}/>
        <div style={{ height: "14px", width: "100px", borderRadius: "4px", ...shimmer, marginBottom: "10px" }}/>
        <div style={{ height: "100px", borderRadius: "10px", ...shimmer }}/>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function NexusGraphScreen({ Maps }: { Maps?: (path: string) => void }) {
  const { assetId } = useParams<{ assetId: string }>();
  const navigate    = useNavigate();
  const handleBack  = () => (Maps ? Maps : navigate)(`/insights/${assetId}`);

  const [payload,      setPayload]      = useState<AnalysisPayload | null>(null);
  const [isLoading,    setIsLoading]    = useState(true);
  const [selectedId,   setSelectedId]   = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const [nodes, setNodes, onNodesChange] = useNodesState<any>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<any>([]);

  // ── Build ReactFlow graph from payload ──
  const buildGraph = useCallback((data: AnalysisPayload) => {
    // Normalize DB status values to what the UI components expect
    const normalizeStatus = (s?: string): NodeStatus => {
      if (!s) return "idle";
      if (s === "completed") return "complete";
      if (s === "failed") return "alert";
      return s as NodeStatus;
    };

    const rfNodes = data.nodes.map(n => ({
      id:       n.id,
      type:     n.type,
      position: n.position,
      data:     { ...n.data, nodeType: n.type, status: normalizeStatus(n.data.status as string) },
      draggable: true,
    }));

    const rfEdges = data.edges.map((e, i) => {
      const srcType = data.nodes.find(n => n.id === e.source)?.type;
      const tgtType = data.nodes.find(n => n.id === e.target)?.type;
      const isThreat = srcType === "threat" || tgtType === "threat";
      return {
        id:        e.id,
        source:    e.source,
        target:    e.target,
        type:      "particle",
        label:     e.label,
        data:      { highlighted: false, isThreat, durOffset: i * 0.16 },
        markerEnd: {
          type:   MarkerType.ArrowClosed,
          width:  13,
          height: 13,
          color:  `${C.accent}55`,
        },
      };
    });

    setNodes(rfNodes as any);
    setEdges(rfEdges as any);
    setIsLoading(false);
  }, [setNodes, setEdges]);

  // ── Fetch from real backend ──
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const result = await apiFetch<AnalysisPayload>(`/api/v1/analysis/${assetId}`);
      if (cancelled) return;

      if (result.ok) {
        setPayload(result.data);
        buildGraph(result.data);
      } else {
        // Fallback to mock only if the real API is unreachable
        console.warn("[NexusGraph] API unavailable, using mock data:", result.error);
        const mock = generateMockPayload(assetId ?? "unknown");
        const t = setTimeout(() => {
          if (!cancelled) { setPayload(mock); buildGraph(mock); }
        }, 1300);
        return () => clearTimeout(t);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [assetId, buildGraph]);

  // ── Highlight connected edges on selection ──
  useEffect(() => {
    setEdges((prev: any[]) =>
      prev.map(e => ({
        ...e,
        data: {
          ...e.data,
          highlighted: !!selectedId && (e.source === selectedId || e.target === selectedId),
        },
        markerEnd: {
          ...(e.markerEnd as any),
          color: !!selectedId && (e.source === selectedId || e.target === selectedId)
            ? C.accent
            : `${C.accent}55`,
        },
      }))
    );
  }, [selectedId, setEdges]);

  // ── Node click ──
  const onNodeClick = useCallback((_: unknown, node: any) => {
    setSelectedId(prev => prev === node.id ? null : node.id);
  }, []);

  // ── Generate report ──
  const handleGenerateReport = useCallback(() => {
    setIsGenerating(true);
    setTimeout(() => {
      setIsGenerating(false);
      const content = [
        "═══════════════════════════════════════════",
        "         OVERWATCH FORENSIC REPORT         ",
        "═══════════════════════════════════════════",
        `Asset ID  : ${assetId}`,
        `Generated : ${new Date().toISOString()}`,
        `Verdict   : ${payload?.nodes.find(n => n.type === "verdict")?.data.label ?? "N/A"}`,
        "",
        "── Node Analysis ──────────────────────────",
        ...(payload?.nodes.map(n => `[${n.type.toUpperCase().padEnd(7)}] ${n.data.label} — score: ${n.data.score ?? "—"}%`) ?? []),
        "",
        "── Ingest Log ─────────────────────────────",
        ...(payload?.ingest_logs ?? []),
        "",
        "═══════════════════════════════════════════",
      ].join("\n");

      const url = URL.createObjectURL(new Blob([content], { type: "text/plain" }));
      const a   = Object.assign(document.createElement("a"), {
        href:     url,
        download: `forensic-report-${(assetId ?? "unknown").slice(-8)}-${Date.now()}.txt`,
      });
      a.click();
      URL.revokeObjectURL(url);
    }, 2600);
  }, [assetId, payload]);

  // ── Loading state ──
  if (isLoading) return (<><GlobalStyles/><LoadingSkeleton/></>);

  return (
    <>
      <GlobalStyles/>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.35 }}
        style={{
          height: "100vh", width: "100vw",
          background: C.bg,
          display: "flex", overflow: "hidden",
          fontFamily: "'DM Sans', sans-serif",
        }}
      >
        {/* ═══════════════ Graph Canvas Area ═══════════════ */}
        <div style={{ flex: 1, position: "relative", minWidth: 0 }} className="nexus-canvas">

          {/* ── Floating Header overlay ── */}
          <div style={{
            position: "absolute", top: 0, left: 0, right: 0, zIndex: 20,
            padding: "18px 22px",
            display: "flex", alignItems: "center", justifyContent: "space-between",
            pointerEvents: "none",
          }}>
            {/* Left: Back + Title */}
            <div style={{ display: "flex", alignItems: "center", gap: "10px", pointerEvents: "auto" }}>
              <motion.button
                whileHover={{ x: -2, scale: 1.03 }}
                whileTap={{ scale: 0.95 }}
                onClick={handleBack}
                style={{
                  display: "flex", alignItems: "center", justifyContent: "center",
                  width: "38px", height: "38px", borderRadius: "10px",
                  background: C.bgCard, border: `1px solid ${C.border}`,
                  cursor: "pointer", color: C.text,
                  boxShadow: "0 2px 8px rgba(0,0,0,0.07)",
                }}
              >
                <ArrowLeft size={17}/>
              </motion.button>

              <motion.div
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1, duration: 0.3 }}
                style={{
                  background: C.bgCard, padding: "8px 15px", borderRadius: "10px",
                  border: `1px solid ${C.border}`,
                  boxShadow: "0 2px 8px rgba(0,0,0,0.07)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "7px", marginBottom: "2px" }}>
                  <GitBranch size={13} color={C.accent}/>
                  <span style={{ fontSize: "13px", fontWeight: 700, color: C.text, letterSpacing: "-0.01em" }}>
                    Nexus Graph
                  </span>
                </div>
                <div style={{
                  fontFamily: "'DM Mono', monospace", fontSize: "9.5px",
                  color: C.textFaint, letterSpacing: "0.06em",
                }}>
                  FAISS Multi-Modal Search
                </div>
              </motion.div>
            </div>

            {/* Right: AUDITOR badge */}
            <motion.div
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.15, duration: 0.3 }}
              style={{
                pointerEvents: "auto",
                display: "flex", alignItems: "center", gap: "8px",
                background: C.bgCard, padding: "8px 14px",
                borderRadius: "10px", border: `1px solid ${C.border}`,
                boxShadow: "0 2px 8px rgba(0,0,0,0.07)",
              }}
            >
              <Shield size={13} color={C.violet}/>
              <span style={{
                fontFamily: "'DM Mono', monospace", fontSize: "11px",
                fontWeight: 600, color: C.textSub, letterSpacing: "0.13em",
              }}>
                AUDITOR
              </span>
              <div style={{
                width: "6px", height: "6px", borderRadius: "50%",
                background: C.violet, boxShadow: `0 0 8px ${C.violet}99`,
              }}/>
            </motion.div>
          </div>

          {/* ── ReactFlow ── */}
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            onPaneClick={() => setSelectedId(null)}
            nodeTypes={NODE_TYPES}
            edgeTypes={EDGE_TYPES}
            fitView
            fitViewOptions={{ padding: 0.18 }}
            minZoom={0.25}
            maxZoom={2.5}
            proOptions={{ hideAttribution: true }}
            style={{ background: "transparent" }}
          >
            <Background
              variant={BackgroundVariant.Dots}
              color={C.bgDot}
              gap={24}
              size={1.3}
            />
            <Controls
              position="bottom-left"
              showInteractive={false}
              style={{ marginBottom: "20px", marginLeft: "20px" }}
            />
          </ReactFlow>

          {/* ── Selection hint ── */}
          <AnimatePresence>
            {!selectedId && payload && (
              <motion.div
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 4 }}
                transition={{ delay: 0.8, duration: 0.3 }}
                style={{
                  position: "absolute", bottom: "24px", left: "50%",
                  transform: "translateX(-50%)",
                  background: C.bgCard, padding: "7px 16px",
                  borderRadius: "20px", border: `1px solid ${C.border}`,
                  boxShadow: "0 2px 8px rgba(0,0,0,0.07)",
                  pointerEvents: "none",
                  display: "flex", alignItems: "center", gap: "7px",
                }}
              >
                <div style={{ width: "5px", height: "5px", borderRadius: "50%", background: C.accent, animation: "pulse-dot 1.5s ease-in-out infinite" }}/>
                <span style={{ fontFamily: "'DM Mono', monospace", fontSize: "10px", color: C.textMuted, letterSpacing: "0.05em" }}>
                  Click any node to inspect
                </span>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* ═══════════════ Forensic Sidebar ═══════════════ */}
        <motion.div
          initial={{ x: 40, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          transition={{ delay: 0.18, duration: 0.4, ease: "easeOut" }}
        >
          <ForensicSidebar
            assetId={assetId ?? "unknown"}
            payload={payload}
            selectedNode={selectedId}
            apiNodes={payload?.nodes ?? []}
            onGenerateReport={handleGenerateReport}
            isGenerating={isGenerating}
          />
        </motion.div>
      </motion.div>
    </>
  );
}
