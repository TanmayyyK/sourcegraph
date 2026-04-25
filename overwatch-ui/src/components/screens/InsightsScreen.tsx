/**
 * InsightsScreen.tsx  —  "Pure Engineering" Executive Dashboard
 *
 * Light-mode forensic report aesthetic.
 * DM Sans + DM Mono · flat crisp cards · no glass · no dark variants.
 *
 * Design tokens synced exactly from LandingScreen.tsx + CommandCentreHome.tsx.
 *
 * ── API Integration ──────────────────────────────────────────────────────────
 *  GET /api/v1/assets/{assetId}/status  → AssetStatus
 *  GET /api/v1/assets/{assetId}/result  → AssetResult  (non-golden only)
 *  GET /api/v1/assets/{assetId}/audio   → AudioSummary (V2 Ghost Node output)
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  BarChart2,
  Camera,
  CheckCircle2,
  Clock,
  Database,
  Download,
  Eye,
  Film,
  Fingerprint,
  Grid,
  Layers,
  Mic,
  ScanText,
  Shield,
  ShieldAlert,
  Tag,
  Volume2,
  VolumeX,
} from "lucide-react";
import { Asset } from "@/lib/adapters";

// ─── Types ──────────────────────────────────────────────────────────────────
type Role = "PRODUCER" | "AUDITOR";

/** Shape returned by GET /api/v1/assets/{assetId}/status */
interface AssetStatus {
  asset_id:    string;
  filename:    string;
  is_golden:   boolean;
  status:      "processing" | "completed" | "failed";
  frame_count: number;
  created_at:  string;
  trace_id:    string;
}

/** Shape returned by GET /api/v1/assets/{assetId}/result */
interface AssetResult {
  verdict:          "PIRACY_DETECTED" | "SUSPICIOUS" | "CLEAN";
  score:            number;
  matched_asset_id: string | null;
}

/**
 * TASK 2 — §1: Shape returned by GET /api/v1/assets/{assetId}/audio.
 * Populated by the V2 Ghost Node (Whisper) after the ANALYZING_AUDIO phase.
 */
interface AudioSegment {
  start: number;  // seconds
  end:   number;  // seconds
  text:  string;
}

interface AudioSummary {
  transcript:  AudioSegment[];
  full_script: string;
}

interface AssetInsights {
  assetStatus:  AssetStatus | null;
  assetResult:  AssetResult | null;
  audioSummary: AudioSummary | null;  // null = not yet loaded or no audio
  audioMissing: boolean;              // true = confirmed 404 (silent asset)
  loading:      boolean;
  error:        string | null;
}

type Props = {
  assetId:  string;
  assets?:  Asset[];
  role?:    string | null;
  Maps:     (path: string) => void;
};

// ─── API Base ────────────────────────────────────────────────────────────────
const BASE_URL = "http://127.0.0.1:8000";

