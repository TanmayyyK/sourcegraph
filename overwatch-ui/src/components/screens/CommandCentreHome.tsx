import React, { useEffect, useRef, useState } from "react";
import { motion, useInView } from "framer-motion";
import {
  ArrowRight,
  Zap,
  Activity,
  ChevronDown,
  Circle,
  LogOut,
  Settings,
} from "lucide-react";

/* ══════════════════════════════════════════════════════════════════════════
   DESIGN TOKENS  —  unified from LandingScreen + OverwatchIngestPortal
   ══════════════════════════════════════════════════════════════════════ */
const C = {
  bg:          "#F5F3EF",
  bgCard:      "#FFFFFF",
  bgMuted:     "#EEEBE3",
  accent:      "#4C63F7",
  blue:        "#4F6AFF",
  violet:      "#7C5CF7",
  coral:       "#F26B5B",
  green:       "#22C55E",
  amber:       "#F59E0B",
  text:        "#0F0F0F",
  ink:         "#18181B",
  muted:       "#9B9897",
  textMuted:   "#6B6860",
  border:      "rgba(0,0,0,0.07)",
} as const;

const EASE_SPRING = [0.22, 1, 0.36, 1] as const;

/* ══════════════════════════════════════════════════════════════════════════
   STATIC DATA
   ══════════════════════════════════════════════════════════════════════ */
const NAV_LINKS = ["Dashboard", "Assets", "Threats", "Analytics", "Settings"];

/* ══════════════════════════════════════════════════════════════════════════
   API TYPES
   ══════════════════════════════════════════════════════════════════════ */
interface FeedAsset {
  id:         string;
  filename:   string;
  status:     "processing" | "completed" | "failed";
  is_golden:  boolean;
  created_at: string;
}

interface DashboardStats {
  totalAssets:  number;
  goldenAssets: number;
  isOffline:    boolean;
  isLoading:    boolean;
  nodes:        Record<string, string>;
}

/* ══════════════════════════════════════════════════════════════════════════
   useDashboardStats  —  inline hook; fetches / once on mount
   ══════════════════════════════════════════════════════════════════════ */
