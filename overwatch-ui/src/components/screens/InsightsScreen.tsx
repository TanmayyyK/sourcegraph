import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { useParams } from "react-router-dom";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  Database,
  Download,
  Eye,
  Film,
  GitBranch,
  Grid,
  Mic,
  ScanText,
  ShieldAlert,
  Tag,
} from "lucide-react";
import { assetApi } from "@/lib/api";
import { useAuth } from "@/components/providers/AuthProvider";
import type {
  AssetStatusResponse,
  AuditorForensics,
  ProducerAnalytics,
  SimilarityResultResponse,
  SimilarityVerdict,
  UserRole,
} from "@/types";
import type { Asset } from "@/lib/adapters";

type Props = {
  assetId?: string;
  assets?: Asset[];
  role?: string | null;
  Maps?: (path: string) => void;
};

type Tone = "green" | "red" | "amber" | "blue" | "neutral";

const C = {
  bg: "#F5F2EC",
  bgCard: "#FFFFFF",
  bgMuted: "#EEEBE3",
  text: "#0F0F0F",
  muted: "#6B6860",
  border: "rgba(0,0,0,0.07)",
  divider: "rgba(0,0,0,0.04)",
  accent: "#4C63F7",
  violet: "#7C5CF7",
  coral: "#FF6B47",
  green: "#0EA872",
  amber: "#F59E0B",
} as const;

const EASE = [0.22, 1, 0.36, 1] as const;

const TONE_MAP: Record<Tone, { bg: string; text: string; dot: string }> = {
  green: { bg: `${C.green}18`, text: C.green, dot: C.green },
  red: { bg: `${C.coral}18`, text: C.coral, dot: C.coral },
  amber: { bg: `${C.amber}18`, text: C.amber, dot: C.amber },
  blue: { bg: `${C.accent}14`, text: C.accent, dot: C.accent },
  neutral: { bg: C.bgMuted, text: C.muted, dot: C.muted },
};

const VERDICT_DISPLAY: Record<SimilarityVerdict, { label: string; shortLabel: string; tone: Tone; color: string }> = {
  PIRACY_DETECTED: { label: "Piracy Detected", shortLabel: "Threat Flagged", tone: "red", color: C.coral },
  SUSPICIOUS: { label: "Suspicious", shortLabel: "Suspicious", tone: "amber", color: C.amber },
  CLEAN: { label: "Clean", shortLabel: "Clean", tone: "green", color: C.green },
  SAFE: { label: "Safe", shortLabel: "Safe", tone: "green", color: C.green },
};

function useFonts() {
  useEffect(() => {
    const id = "ow-insight-fonts";
    if (document.getElementById(id)) return;
    const link = document.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.href =
      "https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700;9..40,800&family=DM+Mono:wght@400;500&display=swap";
    document.head.appendChild(link);
  }, []);
}

function toScorePercent(score: number): number {
  return score > 1 ? Math.round(score) : Math.round(score * 100);
}

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

function normalizeVerdict(verdict: SimilarityVerdict | string | null | undefined): SimilarityVerdict {
  if (verdict === "SAFE") return "SAFE";
  if (verdict === "PIRACY_DETECTED" || verdict === "SUSPICIOUS" || verdict === "CLEAN") return verdict;
  return "CLEAN";
}

function buildProducerAnalytics(status: AssetStatusResponse | null): ProducerAnalytics {
  return {
    assetId: status?.asset_id ?? "unavailable",
    filename: status?.filename ?? "No asset selected",
    totalFrames: status?.frame_count ?? 0,
    visionNodeLatencyMs: 0,
    contextNodeLatencyMs: 0,
    successfulExtractions: status?.frame_count ?? 0,
    databaseVectorsSynced: status?.frame_count ?? 0,
  };
}

function buildAuditorForensics(
  status: AssetStatusResponse | null,
  result: SimilarityResultResponse | null,
): AuditorForensics {
  const payload = result as (SimilarityResultResponse & { audio_score?: number }) | null;
  return {
    assetId: status?.asset_id ?? result?.suspect_asset_id ?? "unavailable",
    filename: status?.filename ?? "No asset selected",
    fusedScore: result?.fused_score ?? 0,
    visualScore: result?.visual_score ?? 0,
    audioScore: payload?.audio_score ?? result?.text_score ?? 0,
    verdict: normalizeVerdict(result?.verdict),
    matchedAssetId: result?.golden_asset_id ?? null,
    matchedTimestamp: result?.matched_timestamp ?? null,
  };
}