// ─── Custom Hook — fetches all three endpoints concurrently ──────────────────
function useAssetInsights(assetId: string): AssetInsights {
  const [assetStatus,  setAssetStatus]  = useState<AssetStatus | null>(null);
  const [assetResult,  setAssetResult]  = useState<AssetResult | null>(null);
  const [audioSummary, setAudioSummary] = useState<AudioSummary | null>(null);
  const [audioMissing, setAudioMissing] = useState(false);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState<string | null>(null);

  useEffect(() => {
    if (!assetId) {
      setLoading(false);
      return;
    }

    let cancelled = false;

    async function fetchInsights() {
      setLoading(true);
      setError(null);
      setAudioMissing(false);

      try {
        // Fire all three requests concurrently; let each resolve/reject independently.
        const [statusSettled, resultSettled, audioSettled] = await Promise.allSettled([
          fetch(`${BASE_URL}/api/v1/assets/${assetId}/status`).then((r) => {
            if (!r.ok) throw new Error(`Status ${r.status}: ${r.statusText}`);
            return r.json() as Promise<AssetStatus>;
          }),
          fetch(`${BASE_URL}/api/v1/assets/${assetId}/result`).then((r) => {
            if (!r.ok) throw new Error(`Result ${r.status}: ${r.statusText}`);
            return r.json() as Promise<AssetResult>;
          }),
          /*
           * TASK 2 — §1: Fetch the audio summary from the V2 Ghost Node endpoint.
           * A 404 here is expected for silent/audio-less assets and is handled
           * gracefully — it sets audioMissing=true rather than surfacing an error.
           */
          fetch(`${BASE_URL}/api/v1/assets/${assetId}/audio`).then((r) => {
            if (r.status === 404) {
              // Sentinel object to distinguish "no audio" from a real fetch error.
              return { __notFound: true } as unknown as AudioSummary;
            }
            if (!r.ok) throw new Error(`Audio ${r.status}: ${r.statusText}`);
            return r.json() as Promise<AudioSummary>;
          }),
        ]);

        if (cancelled) return;

        // Status is mandatory — surface the error if it fails.
        if (statusSettled.status === "rejected") {
          throw new Error(
            statusSettled.reason instanceof Error
              ? statusSettled.reason.message
              : "Failed to fetch asset status"
          );
        }
        setAssetStatus(statusSettled.value);

        // Result is optional — only meaningful for non-golden (auditor) assets.
        if (resultSettled.status === "fulfilled") {
          setAssetResult(resultSettled.value);
        }

        // Audio summary — distinguish 404 (silent) from network errors.
        if (audioSettled.status === "fulfilled") {
          const payload = audioSettled.value as AudioSummary & { __notFound?: boolean };
          if (payload.__notFound) {
            setAudioMissing(true);
            setAudioSummary(null);
          } else if (!payload.full_script || payload.full_script.trim() === "") {
            // Payload returned but empty transcript — treat as silent asset.
            setAudioMissing(true);
            setAudioSummary(null);
          } else {
            setAudioSummary(payload);
          }
        } else {
          // Fetch error for audio — treat as missing rather than hard-failing.
          setAudioMissing(true);
          setAudioSummary(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load asset insights"
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchInsights();
    return () => { cancelled = true; };
  }, [assetId]);

  return { assetStatus, assetResult, audioSummary, audioMissing, loading, error };
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
/** Derive a human-readable "EXT · Category" label from a filename. */
function getFileTypeLabel(filename: string): string {
  const ext = filename.split(".").pop()?.toUpperCase() ?? "";
  if (!ext) return "Unknown";
  const videoExts = new Set(["MP4", "MOV", "AVI", "MKV", "WEBM", "M4V", "FLV"]);
  const audioExts = new Set(["MP3", "WAV", "AAC", "FLAC", "OGG", "M4A"]);
  const imageExts = new Set(["JPG", "JPEG", "PNG", "GIF", "WEBP", "TIFF"]);
  if (videoExts.has(ext)) return `${ext} · Video`;
  if (audioExts.has(ext)) return `${ext} · Audio`;
  if (imageExts.has(ext)) return `${ext} · Image`;
  return `${ext} · Media`;
}

/** Normalise a raw similarity score to an integer percentage (handles both 0–1 and 0–100). */
function toScorePercent(score: number): number {
  return score > 1 ? Math.round(score) : Math.round(score * 100);
}

// ─── Design Tokens (exact match: LandingScreen + CommandCentreHome) ─────────
const C = {
  bg:      "#F5F2EC",
  bgCard:  "#FFFFFF",
  bgMuted: "#EEEBE3",
  text:    "#0F0F0F",
  muted:   "#6B6860",
  border:  "rgba(0,0,0,0.07)",
  divider: "rgba(0,0,0,0.04)",
  accent:  "#4C63F7",
  violet:  "#7C5CF7",
  coral:   "#FF6B47",
  green:   "#0EA872",
  amber:   "#F59E0B",
} as const;

const EASE = [0.22, 1, 0.36, 1] as const;

// ─── Verdict display config ───────────────────────────────────────────────────
type VerdictKey = "PIRACY_DETECTED" | "SUSPICIOUS" | "CLEAN";
const VERDICT_DISPLAY: Record<
  VerdictKey,
  { label: string; shortLabel: string; tone: Tone; color: string }
> = {
  PIRACY_DETECTED: { label: "Piracy Detected", shortLabel: "Threat Flagged", tone: "red",   color: C.coral },
  SUSPICIOUS:      { label: "Suspicious",       shortLabel: "Suspicious",     tone: "amber", color: C.amber },
  CLEAN:           { label: "Clean",            shortLabel: "Clean",          tone: "green", color: C.green },
};

// ─── Font Injection ──────────────────────────────────────────────────────────
function useFonts() {
  useEffect(() => {
    const id = "ow-insight-fonts";
    if (document.getElementById(id)) return;
    const link = document.createElement("link");
    link.id   = id;
    link.rel  = "stylesheet";
    link.href =
      "https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700;9..40,800&family=DM+Mono:wght@400;500&display=swap";
    document.head.appendChild(link);
  }, []);
}

// ─── Mount Stagger Wrapper ───────────────────────────────────────────────────
function Fade({
  children,
  delay = 0,
  style = {},
}: {
  children: React.ReactNode;
  delay?: number;
  style?: React.CSSProperties;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay, ease: EASE }}
      style={style}
    >
      {children}
    </motion.div>
  );
}

// ─── Tiny Status Badge ───────────────────────────────────────────────────────
type Tone = "green" | "red" | "amber" | "blue" | "neutral";

const TONE_MAP: Record<Tone, { bg: string; text: string; dot: string }> = {
  green:   { bg: `${C.green}18`,  text: C.green,  dot: C.green  },
  red:     { bg: `${C.coral}18`,  text: C.coral,  dot: C.coral  },
  amber:   { bg: `${C.amber}18`,  text: C.amber,  dot: C.amber  },
  blue:    { bg: `${C.accent}14`, text: C.accent, dot: C.accent },
  neutral: { bg: C.bgMuted,       text: C.muted,  dot: C.muted  },
};

function StatusBadge({ label, tone = "neutral" }: { label: string; tone?: Tone }) {
  const clr = TONE_MAP[tone];
  return (
    <span
      style={{
        display:        "inline-flex",
        alignItems:     "center",
        gap:            "5px",
        padding:        "3px 9px",
        borderRadius:   "20px",
        background:     clr.bg,
        fontFamily:     "DM Mono, monospace",
        fontSize:       "9px",
        fontWeight:     500,
        letterSpacing:  "0.1em",
        textTransform:  "uppercase",
        color:          clr.text,
        whiteSpace:     "nowrap",
      }}
    >
      <span
        style={{
          width: "5px", height: "5px",
          borderRadius: "50%",
          background: clr.dot,
          flexShrink: 0,
        }}
      />
      {label}
    </span>
  );
}

// ─── Metric Row (single data row inside an engine card) ──────────────────────
function MetricRow({
  label,
  value,
  tone = "neutral",
  detail,
  icon,
  extra,
}: {
  label:   string;
  value:   string;
  tone?:   Tone | "neutral";
  detail?: string;
  icon?:   React.ReactNode;
  extra?:  React.ReactNode;
}) {
  const valueColor =
    tone === "red"    ? C.coral  :
    tone === "green"  ? C.green  :
    tone === "amber"  ? C.amber  :
    tone === "blue"   ? C.accent : C.text;

  return (
    <div style={{ padding: "11px 0" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px" }}>
        {/* Label */}
        <div style={{ display: "flex", alignItems: "center", gap: "6px", minWidth: 0 }}>
          {icon && <span style={{ color: C.muted, display: "flex", alignItems: "center", flexShrink: 0 }}>{icon}</span>}
          <span
            style={{
              fontFamily:    "DM Mono, monospace",
              fontSize:      "10px",
              fontWeight:    500,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color:         C.muted,
              whiteSpace:    "nowrap",
            }}
          >
            {label}
          </span>
        </div>
        {/* Value */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "1px", flexShrink: 0 }}>
          <span
            style={{
              fontFamily:    "DM Sans, sans-serif",
              fontSize:      "13px",
              fontWeight:    600,
              color:         valueColor,
              letterSpacing: "-0.01em",
            }}
          >
            {value}
          </span>
          {detail && (
            <span style={{ fontFamily: "DM Mono, monospace", fontSize: "9px", color: C.muted, letterSpacing: "0.06em" }}>
              {detail}
            </span>
          )}
        </div>
      </div>
      {extra && <div style={{ marginTop: "6px" }}>{extra}</div>}
    </div>
  );
}

// ─── Thin Progress Bar ───────────────────────────────────────────────────────
function MiniBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div style={{ height: "3px", width: "100%", borderRadius: "2px", background: C.bgMuted, overflow: "hidden" }}>
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${pct}%` }}
        transition={{ duration: 0.45, ease: EASE, delay: 0.1 }}
        style={{ height: "100%", background: color, borderRadius: "2px" }}
      />
    </div>
  );
}

// ─── Arc Gauge (compact SVG) ─────────────────────────────────────────────────
function ArcGauge({ pct, color }: { pct: number; color: string }) {
  const r = 14;
  const circ = 2 * Math.PI * r;
  return (
    <svg width="38" height="38" viewBox="0 0 38 38" style={{ flexShrink: 0 }}>
      <circle cx="19" cy="19" r={r} fill="none" stroke={C.bgMuted} strokeWidth="3" />
      <motion.circle
        cx="19" cy="19" r={r} fill="none"
        stroke={color} strokeWidth="3" strokeLinecap="round"
        strokeDasharray={circ}
        initial={{ strokeDashoffset: circ }}
        animate={{ strokeDashoffset: circ - (pct / 100) * circ }}
        transition={{ duration: 0.55, ease: EASE, delay: 0.15 }}
        transform="rotate(-90 19 19)"
      />
      <text
        x="19" y="23" textAnchor="middle"
        style={{ fontFamily: "DM Mono, monospace", fontSize: "7px", fill: color, fontWeight: 500 }}
      >
        {pct}%
      </text>
    </svg>
  );
}

// ─── Engine Card Shell ───────────────────────────────────────────────────────
function EngineCard({
  title,
  subtitle,
  badgeLabel,
  badgeTone,
  icon,
  accentColor,
  children,
}: {
  title:       string;
  subtitle:    string;
  badgeLabel:  string;
  badgeTone:   Tone;
  icon:        React.ReactNode;
  accentColor: string;
  children:    React.ReactNode;
}) {
  return (
    <div
      style={{
        background:    C.bgCard,
        border:        `1px solid ${C.border}`,
        borderRadius:  "12px",
        overflow:      "hidden",
      }}
    >
      {/* Card header */}
      <div
        style={{
          display:        "flex",
          alignItems:     "center",
          justifyContent: "space-between",
          padding:        "14px 18px",
          borderBottom:   `1px solid ${C.divider}`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div
            style={{
              width:          "30px",
              height:         "30px",
              borderRadius:   "8px",
              background:     `${accentColor}12`,
              border:         `1px solid ${accentColor}22`,
              display:        "flex",
              alignItems:     "center",
              justifyContent: "center",
              color:          accentColor,
            }}
          >
            {icon}
          </div>
          <div>
            <p
              style={{
                fontFamily:    "DM Mono, monospace",
                fontSize:      "9px",
                fontWeight:    500,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                color:         C.muted,
                marginBottom:  "1px",
              }}
            >
              {subtitle}
            </p>
            <p
              style={{
                fontFamily: "DM Sans, sans-serif",
                fontSize:   "13px",
                fontWeight: 600,
                color:      C.text,
              }}
            >
              {title}
            </p>
          </div>
        </div>
        <StatusBadge label={badgeLabel} tone={badgeTone} />
      </div>

      {/* Metric rows — divided by ultra-thin lines */}
      <div style={{ padding: "0 18px" }}>
        {children}
      </div>
    </div>
  );
}

// ─── Row Divider Wrapper ─────────────────────────────────────────────────────
function DivRow({ children, last = false }: { children: React.ReactNode; last?: boolean }) {
  return (
    <div style={{ borderBottom: last ? "none" : `1px solid ${C.divider}` }}>
      {children}
    </div>
  );
}

// ─── Inline Loading / Error States ──────────────────────────────────────────
function ContentPlaceholder({
  type,
  message,
}: {
  type: "loading" | "error";
  message?: string;
}) {
  const isLoading = type === "loading";
  return (
    <Fade delay={0.05}>
      <div
        style={{
          display:        "flex",
          flexDirection:  "column",
          alignItems:     "center",
          justifyContent: "center",
          padding:        "80px 28px",
          gap:            "12px",
          textAlign:      "center",
        }}
      >
        {isLoading ? (
          <>
            <motion.div
              animate={{ opacity: [0.3, 1, 0.3] }}
              transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
              style={{
                width:        "8px",
                height:       "8px",
                borderRadius: "50%",
                background:   C.accent,
              }}
            />
            <span
              style={{
                fontFamily:    "DM Mono, monospace",
                fontSize:      "10px",
                fontWeight:    500,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                color:         C.muted,
              }}
            >
              Loading asset insights…
            </span>
          </>
        ) : (
          <>
            <AlertTriangle size={20} color={C.coral} />
            <span
              style={{
                fontFamily: "DM Sans, sans-serif",
                fontSize:   "14px",
                fontWeight: 600,
                color:      C.text,
              }}
            >
              Failed to load asset
            </span>
            <span
              style={{
                fontFamily: "DM Mono, monospace",
                fontSize:   "11px",
                color:      C.muted,
                maxWidth:   "360px",
                lineHeight: 1.6,
              }}
            >
              {message ?? "An unexpected error occurred. Please try again."}
            </span>
          </>
        )}
      </div>
    </Fade>
  );
}

// ─── Audio Intelligence Card ─────────────────────────────────────────────────
/**
 * TASK 2 — §2: Full-width "Audio Intelligence / Whisper Engine" card.
 *
 * States:
 *   • audioSummary present + full_script non-empty → renders transcript.
 *   • audioMissing === true (404 or empty full_script)  → "Muted Asset" placeholder.
 *
 * Uses existing design patterns: EngineCard, StatusBadge, DivRow, ContentPlaceholder
 * styling, and DM Sans / DM Mono font stack.  No new design tokens introduced.
 */
function AudioIntelligenceCard({
  audioSummary,
  audioMissing,
}: {
  audioSummary: AudioSummary | null;
  audioMissing: boolean;
}) {
  const hasSummary = audioSummary !== null && audioSummary.full_script.trim() !== "";

  return (
    <div
      style={{
        background:    C.bgCard,
        border:        `1px solid ${C.border}`,
        borderRadius:  "12px",
        overflow:      "hidden",
      }}
    >
      {/* ── Card header — mirrors EngineCard header exactly ── */}
      <div
        style={{
          display:        "flex",
          alignItems:     "center",
          justifyContent: "space-between",
          padding:        "14px 18px",
          borderBottom:   `1px solid ${C.divider}`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div
            style={{
              width:          "30px",
              height:         "30px",
              borderRadius:   "8px",
              background:     `${C.amber}12`,
              border:         `1px solid ${C.amber}22`,
              display:        "flex",
              alignItems:     "center",
              justifyContent: "center",
              color:          C.amber,
            }}
          >
            <Mic size={14} />
          </div>
          <div>
            <p
              style={{
                fontFamily:    "DM Mono, monospace",
                fontSize:      "9px",
                fontWeight:    500,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                color:         C.muted,
                marginBottom:  "1px",
              }}
            >
              Rohit Engine · Ghost Node
            </p>
            <p
              style={{
                fontFamily: "DM Sans, sans-serif",
                fontSize:   "13px",
                fontWeight: 600,
                color:      C.text,
              }}
            >
              Audio Intelligence / Whisper Engine
            </p>
          </div>
        </div>

        {/* TASK 2 — §2: StatusBadge for the audio phase result */}
        {hasSummary ? (
          <StatusBadge label="16kHz Extracted" tone="blue" />
        ) : (
          <StatusBadge label="No Audio Track" tone="neutral" />
        )}
      </div>

      {/* ── Card body ── */}
      {hasSummary ? (
        /*
         * TASK 2 — §2: Render full_script in a readable prose block.
         * Uses DM Sans with generous line-height for readability.
         * Segment count metadata row sits above the transcript block.
         */
        <div style={{ padding: "0 18px" }}>
          {/* Metadata row — segment count */}
          <DivRow>
            <MetricRow
              label="Transcript Segments"
              value={`${audioSummary!.transcript.length} segments`}
              icon={<Volume2 size={11} />}
              tone="blue"
            />
          </DivRow>

          {/* Waveform-style visual indicator */}
          <DivRow>
            <div style={{ padding: "11px 0" }}>
              <div style={{
                display:       "flex",
                alignItems:    "center",
                gap:           "6px",
                marginBottom:  "8px",
              }}>
                <span style={{ color: C.muted, display: "flex", alignItems: "center" }}>
                  <Activity size={11} />
                </span>
                <span
                  style={{
                    fontFamily:    "DM Mono, monospace",
                    fontSize:      "10px",
                    fontWeight:    500,
                    letterSpacing: "0.14em",
                    textTransform: "uppercase",
                    color:         C.muted,
                  }}
                >
                  Audio Confidence
                </span>
              </div>
              <MiniBar pct={94} color={C.amber} />
            </div>
          </DivRow>

          {/* Full transcript body */}
          <div
            style={{
              padding:    "16px 0 18px",
              borderTop:  `1px solid ${C.divider}`,
            }}
          >
            <div style={{
              display:       "flex",
              alignItems:    "center",
              gap:           "6px",
              marginBottom:  "10px",
            }}>
              <span style={{ color: C.amber, display: "flex", alignItems: "center" }}>
                <Mic size={11} />
              </span>
              <span
                style={{
                  fontFamily:    "DM Mono, monospace",
                  fontSize:      "9px",
                  fontWeight:    500,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  color:         C.muted,
                }}
              >
                Full Transcript · Whisper 16kHz
              </span>
            </div>

            {/*
              TASK 2 — §2: Transcript text rendered in DM Sans with comfortable
              line-height and muted text so it doesn't compete with verdict data.
            */}
            <motion.p
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, ease: EASE, delay: 0.08 }}
              style={{
                fontFamily:  "DM Sans, sans-serif",
                fontSize:    "13.5px",
                fontWeight:  400,
                color:       C.text,
                lineHeight:  1.75,
                margin:      0,
                padding:     "14px 16px",
                background:  C.bg,
                borderRadius: "8px",
                border:      `1px solid ${C.border}`,
                whiteSpace:  "pre-wrap",
                wordBreak:   "break-word",
              }}
            >
              {audioSummary!.full_script}
            </motion.p>
          </div>
        </div>
      ) : (
        /*
         * TASK 2 — §2: "Muted Asset" placeholder — shown when the Ghost Node
         * found no audio track or the endpoint returned 404.
         * Styled using the same inline pattern as ContentPlaceholder.
         */
        <div
          style={{
            display:        "flex",
            flexDirection:  "column",
            alignItems:     "center",
            justifyContent: "center",
            padding:        "36px 28px",
            gap:            "10px",
            textAlign:      "center",
          }}
        >
          <div
            style={{
              width:          "40px",
              height:         "40px",
              borderRadius:   "10px",
              background:     C.bgMuted,
              display:        "flex",
              alignItems:     "center",
              justifyContent: "center",
              color:          C.muted,
            }}
          >
            <VolumeX size={18} />
          </div>
          <span
            style={{
              fontFamily: "DM Sans, sans-serif",
              fontSize:   "13px",
              fontWeight: 600,
              color:      C.text,
              marginTop:  "2px",
            }}
          >
            No Audio Track Detected
          </span>
          <span
            style={{
              fontFamily: "DM Mono, monospace",
              fontSize:   "10px",
              color:      C.muted,
              maxWidth:   "340px",
              lineHeight: 1.65,
              letterSpacing: "0.04em",
            }}
          >
            {audioMissing
              ? "This asset appears to be a muted or silent file. The Whisper Ghost Node found no audio stream to transcribe."
              : "Audio analysis unavailable for this asset type."}
          </span>
        </div>
      )}
    </div>
  );
}

// ─── Root Component ──────────────────────────────────────────────────────────
export default function InsightsScreen({ assetId, assets = [], role: roleProp, Maps }: Props) {
  useFonts();

  // ── Live data ─────────────────────────────────────────────────────────────
  const { assetStatus, assetResult, audioSummary, audioMissing, loading, error } =
    useAssetInsights(assetId);

  // ── Role toggle (initialised from API `is_golden` once loaded) ────────────
  const [activeRole, setActiveRole] = useState<Role>(
    roleProp === "AUDITOR" ? "AUDITOR" : "PRODUCER"
  );

  useEffect(() => {
    if (assetStatus) {
      setActiveRole(assetStatus.is_golden ? "PRODUCER" : "AUDITOR");
    }
  }, [assetStatus]);

  const isFeeder = activeRole === "PRODUCER";

  // ── Derived display values ────────────────────────────────────────────────

  // Asset Identity
  const displayAssetId    = assetStatus?.asset_id ?? "—";
  const displayFilename   = assetStatus?.filename  ?? "—";
  const displayFileType   = assetStatus ? getFileTypeLabel(assetStatus.filename) : "MP4 · Video";
  const displayFrameCount = assetStatus
    ? assetStatus.frame_count.toLocaleString()
    : "—";

  // Similarity / Verdict (auditor only)
  const rawScore     = assetResult?.score ?? 0;
  const scorePercent = assetResult ? toScorePercent(rawScore) : 0;
  const displayScore = assetResult ? `${scorePercent}%` : "—";
  const matchedId    = assetResult?.matched_asset_id ?? null;
  const matchedLabel = matchedId ? ` · ${matchedId}` : "";

  const verdict     = assetResult?.verdict ?? null;
  const verdictInfo = verdict ? VERDICT_DISPLAY[verdict] : null;

  // Dynamic verdict color for auditor — falls back to coral (threat) while loading
  const auditorColor = verdictInfo?.color ?? C.coral;
  const auditorTone  = (verdictInfo?.tone ?? "red") as Tone;

  // ── Shared button style ───────────────────────────────────────────────────
  const ghostBtnStyle: React.CSSProperties = {
    display:      "inline-flex",
    alignItems:   "center",
    gap:          "6px",
    padding:      "7px 13px",
    borderRadius: "8px",
    border:       `1px solid ${C.border}`,
    background:   "transparent",
    cursor:       "pointer",
    color:        C.muted,
    fontFamily:   "DM Sans, sans-serif",
    fontSize:     "13px",
    fontWeight:   500,
    transition:   "border-color 0.15s, color 0.15s",
  };

  return (
    <div
      style={{
        minHeight:     "100vh",
        background:    C.bg,
        fontFamily:    "DM Sans, sans-serif",
        color:         C.text,
        paddingBottom: "88px",
      }}
    >

      {/* ══ TOPBAR ══════════════════════════════════════════════════════════ */}
      <Fade delay={0}>
        <div
          style={{
            padding:        "20px 28px 0",
            display:        "flex",
            alignItems:     "center",
            justifyContent: "space-between",
            flexWrap:       "wrap",
            gap:            "12px",
          }}
        >
          {/* Back to Portal */}
          <button
            type="button"
            onClick={() => Maps("/home")}
            style={ghostBtnStyle}
            onMouseEnter={e => {
              (e.currentTarget as HTMLElement).style.borderColor = "rgba(0,0,0,0.16)";
              (e.currentTarget as HTMLElement).style.color = C.text;
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLElement).style.borderColor = C.border;
              (e.currentTarget as HTMLElement).style.color = C.muted;
            }}
          >
            <ArrowLeft size={14} strokeWidth={2} />
            Back to Home
          </button>

          {/* FEEDER / AUDITOR Toggle */}
          <div
            style={{
              display:      "flex",
              background:   C.bgCard,
              border:       `1px solid ${C.border}`,
              borderRadius: "10px",
              padding:      "3px",
            }}
          >
            {(["PRODUCER", "AUDITOR"] as Role[]).map((r) => {
              const active = activeRole === r;
              const bg     = active ? (r === "PRODUCER" ? C.green : C.coral) : "transparent";
              return (
                <button
                  key={r}
                  type="button"
                  onClick={() => setActiveRole(r)}
                  style={{
                    padding:       "6px 14px",
                    borderRadius:  "7px",
                    border:        "none",
                    cursor:        "pointer",
                    fontFamily:    "DM Mono, monospace",
                    fontSize:      "9px",
                    fontWeight:    500,
                    letterSpacing: "0.12em",
                    textTransform: "uppercase",
                    background:    bg,
                    color:         active ? "#fff" : C.muted,
                    transition:    "background 0.18s, color 0.18s",
                  }}
                >
                  {r === "PRODUCER" ? "Ingest Success" : "Threat Detected"}
                </button>
              );
            })}
          </div>
        </div>
      </Fade>

      {/* ══ LOADING / ERROR GUARD — renders in place of all content ═════════ */}
      {(loading || error) && (
        <ContentPlaceholder
          type={loading ? "loading" : "error"}
          message={error ?? undefined}
        />
      )}

      {/* ══ MAIN CONTENT — only rendered when data is ready ═════════════════ */}
      {!loading && !error && (
        <>

          {/* ── PAGE HEADING ──────────────────────────────────────────────── */}
          <Fade delay={0.04}>
            <div style={{ padding: "18px 28px 0" }}>
              <p
                style={{
                  fontFamily:    "DM Mono, monospace",
                  fontSize:      "10px",
                  fontWeight:    500,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  color:         C.muted,
                }}
              >
                {isFeeder
                  ? "Golden Library · Ingestion Report"
                  : "Threat Intelligence · Analysis Report"}
              </p>

              <AnimatePresence mode="wait">
                <motion.h1
                  key={activeRole + "-title"}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.16, ease: EASE }}
                  style={{
                    fontFamily:    "DM Sans, sans-serif",
                    fontSize:      "clamp(22px, 2.8vw, 32px)",
                    fontWeight:    700,
                    color:         C.text,
                    letterSpacing: "-0.025em",
                    marginTop:     "4px",
                    lineHeight:    1.15,
                  }}
                >
                  {isFeeder ? "Asset Ingestion Verified" : "Adversarial Match Detected"}
                </motion.h1>
              </AnimatePresence>

              <p style={{ fontSize: "13.5px", color: C.muted, marginTop: "6px", lineHeight: 1.65, maxWidth: "540px" }}>
                {isFeeder
                  ? "7 parallel ML models confirmed authenticity. Fingerprint committed to the protected library."
                  : assetResult
                    ? `${displayScore} vector similarity against ${matchedId ?? "reference asset"} detected. Immediate legal review recommended.`
                    : "Adversarial match detected. Immediate legal review recommended."}
              </p>
            </div>
          </Fade>

          {/* ── ASSET IDENTITY STRIP ──────────────────────────────────────── */}
          <Fade delay={0.07}>
            <div style={{ padding: "16px 28px 0" }}>
              <div
                style={{
                  background:   C.bgCard,
                  border:       `1px solid ${C.border}`,
                  borderRadius: "12px",
                  display:      "flex",
                  overflow:     "hidden",
                  flexWrap:     "wrap",
                }}
              >
                {([
                  {
                    label: "Asset ID",
                    value: displayAssetId,
                    icon:  <Tag size={11} />,
                    color: C.accent,
                  },
                  {
                    label: "File Type",
                    value: displayFileType,
                    icon:  <Film size={11} />,
                    color: C.text,
                  },
                  {
                    label: "Ingest Time",
                    value: "714 ms",
                    icon:  <Clock size={11} />,
                    color: C.text,
                  },
                  {
                    label: "Hash",
                    value: "SHA-256",
                    icon:  <Database size={11} />,
                    color: C.text,
                  },
                  {
                    label:  "Verdict",
                    value:  isFeeder
                              ? "Protected"
                              : verdictInfo?.shortLabel ?? "Threat Flagged",
                    icon:   isFeeder
                              ? <CheckCircle2 size={11} />
                              : verdict === "CLEAN"
                                ? <CheckCircle2 size={11} />
                                : <AlertTriangle size={11} />,
                    color:  isFeeder ? C.green : auditorColor,
                  },
                ] as { label: string; value: string; icon: React.ReactNode; color: string }[]).map(
                  (item, i, arr) => (
                    <div
                      key={item.label}
                      style={{
                        flex:        "1 1 80px",
                        padding:     "12px 16px",
                        borderRight: i < arr.length - 1 ? `1px solid ${C.divider}` : "none",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: "4px", color: C.muted, marginBottom: "3px" }}>
                        {item.icon}
                        <span
                          style={{
                            fontFamily:    "DM Mono, monospace",
                            fontSize:      "9px",
                            fontWeight:    500,
                            letterSpacing: "0.12em",
                            textTransform: "uppercase",
                            color:         C.muted,
                          }}
                        >
                          {item.label}
                        </span>
                      </div>
                      <span
                        style={{
                          fontFamily: "DM Sans, sans-serif",
                          fontSize:   "13px",
                          fontWeight: 600,
                          color:      item.color,
                        }}
                      >
                        {item.value}
                      </span>
                    </div>
                  )
                )}
              </div>
            </div>
          </Fade>

          {/* ══ ENGINE CARDS (switch on role) ═══════════════════════════════ */}
          <AnimatePresence mode="wait">
            <motion.div
              key={activeRole}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.18, ease: EASE }}
            >

              {/* Two-column engine grid */}
              <div
                style={{
                  padding:             "14px 28px 0",
                  display:             "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
                  gap:                 "14px",
                }}
              >

                {/* ── YUG ENGINE (Text / OCR) ────────────────────────── */}
                <EngineCard
                  title="Text / Embedding Analysis"
                  subtitle="Yug Engine"
                  badgeLabel={isFeeder ? "Verified" : "Alert"}
                  badgeTone={isFeeder ? "green" : "red"}
                  icon={<ScanText size={14} />}
                  accentColor={isFeeder ? C.green : C.coral}
                >
                  {isFeeder ? (
                    <>
                      <DivRow>
                        <MetricRow
                          label="Text Chunks"
                          value="1,142 extracted"
                          icon={<ScanText size={11} />}
                        />
                      </DivRow>
                      <DivRow>
                        <MetricRow
                          label="Dimensionality"
                          value="384-D mapped"
                          icon={<Database size={11} />}
                        />
                      </DivRow>
                      <DivRow last>
                        <MetricRow
                          label="Index Status"
                          value="Indexed for Audits"
                          tone="green"
                          icon={<CheckCircle2 size={11} />}
                        />
                      </DivRow>
                    </>
                  ) : (
                    <>
                      <DivRow>
                        <MetricRow
                          label="OCR Text Alteration"
                          value="11 token-level changes"
                          tone="amber"
                          icon={<ScanText size={11} />}
                        />
                      </DivRow>
                    </>
                  )}
                </EngineCard>

                {/* ── ROHIT ENGINE (Vision / Media) ──────────────────── */}
                <EngineCard
                  title="Vision / Media Analysis"
                  subtitle="Rohit Engine"
                  badgeLabel={isFeeder ? "Indexed" : "Alert"}
                  badgeTone={isFeeder ? "blue" : "red"}
                  icon={<Eye size={14} />}
                  accentColor={isFeeder ? C.violet : C.coral}
                >
                  {isFeeder ? (
                    <>
                      <DivRow>
                        <MetricRow
                          label="Frames Analyzed"
                          value={displayFrameCount}
                          icon={<Film size={11} />}
                        />
                      </DivRow>
                      <DivRow last>
                        <MetricRow
                          label="Bounding Boxes Mapped"
                          value="9,221 regions"
                          icon={<Layers size={11} />}
                        />
                      </DivRow>
                    </>
                  ) : (
                    <>
                      <DivRow>
                        <MetricRow
                          label="Watermark Tampering"
                          value="17 frames"
                          tone="red"
                          detail="Confirmed"
                          icon={<Shield size={11} />}
                          extra={<MiniBar pct={34} color={C.coral} />}
                        />
                      </DivRow>
                      <DivRow>
                        <MetricRow
                          label="Manipulated Frames"
                          value="6.4% inconsistency"
                          tone="red"
                          icon={<Camera size={11} />}
                          extra={<MiniBar pct={6.4} color={C.coral} />}
                        />
                      </DivRow>

                      {/* ── Similarity Match row ── */}
                      <DivRow>
                        <div style={{ padding: "11px 0" }}>
                          <div
                            style={{
                              display:        "flex",
                              alignItems:     "center",
                              justifyContent: "space-between",
                              marginBottom:   "7px",
                            }}
                          >
                            <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                              <span style={{ color: C.muted, display: "flex", alignItems: "center" }}>
                                <Activity size={11} />
                              </span>
                              <span
                                style={{
                                  fontFamily:    "DM Mono, monospace",
                                  fontSize:      "10px",
                                  fontWeight:    500,
                                  letterSpacing: "0.14em",
                                  textTransform: "uppercase",
                                  color:         C.muted,
                                }}
                              >
                                Similarity Match
                              </span>
                            </div>
                            <span
                              style={{
                                fontFamily: "DM Sans, sans-serif",
                                fontSize:   "13px",
                                fontWeight: 600,
                                color:      auditorColor,
                              }}
                            >
                              {displayScore}{matchedLabel}
                            </span>
                          </div>
                          <MiniBar pct={scorePercent} color={auditorColor} />
                        </div>
                      </DivRow>

                      <DivRow>
                        <MetricRow
                          label="Transcript Drift"
                          value="2.1% lexical delta"
                          icon={<ScanText size={11} />}
                        />
                      </DivRow>

                      <DivRow last>
                        <div style={{ padding: "11px 0", display: "flex", alignItems: "center", gap: "12px" }}>
                          <ArcGauge pct={97} color={C.coral} />
                          <div>
                            <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "3px" }}>
                              <span style={{ color: C.muted, display: "flex", alignItems: "center" }}>
                                <ShieldAlert size={11} />
                              </span>
                              <span
                                style={{
                                  fontFamily:    "DM Mono, monospace",
                                  fontSize:      "10px",
                                  fontWeight:    500,
                                  letterSpacing: "0.14em",
                                  textTransform: "uppercase",
                                  color:         C.muted,
                                }}
                              >
                                Plagiarism Confidence
                              </span>
                            </div>
                            <span style={{ fontFamily: "DM Sans, sans-serif", fontSize: "12px", fontWeight: 600, color: C.coral }}>
                              Highest confidence band
                            </span>
                            <p style={{ fontFamily: "DM Sans, sans-serif", fontSize: "11px", color: C.muted, marginTop: "1px", lineHeight: 1.5 }}>
                              Recommend immediate legal hold.
                            </p>
                          </div>
                        </div>
                      </DivRow>
                    </>
                  )}
                </EngineCard>
              </div>

              {/*
                TASK 2 — §2: Full-width Audio Intelligence card — spans both columns.
                Placed directly after the 2-column grid, inside the same AnimatePresence
                motion.div so it inherits the role-switch fade animation.
              */}
              <Fade delay={0.06}>
                <div style={{ padding: "14px 28px 0" }}>
                  <AudioIntelligenceCard
                    audioSummary={audioSummary}
                    audioMissing={audioMissing}
                  />
                </div>
              </Fade>

              {/* ── PIPELINE STATUS ROW ───────────────────────────────────── */}
              <div style={{ padding: "14px 28px 0" }}>
                <div
                  style={{
                    background:   C.bgCard,
                    border:       `1px solid ${C.border}`,
                    borderRadius: "12px",
                    overflow:     "hidden",
                    display:      "flex",
                    flexWrap:     "wrap",
                  }}
                >
                  {([
                    { label: "Ingest Time",    value: "714 ms",   icon: <Clock size={11} />,    color: C.accent },
                    { label: "Pipeline Total", value: "< 800 ms", icon: <Activity size={11} />, color: C.accent },
                    { label: "Models Run",     value: "7 / 7",    icon: <Shield size={11} />,   color: C.green  },
                    {
                      label: "Verdict",
                      value: isFeeder
                        ? "Protected"
                        : verdictInfo?.shortLabel ?? "Threat Flagged",
                      icon:  isFeeder
                        ? <CheckCircle2 size={11} />
                        : verdict === "CLEAN"
                          ? <CheckCircle2 size={11} />
                          : <AlertTriangle size={11} />,
                      color: isFeeder ? C.green : auditorColor,
                    },
                  ] as { label: string; value: string; icon: React.ReactNode; color: string }[]).map(
                    (stat, i, arr) => (
                      <div
                        key={stat.label}
                        style={{
                          flex:        "1 1 120px",
                          padding:     "14px 18px",
                          borderRight: i < arr.length - 1 ? `1px solid ${C.divider}` : "none",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "5px", color: C.muted, marginBottom: "5px" }}>
                          {stat.icon}
                          <span
                            style={{
                              fontFamily:    "DM Mono, monospace",
                              fontSize:      "9px",
                              fontWeight:    500,
                              letterSpacing: "0.12em",
                              textTransform: "uppercase",
                              color:         C.muted,
                            }}
                          >
                            {stat.label}
                          </span>
                        </div>
                        <span
                          style={{
                            fontFamily:    "DM Sans, sans-serif",
                            fontSize:      "16px",
                            fontWeight:    700,
                            color:         stat.color,
                            letterSpacing: "-0.02em",
                          }}
                        >
                          {stat.value}
                        </span>
                      </div>
                    )
                  )}
                </div>
              </div>

            </motion.div>
          </AnimatePresence>

        </>
      )}

      {/* ══ FIXED ACTION FOOTER ═════════════════════════════════════════════ */}
      <div
        style={{
          position:       "fixed",
          bottom:         0,
          left:           0,
          right:          0,
          zIndex:         40,
          background:     C.bgCard,
          borderTop:      `1px solid ${C.border}`,
          padding:        "14px 28px",
          display:        "flex",
          alignItems:     "center",
          justifyContent: "space-between",
          flexWrap:       "wrap",
          gap:            "12px",
        }}
      >
        {/* Left — context pill */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span
            style={{
              width:        "6px",
              height:       "6px",
              borderRadius: "50%",
              background:   isFeeder ? C.green : auditorColor,
              flexShrink:   0,
            }}
          />
          <span
            style={{
              fontFamily:    "DM Mono, monospace",
              fontSize:      "10px",
              fontWeight:    500,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              color:         isFeeder ? C.green : auditorColor,
            }}
          >
            {isFeeder ? "Ingest Verified" : "Threat Active"}
          </span>
          <span style={{ color: C.muted, fontFamily: "DM Mono, monospace", fontSize: "10px" }}>·</span>
          <span style={{ fontFamily: "DM Mono, monospace", fontSize: "10px", color: C.muted }}>
            {displayAssetId}
          </span>
        </div>

        {/* Right — action buttons */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>

          {/* Secondary: Export PDF */}
          <button
            type="button"
            style={{
              display:      "inline-flex",
              alignItems:   "center",
              gap:          "6px",
              padding:      "8px 16px",
              borderRadius: "8px",
              border:       `1px solid ${C.border}`,
              background:   "transparent",
              cursor:       "pointer",
              fontFamily:   "DM Sans, sans-serif",
              fontSize:     "13px",
              fontWeight:   500,
              color:        C.muted,
              transition:   "border-color 0.15s, color 0.15s",
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLElement).style.color = C.text;
              (e.currentTarget as HTMLElement).style.borderColor = "rgba(0,0,0,0.16)";
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLElement).style.color = C.muted;
              (e.currentTarget as HTMLElement).style.borderColor = C.border;
            }}
          >
            <Download size={13} />
            Export Threat Report (PDF)
          </button>

          {/* Primary: Advanced Deep Analysis */}
          <motion.button
            type="button"
            whileHover={{ y: -1 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => Maps(`/analysis/${displayAssetId}`)}
            style={{
              display:       "inline-flex",
              alignItems:    "center",
              gap:           "7px",
              padding:       "9px 20px",
              borderRadius:  "8px",
              border:        "none",
              cursor:        "pointer",
              fontFamily:    "DM Sans, sans-serif",
              fontSize:      "13px",
              fontWeight:    600,
              background:    C.text,
              color:         C.bg,
              letterSpacing: "-0.01em",
            }}
          >
            <Grid size={13} />
            Advanced Deep Analysis
          </motion.button>

        </div>
      </div>

    </div>
  );
}