function useDashboardStats(): DashboardStats {
  const [stats, setStats] = useState<DashboardStats>({
    totalAssets:  0,
    goldenAssets: 0,
    isOffline:    false,
    isLoading:    true,
    nodes:        {},
  });

  useEffect(() => {
    let cancelled = false;

    async function fetchHealth() {
      try {
        const res = await fetch("http://127.0.0.1:8000/");
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (cancelled) return;
        setStats({
          totalAssets:  data.total_assets,
          goldenAssets: data.golden_assets,
          isOffline:    false,
          isLoading:    false,
          nodes:        data.nodes || {},
        });
      } catch (err) {
        console.error("[CommandCentre] Health fetch failed:", err);
        if (cancelled) return;
        setStats((prev) => ({ ...prev, isOffline: true, isLoading: false }));
      }
    }

    fetchHealth();
    const intervalId = setInterval(fetchHealth, 5000);
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, []);

  return stats;
}

/* ══════════════════════════════════════════════════════════════════════════
   FONT INJECTION
   ══════════════════════════════════════════════════════════════════════ */
function useFonts() {
  useEffect(() => {
    if (document.getElementById("cc-fonts")) return;
    const l = document.createElement("link");
    l.id = "cc-fonts";
    l.rel = "stylesheet";
    l.href =
      "https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700;9..40,800&family=DM+Mono:wght@400;500&display=swap";
    document.head.appendChild(l);
  }, []);
}

/* ══════════════════════════════════════════════════════════════════════════
   PROPS
   ══════════════════════════════════════════════════════════════════════ */
export interface CommandCenterHomeProps {
  userName:   string;
  userRole:   string;
  onNavigate: (destination: "INGEST" | "ASSETS" | "LOGS" | string) => void;
  onLogout?:  () => void;
}

/* ══════════════════════════════════════════════════════════════════════════
   INLINE SVG ICONS
   ══════════════════════════════════════════════════════════════════════ */
function SvgIcon({ name, size = 20, color = "currentColor" }: {
  name: string; size?: number; color?: string;
}) {
  const p = {
    width: size, height: size, viewBox: "0 0 24 24", fill: "none",
    stroke: color, strokeWidth: 1.8,
    strokeLinecap: "round" as const, strokeLinejoin: "round" as const,
  };
  if (name === "shield")
    return <svg {...p}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>;
  if (name === "database")
    return <svg {...p}><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>;
  if (name === "shield-check")
    return <svg {...p}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>;
  if (name === "activity")
    return <svg {...p}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>;
  if (name === "users")
    return <svg {...p}><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>;
  return null;
}

/* ══════════════════════════════════════════════════════════════════════════
   PULSE DOT
   ══════════════════════════════════════════════════════════════════════ */
const PulseDot: React.FC<{ color?: string; size?: number }> = ({
  color = C.green, size = 8,
}) => (
  <span style={{
    position: "relative", display: "inline-flex",
    width: size, height: size, flexShrink: 0,
  }}>
    <motion.span
      style={{
        position: "absolute", inset: 0,
        borderRadius: "50%", background: color, opacity: 0.35,
      }}
      animate={{ scale: [1, 2.4, 1], opacity: [0.35, 0, 0.35] }}
      transition={{ duration: 2.4, repeat: Infinity, ease: "easeOut" }}
    />
    <span style={{
      width: size, height: size,
      borderRadius: "50%", background: color, display: "block",
    }} />
  </span>
);

/* ══════════════════════════════════════════════════════════════════════════
   NAVBAR
   ══════════════════════════════════════════════════════════════════════ */
const AppNavbar: React.FC<{
  userName:   string;
  userRole:   string;
  onNavigate: (dest: string) => void;
  onLogout?:  () => void;
}> = ({ userName, userRole, onNavigate, onLogout }) => {
  const [scrolled,  setScrolled]  = useState(false);
  const [menuOpen,  setMenuOpen]  = useState(false);

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 18);
    window.addEventListener("scroll", handler, { passive: true });
    return () => window.removeEventListener("scroll", handler);
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    const close = () => setMenuOpen(false);
    window.addEventListener("mousedown", close);
    return () => window.removeEventListener("mousedown", close);
  }, [menuOpen]);

  const linkBase: React.CSSProperties = {
    padding: "7px 13px", borderRadius: "8px", border: "none",
    background: "transparent", cursor: "pointer",
    fontSize: "14px", fontWeight: 500, color: C.textMuted,
    fontFamily: "DM Sans, sans-serif",
    transition: "background 0.15s, color 0.15s",
  };

  const initials = userName.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase();

  return (
    <nav style={{
      position:       "fixed",
      top: 0, left: 0, right: 0,
      zIndex:         200,
      height:         "60px",
      display:        "flex",
      alignItems:     "center",
      justifyContent: "space-between",
      padding:        "0 clamp(20px, 4vw, 48px)",
      background:     scrolled ? "rgba(245,243,239,0.92)" : "transparent",
      backdropFilter: scrolled ? "blur(18px)" : "none",
      WebkitBackdropFilter: scrolled ? "blur(18px)" : "none",
      borderBottom:   scrolled ? `1px solid ${C.border}` : "1px solid transparent",
      transition:     "background 0.3s, border-color 0.3s",
    }}>

      {/* Logo */}
      <div
        style={{ display: "flex", alignItems: "center", gap: "9px", flexShrink: 0, cursor: "pointer" }}
        onClick={() => onNavigate("HOME")}
      >
        <div style={{
          width: "30px", height: "30px", borderRadius: "8px",
          background: `linear-gradient(135deg, ${C.accent}, ${C.violet})`,
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: `0 4px 12px ${C.accent}44`,
        }}>
          <SvgIcon name="shield" size={15} color="#fff" />
        </div>
        <span style={{
          fontWeight: 800, fontSize: "17px", color: C.text,
          letterSpacing: "-0.01em", fontFamily: "DM Sans, sans-serif",
        }}>
          Overwatch
        </span>
      </div>

      {/* Centre nav links */}
      <div style={{ display: "flex", alignItems: "center", gap: "2px" }}>
        {NAV_LINKS.map((l) => (
          <button
            key={l} type="button" style={linkBase}
            onMouseEnter={(e) => { e.currentTarget.style.background = C.bgMuted; e.currentTarget.style.color = C.text; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = C.textMuted; }}
            onClick={() => onNavigate(l.toUpperCase())}
          >
            {l}
          </button>
        ))}
      </div>

      {/* Right: authenticated user pill */}
      <div
        style={{ position: "relative", flexShrink: 0 }}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <motion.button
          type="button"
          whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
          onClick={() => setMenuOpen((v) => !v)}
          style={{
            display: "flex", alignItems: "center", gap: "8px",
            padding: "6px 10px 6px 6px", borderRadius: "10px",
            border: `1.5px solid ${C.border}`,
            background: C.bgCard, cursor: "pointer",
            boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
          }}
        >
          <div style={{
            width: "26px", height: "26px", borderRadius: "7px",
            background: `linear-gradient(135deg, ${C.accent}cc, ${C.violet}cc)`,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <span style={{ fontFamily: "DM Sans, sans-serif", fontSize: "10px", fontWeight: 800, color: "#fff" }}>
              {initials}
            </span>
          </div>
          <div style={{ textAlign: "left", lineHeight: 1.2 }}>
            <p style={{ fontFamily: "DM Sans, sans-serif", fontSize: "12px", fontWeight: 700, color: C.text, margin: 0 }}>
              {userName}
            </p>
            <p style={{ fontFamily: "DM Mono, monospace", fontSize: "9px", color: C.textMuted, margin: 0, letterSpacing: "0.06em", textTransform: "uppercase" }}>
              {userRole}
            </p>
          </div>
          <ChevronDown size={13} color={C.textMuted} strokeWidth={2.5} style={{ transform: menuOpen ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }} />
        </motion.button>

        {/* Dropdown */}
        {menuOpen && (
          <motion.div
            initial={{ opacity: 0, y: 6, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.18 }}
            style={{
              position: "absolute", top: "calc(100% + 8px)", right: 0,
              minWidth: "160px", background: C.bgCard,
              border: `1px solid ${C.border}`, borderRadius: "12px",
              padding: "6px", boxShadow: "0 12px 40px rgba(0,0,0,0.10)", zIndex: 300,
            }}
          >
            <button
              type="button"
              style={{ display: "flex", alignItems: "center", gap: "8px", width: "100%", padding: "9px 12px", borderRadius: "8px", border: "none", background: "transparent", cursor: "pointer", fontFamily: "DM Sans, sans-serif", fontSize: "13px", fontWeight: 500, color: C.text, textAlign: "left" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = C.bgMuted)}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <Settings size={13} strokeWidth={2} color={C.textMuted} /> Account Settings
            </button>
            <div style={{ height: 1, background: C.border, margin: "4px 0" }} />
            <button
              type="button" onClick={onLogout}
              style={{ display: "flex", alignItems: "center", gap: "8px", width: "100%", padding: "9px 12px", borderRadius: "8px", border: "none", background: "transparent", cursor: "pointer", fontFamily: "DM Sans, sans-serif", fontSize: "13px", fontWeight: 500, color: C.coral, textAlign: "left" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = `${C.coral}10`)}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <LogOut size={13} strokeWidth={2} color={C.coral} /> Sign out
            </button>
          </motion.div>
        )}
      </div>
    </nav>
  );
};

/* ══════════════════════════════════════════════════════════════════════════
   HERO SECTION
   ══════════════════════════════════════════════════════════════════════ */
const HeroSection: React.FC<{
  userName:    string;
  onNavigate:  (dest: string) => void;
  statsData:   DashboardStats;            // ← live stats
}> = ({ userName, onNavigate, statsData }) => {
  const hour    = new Date().getHours();
  const timeTag = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const firstName = userName.split(" ")[0];

  const [glowPrimary, setGlowPrimary] = useState(false);

  /** Formats the live count, with graceful fallbacks during load / offline */
  const fmtCount = (n: number) => n.toLocaleString();
  const assetsValue = statsData.isLoading
    ? "…"
    : statsData.isOffline
    ? "—"
    : fmtCount(statsData.totalAssets);

  return (
    <section style={{
      position:       "relative",
      minHeight:      "100vh",
      display:        "flex",
      flexDirection:  "column",
      alignItems:     "center",
      justifyContent: "center",
      textAlign:      "center",
      padding:        "120px 24px 100px",
      overflow:       "hidden",
      background:     C.bg,
      fontFamily:     "DM Sans, sans-serif",
    }}>

      {/* ── Ambient glow bubbles ── */}
      <div aria-hidden style={{ position: "absolute", top: "-100px", left: "6%", width: "520px", height: "520px", borderRadius: "50%", background: `radial-gradient(circle, ${C.accent}0d, transparent 65%)`, pointerEvents: "none" }} />
      <div aria-hidden style={{ position: "absolute", bottom: "-60px", right: "5%",  width: "420px", height: "420px", borderRadius: "50%", background: `radial-gradient(circle, ${C.violet}0b, transparent 65%)`, pointerEvents: "none" }} />
      <div aria-hidden style={{ position: "absolute", top: "38%",   right: "10%", width: "300px", height: "300px", borderRadius: "50%", background: `radial-gradient(circle, ${C.coral}08, transparent 60%)`, pointerEvents: "none" }} />

      {/* ── SVG grid ── */}
      <svg aria-hidden style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none", opacity: 0.06 }}>
        <defs>
          <pattern id="hero-grid" x="0" y="0" width="44" height="44" patternUnits="userSpaceOnUse">
            <path d="M 44 0 L 0 0 0 44" fill="none" stroke={C.ink} strokeWidth="0.9" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#hero-grid)" />
      </svg>

      {/* ── Dot grid ── */}
      <svg aria-hidden style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none", opacity: 0.38 }}>
        <defs>
          <pattern id="hero-dots" x="0" y="0" width="26" height="26" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="0.85" fill="rgba(0,0,0,0.055)" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#hero-dots)" />
      </svg>

      {/* ── Content ── */}
      <div style={{ position: "relative", zIndex: 1, maxWidth: "820px", width: "100%" }}>

        {/* Time-of-day eyebrow */}
        <motion.p
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.05, ease: EASE_SPRING }}
          style={{
            fontFamily:    "DM Mono, monospace",
            fontSize:      "11px",
            letterSpacing: "0.22em",
            textTransform: "uppercase",
            color:         C.textMuted,
            margin:        "0 0 20px",
          }}
        >
          {timeTag}
        </motion.p>

        {/* Main heading */}
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.72, delay: 0.1, ease: EASE_SPRING }}
          style={{
            fontSize:      "clamp(54px, 9.5vw, 118px)",
            fontWeight:    800,
            color:         C.text,
            lineHeight:    1.0,
            letterSpacing: "-0.036em",
            margin:        "0 0 30px",
            fontFamily:    "DM Sans, sans-serif",
          }}
        >
          {firstName},
          <br />
          <span style={{
            background:          `linear-gradient(135deg, ${C.accent} 0%, ${C.violet} 60%)`,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip:      "text",
          }}>
            welcome back.
          </span>
        </motion.h1>

        {/* Sub-copy */}
        <motion.p
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, delay: 0.2, ease: EASE_SPRING }}
          style={{
            fontSize:   "clamp(15px, 1.5vw, 18px)",
            color:      C.textMuted,
            maxWidth:   "480px",
            lineHeight: 1.75,
            margin:     "0 auto 48px",
            fontFamily: "DM Sans, sans-serif",
          }}
        >
          Your pipeline is live. Every asset fingerprinted, analyzed, and scored
          in real time — zero blind spots.
        </motion.p>

        {/* CTA buttons */}
        <motion.div
          initial={{ opacity: 0, y: 18 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3, ease: EASE_SPRING }}
          style={{ display: "flex", gap: "12px", justifyContent: "center", flexWrap: "wrap" }}
        >
          {/* Primary: Launch Portal */}
          <motion.button
            type="button"
            onClick={() => onNavigate("INGEST")}
            onHoverStart={() => setGlowPrimary(true)}
            onHoverEnd={() => setGlowPrimary(false)}
            whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.97 }}
            style={{
              display:      "inline-flex",
              alignItems:   "center",
              gap:          "9px",
              padding:      "15px 34px",
              borderRadius: "12px",
              border:       "none",
              cursor:       "pointer",
              fontSize:     "16px",
              fontWeight:   700,
              background:   `linear-gradient(135deg, ${C.accent}, ${C.violet})`,
              color:        "#fff",
              boxShadow:    glowPrimary
                ? `0 8px 48px ${C.accent}68, 0 0 0 5px ${C.accent}1c`
                : `0 8px 28px ${C.accent}40`,
              fontFamily:   "DM Sans, sans-serif",
              transition:   "box-shadow 0.35s ease",
            }}
          >
            <Zap size={16} strokeWidth={2.3} />
            Launch Portal
          </motion.button>

          {/* Secondary: System Logs */}
          <motion.button
            type="button"
            onClick={() => onNavigate("LOGS")}
            whileHover={{ scale: 1.03, backgroundColor: C.bgMuted }}
            whileTap={{ scale: 0.97 }}
            style={{
              display:      "inline-flex",
              alignItems:   "center",
              gap:          "9px",
              padding:      "15px 34px",
              borderRadius: "12px",
              border:       `1.5px solid ${C.border}`,
              cursor:       "pointer",
              fontSize:     "16px",
              fontWeight:   600,
              background:   C.bgCard,
              color:        C.text,
              boxShadow:    "0 2px 12px rgba(0,0,0,0.05)",
              fontFamily:   "DM Sans, sans-serif",
              transition:   "background-color 0.15s",
            }}
          >
            <Activity size={15} strokeWidth={2} />
            System Logs
          </motion.button>
        </motion.div>

        {/* Stats row — "Assets Protected" now uses live totalAssets */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8, delay: 0.48 }}
          style={{
            display:        "flex",
            gap:            "clamp(28px, 5vw, 56px)",
            marginTop:      "72px",
            flexWrap:       "wrap",
            justifyContent: "center",
          }}
        >
          {[
            { value: assetsValue, label: "Assets Protected" },
            { value: "99.97%",   label: "Uptime"           },
            { value: "< 800ms",  label: "Avg Ingest Time"  },
            { value: "24",       label: "Threats Blocked"  },
          ].map((s) => (
            <div key={s.label} style={{ textAlign: "center" }}>
              <p style={{
                fontSize: "clamp(22px, 2.5vw, 30px)", fontWeight: 800,
                color: C.text, lineHeight: 1, marginBottom: "5px",
                letterSpacing: "-0.03em", fontFamily: "DM Sans, sans-serif",
              }}>
                {s.value}
              </p>
              <p style={{
                fontSize: "11px", color: C.textMuted, whiteSpace: "nowrap",
                fontFamily: "DM Mono, monospace", letterSpacing: "0.07em", margin: 0,
              }}>
                {s.label}
              </p>
            </div>
          ))}
        </motion.div>
      </div>

      {/* Scroll cue */}
      <motion.div
        initial={{ opacity: 0 }} animate={{ opacity: 1 }}
        transition={{ delay: 1.1, duration: 0.6 }}
        style={{ position: "absolute", bottom: "36px", left: "50%", transform: "translateX(-50%)", display: "flex", flexDirection: "column", alignItems: "center", gap: "6px" }}
      >
        <motion.div
          animate={{ y: [0, 7, 0] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
          style={{ width: "1px", height: "44px", background: `linear-gradient(to bottom, transparent, ${C.textMuted}55)` }}
        />
        <span style={{ fontFamily: "DM Mono, monospace", fontSize: "9px", letterSpacing: "0.18em", color: C.textMuted, textTransform: "uppercase" }}>
          Scroll
        </span>
      </motion.div>
    </section>
  );
};