function Fade({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, delay, ease: EASE }}
    >
      {children}
    </motion.div>
  );
}

function StatusBadge({ label, tone = "neutral" }: { label: string; tone?: Tone }) {
  const clr = TONE_MAP[tone];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "5px",
        padding: "3px 9px",
        borderRadius: "20px",
        background: clr.bg,
        fontFamily: "DM Mono, monospace",
        fontSize: "9px",
        fontWeight: 500,
        letterSpacing: "0.1em",
        textTransform: "uppercase",
        color: clr.text,
        whiteSpace: "nowrap",
      }}
    >
      <span style={{ width: "5px", height: "5px", borderRadius: "50%", background: clr.dot, flexShrink: 0 }} />
      {label}
    </span>
  );
}

function MiniBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div style={{ height: "3px", width: "100%", borderRadius: "2px", background: C.bgMuted, overflow: "hidden" }}>
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
        transition={{ duration: 0.45, ease: EASE, delay: 0.1 }}
        style={{ height: "100%", background: color, borderRadius: "2px" }}
      />
    </div>
  );
}

function ArcGauge({ pct, color }: { pct: number; color: string }) {
  const clamped = Math.max(0, Math.min(100, pct));
  const r = 14;
  const circ = 2 * Math.PI * r;
  return (
    <svg width="38" height="38" viewBox="0 0 38 38" style={{ flexShrink: 0 }}>
      <circle cx="19" cy="19" r={r} fill="none" stroke={C.bgMuted} strokeWidth="3" />
      <motion.circle
        cx="19"
        cy="19"
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="3"
        strokeLinecap="round"
        strokeDasharray={circ}
        initial={{ strokeDashoffset: circ }}
        animate={{ strokeDashoffset: circ - (clamped / 100) * circ }}
        transition={{ duration: 0.55, ease: EASE, delay: 0.15 }}
        transform="rotate(-90 19 19)"
      />
      <text
        x="19"
        y="23"
        textAnchor="middle"
        style={{ fontFamily: "DM Mono, monospace", fontSize: "7px", fill: color, fontWeight: 500 }}
      >
        {clamped}%
      </text>
    </svg>
  );
}

function MetricRow({
  label,
  value,
  tone = "neutral",
  icon,
  extra,
}: {
  label: string;
  value: string;
  tone?: Tone;
  icon?: React.ReactNode;
  extra?: React.ReactNode;
}) {
  const valueColor =
    tone === "red" ? C.coral :
    tone === "green" ? C.green :
    tone === "amber" ? C.amber :
    tone === "blue" ? C.accent :
    C.text;

  return (
    <div style={{ padding: "11px 0" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "12px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px", minWidth: 0 }}>
          {icon && <span style={{ color: C.muted, display: "flex", alignItems: "center", flexShrink: 0 }}>{icon}</span>}
          <span
            style={{
              fontFamily: "DM Mono, monospace",
              fontSize: "10px",
              fontWeight: 500,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: C.muted,
              whiteSpace: "nowrap",
            }}
          >
            {label}
          </span>
        </div>
        <span
          style={{
            fontFamily: "DM Sans, sans-serif",
            fontSize: "13px",
            fontWeight: 600,
            color: valueColor,
            letterSpacing: "-0.01em",
            textAlign: "right",
          }}
        >
          {value}
        </span>
      </div>
      {extra && <div style={{ marginTop: "6px" }}>{extra}</div>}
    </div>
  );
}

function DivRow({ children, last = false }: { children: React.ReactNode; last?: boolean }) {
  return <div style={{ borderBottom: last ? "none" : `1px solid ${C.divider}` }}>{children}</div>;
}

function EngineCard({
  title,
  subtitle,
  badgeLabel,
  badgeTone,
  icon,
  accentColor,
  children,
}: {
  title: string;
  subtitle: string;
  badgeLabel: string;
  badgeTone: Tone;
  icon: React.ReactNode;
  accentColor: string;
  children: React.ReactNode;
}) {
  return (
    <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: "12px", overflow: "hidden" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "14px 18px",
          borderBottom: `1px solid ${C.divider}`,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div
            style={{
              width: "30px",
              height: "30px",
              borderRadius: "8px",
              background: `${accentColor}12`,
              border: `1px solid ${accentColor}22`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: accentColor,
            }}
          >
            {icon}
          </div>
          <div>
            <p
              style={{
                fontFamily: "DM Mono, monospace",
                fontSize: "9px",
                fontWeight: 500,
                letterSpacing: "0.14em",
                textTransform: "uppercase",
                color: C.muted,
                marginBottom: "1px",
              }}
            >
              {subtitle}
            </p>
            <p style={{ fontFamily: "DM Sans, sans-serif", fontSize: "13px", fontWeight: 600, color: C.text }}>
              {title}
            </p>
          </div>
        </div>
        <StatusBadge label={badgeLabel} tone={badgeTone} />
      </div>
      <div style={{ padding: "0 18px" }}>{children}</div>
    </div>
  );
}

