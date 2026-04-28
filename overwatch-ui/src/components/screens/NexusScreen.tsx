import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Activity,
  Database,
  Image as ImageIcon,
  Mic,
  ScanText,
  Zap
} from "lucide-react";
import { useParams } from "react-router-dom";

// ─── Design Tokens (Synced from InsightsScreen) ─────────────────────────────
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

// ─── API Interfaces ──────────────────────────────────────────────────────────
export interface NexusTimelinePoint {
  timestamp: number;
  visual_score: number;
  audio_score: number;
  text_score: number;
  fused_score: number;
  is_threat: boolean;
}

export interface NexusKeyFrame {
  timestamp: number;
  bounding_boxes: number;
  faiss_distance: number;
  ocr_text: string[];
  whisper_chunk: string;
}

export interface NexusForensicData {
  asset_id: string;
  timeline: NexusTimelinePoint[];
  key_frames: NexusKeyFrame[];
}

// ─── Mock Data ───────────────────────────────────────────────────────────────
const mockNexusData: NexusForensicData = {
  asset_id: "ingest_a1b2c3d4",
  timeline: [
    { timestamp: 0,  visual_score: 12, audio_score: 5,  text_score: 0,  fused_score: 8,  is_threat: false },
    { timestamp: 5,  visual_score: 15, audio_score: 10, text_score: 0,  fused_score: 11, is_threat: false },
    { timestamp: 10, visual_score: 22, audio_score: 18, text_score: 45, fused_score: 25, is_threat: false },
    { timestamp: 15, visual_score: 89, audio_score: 92, text_score: 85, fused_score: 89, is_threat: true },
    { timestamp: 20, visual_score: 95, audio_score: 94, text_score: 90, fused_score: 94, is_threat: true },
    { timestamp: 25, visual_score: 40, audio_score: 50, text_score: 20, fused_score: 38, is_threat: false },
    { timestamp: 30, visual_score: 10, audio_score: 5,  text_score: 0,  fused_score: 7,  is_threat: false },
  ],
  key_frames: [
    {
      timestamp: 15,
      bounding_boxes: 12,
      faiss_distance: 1.42,
      ocr_text: ["SKY SPORTS", "LIVE", "PREMIER LEAGUE"],
      whisper_chunk: "welcome back to the live broadcast of the premier league match..."
    },
    {
      timestamp: 20,
      bounding_boxes: 15,
      faiss_distance: 1.15,
      ocr_text: ["SCORE 2-1", "WATERMARK_DETECTED"],
      whisper_chunk: "and that's a brilliant goal from the home team, absolutely stunning..."
    }
  ]
};

// ─── Animations ──────────────────────────────────────────────────────────────
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

// ─── Common UI Components ────────────────────────────────────────────────────
function SectionHeader({ title, subtitle, icon }: { title: string; subtitle: string; icon: React.ReactNode }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
      <div style={{
        width: "32px", height: "32px", borderRadius: "8px",
        background: C.bgCard, border: `1px solid ${C.border}`,
        display: "flex", alignItems: "center", justifyContent: "center", color: C.text
      }}>
        {icon}
      </div>
      <div>
        <h3 style={{ fontFamily: "DM Sans, sans-serif", fontSize: "15px", fontWeight: 700, margin: 0, color: C.text, letterSpacing: "-0.01em" }}>
          {title}
        </h3>
        <p style={{ fontFamily: "DM Mono, monospace", fontSize: "10px", fontWeight: 500, letterSpacing: "0.14em", textTransform: "uppercase", color: C.muted, margin: "2px 0 0 0" }}>
          {subtitle}
        </p>
      </div>
    </div>
  );
}