/* ══════════════════════════════════════════════════════════════════════════
   MINI BAR CHART
   ══════════════════════════════════════════════════════════════════════ */
const MiniBarChart: React.FC<{ color: string }> = ({ color }) => {
  const ref    = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const bars   = [42, 58, 50, 66, 73, 61, 78, 70, 85, 80, 93, 88];

  return (
    <div ref={ref}>
      <div style={{ display: "flex", alignItems: "flex-end", gap: "3px", height: "36px", marginBottom: "10px" }}>
        {bars.map((h, i) => (
          <motion.div
            key={i}
            initial={{ scaleY: 0 }}
            animate={inView ? { scaleY: 1 } : {}}
            transition={{ delay: i * 0.04, duration: 0.4, ease: "easeOut" }}
            style={{
              flex: 1, borderRadius: "3px 3px 2px 2px",
              background: i >= bars.length - 2 ? color : `${color}28`,
              height: `${h}%`, transformOrigin: "bottom",
            }}
          />
        ))}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span style={{ fontFamily: "DM Mono, monospace", fontSize: "10px", color: C.textMuted, letterSpacing: "0.06em" }}>Last 12 weeks</span>
        <span style={{ fontFamily: "DM Mono, monospace", fontSize: "10px", color, letterSpacing: "0.04em", fontWeight: 500 }}>↑ 3.1%</span>
      </div>
    </div>
  );
};