function ContentPlaceholder({ type, message }: { type: "loading" | "error" | "empty"; message?: string }) {
  const isLoading = type === "loading";
  const isError = type === "error";
  return (
    <div style={{ minHeight: "100vh", background: C.bg, fontFamily: "DM Sans, sans-serif", color: C.text }}>
      <Fade delay={0.05}>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "80px 28px",
            gap: "12px",
            textAlign: "center",
          }}
        >
          {isLoading ? (
            <motion.div
              animate={{ opacity: [0.3, 1, 0.3] }}
              transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
              style={{ width: "8px", height: "8px", borderRadius: "50%", background: C.accent }}
            />
          ) : isError ? (
            <AlertTriangle size={20} color={C.coral} />
          ) : (
            <Database size={20} color={C.muted} />
          )}
          <span
            style={{
              fontFamily: isLoading ? "DM Mono, monospace" : "DM Sans, sans-serif",
              fontSize: isLoading ? "10px" : "14px",
              fontWeight: isLoading ? 500 : 600,
              letterSpacing: isLoading ? "0.14em" : 0,
              textTransform: isLoading ? "uppercase" : "none",
              color: isLoading ? C.muted : C.text,
            }}
          >
            {isLoading ? "Loading asset insights" : isError ? "Failed to load asset" : "Select an asset to view insights"}
          </span>
          {!isLoading && (
            <span style={{ fontFamily: "DM Mono, monospace", fontSize: "11px", color: C.muted, maxWidth: "360px", lineHeight: 1.6 }}>
              {message ?? "Upload or select an asset from the command center."}
            </span>
          )}
        </div>
      </Fade>
    </div>
  );
}

