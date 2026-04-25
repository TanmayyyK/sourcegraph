/**
 * NexusScreen.tsx — Pure Engineering Forensic Workbench
 *
 * Design System: DM Sans + DM Mono · Strict Light Mode · #F5F2EC base
 *
 * Architecture:
 *  1. MOCK_PAYLOAD    — hardcoded realistic data; bypasses fetch for immediate dev testing
 *  2. ForensicNode    — clean white card, flat accent dot, dark text, zero glow
 *  3. ForensicEdge    — thin crisp lines; threat = coral dashed stroke, no SVG filters
 *  4. AuditorWorkbench — ReactFlow graph + slide-in node inspector sidebar
 *  5. Terminal        — light-mode DM Mono build log report; no scanlines, no dark bg
 *  6. Back button     — ArrowLeft → navigate(-1) on both views
 *
 * To restore live fetch: uncomment the useEffect block in NexusScreen and
 * remove the `const [state] = useState(...)` mock line.
 */

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MiniMap,
  Position,
  getBezierPath,
  type Edge,
  type Node,
  type NodeProps,
  type EdgeProps,
  type ReactFlowInstance,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Clock,
  Copy,
  Cpu,
  Database,
  Eye,
  Fingerprint,
  GitBranch,
  Hash,
  Network,
  Radar,
  Server,
  ShieldAlert,
  TerminalSquare,
  X,
  Zap,
} from "lucide-react";
import { useAuth } from "@/components/providers/AuthProvider";

/* ─────────────────────────────────────────────────────────────────────────────
   Design Tokens — mirrors LandingScreen.tsx & CommandCentreHome.tsx exactly
───────────────────────────────────────────────────────────────────────────── */

const C = {
  bg:      "#F5F2EC",    // parchment background — main page surface
  card:    "#FFFFFF",    // pure white — all cards, panels, sidebar, canvas
  bgMuted: "#EEEBE3",    // slightly darker — skeleton, panel headers
  border:  "rgba(0,0,0,0.07)",  // universal crisp border
  text:    "#0F0F0F",    // primary text
  muted:   "#6B6860",    // labels, secondary text
  coral:   "#FF6B47",    // Threat / high-risk
  green:   "#0EA872",    // Success / active
  blue:    "#4C63F7",    // Engine / telemetry / primary accent
  violet:  "#7C5CF7",    // supporting accent (edge labels, etc.)
} as const;

/* ─────────────────────────────────────────────────────────────────────────────
   Font Injection — DM Sans + DM Mono
───────────────────────────────────────────────────────────────────────────── */

function useFonts() {
  useEffect(() => {
    if (document.getElementById("nexus-fonts")) return;
    const link = document.createElement("link");
    link.id    = "nexus-fonts";
    link.rel   = "stylesheet";
    link.href  =
      "https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700;9..40,800&family=DM+Mono:wght@400;500&display=swap";
    document.head.appendChild(link);
  }, []);
}

/* ─────────────────────────────────────────────────────────────────────────────
   Types
───────────────────────────────────────────────────────────────────────────── */

export interface AnalysisPayload {
  nodes:       unknown[];
  edges:       unknown[];
  ingest_logs: string[];
}

type LoadState =
  | { status: "idle" | "loading" }
  | { status: "error"; message: string }
  | { status: "success"; data: AnalysisPayload };

type ForensicNodeData = {
  label: string;
  kind?: string;
  tone?: "threat" | "engine" | "asset" | "neutral";
  raw?: unknown;
};

type EdgeDataShape = {
  isThreat?: boolean;
};

/* ─────────────────────────────────────────────────────────────────────────────
   MOCK PAYLOAD
   Hardcoded realistic forensic data — bypasses the backend fetch entirely.
   6 nodes (1 asset, 3 engines, 3 piracy clusters) + 7 realistic edges.
   Remove/comment the `const [state] = useState(...)` line in NexusScreen
   and restore the useEffect to switch to live mode.
───────────────────────────────────────────────────────────────────────────── */