/* ══════════════════════════════════════════════════════════════════════════
   THREAT TIMELINE
   ══════════════════════════════════════════════════════════════════════ */
const ThreatTimeline: React.FC = () => {
  const ref    = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const items  = [
    { label: "Deepfake signature detected",   time: "2m ago",    color: C.coral },
    { label: "Supply-chain anomaly flagged",   time: "41m ago",   color: C.amber },
    { label: "Plagiarism cluster resolved",    time: "3h ago",    color: C.amber },
    { label: "Adversarial embed neutralised",  time: "Yesterday", color: C.green },
  ];

  return (
    <div ref={ref} style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
      {items.map((item, i) => (
        <motion.div
          key={item.label}
          initial={{ opacity: 0, x: -12 }}
          animate={inView ? { opacity: 1, x: 0 } : {}}
          transition={{ delay: i * 0.08 + 0.1, duration: 0.4, ease: "easeOut" }}
          style={{
            display:        "flex",
            alignItems:     "center",
            justifyContent: "space-between",
            padding:        "8px 12px",
            borderRadius:   "10px",
            background:     `${item.color}09`,
            border:         `1px solid ${item.color}1c`,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Circle size={6} fill={item.color} stroke="none" />
            <span style={{ fontFamily: "DM Sans, sans-serif", fontSize: "12px", fontWeight: 500, color: C.text }}>
              {item.label}
            </span>
          </div>
          <span style={{ fontFamily: "DM Mono, monospace", fontSize: "10px", color: C.textMuted, flexShrink: 0, marginLeft: "12px" }}>
            {item.time}
          </span>
        </motion.div>
      ))}
    </div>
  );
};

/* ══════════════════════════════════════════════════════════════════════════
   NODE ROSTER
   ══════════════════════════════════════════════════════════════════════ */
const NodeRoster: React.FC<{ statsData: DashboardStats }> = ({ statsData }) => {
  const ref    = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const nodes  = [
    { name: "Yogesh", id: "orchestrator",   role: "Lead Analyst",   color: C.accent },
    { name: "Yug",    id: "text_processor",  role: "Text & OCR Engine",  color: C.violet },
    { name: "Rohit",  id: "vision_engine", role: "Vision Engine", color: C.green  },
  ];

  return (
    <div ref={ref} style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
      {nodes.map((n, i) => {
        const isOk = statsData.nodes[n.id] === "OK";
        const dotColor = isOk ? C.green : C.coral;
        return (
        <motion.div
          key={n.name}
          initial={{ opacity: 0, x: -10 }}
          animate={inView ? { opacity: 1, x: 0 } : {}}
          transition={{ delay: i * 0.1 + 0.05, duration: 0.4, ease: "easeOut" }}
          style={{
            display: "flex", alignItems: "center", gap: "12px",
            padding: "10px 14px", borderRadius: "12px",
            background: "rgba(0,0,0,0.025)", border: `1px solid ${C.border}`,
          }}
        >
          <div style={{
            width: "32px", height: "32px", borderRadius: "50%",
            background: `linear-gradient(135deg, ${n.color}cc, ${n.color}77)`,
            display: "flex", alignItems: "center", justifyContent: "center",
            flexShrink: 0, boxShadow: `0 2px 8px ${n.color}28`,
          }}>
            <span style={{ fontFamily: "DM Sans, sans-serif", fontSize: "11px", fontWeight: 800, color: "#fff" }}>
              {n.name[0]}
            </span>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{ fontFamily: "DM Sans, sans-serif", fontSize: "13px", fontWeight: 600, color: C.text, margin: 0, lineHeight: 1.2 }}>{n.name}</p>
            <p style={{ fontFamily: "DM Mono, monospace", fontSize: "9px", color: C.textMuted, margin: 0, letterSpacing: "0.06em", textTransform: "uppercase" }}>{n.role}</p>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "5px", background: `${dotColor}12`, border: `1px solid ${dotColor}22`, borderRadius: 999, padding: "3px 9px" }}>
            <PulseDot color={dotColor} size={6} />
            <span style={{ fontFamily: "DM Mono, monospace", fontSize: "9px", color: dotColor, letterSpacing: "0.08em" }}>{isOk ? "ONLINE" : "ERR"}</span>
          </div>
        </motion.div>
      )})}
    </div>
  );
};