function InsightsShell({
  mode,
  assetId,
  fileType,
  verdictLabel,
  verdictColor,
  Maps,
  children,
}: {
  mode: UserRole;
  assetId: string;
  fileType: string;
  verdictLabel: string;
  verdictColor: string;
  Maps: (path: string) => void;
  children: React.ReactNode;
}) {
  const isAuditor = mode === "AUDITOR";
  const ghostBtnStyle: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: "6px",
    padding: "7px 13px",
    borderRadius: "8px",
    border: `1px solid ${C.border}`,
    background: "transparent",
    cursor: "pointer",
    color: C.muted,
    fontFamily: "DM Sans, sans-serif",
    fontSize: "13px",
    fontWeight: 500,
    transition: "border-color 0.15s, color 0.15s",
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: C.bg,
        fontFamily: "DM Sans, sans-serif",
        color: C.text,
        paddingBottom: "88px",
      }}
    >
      <Fade delay={0}>
        <div
          style={{
            padding: "20px 28px 0",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "12px",
          }}
        >
          <button
            type="button"
            onClick={() => Maps("/home")}
            style={ghostBtnStyle}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = "rgba(0,0,0,0.16)";
              e.currentTarget.style.color = C.text;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = C.border;
              e.currentTarget.style.color = C.muted;
            }}
          >
            <ArrowLeft size={14} strokeWidth={2} />
            Back to Home
          </button>

          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              background: `${verdictColor}10`,
              border: `1px solid ${C.border}`,
              borderRadius: "10px",
              padding: "8px 12px",
            }}
          >
            {isAuditor ? <ShieldAlert size={14} /> : <CheckCircle2 size={14} />}
            <span
              style={{
                fontFamily: "DM Mono, monospace",
                fontSize: "10px",
                fontWeight: 600,
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                color: verdictColor,
              }}
            >
              {isAuditor ? "Auditor Mode · Locked" : "Producer Mode · Locked"}
            </span>
          </div>
        </div>
      </Fade>

      <Fade delay={0.04}>
        <div style={{ padding: "18px 28px 0" }}>
          <p
            style={{
              fontFamily: "DM Mono, monospace",
              fontSize: "10px",
              fontWeight: 500,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: C.muted,
            }}
          >
            {isAuditor ? "Threat Intelligence · Analysis Report" : "Golden Library · Ingestion Report"}
          </p>
          <h1
            style={{
              fontFamily: "DM Sans, sans-serif",
              fontSize: "clamp(22px, 2.8vw, 32px)",
              fontWeight: 700,
              color: C.text,
              letterSpacing: "-0.025em",
              marginTop: "4px",
              lineHeight: 1.15,
            }}
          >
            {isAuditor ? "Forensic Verdict" : "Producer Ingestion Telemetry"}
          </h1>
        </div>
      </Fade>

      <Fade delay={0.07}>
        <div style={{ padding: "16px 28px 0" }}>
          <div
            style={{
              background: C.bgCard,
              border: `1px solid ${C.border}`,
              borderRadius: "12px",
              display: "flex",
              overflow: "hidden",
              flexWrap: "wrap",
            }}
          >
            {[
              { label: "Asset ID", value: assetId, icon: <Tag size={11} />, color: C.accent },
              { label: "File Type", value: fileType, icon: <Film size={11} />, color: C.text },
              { label: "Mode", value: isAuditor ? "Suspect Audit" : "Golden Ingest", icon: <ShieldAlert size={11} />, color: C.text },
              { label: "Verdict", value: verdictLabel, icon: isAuditor ? <AlertTriangle size={11} /> : <CheckCircle2 size={11} />, color: verdictColor },
            ].map((item, i, arr) => (
              <div
                key={item.label}
                style={{
                  flex: "1 1 120px",
                  padding: "12px 16px",
                  borderRight: i < arr.length - 1 ? `1px solid ${C.divider}` : "none",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "4px", color: C.muted, marginBottom: "3px" }}>
                  {item.icon}
                  <span
                    style={{
                      fontFamily: "DM Mono, monospace",
                      fontSize: "9px",
                      fontWeight: 500,
                      letterSpacing: "0.12em",
                      textTransform: "uppercase",
                      color: C.muted,
                    }}
                  >
                    {item.label}
                  </span>
                </div>
                <span style={{ fontFamily: "DM Sans, sans-serif", fontSize: "13px", fontWeight: 600, color: item.color }}>
                  {item.value}
                </span>
              </div>
            ))}
          </div>
        </div>
      </Fade>

      {children}

      <div
        style={{
          position: "fixed",
          bottom: 0,
          left: 0,
          right: 0,
          zIndex: 40,
          background: C.bgCard,
          borderTop: `1px solid ${C.border}`,
          padding: "14px 28px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: verdictColor, flexShrink: 0 }} />
          <span
            style={{
              fontFamily: "DM Mono, monospace",
              fontSize: "10px",
              fontWeight: 500,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              color: verdictColor,
            }}
          >
            {isAuditor ? "Forensics Ready" : "Ingest Verified"}
          </span>
          <span style={{ color: C.muted, fontFamily: "DM Mono, monospace", fontSize: "10px" }}>·</span>
          <span style={{ fontFamily: "DM Mono, monospace", fontSize: "10px", color: C.muted }}>{assetId}</span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <button
            type="button"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "8px 16px",
              borderRadius: "8px",
              border: `1px solid ${C.border}`,
              background: "transparent",
              cursor: "pointer",
              fontFamily: "DM Sans, sans-serif",
              fontSize: "13px",
              fontWeight: 500,
              color: C.muted,
              transition: "border-color 0.15s, color 0.15s",
            }}
          >
            <Download size={13} />
            {isAuditor ? "Export Threat Report" : "Export Ingestion Report"}
          </button>

          {isAuditor && (
            <motion.button
              type="button"
              whileHover={{ y: -1 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => Maps(`/nexus/${assetId}`)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "7px",
                padding: "9px 20px",
                borderRadius: "8px",
                border: "none",
                cursor: "pointer",
                fontFamily: "DM Sans, sans-serif",
                fontSize: "13px",
                fontWeight: 600,
                background: C.text,
                color: C.bg,
                letterSpacing: "-0.01em",
              }}
            >
              <GitBranch size={13} />
              Nexus Graph Analysis
            </motion.button>
          )}
        </div>
      </div>
    </div>
  );
}