const MOCK_PAYLOAD: AnalysisPayload = {
  nodes: [
    {
      id:           "asset:vid-9f3c2a",
      kind:         "asset",
      label:        "Video Asset · vid-9f3c2a",
      position:     { x: 400, y: 290 },
      fingerprint:  "sha256:9f3c2a84b1e5d7c0f2a9b3e6d8c1f4a7",
      duration_ms:  5820000,
      format:       "mp4/H.264",
      size_gb:      2.4,
      ingested_at:  "2025-07-14T08:32:11Z",
      risk_score:   0.87,
      classification: "HIGH",
    },
    {
      id:                  "engine:ocr-v4",
      kind:                "engine",
      label:               "Text & OCR Engine (Yug)",
      position:            { x: 60, y: 100 },
      model:               "overwatch-ocr-v4",
      confidence_threshold: 0.91,
      processed_frames:    1740,
      avg_confidence:      0.94,
      status:              "COMPLETE",
      duration_ms:         9140,
    },
    {
      id:             "engine:vision-v3",
      kind:           "engine",
      label:          "Vision Engine (Rohit)",
      position:       { x: 740, y: 100 },
      model:          "owv-vision-3-large",
      dimensions:     512,
      vector_db:      "pinecone:prod-index-3",
      vectors_written: 1740,
      status:         "COMPLETE",
      duration_ms:    3210,
    },
    {
      id:               "engine:analysis-hub",
      kind:             "engine",
      label:            "Forensic Analysis Hub",
      position:         { x: 400, y: 30 },
      model:            "ow-forensic-v1",
      classes_detected: ["watermark", "logo", "caption"],
      inference_ms:     334,
      frames_flagged:   47,
      status:           "COMPLETE",
    },
    {
      id:             "cluster:piracy-sea-7",
      kind:           "cluster",
      label:          "Piracy Cluster · SEA-7",
      position:       { x: 60, y: 490 },
      region:         "Southeast Asia",
      known_domains:  43,
      active_mirrors: 11,
      first_seen:     "2024-11-02",
      last_seen:      "2025-07-13",
      threat_level:   "HIGH",
      vector_distance: 0.042,
      similarity:     0.96,
    },
    {
      id:              "cluster:piracy-eu-w3",
      kind:            "cluster",
      label:           "Piracy Cluster · EU-W-3",
      position:        { x: 740, y: 490 },
      region:          "EU West (DE / NL)",
      known_domains:   18,
      active_mirrors:  4,
      first_seen:      "2025-01-19",
      last_seen:       "2025-07-12",
      threat_level:    "MEDIUM",
      vector_distance: 0.11,
      similarity:      0.83,
    },
    {
      id:                  "cluster:watermark-spoof",
      kind:                "cluster",
      label:               "Watermark Spoof Group",
      position:            { x: 400, y: 560 },
      tactic:              "watermark_removal",
      toolchain:           "ffmpeg + inpaint-v2",
      assets_matched:      7,
      threat_level:        "CRITICAL",
      vector_distance:     0.027,
      similarity:          0.98,
      timestamp_match_ms:  120,
    },
  ],
  edges: [
    { source: "engine:ocr-v4",      target: "asset:vid-9f3c2a",          kind: "processed",    label: "OCR scan"    },
    { source: "engine:vision-v3",   target: "asset:vid-9f3c2a",          kind: "embedded",     label: "Vision pass"  },
    { source: "engine:analysis-hub", target: "asset:vid-9f3c2a",          kind: "classified",   label: "Hub Analysis" },
    { source: "asset:vid-9f3c2a",   target: "cluster:piracy-sea-7",      kind: "threat_match", label: "Match 96%"   },
    { source: "asset:vid-9f3c2a",   target: "cluster:piracy-eu-w3",      kind: "threat_match", label: "Match 83%"   },
    { source: "asset:vid-9f3c2a",   target: "cluster:watermark-spoof",   kind: "threat_match", label: "Match 98%"   },
    { source: "engine:ocr-v4",      target: "cluster:watermark-spoof",   kind: "evidence",     label: "WM removed"  },
  ],
  ingest_logs: [
    "[2025-07-14T08:32:01Z] [INF] [orchestrator] Pipeline initialized · asset=vid-9f3c2a version=3.4.1",
    "[2025-07-14T08:32:02Z] [INF] [ingest] File received · size=2.4GB format=mp4/H.264 codec=avc1",
    "[2025-07-14T08:32:03Z] [INF] [fingerprint] SHA-256 computed · hash=9f3c2a84b1e5d7c0f2a9b3e6d8c1f4a7",
    "[2025-07-14T08:32:04Z] [INF] [chain-of-custody] Ledger entry written · block=00041fa2 prev=0003e91c",
    "[2025-07-14T08:32:05Z] [INF] [frame-sampler] Sampling 1740 frames at 0.3fps · keyframes=87",
    "[2025-07-14T08:32:06Z] [INF] [ocr-v4] Starting text extraction on 1740 frames",
    "[2025-07-14T08:32:09Z] [INF] [ocr-v4] Processed 500/1740 frames · avg_confidence=0.96",
    "[2025-07-14T08:32:11Z] [OK ] [ocr-v4] Extraction complete · frames=1740 avg_confidence=0.94 duration=9140ms",
    "[2025-07-14T08:32:11Z] [INF] [vision-v3] Running watermark + logo + caption detection",
    "[2025-07-14T08:32:13Z] [WARN] [vision-v3] Low-confidence region at frame 812 · score=0.54 · class=logo",
    "[2025-07-14T08:32:14Z] [WARN] [vision-v3] Possible watermark artifact at frames 1102–1118 · confidence=0.71",
    "[2025-07-14T08:32:15Z] [OK ] [vision-v3] Classification done · flagged=47 classes=[watermark,caption] duration=4210ms",
    "[2025-07-14T08:32:15Z] [INF] [embed-v2] Generating 1536-dim embedding vectors · model=overwatch-embed-v2",
    "[2025-07-14T08:32:18Z] [OK ] [embed-v2] 1740 vectors written to pinecone:prod-index-3 · duration=3210ms",
    "[2025-07-14T08:32:19Z] [INF] [nexus] Running ANN similarity search against known piracy clusters",
    "[2025-07-14T08:32:19Z] [INF] [nexus] Querying 4.2M cluster vectors across 3 threat indices",
    "[2025-07-14T08:32:21Z] [ERR] [nexus] CRITICAL: Watermark removal detected · cluster=watermark-spoof · similarity=0.98 · distance=0.027",
    "[2025-07-14T08:32:21Z] [ERR] [nexus] HIGH: Threat match confirmed · cluster=piracy-sea-7 · similarity=0.96 · distance=0.042",
    "[2025-07-14T08:32:22Z] [WARN] [nexus] MEDIUM: Partial match · cluster=piracy-eu-w3 · similarity=0.83 · distance=0.11",
    "[2025-07-14T08:32:22Z] [OK ] [risk-scorer] Score computed · risk=0.87 · classification=HIGH · contributing_factors=3",
    "[2025-07-14T08:32:23Z] [INF] [graph-builder] Constructing Nexus topology · nodes=7 edges=7",
    "[2025-07-14T08:32:23Z] [OK ] [graph-builder] Topology ready · threat_edges=4 data_edges=3",
    "[2025-07-14T08:32:23Z] [OK ] [orchestrator] Pipeline complete · total_duration=22.1s · result=HIGH_RISK",
    "[2025-07-14T08:32:23Z] [INF] [api] Result available at /api/v1/analysis/vid-9f3c2a",
  ],
};

/* ─────────────────────────────────────────────────────────────────────────────
   Motion Variants — single fast fade-in only, no springs, no blobs
───────────────────────────────────────────────────────────────────────────── */

const fadeIn = {
  hidden: { opacity: 0, y: 10 },
  show:   { opacity: 1, y: 0, transition: { duration: 0.2, ease: "easeOut" } },
};

const sidebarVariant = {
  hidden: { opacity: 0, x: 16 },
  show:   { opacity: 1, x: 0,  transition: { duration: 0.2, ease: "easeOut" } },
  exit:   { opacity: 0, x: 16, transition: { duration: 0.15, ease: "easeIn" } },
};

/* ─────────────────────────────────────────────────────────────────────────────
   Helpers
───────────────────────────────────────────────────────────────────────────── */

function safeString(v: unknown): string {
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  if (v === null || v === undefined) return "";
  try { return JSON.stringify(v); } catch { return String(v); }
}

function pick<T extends Record<string, unknown>>(
  obj: unknown,
  key: string,
): T[keyof T] | undefined {
  if (!obj || typeof obj !== "object") return undefined;
  return (obj as Record<string, unknown>)[key] as T[keyof T];
}

function toNodeId(n: unknown, idx: number): string {
  const id =
    pick<Record<string, unknown>>(n, "id") ??
    pick<Record<string, unknown>>(n, "node_id") ??
    pick<Record<string, unknown>>(n, "key");
  const s = safeString(id);
  return s ? s : `node-${idx}`;
}

function toEdgeId(e: unknown, idx: number, source: string, target: string): string {
  const id = pick<Record<string, unknown>>(e, "id");
  const s  = safeString(id);
  return s ? s : `edge-${source}-${target}-${idx}`;
}

function toXY(n: unknown): { x: number; y: number } | null {
  const pos = pick<Record<string, unknown>>(n, "position");
  if (pos && typeof pos === "object") {
    const x = Number((pos as Record<string, unknown>).x);
    const y = Number((pos as Record<string, unknown>).y);
    if (Number.isFinite(x) && Number.isFinite(y)) return { x, y };
  }
  const x = Number(pick<Record<string, unknown>>(n, "x"));
  const y = Number(pick<Record<string, unknown>>(n, "y"));
  if (Number.isFinite(x) && Number.isFinite(y)) return { x, y };
  return null;
}

function inferKind(n: unknown): string {
  const kind =
    safeString(pick<Record<string, unknown>>(n, "kind")) ||
    safeString(pick<Record<string, unknown>>(n, "type")) ||
    safeString(pick<Record<string, unknown>>(n, "category"));
  return kind ? kind.toLowerCase() : "node";
}