/* ══════════════════════════════════════════════════════════════════════════
   INTEL CARD
   ══════════════════════════════════════════════════════════════════════ */
interface CardDef {
  tag:    string;
  title:  string;
  body:   string;
  accent: string;
  icon:   React.ReactNode;
  span:   number;
  meta?:  React.ReactNode;
}

const IntelCard: React.FC<{ card: CardDef; index: number }> = ({ card, index }) => {
  const ref    = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-50px" });

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 40 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.65, delay: index * 0.08, ease: EASE_SPRING }}
      whileHover={{ y: -5, transition: { duration: 0.22 } }}
      style={{
        gridColumn:   `span ${card.span}`,
        background:   C.bgCard,
        borderRadius: "26px",
        border:       `1px solid ${C.border}`,
        padding:      "clamp(28px, 3vw, 44px)",
        position:     "relative",
        overflow:     "hidden",
        cursor:       "default",
        boxShadow:    "0 2px 12px rgba(0,0,0,0.04)",
      }}
    >
      {/* Corner ambient glow */}
      <div style={{ position: "absolute", top: "-50px", right: "-50px", width: "200px", height: "200px", borderRadius: "50%", background: `radial-gradient(circle, ${card.accent}1a, transparent 70%)`, pointerEvents: "none" }} />

      {/* Tag */}
      <span style={{
        display: "inline-block", fontSize: "10px", fontWeight: 700,
        letterSpacing: "0.1em", textTransform: "uppercase",
        color: card.accent, background: `${card.accent}18`,
        padding: "4px 10px", borderRadius: "6px",
        marginBottom: "20px", fontFamily: "DM Mono, monospace",
      }}>
        {card.tag}
      </span>

      {/* Icon */}
      <div style={{
        width: "44px", height: "44px", borderRadius: "12px",
        background: `${card.accent}18`, border: `1.5px solid ${card.accent}30`,
        display: "flex", alignItems: "center", justifyContent: "center",
        marginBottom: "18px",
      }}>
        {card.icon}
      </div>

      {/* Heading */}
      <h3 style={{
        fontSize: "clamp(22px, 2.4vw, 30px)", fontWeight: 800,
        color: C.text, marginBottom: "12px", lineHeight: 1.15,
        whiteSpace: "pre-line", fontFamily: "DM Sans, sans-serif",
        letterSpacing: "-0.02em",
      }}>
        {card.title}
      </h3>

      {/* Body */}
      <p style={{
        fontSize: "clamp(14px, 1.2vw, 16px)",
        color: C.textMuted, lineHeight: 1.75,
        maxWidth: "460px", fontFamily: "DM Sans, sans-serif",
        margin: card.meta ? "0 0 28px" : "0",
      }}>
        {card.body}
      </p>

      {card.meta}
    </motion.div>
  );
};