export function AuditorInsights({ data, Maps }: { data: AuditorForensics; Maps: (path: string) => void }) {
  const verdictInfo = VERDICT_DISPLAY[data.verdict];
  const visualPct = toScorePercent(data.visualScore);
  const audioPct = toScorePercent(data.audioScore);
  const fusedPct = toScorePercent(data.fusedScore);
  const fileType = getFileTypeLabel(data.filename);

  return (
    <InsightsShell
      mode="AUDITOR"
      assetId={data.assetId}
      fileType={fileType}
      verdictLabel={verdictInfo.label}
      verdictColor={verdictInfo.color}
      Maps={Maps}
    >
      <Fade delay={0.1}>
        <div style={{ padding: "14px 28px 0" }}>
          <div
            style={{
              background: C.bgCard,
              border: `1px solid ${C.border}`,
              borderRadius: "12px",
              padding: "18px",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "18px",
              flexWrap: "wrap",
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <StatusBadge label={verdictInfo.shortLabel} tone={verdictInfo.tone} />
              <h2 style={{ fontSize: "24px", fontWeight: 800, color: verdictInfo.color, marginTop: "10px", letterSpacing: "-0.02em" }}>
                {data.verdict === "PIRACY_DETECTED" ? `PIRACY DETECTED: ${fusedPct}% Match` : verdictInfo.label}
              </h2>
              <p style={{ fontSize: "13px", color: C.muted, marginTop: "5px", lineHeight: 1.6 }}>
                {data.matchedAssetId
                  ? `Matched against reference asset ${data.matchedAssetId}.`
                  : "No protected reference asset was returned by the auditor service."}
              </p>
              <motion.button
                type="button"
                whileHover={{ scale: 1.02, y: -1 }}
                whileTap={{ scale: 0.97 }}
                onClick={() => Maps(`/nexus/${data.assetId}`)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                  marginTop: "14px",
                  padding: "10px 22px",
                  borderRadius: "8px",
                  border: "none",
                  cursor: "pointer",
                  fontFamily: "DM Sans, sans-serif",
                  fontSize: "13px",
                  fontWeight: 700,
                  background: C.text,
                  color: C.bg,
                  letterSpacing: "-0.01em",
                }}
              >
                <GitBranch size={14} strokeWidth={2.5} />
                Advanced Analysis
              </motion.button>
            </div>
            <ArcGauge pct={fusedPct} color={verdictInfo.color} />
          </div>
        </div>
      </Fade>

      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.18, ease: EASE }}
      >
        <div
          style={{
            padding: "14px 28px 0",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            gap: "14px",
          }}
        >
          <EngineCard
            title="Visual Similarity"
            subtitle="Rohit Engine"
            badgeLabel="FAISS"
            badgeTone={visualPct >= 70 ? "red" : "green"}
            icon={<Eye size={14} />}
            accentColor={visualPct >= 70 ? C.coral : C.green}
          >
            <DivRow>
              <MetricRow
                label="Visual Match"
                value={`${visualPct}%`}
                tone={visualPct >= 70 ? "red" : "green"}
                icon={<Eye size={11} />}
                extra={<MiniBar pct={visualPct} color={visualPct >= 70 ? C.coral : C.green} />}
              />
            </DivRow>
            <DivRow last>
              <MetricRow
                label="Matched Timestamp"
                value={data.matchedTimestamp == null ? "No frame match" : `${data.matchedTimestamp.toFixed(2)}s`}
                icon={<Clock size={11} />}
              />
            </DivRow>
          </EngineCard>

          <EngineCard
            title="Audio Similarity"
            subtitle="Ghost Node"
            badgeLabel="DTW"
            badgeTone={audioPct >= 70 ? "red" : "green"}
            icon={<Mic size={14} />}
            accentColor={audioPct >= 70 ? C.coral : C.green}
          >
            <DivRow>
              <MetricRow
                label="Audio Match"
                value={`${audioPct}%`}
                tone={audioPct >= 70 ? "red" : "green"}
                icon={<Mic size={11} />}
                extra={<MiniBar pct={audioPct} color={audioPct >= 70 ? C.coral : C.green} />}
              />
            </DivRow>
            <DivRow last>
              <MetricRow
                label="Overall Fused Score"
                value={`${fusedPct}%`}
                tone={verdictInfo.tone}
                icon={<Activity size={11} />}
                extra={<MiniBar pct={fusedPct} color={verdictInfo.color} />}
              />
            </DivRow>
          </EngineCard>
        </div>
      </motion.div>
    </InsightsShell>
  );
}