function inferTone(kind: string): ForensicNodeData["tone"] {
  if (
    kind.includes("threat") || kind.includes("piracy") ||
    kind.includes("cluster") || kind.includes("risk")
  ) return "threat";
  if (
    kind.includes("engine") || kind.includes("model") ||
    kind.includes("ocr") || kind.includes("embed") ||
    kind.includes("vision")
  ) return "engine";
  if (kind.includes("asset")) return "asset";
  return "neutral";
}

function toneAccent(tone: ForensicNodeData["tone"]): string {
  if (tone === "threat") return C.coral;
  if (tone === "engine") return C.blue;
  if (tone === "asset")  return C.violet;
  return C.green;
}

function mapPayloadToFlow(
  payload: AnalysisPayload,
  assetId: string,
): { nodes: Node<ForensicNodeData>[]; edges: Edge[] } {
  const rawNodes = payload.nodes ?? [];
  const rawEdges = payload.edges ?? [];

  const computed: Node<ForensicNodeData>[] = rawNodes.map((n, idx) => {
    const id   = toNodeId(n, idx);
    const kind = inferKind(n);
    const label =
      safeString(pick<Record<string, unknown>>(n, "label")) ||
      safeString(pick<Record<string, unknown>>(n, "name")) ||
      safeString(pick<Record<string, unknown>>(n, "title")) ||
      id;
    const pos = toXY(n);
    return {
      id,
      type: "forensicNode",
      position: pos ?? { x: (idx % 4) * 300, y: Math.floor(idx / 4) * 190 },
      data: { label, kind, tone: inferTone(kind), raw: n },
    };
  });

  // Fallback: ensure there's always at least an asset node
  if (computed.length === 0) {
    computed.push({
      id:       `asset:${assetId}`,
      type:     "forensicNode",
      position: { x: 0, y: 0 },
      data: {
        label: `Video Asset · ${assetId}`,
        kind:  "asset",
        tone:  "asset",
        raw:   { id: assetId },
      },
    });
  }

  const nodeIds = new Set(computed.map((n) => n.id));

  const edges: Edge[] = rawEdges
    .map((e, idx) => {
      const source =
        safeString(pick<Record<string, unknown>>(e, "source")) ||
        safeString(pick<Record<string, unknown>>(e, "from")) ||
        safeString(pick<Record<string, unknown>>(e, "src"));
      const target =
        safeString(pick<Record<string, unknown>>(e, "target")) ||
        safeString(pick<Record<string, unknown>>(e, "to")) ||
        safeString(pick<Record<string, unknown>>(e, "dst"));

      if (!source || !target) return null;
      if (!nodeIds.has(source) || !nodeIds.has(target)) return null;

      const kind = safeString(pick<Record<string, unknown>>(e, "kind")) || "link";
      const label = safeString(pick<Record<string, unknown>>(e, "label"));
      const isThreat =
        kind.toLowerCase().includes("threat") ||
        kind.toLowerCase().includes("piracy") ||
        kind.toLowerCase().includes("match") ||
        kind.toLowerCase().includes("evidence");

      return {
        id:       toEdgeId(e, idx, source, target),
        source,
        target,
        type:     "forensicEdge",
        label:    label || undefined,
        animated: false,
        data:     { isThreat } satisfies EdgeDataShape,
      } satisfies Edge;
    })
    .filter((x): x is Edge => Boolean(x));

  return { nodes: computed, edges };
}

/* ─────────────────────────────────────────────────────────────────────────────
   ForensicEdge — thin crisp SVG lines, zero glow filters
   Threat linkage = coral dashed stroke  |  Data flow = muted solid stroke
───────────────────────────────────────────────────────────────────────────── */

function ForensicEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  label,
}: EdgeProps) {
  const edgeData  = (data ?? {}) as EdgeDataShape;
  const isThreat  = edgeData.isThreat ?? false;
  const stroke    = isThreat ? C.coral : "rgba(0,0,0,0.18)";
  const strokeW   = isThreat ? 1.5 : 1;
  const dashArray = isThreat ? "6 5" : undefined;

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX, sourceY, sourcePosition,
    targetX, targetY, targetPosition,
  });

  return (
    <g>
      <path
        id={id}
        d={edgePath}
        fill="none"
        stroke={stroke}
        strokeWidth={strokeW}
        strokeDasharray={dashArray}
        strokeLinecap="round"
        className="react-flow__edge-path"
      />
      {label && (
        <g transform={`translate(${labelX}, ${labelY})`}>
          <rect
            x="-24" y="-10" width="48" height="20" rx="4"
            fill={C.card}
            stroke={isThreat ? C.coral : C.border}
            strokeWidth="1"
          />
          <text
            textAnchor="middle"
            dominantBaseline="middle"
            style={{
              fontSize: "9px",
              fontFamily: "DM Mono, monospace",
              fill: isThreat ? C.coral : C.muted,
              letterSpacing: "0.04em",
            }}
          >
            {String(label).slice(0, 14)}
          </text>
        </g>
      )}
    </g>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   Kind icon / label maps
───────────────────────────────────────────────────────────────────────────── */

const KIND_ICONS: Record<string, ReactNode> = {
  asset:   <Database    size={12} />,
  cluster: <ShieldAlert size={12} />,
  engine:  <Cpu         size={12} />,
  embed:   <Zap         size={12} />,
  ocr:     <Eye         size={12} />,
  model:   <Network     size={12} />,
  server:  <Server      size={12} />,
  threat:  <ShieldAlert size={12} />,
  branch:  <GitBranch   size={12} />,
  node:    <Activity    size={12} />,
};

const KIND_LABELS: Record<string, string> = {
  asset:   "Asset",
  cluster: "Piracy Cluster",
  engine:  "Analysis Engine",
  embed:   "Embeddings",
  ocr:     "OCR Engine",
  model:   "ML Model",
  server:  "Server",
  threat:  "Threat Node",
  node:    "Module",
};

/* ─────────────────────────────────────────────────────────────────────────────
   ForensicNode — clean white card with flat colored dot, dark text, no glow
───────────────────────────────────────────────────────────────────────────── */

function ForensicNode({ data, selected }: NodeProps<Node<ForensicNodeData>>) {
  const accent    = toneAccent(data.tone);
  const kindKey   = data.kind ?? "node";
  const kindLabel = KIND_LABELS[kindKey] ?? kindKey;
  const kindIcon  = KIND_ICONS[kindKey] ?? <Activity size={12} />;

  const rawId =
    typeof data.raw === "object" && data.raw !== null && "id" in (data.raw as Record<string, unknown>)
      ? safeString((data.raw as Record<string, unknown>).id)
      : kindKey;

  return (
    <div
      style={{
        minWidth:    210,
        maxWidth:    280,
        borderRadius: 10,
        border: `1px solid ${selected ? accent : C.border}`,
        background: C.card,
        padding:    "12px 14px",
        boxShadow:  selected
          ? `0 0 0 2px ${accent}20, 0 2px 12px rgba(0,0,0,0.06)`
          : "0 1px 4px rgba(0,0,0,0.05)",
        fontFamily: "DM Sans, sans-serif",
        cursor:     "pointer",
        transition: "border-color 0.12s, box-shadow 0.12s",
      }}
    >
      {/* Top accent bar (thin, only on selected) */}
      {selected && (
        <div style={{
          position: "absolute", top: -1, left: 10, right: 10,
          height: 2, borderRadius: "0 0 2px 2px",
          background: accent,
        }} />
      )}

      {/* Row 1: flat dot + kind label + icon */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 9 }}>
        <div style={{
          width: 7, height: 7, borderRadius: "50%",
          background: accent, flexShrink: 0,
        }} />
        <span style={{
          fontSize: 9.5, fontWeight: 600, letterSpacing: "0.07em",
          color: C.muted, textTransform: "uppercase", flex: 1,
        }}>
          {kindLabel}
        </span>
        <span style={{ color: C.muted, display: "flex", opacity: 0.55 }}>
          {kindIcon}
        </span>
      </div>

      {/* Row 2: main label */}
      <p style={{
        fontSize: 13, fontWeight: 600, color: C.text,
        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        letterSpacing: "-0.01em", marginBottom: 5,
      }}>
        {data.label}
      </p>

      {/* Row 3: mono ID */}
      <p style={{
        fontSize: 10, fontFamily: "DM Mono, monospace",
        color: C.muted,
        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
      }}>
        {rawId}
      </p>

      {/* Handles */}
      <Handle
        type="target"
        position={Position.Left}
        style={{
          width: 8, height: 8,
          border: `1.5px solid ${C.border}`,
          background: C.card, left: -4,
        }}
      />
      <Handle
        type="source"
        position={Position.Right}
        style={{
          width: 8, height: 8,
          border: `1.5px solid ${C.border}`,
          background: C.card, right: -4,
        }}
      />
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   Shared: BackButton — used by both views
───────────────────────────────────────────────────────────────────────────── */

function BackButton({ onBack }: { onBack: () => void }) {
  return (
    <button
      type="button"
      onClick={onBack}
      style={{
        display:    "inline-flex",
        alignItems: "center",
        gap:        6,
        marginBottom: 20,
        padding:    "6px 13px",
        borderRadius: 7,
        border:     `1px solid ${C.border}`,
        background: C.card,
        color:      C.muted,
        fontSize:   12,
        fontWeight: 500,
        cursor:     "pointer",
        fontFamily: "DM Sans, sans-serif",
        transition: "background 0.12s",
      }}
      onMouseEnter={e => (e.currentTarget.style.background = C.bgMuted)}
      onMouseLeave={e => (e.currentTarget.style.background = C.card)}
    >
      <ArrowLeft size={13} />
      Back to Insights
    </button>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   LightSkeleton — parchment pulse skeleton
───────────────────────────────────────────────────────────────────────────── */

function LightSkeleton() {
  return (
    <div style={{
      minHeight: "100vh", background: C.bg,
      padding: "28px 32px", fontFamily: "DM Sans, sans-serif",
    }}>
      <style>{`@keyframes pw{0%,100%{opacity:1}50%{opacity:.45}}`}</style>
      <div style={{ maxWidth: 1440, margin: "0 auto" }}>
        <div style={{ marginBottom: 22 }}>
          <div style={{ height: 11, width: 110, borderRadius: 6, background: C.bgMuted, marginBottom: 10, animation: "pw 1.6s ease-in-out infinite" }} />
          <div style={{ height: 30, width: 420, borderRadius: 8, background: C.bgMuted, marginBottom: 8, animation: "pw 1.6s ease-in-out infinite" }} />
          <div style={{ height: 14, width: 300, borderRadius: 6, background: C.bgMuted, animation: "pw 1.6s ease-in-out infinite" }} />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 300px", gap: 12 }}>
          <div style={{ height: 560, borderRadius: 12, background: C.bgMuted, animation: "pw 1.6s ease-in-out infinite" }} />
          <div style={{ height: 560, borderRadius: 12, background: C.bgMuted, animation: "pw 1.6s ease-in-out infinite" }} />
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   ErrorPanel — light mode, clean
───────────────────────────────────────────────────────────────────────────── */

function ErrorPanel({ message }: { message: string }) {
  return (
    <div style={{
      minHeight: "100vh", background: C.bg,
      display: "flex", alignItems: "center", justifyContent: "center",
      fontFamily: "DM Sans, sans-serif", padding: 32,
    }}>
      <div style={{
        maxWidth: 520, width: "100%",
        background: C.card, borderRadius: 12,
        border: `1px solid ${C.border}`,
        padding: "28px 32px",
        boxShadow: "0 2px 14px rgba(0,0,0,0.06)",
      }}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 8, flexShrink: 0,
            background: `${C.coral}10`,
            border: `1px solid ${C.coral}28`,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <AlertTriangle size={16} color={C.coral} />
          </div>
          <div>
            <p style={{ fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase", color: C.muted, marginBottom: 5 }}>
              Analysis Error
            </p>
            <h2 style={{ fontSize: 16, fontWeight: 700, color: C.text, marginBottom: 8, letterSpacing: "-0.01em" }}>
              Unable to load forensic payload
            </h2>
            <p style={{ fontSize: 13, color: C.muted, lineHeight: 1.55 }}>{message}</p>
            <p style={{ marginTop: 14, fontSize: 11, fontFamily: "DM Mono, monospace", color: C.muted }}>
              Verify backend at <span style={{ color: C.text }}>localhost:8000</span> · assetId must exist
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   SidebarDetails type
───────────────────────────────────────────────────────────────────────────── */

type SidebarDetails = {
  id:                  string;
  label:               string;
  kind:                string;
  vector_distance?:    unknown;
  similarity_score?:   unknown;
  timestamp_match_ms?: unknown;
  raw:                 unknown;
  edges:               number;
  nodes:               number;
};

/* ─────────────────────────────────────────────────────────────────────────────
   KvRow — light mode key-value row used in the node inspector
───────────────────────────────────────────────────────────────────────────── */

function KvRow({
  label,
  value,
  accent = false,
}: {
  label:   string;
  value:   ReactNode;
  accent?: boolean;
}) {
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "40% 1fr",
      padding: "5.5px 0",
      borderBottom: `1px solid ${C.border}`,
      alignItems: "start",
    }}>
      <span style={{
        fontSize: 10, letterSpacing: "0.07em", textTransform: "uppercase",
        color: C.muted, paddingTop: 1.5,
      }}>
        {label}
      </span>
      <span style={{
        fontSize: 11.5,
        fontFamily: "DM Mono, monospace",
        color:  accent ? C.coral : C.text,
        wordBreak: "break-all",
        lineHeight: 1.55,
      }}>
        {value}
      </span>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   NodeDetailSidebar — pure white slide-in inspector panel
───────────────────────────────────────────────────────────────────────────── */

function NodeDetailSidebar({
  details,
  onClose,
}: {
  details:  SidebarDetails;
  onClose:  () => void;
}) {
  const isThreat = details.kind?.includes("threat") || details.kind?.includes("cluster");
  const accent   = isThreat ? C.coral : C.blue;

  const rawEntries = useMemo(() => {
    if (!details.raw || typeof details.raw !== "object") return [];
    return Object.entries(details.raw as Record<string, unknown>)
      .filter(([k]) => !["id", "kind", "label", "position"].includes(k))
      .slice(0, 14);
  }, [details.raw]);

  return (
    <motion.aside
      key="sidebar"
      variants={sidebarVariant}
      initial="hidden"
      animate="show"
      exit="exit"
      style={{
        position: "relative",
        overflow: "hidden",
        borderRadius: 12,
        border: `1px solid ${C.border}`,
        background: C.card,
        display: "flex",
        flexDirection: "column",
        height: "100%",
        fontFamily: "DM Sans, sans-serif",
      }}
    >
      {/* Top accent bar */}
      <div style={{ height: 3, flexShrink: 0, background: accent }} />

      {/* Header */}
      <div style={{
        display: "flex", alignItems: "flex-start", justifyContent: "space-between",
        padding: "14px 16px 12px",
        borderBottom: `1px solid ${C.border}`,
        flexShrink: 0,
      }}>
        <div style={{ minWidth: 0 }}>
          <p style={{
            fontSize: 9.5, letterSpacing: "0.12em", textTransform: "uppercase",
            color: C.muted, marginBottom: 5,
          }}>
            Node Inspector
          </p>
          <h2 style={{
            fontSize: 14, fontWeight: 700, color: C.text,
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
            maxWidth: 210, letterSpacing: "-0.01em",
          }}>
            {details.label}
          </h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          style={{
            width: 28, height: 28, borderRadius: 6, flexShrink: 0,
            border: `1px solid ${C.border}`,
            background: "transparent",
            display: "flex", alignItems: "center", justifyContent: "center",
            cursor: "pointer", color: C.muted,
            transition: "background 0.12s",
          }}
          onMouseEnter={e => (e.currentTarget.style.background = C.bgMuted)}
          onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
        >
          <X size={13} />
        </button>
      </div>

      {/* Scrollable body */}
      <div style={{
        flex: 1, overflowY: "auto",
        padding: "14px 16px",
        display: "flex", flexDirection: "column", gap: 14,
        scrollbarWidth: "thin",
        scrollbarColor: `${C.border} transparent`,
      }}>

        {/* ── Metric chips 2×2 grid ── */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          {[
            {
              label: "Vector Dist",
              val:   details.vector_distance != null ? safeString(details.vector_distance) : "—",
              color: details.vector_distance != null ? C.coral : C.muted,
              icon:  <Zap size={11} />,
            },
            {
              label: "Similarity",
              val:   details.similarity_score != null
                ? `${Math.round(Number(details.similarity_score) * 100)}%`
                : "—",
              color: details.similarity_score != null ? C.coral : C.muted,
              icon:  <Fingerprint size={11} />,
            },
            {
              label: "Timestamp Δ",
              val:   details.timestamp_match_ms != null
                ? `±${safeString(details.timestamp_match_ms)}ms`
                : "—",
              color: C.blue,
              icon:  <Clock size={11} />,
            },
            {
              label: "Category",
              val:   details.kind.toUpperCase(),
              color: isThreat ? C.coral : C.blue,
              icon:  <Hash size={11} />,
            },
          ].map(({ label, val, color, icon }) => (
            <div
              key={label}
              style={{
                borderRadius: 8,
                border: `1px solid ${C.border}`,
                background: C.bg,
                padding: "10px 12px",
              }}
            >
              <div style={{
                display: "flex", alignItems: "center", gap: 5,
                marginBottom: 5, color: C.muted,
              }}>
                {icon}
                <span style={{ fontSize: 9, letterSpacing: "0.10em", textTransform: "uppercase" }}>
                  {label}
                </span>
              </div>
              <p style={{
                fontSize: 14, fontFamily: "DM Mono, monospace",
                fontWeight: 600, color,
              }}>
                {val}
              </p>
            </div>
          ))}
        </div>

        {/* ── Node Attributes KV grid ── */}
        <div style={{
          borderRadius: 8, border: `1px solid ${C.border}`,
          background: C.bg, padding: "12px 14px",
        }}>
          <p style={{
            fontSize: 9.5, letterSpacing: "0.10em", textTransform: "uppercase",
            color: C.muted, marginBottom: 10,
          }}>
            Node Attributes
          </p>
          <KvRow label="Node ID" value={details.id} />
          <KvRow label="Kind"    value={details.kind} />
          {rawEntries.map(([k, v]) => (
            <KvRow
              key={k}
              label={k}
              value={safeString(v) || "—"}
              accent={
                k.toLowerCase().includes("threat") ||
                k.toLowerCase().includes("risk") ||
                k.toLowerCase().includes("vector") ||
                k.toLowerCase().includes("similarity")
              }
            />
          ))}
        </div>

        {/* ── Graph stats ── */}
        <div style={{ display: "flex", gap: 8 }}>
          {[
            { label: "Total Nodes", val: details.nodes },
            { label: "Total Edges", val: details.edges },
          ].map(({ label, val }) => (
            <div key={label} style={{
              flex: 1, borderRadius: 8,
              border: `1px solid ${C.border}`,
              background: C.bg,
              padding: "10px 12px",
              textAlign: "center",
            }}>
              <p style={{
                fontSize: 9, letterSpacing: "0.10em", textTransform: "uppercase",
                color: C.muted, marginBottom: 5,
              }}>
                {label}
              </p>
              <p style={{
                fontFamily: "DM Mono, monospace",
                fontSize: 22, fontWeight: 700, color: C.text,
              }}>
                {val}
              </p>
            </div>
          ))}
        </div>

        {/* ── Raw JSON payload ── */}
        <div style={{
          borderRadius: 8, border: `1px solid ${C.border}`,
          background: C.bg, overflow: "hidden",
        }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "8px 14px",
            borderBottom: `1px solid ${C.border}`,
          }}>
            <Radar size={11} color={C.muted} />
            <span style={{
              fontSize: 9.5, fontFamily: "DM Mono, monospace",
              letterSpacing: "0.10em", color: C.muted,
            }}>
              RAW PAYLOAD
            </span>
          </div>
          <pre style={{
            maxHeight: 170, overflowY: "auto",
            padding: "12px 14px",
            fontFamily: "DM Mono, monospace", fontSize: 10.5,
            lineHeight: 1.7, color: C.blue,
            whiteSpace: "pre-wrap", wordBreak: "break-all",
            scrollbarWidth: "thin",
            scrollbarColor: `${C.border} transparent`,
          }}>
            {JSON.stringify(details.raw, null, 2)}
          </pre>
        </div>
      </div>
    </motion.aside>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   Terminal — Light-mode DM Mono build-log report (Feeder view)
   No scanlines · No dark backgrounds · No typewriter animation
───────────────────────────────────────────────────────────────────────────── */

type LogLevel = "error" | "warn" | "success" | "debug" | "info";

function parseLogLevel(line: string): LogLevel {
  const l = line.toLowerCase();
  if (l.includes("error") || l.includes("fail") || l.includes("critical")) return "error";
  if (l.includes("warn")  || l.includes("caution"))                          return "warn";
  if (l.includes("[ok") || l.includes("success") || l.includes("complete"))  return "success";
  if (l.includes("debug") || l.includes("trace"))                            return "debug";
  return "info";
}

const LOG_STYLES: Record<LogLevel, { textColor: string; labelColor: string; bg: string; label: string }> = {
  error:   { textColor: C.text, labelColor: C.coral,           bg: `${C.coral}08`,   label: "ERR" },
  warn:    { textColor: C.text, labelColor: "#B86A00",          bg: "#FFF8E8",         label: "WRN" },
  success: { textColor: C.text, labelColor: C.green,            bg: `${C.green}08`,   label: " OK" },
  debug:   { textColor: C.text, labelColor: C.blue,             bg: `${C.blue}06`,    label: "DBG" },
  info:    { textColor: C.text, labelColor: C.muted,            bg: "transparent",     label: "INF" },
};

function Terminal({ logs, onBack }: { logs: string[]; onBack: () => void }) {
  const [copied, setCopied]    = useState(false);
  const termRef                = useRef<HTMLDivElement>(null);
  const text                   = useMemo(() => logs.join("\n"), [logs]);
  const errors                 = useMemo(() => logs.filter(l => parseLogLevel(l) === "error").length, [logs]);
  const warnings               = useMemo(() => logs.filter(l => parseLogLevel(l) === "warn").length, [logs]);

  const copy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch { /* silent */ }
  }, [text]);

  useEffect(() => {
    if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight;
  }, [logs.length]);

  return (
    <motion.div
      variants={fadeIn}
      initial="hidden"
      animate="show"
      style={{
        minHeight:  "100vh",
        background: C.bg,
        padding:    "28px 32px 48px",
        fontFamily: "DM Sans, sans-serif",
      }}
    >
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>

        {/* Back */}
        <BackButton onBack={onBack} />

        {/* Page header */}
        <div style={{
          display: "flex", alignItems: "flex-start",
          justifyContent: "space-between",
          marginBottom: 20, flexWrap: "wrap", gap: 12,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{
              width: 40, height: 40, borderRadius: 10,
              border: `1px solid ${C.border}`,
              background: C.card,
              display: "flex", alignItems: "center", justifyContent: "center",
              boxShadow: "0 1px 4px rgba(0,0,0,0.05)",
            }}>
              <TerminalSquare size={18} color={C.blue} />
            </div>
            <div>
              <p style={{ fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase", color: C.muted, marginBottom: 2 }}>
                Data Feeder
              </p>
              <h1 style={{ fontSize: 20, fontWeight: 700, color: C.text, letterSpacing: "-0.02em" }}>
                Ingestion Build Log
              </h1>
            </div>
          </div>

          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            {errors > 0 && (
              <div style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "5px 11px", borderRadius: 6,
                border: `1px solid ${C.coral}28`,
                background: `${C.coral}08`,
                fontSize: 11, fontWeight: 600, color: C.coral,
                fontFamily: "DM Mono, monospace",
              }}>
                <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.coral }} />
                {errors} error{errors !== 1 ? "s" : ""}
              </div>
            )}
            {warnings > 0 && (
              <div style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "5px 11px", borderRadius: 6,
                border: "1px solid #B86A0028",
                background: "#FFF8E8",
                fontSize: 11, fontWeight: 600, color: "#B86A00",
                fontFamily: "DM Mono, monospace",
              }}>
                {warnings} warning{warnings !== 1 ? "s" : ""}
              </div>
            )}
            <button
              type="button"
              onClick={copy}
              style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "6px 14px", borderRadius: 6,
                border: `1px solid ${C.border}`,
                background: C.card,
                color:  copied ? C.green : C.muted,
                fontSize: 12, fontWeight: 500, cursor: "pointer",
                fontFamily: "inherit",
                transition: "color 0.15s",
              }}
            >
              <Copy size={12} />
              {copied ? "Copied!" : "Copy Logs"}
            </button>
          </div>
        </div>

        {/* Log panel */}
        <div style={{
          borderRadius: 10,
          border: `1px solid ${C.border}`,
          background: C.card,
          overflow: "hidden",
          boxShadow: "0 1px 6px rgba(0,0,0,0.05)",
        }}>
          {/* Panel title bar */}
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "9px 16px",
            borderBottom: `1px solid ${C.border}`,
            background: C.bg,
          }}>
            <span style={{
              fontFamily: "DM Mono, monospace", fontSize: 10.5,
              color: C.muted, letterSpacing: "0.08em",
            }}>
              ORCHESTRATOR · INGEST STREAM · {String(logs.length).padStart(4, "0")} EVENTS
            </span>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.green }} />
              <span style={{
                fontFamily: "DM Mono, monospace", fontSize: 10,
                color: C.green, letterSpacing: "0.10em", fontWeight: 500,
              }}>
                PIPELINE COMPLETE
              </span>
            </div>
          </div>

          {/* Log lines */}
          <div
            ref={termRef}
            style={{
              maxHeight: "65vh", overflowY: "auto",
              padding: "6px 0",
              scrollbarWidth: "thin",
              scrollbarColor: `${C.border} transparent`,
            }}
          >
            {logs.length === 0 ? (
              <p style={{
                fontFamily: "DM Mono, monospace", fontSize: 12,
                color: C.muted, padding: "10px 18px",
              }}>
                No ingest logs returned · expected key: ingest_logs
              </p>
            ) : (
              logs.map((line, idx) => {
                const level = parseLogLevel(line);
                const st    = LOG_STYLES[level];
                return (
                  <div
                    key={idx}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: 10,
                      padding: "2px 18px",
                      background: st.bg,
                      fontFamily: "DM Mono, monospace",
                      fontSize: 11.5,
                      lineHeight: 1.8,
                    }}
                  >
                    {/* Line number */}
                    <span style={{
                      color: C.muted, flexShrink: 0,
                      fontSize: 10, paddingTop: 3,
                      userSelect: "none", minWidth: 28,
                      textAlign: "right",
                    }}>
                      {String(idx + 1).padStart(3, "0")}
                    </span>

                    {/* Level tag */}
                    <span style={{
                      flexShrink: 0, fontSize: 9.5,
                      fontWeight: 600, letterSpacing: "0.06em",
                      paddingTop: 3, userSelect: "none",
                      color: st.labelColor,
                      minWidth: 26,
                    }}>
                      {st.label}
                    </span>

                    {/* Log content */}
                    <span style={{ color: st.textColor, wordBreak: "break-all" }}>
                      {line}
                    </span>
                  </div>
                );
              })
            )}
          </div>

          {/* Footer bar */}
          <div style={{
            borderTop: `1px solid ${C.border}`,
            padding: "8px 18px",
            display: "flex", alignItems: "center", justifyContent: "space-between",
            background: C.bg,
          }}>
            <div style={{ display: "flex", gap: 20 }}>
              {[
                { label: "Events",   value: logs.length, color: C.text },
                { label: "Errors",   value: errors,      color: errors   > 0 ? C.coral   : C.muted },
                { label: "Warnings", value: warnings,    color: warnings > 0 ? "#B86A00" : C.muted },
              ].map(({ label, value, color }) => (
                <span key={label} style={{ fontSize: 10.5, fontFamily: "DM Mono, monospace", color: C.muted }}>
                  {label}:{" "}
                  <span style={{ color, fontWeight: 600 }}>{value}</span>
                </span>
              ))}
            </div>
            <span style={{ fontSize: 10, fontFamily: "DM Mono, monospace", color: C.muted, letterSpacing: "0.08em" }}>
              /api/v1/ingest/stream
            </span>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   AuditorWorkbench — Enterprise-grade ReactFlow forensic graph view