/* ══════════════════════════════════════════════════════════════════════════
   CARDS SECTION
   ══════════════════════════════════════════════════════════════════════ */
const CardsSection: React.FC<{
  onNavigate: (dest: string) => void;
  statsData:  DashboardStats;           // ← live stats
}> = ({ onNavigate, statsData }) => {
  const titleRef    = useRef<HTMLDivElement>(null);
  const titleInView = useInView(titleRef, { once: true, margin: "-60px" });

  /** Format golden asset count with graceful loading / offline states */
  const goldenValue = statsData.isLoading
    ? "…"
    : statsData.isOffline
    ? "—"
    : statsData.goldenAssets.toLocaleString();

  const CARDS: CardDef[] = [
    {
      tag:   "Protected Library",
      // Live: replace hardcoded 1,402 with real golden asset count
      title: `${goldenValue}\nGolden Assets`,
      body:  "Every file fingerprinted with a tamper-evident chain of custody. Your digital library — immutable and fully auditable.",
      accent: C.accent,
      span:   6,
      icon:  <SvgIcon name="database"     size={20} color={C.accent} />,
      meta:  <MiniBarChart color={C.accent} />,
    },
    {
      tag:   "Threats Prevented",
      title: "24 Adversarial\nMatches Blocked",
      body:  "Seven parallel ML models run every ingest in real time, catching deepfakes, plagiarism clusters, and supply-chain anomalies before they land.",
      accent: C.coral,
      span:   6,
      icon:  <SvgIcon name="shield-check" size={20} color={C.coral}  />,
      meta:  <ThreatTimeline />,
    },
    {
      tag:   "Active Nodes",
      title: "All 3 Nodes\nOperational",
      body:  "Vision, text, and analysis engines running at full capacity with real-time coordination across the inference mesh.",
      accent: C.green,
      span:   6,
      icon:  <SvgIcon name="users"        size={20} color={C.green}  />,
      meta:  <NodeRoster statsData={statsData} />,
    },
    {
      tag:   "Pipeline Velocity",
      title: "< 800ms\nEnd-to-End",
      body:  "From byte zero to signed report: fingerprint, bifurcation, seven-model analysis, and verdict synthesis — all under a second.",
      accent: C.violet,
      span:   6,
      icon:  <SvgIcon name="activity"     size={20} color={C.violet} />,
      meta: (
        <motion.button
          type="button"
          onClick={() => onNavigate("INGEST")}
          whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
          style={{
            display: "inline-flex", alignItems: "center", gap: "8px",
            padding: "11px 22px", borderRadius: "10px", border: "none",
            cursor: "pointer", fontSize: "13px", fontWeight: 700,
            background: `linear-gradient(135deg, ${C.violet}, #9B5CF7)`,
            color: "#fff", boxShadow: `0 6px 20px ${C.violet}38`,
            fontFamily: "DM Sans, sans-serif",
          }}
        >
          Run a simulation <ArrowRight size={14} strokeWidth={2.5} />
        </motion.button>
      ),
    },
  ];

  return (
    <section style={{
      padding:    "100px 24px 120px",
      background: C.bg,
      fontFamily: "DM Sans, sans-serif",
    }}>
      <div style={{ maxWidth: "1200px", margin: "0 auto" }}>

        {/* Section header */}
        <div ref={titleRef} style={{ marginBottom: "52px" }}>
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={titleInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.55, ease: EASE_SPRING }}
            style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.14em", color: C.accent, textTransform: "uppercase", marginBottom: "12px", fontFamily: "DM Mono, monospace" }}
          >
            Intelligence Dashboard
          </motion.p>
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            animate={titleInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.65, delay: 0.06, ease: EASE_SPRING }}
            style={{ fontSize: "clamp(30px, 4vw, 52px)", fontWeight: 800, color: C.text, marginBottom: "14px", lineHeight: 1.08, letterSpacing: "-0.025em", fontFamily: "DM Sans, sans-serif" }}
          >
            Everything running{" "}
            <span style={{ color: C.accent }}>as expected</span>
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={titleInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.6, delay: 0.12, ease: EASE_SPRING }}
            style={{ fontSize: "clamp(15px, 1.4vw, 17px)", color: C.textMuted, maxWidth: "460px", lineHeight: 1.7, margin: 0, fontFamily: "DM Sans, sans-serif" }}
          >
            Live metrics across your protected library, active threats, and inference
            nodes — always in view.
          </motion.p>
        </div>

        {/* 12-col bento grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(12, 1fr)", gap: "16px" }}>
          {CARDS.map((card, i) => (
            <IntelCard key={card.tag} card={card} index={i} />
          ))}
        </div>

      </div>
    </section>
  );
};

/* ══════════════════════════════════════════════════════════════════════════
   STICKY SYSTEM STATUS
   Graceful degradation: shows "System Offline" if backend fetch failed.
   ══════════════════════════════════════════════════════════════════════ */
const StickyStatus: React.FC<{ statsData: DashboardStats }> = ({ statsData }) => {
  const [expanded, setExpanded] = useState(false);
  const isOffline = statsData.isOffline;

  const services = [
    { label: "Ingest API",        ok: !isOffline },
    { label: "Vision Engine",     ok: statsData?.nodes?.vision_engine === "OK" },
    { label: "Text Processor",    ok: statsData?.nodes?.text_processor === "OK" },
    { label: "Orchestrator",      ok: statsData?.nodes?.orchestrator === "OK" },
    { label: "All Microservices", ok: !isOffline },
  ];

  const dotColor    = isOffline ? C.coral : C.green;
  const statusLabel = isOffline ? "System Offline" : "System Online";
  const nodeLabel   = isOffline ? "unreachable" : "3/3 nodes";

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 1.4, duration: 0.5, ease: EASE_SPRING }}
      style={{ position: "fixed", bottom: "24px", left: "24px", zIndex: 150 }}
    >
      <motion.div
        layout
        style={{
          background:          "rgba(255,255,255,0.88)",
          backdropFilter:      "blur(20px)",
          WebkitBackdropFilter:"blur(20px)",
          border:              `1px solid ${C.border}`,
          borderRadius:        "14px",
          boxShadow:           "0 8px 32px rgba(0,0,0,0.08)",
          overflow:            "hidden",
        }}
      >
        {/* Collapsed pill */}
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          style={{ display: "flex", alignItems: "center", gap: "8px", padding: "9px 14px", background: "transparent", border: "none", cursor: "pointer", width: "100%" }}
        >
          <PulseDot color={dotColor} size={7} />
          <span style={{ fontFamily: "DM Mono, monospace", fontSize: "10px", color: dotColor, letterSpacing: "0.1em", textTransform: "uppercase", fontWeight: 500 }}>
            {statusLabel}
          </span>
          <span style={{ fontFamily: "DM Mono, monospace", fontSize: "9px", color: C.textMuted, marginLeft: "4px" }}>
            {nodeLabel}
          </span>
          <ChevronDown size={11} color={C.textMuted} strokeWidth={2.5} style={{ transform: expanded ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s", marginLeft: "2px" }} />
        </button>

        {/* Expanded detail */}
        {expanded && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            transition={{ duration: 0.18 }}
            style={{ padding: "10px 14px 12px", borderTop: `1px solid ${C.border}` }}
          >
            {services.map((s) => (
              <div key={s.label} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "24px", padding: "4px 0" }}>
                <span style={{ fontFamily: "DM Mono, monospace", fontSize: "10px", color: C.textMuted }}>{s.label}</span>
                <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                  <Circle size={5} fill={s.ok ? C.green : C.coral} stroke="none" />
                  <span style={{ fontFamily: "DM Mono, monospace", fontSize: "9px", color: s.ok ? C.green : C.coral, letterSpacing: "0.06em" }}>
                    {s.ok ? "OK" : "ERR"}
                  </span>
                </div>
              </div>
            ))}
          </motion.div>
        )}
      </motion.div>
    </motion.div>
  );
};

/* ══════════════════════════════════════════════════════════════════════════
   ROOT EXPORT
   ══════════════════════════════════════════════════════════════════════ */
const CommandCenterHome: React.FC<CommandCenterHomeProps> = ({
  userName,
  userRole,
  onNavigate,
  onLogout,
}) => {
  useFonts();

  // Single source of truth for live backend data — threaded down as props
  const statsData = useDashboardStats();

  return (
    <div
      className="w-full min-h-screen overflow-y-auto"
      style={{ background: C.bg, fontFamily: "DM Sans, sans-serif", color: C.text }}
    >
      <AppNavbar
        userName={userName}
        userRole={userRole}
        onNavigate={onNavigate}
        onLogout={onLogout}
      />

      <HeroSection
        userName={userName}
        onNavigate={onNavigate}
        statsData={statsData}
      />

      <CardsSection
        onNavigate={onNavigate}
        statsData={statsData}
      />

      <StickyStatus statsData={statsData} />
    </div>
  );
};

export default CommandCenterHome;