export function ProducerInsights({ data, Maps }: { data: ProducerAnalytics; Maps: (path: string) => void }) {
  const fileType = getFileTypeLabel(data.filename);

  return (
    <InsightsShell
      mode="PRODUCER"
      assetId={data.assetId}
      fileType={fileType}
      verdictLabel="Protected"
      verdictColor={C.green}
      Maps={Maps}
    >
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.18, ease: EASE }}
      >
        <div
          style={{
            padding: "14px 28px 0",
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: "14px",
          }}
        >
          <EngineCard
            title="Frame Extraction"
            subtitle="M2 Extractor"
            badgeLabel="Complete"
            badgeTone="green"
            icon={<Film size={14} />}
            accentColor={C.green}
          >
            <DivRow>
              <MetricRow
                label="Total Frames Processed"
                value={data.totalFrames.toLocaleString()}
                tone="green"
                icon={<Film size={11} />}
              />
            </DivRow>
            <DivRow last>
              <MetricRow
                label="Successful Extractions"
                value={data.successfulExtractions.toLocaleString()}
                tone="green"
                icon={<CheckCircle2 size={11} />}
              />
            </DivRow>
          </EngineCard>

          <EngineCard
            title="Node Execution"
            subtitle="Distributed GPU Nodes"
            badgeLabel="Synced"
            badgeTone="blue"
            icon={<Activity size={14} />}
            accentColor={C.accent}
          >
            <DivRow>
              <MetricRow
                label="Vision Node Execution Time"
                value={data.visionNodeLatencyMs > 0 ? `${data.visionNodeLatencyMs} ms` : "Awaiting telemetry"}
                icon={<Eye size={11} />}
              />
            </DivRow>
            <DivRow last>
              <MetricRow
                label="Text Node Execution Time"
                value={data.contextNodeLatencyMs > 0 ? `${data.contextNodeLatencyMs} ms` : "Awaiting telemetry"}
                icon={<ScanText size={11} />}
              />
            </DivRow>
          </EngineCard>

          <EngineCard
            title="Vector Persistence"
            subtitle="PostgreSQL"
            badgeLabel="Permanent"
            badgeTone="green"
            icon={<Database size={14} />}
            accentColor={C.violet}
          >
            <DivRow last>
              <MetricRow
                label="Database Vectors Synced"
                value={data.databaseVectorsSynced.toLocaleString()}
                tone="green"
                icon={<Database size={11} />}
                extra={<MiniBar pct={data.totalFrames > 0 ? 100 : 0} color={C.green} />}
              />
            </DivRow>
          </EngineCard>
        </div>
      </motion.div>
    </InsightsShell>
  );
}

export default function InsightsScreen({ assetId, role: roleProp, Maps = () => {} }: Props) {
  useFonts();
  const params = useParams<{ assetId: string }>();
  const resolvedAssetId = assetId ?? params.assetId;
  const { userRole, isAuditor: authIsAuditor } = useAuth();
  const [assetStatus, setAssetStatus] = useState<AssetStatusResponse | null>(null);
  const [assetResult, setAssetResult] = useState<SimilarityResultResponse | null>(null);
  const [loading, setLoading] = useState(Boolean(resolvedAssetId));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!resolvedAssetId) {
      setLoading(false);
      return;
    }

    const currentAssetId = resolvedAssetId;
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      setAssetResult(null);

      const statusResponse = await assetApi.status(currentAssetId);
      if (cancelled) return;

      if (!statusResponse.ok) {
        setError(statusResponse.error);
        setLoading(false);
        return;
      }

      setAssetStatus(statusResponse.data);

      if (!statusResponse.data.is_golden) {
        const resultResponse = await assetApi.result(currentAssetId);
        if (cancelled) return;
        if (resultResponse.ok) {
          setAssetResult(resultResponse.data);
        } else {
          setError(resultResponse.error);
        }
      }

      setLoading(false);
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [resolvedAssetId]);

  const activeRole: UserRole = assetStatus
    ? assetStatus.is_golden ? "PRODUCER" : "AUDITOR"
    : roleProp === "AUDITOR" || userRole === "AUDITOR" || authIsAuditor ? "AUDITOR" : "PRODUCER";

  const producerData = useMemo(() => buildProducerAnalytics(assetStatus), [assetStatus]);
  const auditorData = useMemo(() => buildAuditorForensics(assetStatus, assetResult), [assetStatus, assetResult]);
  const isAuditor = activeRole === "AUDITOR";

  if (!resolvedAssetId) {
    return <ContentPlaceholder type="empty" />;
  }

  if (loading) {
    return <ContentPlaceholder type="loading" />;
  }

  if (error) {
    return <ContentPlaceholder type="error" message={error} />;
  }

  return isAuditor ? (
    <AuditorInsights data={auditorData} Maps={Maps} />
  ) : (
    <ProducerInsights data={producerData} Maps={Maps} />
  );
}