// ─── Main Screen Component ───────────────────────────────────────────────────
export default function NexusScreen({ Maps }: { Maps?: (path: string) => void }) {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<NexusForensicData | null>(null);

  useEffect(() => {
    // Inject Fonts
    if (!document.getElementById("ow-nexus-fonts")) {
      const link = document.createElement("link");
      link.id = "ow-nexus-fonts";
      link.rel = "stylesheet";
      link.href = "https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700;9..40,800&family=DM+Mono:wght@400;500&display=swap";
      document.head.appendChild(link);
    }
    
    // Mock API Load
    const timer = setTimeout(() => {
      setData(mockNexusData);
    }, 400);
    return () => clearTimeout(timer);
  }, [id]);

  if (!data) {
    return (
      <div style={{ height: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: C.bg }}>
        <motion.div animate={{ opacity: [0.3, 1, 0.3] }} transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }} style={{ width: "8px", height: "8px", borderRadius: "50%", background: C.accent }} />
      </div>
    );
  }

  const activeFrame = data.key_frames[0]; // Just picking the first keyframe for the demo

  return (
    <div style={{ minHeight: "100vh", background: C.bg, fontFamily: "DM Sans, sans-serif", color: C.text, paddingBottom: "60px" }}>
      
      {/* ─── Header ────────────────────────────────────────────────────────── */}
      <header style={{ 
        position: "sticky", top: 0, zIndex: 100,
        background: C.bgCard, borderBottom: `1px solid ${C.border}`,
        padding: "16px 32px", display: "flex", alignItems: "center", justifyContent: "space-between"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <motion.button
            whileHover={{ x: -2 }}
            onClick={() => Maps && Maps(`/insights/${id}`)}
            style={{ 
              display: "flex", alignItems: "center", justifyContent: "center",
              width: "36px", height: "36px", borderRadius: "8px",
              background: C.bgMuted, border: `1px solid ${C.divider}`,
              cursor: "pointer", color: C.text
            }}
          >
            <ArrowLeft size={16} />
          </motion.button>
          <div>
            <h1 style={{ fontSize: "18px", fontWeight: 700, margin: 0, letterSpacing: "-0.02em" }}>Nexus Engine</h1>
            <p style={{ fontFamily: "DM Mono, monospace", fontSize: "11px", fontWeight: 500, letterSpacing: "0.1em", textTransform: "uppercase", color: C.muted, margin: "2px 0 0 0" }}>
              Deep Forensic Analysis · {id}
            </p>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontFamily: "DM Mono, monospace", fontSize: "10px", fontWeight: 600, padding: "4px 8px", background: `${C.coral}18`, color: C.coral, borderRadius: "4px", letterSpacing: "0.1em" }}>
            AUDITOR CLEARANCE
          </span>
        </div>
      </header>

      <main style={{ maxWidth: "1200px", margin: "0 auto", padding: "32px", display: "flex", flexDirection: "column", gap: "24px" }}>
        
        {/* ─── Section 1: Threat Timeline ──────────────────────────────────── */}
        <Fade delay={0.1}>
          <section>
            <SectionHeader title="Temporal Threat Signature" subtitle="Fused Score Alignment via DTW" icon={<Activity size={16} />} />
            <div style={{ background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: "12px", padding: "24px", overflow: "hidden" }}>
              
              {/* Fake Area Chart / Timeline */}
              <div style={{ position: "relative", height: "120px", display: "flex", alignItems: "flex-end", gap: "4px", borderBottom: `1px solid ${C.divider}` }}>
                {data.timeline.map((pt, i) => {
                  const height = `${Math.max(pt.fused_score, 2)}%`;
                  const color = pt.is_threat ? C.coral : (pt.fused_score > 40 ? C.amber : C.accent);
                  return (
                    <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: "8px" }}>
                      <motion.div
                        initial={{ height: 0 }}
                        animate={{ height }}
                        transition={{ duration: 0.6, delay: 0.2 + (i * 0.05), ease: EASE }}
                        style={{ width: "100%", background: color, borderRadius: "2px 2px 0 0", opacity: pt.is_threat ? 0.8 : 0.4 }}
                      />
                    </div>
                  );
                })}
                {/* Threat Threshold Line */}
                <div style={{ position: "absolute", bottom: "85%", left: 0, right: 0, borderTop: `1px dashed ${C.coral}`, opacity: 0.5 }} />
                <span style={{ position: "absolute", bottom: "85%", left: "12px", fontFamily: "DM Mono, monospace", fontSize: "9px", color: C.coral, background: C.bgCard, padding: "0 4px", transform: "translateY(50%)" }}>85% PIRACY THRESHOLD</span>
              </div>
              
              {/* Timeline Axis */}
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: "12px", fontFamily: "DM Mono, monospace", fontSize: "10px", color: C.muted }}>
                {data.timeline.map((pt, i) => <span key={i}>{pt.timestamp}s</span>)}
              </div>

            </div>
          </section>
        </Fade>

        {/* ─── Section 2: Multimodal Breakdown Grid ────────────────────────── */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "24px" }}>
          
          {/* Card A: Visual & Spatial */}
          <Fade delay={0.2} style={{ display: "flex" }}>
            <div style={{ flex: 1, background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: "12px", padding: "20px", display: "flex", flexDirection: "column" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
                <ImageIcon size={14} color={C.accent} />
                <h4 style={{ fontSize: "13px", fontWeight: 600, margin: 0, textTransform: "uppercase", letterSpacing: "0.06em", color: C.text }}>Visual & Spatial</h4>
              </div>
              
              {/* Target Frame Simulation */}
              <div style={{ 
                position: "relative", width: "100%", aspectRatio: "16/9", background: C.bgMuted, 
                borderRadius: "8px", overflow: "hidden", marginBottom: "16px", border: `1px solid ${C.divider}`
              }}>
                <div style={{ position: "absolute", inset: 0, background: "linear-gradient(45deg, rgba(0,0,0,0.02) 25%, transparent 25%, transparent 50%, rgba(0,0,0,0.02) 50%, rgba(0,0,0,0.02) 75%, transparent 75%, transparent)" }} />
                {/* Fake Bounding Boxes */}
                <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.5, ease: EASE }} style={{ position: "absolute", top: "20%", left: "30%", width: "40%", height: "30%", border: `1.5px solid ${C.accent}`, background: `${C.accent}11` }}>
                  <span style={{ position: "absolute", top: "-14px", left: "-1px", background: C.accent, color: C.bgCard, fontFamily: "DM Mono", fontSize: "8px", padding: "2px 4px", fontWeight: 600 }}>YOLOv8 Obj</span>
                </motion.div>
                <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ delay: 0.6, ease: EASE }} style={{ position: "absolute", top: "10%", right: "10%", width: "20%", height: "15%", border: `1.5px solid ${C.coral}`, background: `${C.coral}11` }}>
                  <span style={{ position: "absolute", top: "-14px", left: "-1px", background: C.coral, color: C.bgCard, fontFamily: "DM Mono", fontSize: "8px", padding: "2px 4px", fontWeight: 600 }}>WATERMARK</span>
                </motion.div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "12px", fontFamily: "DM Mono, monospace", fontSize: "11px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", borderBottom: `1px solid ${C.divider}`, paddingBottom: "6px" }}>
                  <span style={{ color: C.muted }}>FAISS L2 Distance</span>
                  <span style={{ fontWeight: 600, color: C.text }}>{activeFrame.faiss_distance.toFixed(4)}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", borderBottom: `1px solid ${C.divider}`, paddingBottom: "6px" }}>
                  <span style={{ color: C.muted }}>Objects Detected</span>
                  <span style={{ fontWeight: 600, color: C.text }}>{activeFrame.bounding_boxes}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: C.muted }}>Vector Dim</span>
                  <span style={{ fontWeight: 600, color: C.text }}>512-D</span>
                </div>
              </div>
            </div>
          </Fade>

          {/* Card B: Audio & Whisper */}
          <Fade delay={0.3} style={{ display: "flex" }}>
            <div style={{ flex: 1, background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: "12px", padding: "20px", display: "flex", flexDirection: "column" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
                <Mic size={14} color={C.amber} />
                <h4 style={{ fontSize: "13px", fontWeight: 600, margin: 0, textTransform: "uppercase", letterSpacing: "0.06em", color: C.text }}>Audio & Whisper</h4>
              </div>

              <div style={{ background: C.bg, border: `1px solid ${C.divider}`, borderRadius: "8px", padding: "12px", marginBottom: "16px", flex: 1 }}>
                <p style={{ fontFamily: "DM Mono, monospace", fontSize: "9px", color: C.muted, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "8px", display: "flex", alignItems: "center", gap: "4px" }}>
                  <Zap size={10} color={C.amber} />
                  16kHz High-Confidence Match
                </p>
                <p style={{ fontFamily: "DM Sans, sans-serif", fontSize: "13px", lineHeight: 1.6, color: C.text, margin: 0, paddingLeft: "8px", borderLeft: `2px solid ${C.amber}` }}>
                  "{activeFrame.whisper_chunk}"
                </p>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "12px", fontFamily: "DM Mono, monospace", fontSize: "11px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", borderBottom: `1px solid ${C.divider}`, paddingBottom: "6px" }}>
                  <span style={{ color: C.muted }}>Target Sequence</span>
                  <span style={{ fontWeight: 600, color: C.text }}>t={activeFrame.timestamp}s</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", borderBottom: `1px solid ${C.divider}`, paddingBottom: "6px" }}>
                  <span style={{ color: C.muted }}>Model</span>
                  <span style={{ fontWeight: 600, color: C.text }}>Whisper-V2</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: C.muted }}>Vector Dim</span>
                  <span style={{ fontWeight: 600, color: C.text }}>384-D</span>
                </div>
              </div>
            </div>
          </Fade>

          {/* Card C: Text & OCR */}
          <Fade delay={0.4} style={{ display: "flex" }}>
            <div style={{ flex: 1, background: C.bgCard, border: `1px solid ${C.border}`, borderRadius: "12px", padding: "20px", display: "flex", flexDirection: "column" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "16px" }}>
                <ScanText size={14} color={C.green} />
                <h4 style={{ fontSize: "13px", fontWeight: 600, margin: 0, textTransform: "uppercase", letterSpacing: "0.06em", color: C.text }}>Text & OCR</h4>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "16px", flex: 1 }}>
                {activeFrame.ocr_text.map((txt, idx) => (
                  <motion.div 
                    key={idx}
                    initial={{ x: -10, opacity: 0 }}
                    animate={{ x: 0, opacity: 1 }}
                    transition={{ delay: 0.6 + (idx * 0.1), ease: EASE }}
                    style={{ background: `${C.green}11`, border: `1px solid ${C.green}33`, borderRadius: "6px", padding: "8px 12px", fontFamily: "DM Mono, monospace", fontSize: "12px", fontWeight: 600, color: C.text, display: "flex", alignItems: "center", gap: "8px" }}
                  >
                    <Database size={10} color={C.green} />
                    {txt}
                  </motion.div>
                ))}
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "12px", fontFamily: "DM Mono, monospace", fontSize: "11px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", borderBottom: `1px solid ${C.divider}`, paddingBottom: "6px" }}>
                  <span style={{ color: C.muted }}>Engine</span>
                  <span style={{ fontWeight: 600, color: C.text }}>EasyOCR + MiniLM</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", borderBottom: `1px solid ${C.divider}`, paddingBottom: "6px" }}>
                  <span style={{ color: C.muted }}>Total Entities</span>
                  <span style={{ fontWeight: 600, color: C.text }}>{activeFrame.ocr_text.length}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between" }}>
                  <span style={{ color: C.muted }}>Vector Dim</span>
                  <span style={{ fontWeight: 600, color: C.text }}>384-D</span>
                </div>
              </div>
            </div>
          </Fade>

        </div>
      </main>
    </div>
  );
}