───────────────────────────────────────────────────────────────────────────── */

function AuditorWorkbench({
  assetId,
  payload,
  onBack,
}: {
  assetId: string;
  payload: AnalysisPayload;
  onBack:  () => void;
}) {
  const flow = useMemo(() => mapPayloadToFlow(payload, assetId), [payload, assetId]);

  const [selectedNode, setSelectedNode] = useState<Node<ForensicNodeData> | null>(
    flow.nodes[0] ?? null,
  );
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [rf, setRf]                   = useState<ReactFlowInstance | null>(null);

  const nodeTypes = useMemo(() => ({ forensicNode: ForensicNode }), []);
  const edgeTypes = useMemo(() => ({ forensicEdge: ForensicEdge }), []);

  const details = useMemo<SidebarDetails>(() => {
    const d    = selectedNode?.data;
    const raw  = d?.raw ?? null;
    const kind = d?.kind ?? "node";
    return {
      id:    selectedNode?.id ?? "—",
      label: d?.label ?? "—",
      kind,
      vector_distance:
        typeof raw === "object" && raw && "vector_distance" in (raw as Record<string, unknown>)
          ? (raw as Record<string, unknown>).vector_distance
          : undefined,
      similarity_score:
        typeof raw === "object" && raw && "similarity" in (raw as Record<string, unknown>)
          ? (raw as Record<string, unknown>).similarity
          : undefined,
      timestamp_match_ms:
        typeof raw === "object" && raw && "timestamp_match_ms" in (raw as Record<string, unknown>)
          ? (raw as Record<string, unknown>).timestamp_match_ms
          : undefined,
      raw,
      edges: payload.edges.length,
      nodes: payload.nodes.length,
    };
  }, [selectedNode, payload]);

  const handleNodeClick = useCallback((_: React.MouseEvent, n: Node) => {
    setSelectedNode(n as Node<ForensicNodeData>);
    setSidebarOpen(true);
  }, []);

  const closeSidebar = useCallback(() => setSidebarOpen(false), []);

  const threatEdgeCount = flow.edges.filter(
    e => (e.data as EdgeDataShape)?.isThreat,
  ).length;

  return (
    <motion.div
      variants={fadeIn}
      initial="hidden"
      animate="show"
      style={{
        minHeight:  "100vh",
        background: C.bg,
        padding:    "24px 28px 32px",
        fontFamily: "DM Sans, sans-serif",
        color:      C.text,
      }}
    >
      {/* Back */}
      <BackButton onBack={onBack} />

      {/* ── Page Header ── */}
      <div style={{
        display: "flex", alignItems: "flex-start",
        justifyContent: "space-between",
        flexWrap: "wrap", gap: 16, marginBottom: 20,
      }}>
        <div>
          <p style={{
            fontSize: 10, letterSpacing: "0.12em",
            textTransform: "uppercase", color: C.muted, marginBottom: 4,
          }}>
            Forensic Workbench
          </p>
          <h1 style={{
            fontSize: "clamp(20px, 2.4vw, 27px)",
            fontWeight: 700, letterSpacing: "-0.02em", color: C.text,
          }}>
            Nexus Graph · Relationship Analysis
          </h1>
          <p style={{ marginTop: 5, fontSize: 13, color: C.muted }}>
            Asset{" "}
            <span style={{ fontFamily: "DM Mono, monospace", color: C.text }}>
              {assetId}
            </span>
            {" "}·{" "}
            <span style={{ color: C.coral }}>
              {threatEdgeCount} threat-linked {threatEdgeCount === 1 ? "edge" : "edges"}
            </span>
            {" "}detected across forensic topology
          </p>
        </div>

        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {/* Nodes / Edges chip */}
          <div style={{
            display: "flex", alignItems: "center", gap: 8,
            padding: "7px 14px", borderRadius: 8,
            border: `1px solid ${C.border}`,
            background: C.card,
            fontSize: 12, color: C.muted,
            boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
          }}>
            <Network size={13} color={C.blue} />
            <span>
              {payload.nodes.length}{" "}
              <span style={{ color: C.muted }}>nodes</span>
            </span>
            <span style={{ color: C.border }}>·</span>
            <span>
              {payload.edges.length}{" "}
              <span style={{ color: C.muted }}>edges</span>
            </span>
          </div>

          {/* High Risk badge */}
          <div style={{
            display: "flex", alignItems: "center", gap: 7,
            padding: "7px 13px", borderRadius: 8,
            border: `1px solid ${C.coral}28`,
            background: `${C.coral}08`,
            fontSize: 11.5, fontWeight: 700, color: C.coral,
            letterSpacing: "0.06em",
          }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.coral }} />
            HIGH RISK
          </div>

          {/* Fit View */}
          <button
            type="button"
            onClick={() => rf?.fitView({ padding: 0.18, duration: 360 })}
            style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "7px 13px", borderRadius: 8,
              border: `1px solid ${C.border}`,
              background: C.card,
              color: C.muted, fontSize: 12, fontWeight: 500,
              cursor: "pointer", fontFamily: "inherit",
              boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
              transition: "background 0.12s",
            }}
            onMouseEnter={e => (e.currentTarget.style.background = C.bgMuted)}
            onMouseLeave={e => (e.currentTarget.style.background = C.card)}
          >
            <Radar size={12} color={C.blue} />
            Fit View
          </button>

          {/* Toggle sidebar */}
          {!sidebarOpen && (
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "7px 13px", borderRadius: 8,
                border: `1px solid ${C.border}`,
                background: C.card,
                color: C.muted, fontSize: 12, fontWeight: 500,
                cursor: "pointer", fontFamily: "inherit",
                transition: "background 0.12s",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = C.bgMuted)}
              onMouseLeave={e => (e.currentTarget.style.background = C.card)}
            >
              Inspector
            </button>
          )}
        </div>
      </div>

      {/* ── Main Content Grid ── */}
      <div style={{
        display: "grid",
        gridTemplateColumns: sidebarOpen ? "1fr 300px" : "1fr",
        gap: 12,
        transition: "grid-template-columns 0.25s ease",
      }}>
        {/* ── Canvas ── */}
        <section style={{
          position: "relative",
          overflow: "hidden",
          borderRadius: 12,
          border: `1px solid ${C.border}`,
          background: C.card,
          boxShadow: "0 1px 6px rgba(0,0,0,0.05)",
        }}>
          {/* Canvas header bar */}
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            borderBottom: `1px solid ${C.border}`,
            padding: "10px 16px",
            background: C.bg,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div style={{
                width: 30, height: 30, borderRadius: 7,
                border: `1px solid ${C.border}`,
                background: C.card,
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <Radar size={14} color={C.blue} />
              </div>
              <div>
                <p style={{
                  fontSize: 9.5, letterSpacing: "0.10em",
                  textTransform: "uppercase", color: C.muted,
                }}>
                  Nexus Canvas
                </p>
                <p style={{ fontSize: 12.5, fontWeight: 600, color: C.text, marginTop: 1 }}>
                  Relationship Graph
                </p>
              </div>
            </div>
            <span style={{
              fontSize: 10.5, color: C.muted,
              fontFamily: "DM Mono, monospace",
            }}>
              /api/v1/analysis/{assetId}
            </span>
          </div>

          {/* React Flow canvas */}
          <div style={{ height: "calc(100vh - 248px)", minHeight: 480 }}>
            <ReactFlow
              nodes={flow.nodes}
              edges={flow.edges}
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              fitView
              fitViewOptions={{ padding: 0.22 }}
              onInit={(instance) => {
                setRf(instance);
                instance.fitView({ padding: 0.22, duration: 400 });
              }}
              onNodeClick={handleNodeClick}
              proOptions={{ hideAttribution: true }}
              style={{ background: C.card }}
              minZoom={0.12}
              maxZoom={2.8}
            >
              {/* Subtle dot grid */}
              <Background
                variant={BackgroundVariant.Dots}
                gap={24}
                size={1}
                color={C.border}
              />

              {/* Controls — white bg, crisp border */}
              <Controls
                position="bottom-right"
                showInteractive={false}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: 2,
                  background: C.card,
                  border: `1px solid ${C.border}`,
                  borderRadius: 8,
                  padding: 4,
                  boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
                }}
              />

              {/* MiniMap — white bg, crisp border, semantic node colors */}
              <MiniMap
                position="bottom-left"
                nodeColor={(n) => {
                  const d = n.data as ForensicNodeData;
                  if (d.tone === "threat") return C.coral;
                  if (d.tone === "engine") return C.blue;
                  if (d.tone === "asset")  return C.violet;
                  return C.green;
                }}
                maskColor="rgba(245,242,236,0.72)"
                style={{
                  background: C.card,
                  border: `1px solid ${C.border}`,
                  borderRadius: 8,
                  boxShadow: "0 2px 8px rgba(0,0,0,0.06)",
                }}
              />
            </ReactFlow>
          </div>
        </section>

        {/* ── Node Inspector Sidebar ── */}
        <AnimatePresence mode="wait">
          {sidebarOpen && selectedNode && (
            <NodeDetailSidebar
              key={selectedNode.id}
              details={details}
              onClose={closeSidebar}
            />
          )}
        </AnimatePresence>
      </div>

      {/* ── Legend Footer ── */}
      <div style={{
        marginTop: 12,
        borderRadius: 8,
        border: `1px solid ${C.border}`,
        background: C.card,
        padding: "10px 18px",
        display: "flex", alignItems: "center",
        justifyContent: "space-between",
        flexWrap: "wrap", gap: 12,
        boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
      }}>
        <p style={{ fontSize: 11.5, color: C.muted }}>
          Click any node to open the inspector.
          Dashed edges denote confirmed threat linkage.
        </p>
        <div style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
          {[
            { label: "Threat Edge",       isLine: true,  color: C.coral,  dashed: true  },
            { label: "Data Flow Edge",    isLine: true,  color: "rgba(0,0,0,0.18)", dashed: false },
            { label: "Piracy Cluster",    isLine: false, color: C.coral  },
            { label: "Analysis Engine",   isLine: false, color: C.blue   },
            { label: "Asset",             isLine: false, color: C.violet },
          ].map(({ label, isLine, color, dashed }) => (
            <div key={label} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {isLine ? (
                <svg width="22" height="6" style={{ flexShrink: 0 }}>
                  <line
                    x1="0" y1="3" x2="22" y2="3"
                    stroke={color}
                    strokeWidth="1.5"
                    strokeDasharray={dashed ? "5 4" : undefined}
                    strokeLinecap="round"
                  />
                </svg>
              ) : (
                <div style={{
                  width: 7, height: 7, borderRadius: "50%",
                  background: color, flexShrink: 0,
                }} />
              )}
              <span style={{ fontSize: 10.5, color: C.muted }}>{label}</span>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   NexusScreen — Root Entry Point
   MOCK MODE:  state is hardwired to { status: "success", data: MOCK_PAYLOAD }
   LIVE MODE:  comment out the mock useState line and restore the useEffect block
───────────────────────────────────────────────────────────────────────────── */

export default function NexusScreen() {
  useFonts();

  const { assetId }  = useParams();
  const { userRole } = useAuth();
  const navigate     = useNavigate();

  const role      = (userRole || "").toUpperCase();
  const isAuditor = role === "AUDITOR";
  const isFeeder  = role === "PRODUCER";

  const onBack = useCallback(() => navigate(-1), [navigate]);

  // ── LIVE MODE ──
  const [state, setState] = useState<LoadState>({ status: "idle" });

  useEffect(() => {
    if (!assetId) return;
    const controller = new AbortController();
    const run = async () => {
      setState({ status: "loading" });
      try {
        const res = await fetch(`http://localhost:8000/api/v1/analysis/${assetId}`, {
          signal:  controller.signal,
          headers: { Accept: "application/json" },
        });
        if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
        const json = (await res.json()) as Partial<AnalysisPayload>;
        setState({
          status: "success",
          data: {
            nodes:       Array.isArray(json.nodes) ? json.nodes : [],
            edges:       Array.isArray(json.edges) ? json.edges : [],
            ingest_logs: Array.isArray(json.ingest_logs)
              ? (json.ingest_logs as unknown[]).map(safeString)
              : [],
          },
        });
      } catch (e) {
        if (controller.signal.aborted) return;
        setState({
          status: "error",
          message: e instanceof Error ? e.message : "Unknown error",
        });
      }
    };
    void run();
    return () => controller.abort();
  }, [assetId]);

  if (!assetId)
    return <ErrorPanel message="Missing assetId URL parameter." />;
  if (state.status === "idle" || state.status === "loading")
    return <LightSkeleton />;
  if (state.status === "error")
    return <ErrorPanel message={state.message} />;

  if (isFeeder)  return <Terminal  logs={state.data.ingest_logs} onBack={onBack} />;
  if (isAuditor) return <AuditorWorkbench assetId={assetId} payload={state.data} onBack={onBack} />;

  return (
    <ErrorPanel
      message={`Unsupported role "${userRole}". Expected "PRODUCER" or "AUDITOR".`}
    />
  );
}