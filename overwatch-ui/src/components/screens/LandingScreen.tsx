import { useRef, useEffect, useState } from "react";
import { motion, useInView } from "framer-motion";
import { Link } from "react-router-dom";
import SystemStatusOverlay from "./SystemStatusOverlay";

// ─── Colour tokens ────────────────────────────────────────────────────────────
const C = {
  bg: "#F5F2EC",
  bgCard: "#FFFFFF",
  bgMuted: "#EEEBE3",
  bgDark: "#111010",
  accent: "#4C63F7",
  violet: "#7C5CF7",
  coral: "#FF6B47",
  green: "#0EA872",
  text: "#0F0F0F",
  textInverted: "#F5F2EC",
  muted: "#6B6860",
  border: "rgba(0,0,0,0.07)",
  borderDark: "rgba(255,255,255,0.08)",
};

// ─── Data ─────────────────────────────────────────────────────────────────────
const LOGOS = [
  { 
    value: "Distributed Inference", 
    label: "Innovation: Asynchronous multi-node processing utilizing independent ATLAS, ARGUS, and HERMES GPU engines." 
  },
  { 
    value: "Zero-Poison Guards", 
    label: "Innovation: Ephemeral Ghost Nodes and strict VRAM governance prevent OOM crashes and corrupt vector ingestion." 
  },
  { 
    value: "Forensic Tracking", 
    label: "Impact: Cryptographically verifiable JSON-LD incident reports designed for enterprise legal teams." 
  },
  { 
    value: "Sub-Second Detection", 
    label: "Impact: Real-time dual-vector fusion (CLIP + MiniLM) instantly flags piracy and visual supply-chain anomalies." 
  },
];

const FLOW_NODES = [
  { id: 1, label: "Upload Assets",   sub: "Drag & drop any file",     color: "#4C63F7", icon: "upload"  },
  { id: 2, label: "Fingerprint",     sub: "Hash & chain-of-custody",  color: "#7C5CF7", icon: "scan"    },
  { id: 3, label: "AI Analysis",     sub: "7 parallel ML models",     color: "#B05CF7", icon: "brain"   },
  { id: 4, label: "Risk Score",      sub: "Threat classification",    color: "#E05CF0", icon: "zap"     },
  { id: 5, label: "Command Center",  sub: "Live response dashboard",  color: "#FF6B47", icon: "monitor" },
];

const FEATURES = [
  { tag: "Ingestion Engine",    title: "Drop anything.\nFingerprint everything.",    body: "PDFs, images, video, code — Overwatch fingerprints every byte and builds a tamper-evident chain of custody before the file lands on disk.",        accent: "#4C63F7", span: "7", dark: false, icon: "upload"  },
  { tag: "AI Analysis",        title: "Patterns humans miss",                        body: "Seven parallel ML models scan simultaneously for plagiarism, deepfakes, and supply-chain anomalies.",                                              accent: "#7C5CF7", span: "5", dark: false, icon: "brain"   },
  { tag: "Command Center",     title: "One screen,\nevery signal",                   body: "Live risk feed, asset timeline, and one-click SIEM export — all in a single pane of glass.",                                                      accent: "#FF6B47", span: "5", dark: true,  icon: "monitor" },
  { tag: "Trend Intelligence", title: "Act weeks before the threat lands",           body: "Rolling 30-day analytics surface emerging attack patterns and similarity clusters so your team is always a step ahead.",                           accent: "#0EA872", span: "7", dark: false, icon: "chart"   },
];

const TEAM = [
  { name: "Tanmay Kumar",  role: "Founder & Chief Architect",     init: "TK", color: "#4C63F7" },
  { name: "Yogesh Sharma", role: "Head of AI & Threat Intel",     init: "YS", color: "#FF6B47" },
  { name: "Rohit Kumar",   role: "Lead, Vector & Text Engine",    init: "RK", color: "#7C5CF7" },
  { name: "Yug",           role: "Lead, Vision & OCR Engine",     init: "YG", color: "#0EA872" },
];


const STATS = [
  { value: "96.2%",   label: "Detection Precision" }, 
  { value: "<2min",   label: "Average Pipeline"    }, 
  { value: "AES-256", label: "Data Encryption"     }, 
  { value: "JSON-LD", label: "Structured Reports"  }, 
];
const NAV_LINKS = [
  { name: "Home", type: "link", to: "/" },
  { name: "Features", type: "scroll", to: "features-section" },
  { name: "GitHub", type: "external", to: "https://github.com/TanmayyyK/sourcegraph" },
  { name: "Docs", type: "link", to: "/docs" }
];

const FOOTER_COLS = [
  {
    heading: "Company",
    links: [
      { name: "Team", href: "#team" },
      { name: "About Us", href: "/docs/intro" }
    ]
  },
  {
    heading: "Resources",
    links: [
      { name: "Documentation", href: "/docs" },
      { name: "API Reference", href: "https://github.com/TanmayyyK/sourcegraph#readme" }
    ]
  },
  {
    heading: "Connect",
    links: [
      { name: "GitHub", href: "https://github.com/TanmayyyK/sourcegraph" }
    ]
  },
];

// ─── Font injection ───────────────────────────────────────────────────────────
function useFonts() {
  useEffect(() => {
    const id = "ow-fonts";
    if (document.getElementById(id)) return;
    const link = document.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.href = "https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,700;9..40,800&family=DM+Mono:wght@400;500&display=swap";
    document.head.appendChild(link);
  }, []);
}

// ─── SVG Icons ────────────────────────────────────────────────────────────────
function Icon({ name, size = 22, color = "currentColor" }: { name: string; size?: number; color?: string }) {
  const p = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: color, strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  if (name === "upload")  return <svg {...p}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>;
  if (name === "scan")    return <svg {...p}><path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/><circle cx="12" cy="12" r="3"/></svg>;
  if (name === "brain")   return <svg {...p}><path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15a2.5 2.5 0 0 1-4.96-.44 2.5 2.5 0 0 1-2.96-3.08 3 3 0 0 1-.34-5.58 2.5 2.5 0 0 1 1.32-4.24 2.5 2.5 0 0 1 1.98-3A2.5 2.5 0 0 1 9.5 2Z"/><path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 4.96-.44 2.5 2.5 0 0 0 2.96-3.08 3 3 0 0 0 .34-5.58 2.5 2.5 0 0 0-1.32-4.24 2.5 2.5 0 0 0-1.98-3A2.5 2.5 0 0 0 14.5 2Z"/></svg>;
  if (name === "zap")     return <svg {...p}><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>;
  if (name === "monitor") return <svg {...p}><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4"/></svg>;
  if (name === "chart")   return <svg {...p}><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>;
  if (name === "shield")  return <svg {...p}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>;
  if (name === "arrow-r") return <svg {...p}><line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/></svg>;
  return null;
}

// ─── FadeUp helper ────────────────────────────────────────────────────────────
function FadeUp({ children, delay = 0, style = {} }: { children: React.ReactNode; delay?: number; style?: React.CSSProperties }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });
  return (
    <motion.div ref={ref}
      initial={{ opacity: 0, y: 30 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6, delay, ease: [0.22, 1, 0.36, 1] }}
      style={style}
    >
      {children}
    </motion.div>
  );
}

// ─── Navbar ───────────────────────────────────────────────────────────────────
function Navbar({ onLoginClick, onSignupClick }: { onLoginClick: () => void; onSignupClick: () => void }) {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 18);
    window.addEventListener("scroll", handler, { passive: true });
    return () => window.removeEventListener("scroll", handler);
  }, []);

  const linkBase: React.CSSProperties = {
    padding: "7px 13px", borderRadius: "8px", border: "none",
    background: "transparent", cursor: "pointer",
    fontSize: "14px", fontWeight: 500, color: C.muted,
    fontFamily: "DM Sans, sans-serif", transition: "background 0.15s, color 0.15s",
  };

  return (
    <nav style={{
      position: "fixed", top: 0, left: 0, right: 0, zIndex: 200,
      height: "60px", display: "flex", alignItems: "center",
      justifyContent: "space-between",
      padding: "0 clamp(20px, 4vw, 48px)",
      background: scrolled ? "rgba(245,242,236,0.9)" : "transparent",
      backdropFilter: scrolled ? "blur(16px)" : "none",
      WebkitBackdropFilter: scrolled ? "blur(16px)" : "none",
      borderBottom: scrolled ? `1px solid ${C.border}` : "1px solid transparent",
      transition: "background 0.3s, border-color 0.3s",
    }}>
      {/* Logo */}
      <div style={{ display: "flex", alignItems: "center", gap: "9px", flexShrink: 0 }}>
        <div style={{
          width: "30px", height: "30px", borderRadius: "8px",
          background: `linear-gradient(135deg, ${C.accent}, ${C.violet})`,
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: `0 4px 12px ${C.accent}44`,
        }}>
          <Icon name="shield" size={15} color="#fff" />
        </div>
        <span style={{ fontWeight: 800, fontSize: "17px", color: C.text, letterSpacing: "-0.01em", fontFamily: "DM Sans, sans-serif" }}>
          Overwatch
        </span>
      </div>

      {/* Centre nav */}
      <div style={{ display: "flex", alignItems: "center", gap: "2px" }}>
        {NAV_LINKS.map((l) => (
          l.type === "link" ? (
            <Link key={l.name} to={l.to!} style={{ ...linkBase, textDecoration: "none" }}
              onMouseEnter={e => { const el = e.currentTarget; el.style.background = C.bgMuted; el.style.color = C.text; }}
              onMouseLeave={e => { const el = e.currentTarget; el.style.background = "transparent"; el.style.color = C.muted; }}
            >
              {l.name}
            </Link>
          ) : l.type === "external" ? (
            <a key={l.name} href={l.to!} target="_blank" rel="noopener noreferrer" style={{ ...linkBase, textDecoration: "none", display: "inline-block" }}
              onMouseEnter={e => { const el = e.currentTarget; el.style.background = C.bgMuted; el.style.color = C.text; }}
              onMouseLeave={e => { const el = e.currentTarget; el.style.background = "transparent"; el.style.color = C.muted; }}
            >
              {l.name}
            </a>
          ) : (
            <button key={l.name} type="button" style={linkBase}
              onClick={() => {
                if (l.type === "scroll" && l.to) {
                  document.getElementById(l.to)?.scrollIntoView({ behavior: "smooth" });
                }
              }}
              onMouseEnter={e => { const el = e.currentTarget; el.style.background = C.bgMuted; el.style.color = C.text; }}
              onMouseLeave={e => { const el = e.currentTarget; el.style.background = "transparent"; el.style.color = C.muted; }}
            >
              {l.name}
            </button>
          )
        ))}
      </div>

      {/* Right actions */}
      <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
        <button type="button" onClick={onLoginClick} style={linkBase}
          onMouseEnter={e => { (e.currentTarget).style.color = C.text; }}
          onMouseLeave={e => { (e.currentTarget).style.color = C.muted; }}
        >
          Log in
        </button>
        <motion.button type="button" onClick={onSignupClick}
          whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}
          style={{
            padding: "8px 18px", borderRadius: "9px",
            border: `1.5px solid ${C.accent}`,
            background: "transparent", cursor: "pointer",
            fontSize: "14px", fontWeight: 600, color: C.accent,
            fontFamily: "DM Sans, sans-serif",
          }}
          onMouseEnter={e => { const el = e.currentTarget; el.style.background = C.accent; el.style.color = "#fff"; }}
          onMouseLeave={e => { const el = e.currentTarget; el.style.background = "transparent"; el.style.color = C.accent; }}
        >
          Create account
        </motion.button>
      </div>
    </nav>
  );
}

// ─── Hero ─────────────────────────────────────────────────────────────────────
function HeroSection({ onSignupClick }: { onSignupClick: () => void }) {
  return (
    <section style={{
      minHeight: "100vh", background: C.bg, display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", padding: "120px 24px 80px",
      position: "relative", overflow: "hidden", textAlign: "center",
      fontFamily: "DM Sans, sans-serif",
    }}>
      <div style={{ position: "absolute", top: "-100px", left: "6%", width: "480px", height: "480px", borderRadius: "50%", background: `radial-gradient(circle, ${C.accent}0c, transparent 65%)`, pointerEvents: "none" }} />
      <div style={{ position: "absolute", bottom: "-60px", right: "5%", width: "360px", height: "360px", borderRadius: "50%", background: `radial-gradient(circle, ${C.coral}0c, transparent 65%)`, pointerEvents: "none" }} />

      <motion.h1
        initial={{ opacity: 0, y: 28 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        style={{ fontSize: "clamp(42px, 6.5vw, 88px)", fontWeight: 800, color: C.text, lineHeight: 1.05, marginBottom: "22px", maxWidth: "900px", letterSpacing: "-0.02em" }}
      >
        Asset intelligence
        <br />
        <span style={{ background: `linear-gradient(135deg, ${C.accent}, ${C.violet})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
          without blind spots
        </span>
      </motion.h1>

      <motion.p
        initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.65, delay: 0.12, ease: [0.22, 1, 0.36, 1] }}
        style={{ fontSize: "clamp(16px, 1.6vw, 20px)", color: C.muted, maxWidth: "500px", lineHeight: 1.7, marginBottom: "44px" }}
      >
        Fingerprint, analyze, and act on every digital asset in your pipeline. Real-time threat scoring. Zero guesswork.
      </motion.p>

      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 0.22 }}
        style={{ display: "flex", gap: "12px", flexWrap: "wrap", justifyContent: "center" }}
      >
        <motion.button type="button" onClick={onSignupClick}
          whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}
          style={{
            padding: "15px 34px", borderRadius: "12px", border: "none", cursor: "pointer",
            fontSize: "16px", fontWeight: 700,
            background: `linear-gradient(135deg, ${C.accent}, ${C.violet})`,
            color: "#fff", boxShadow: `0 8px 28px ${C.accent}40`,
            fontFamily: "DM Sans, sans-serif",
          }}
        >
          Get started — free
        </motion.button>
        <motion.button type="button"
          whileHover={{ scale: 1.03, backgroundColor: C.bgMuted }} whileTap={{ scale: 0.97 }}
          style={{
            padding: "15px 34px", borderRadius: "12px",
            border: `1.5px solid ${C.border}`, cursor: "pointer",
            fontSize: "16px", fontWeight: 600, background: C.bgCard, color: C.text,
            fontFamily: "DM Sans, sans-serif",
          }}
        >
          Watch demo
        </motion.button>
      </motion.div>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
        transition={{ duration: 0.8, delay: 0.42 }}
        style={{ display: "flex", gap: "clamp(28px, 5vw, 56px)", marginTop: "72px", flexWrap: "wrap", justifyContent: "center" }}
      >
        {STATS.map((s, i) => (
          <div key={i} style={{ textAlign: "center" }}>
            <p style={{ fontSize: "clamp(22px, 2.5vw, 30px)", fontWeight: 800, color: C.text, lineHeight: 1, marginBottom: "5px" }}>{s.value}</p>
            <p style={{ fontSize: "11px", color: C.muted, whiteSpace: "nowrap", fontFamily: "DM Mono, monospace", letterSpacing: "0.07em" }}>{s.label}</p>
          </div>
        ))}
      </motion.div>
    </section>
  );
}

// ─── Marquee ──────────────────────────────────────────────────────────────────
function Marquee() {
  return (
    <div style={{ overflow: "hidden", background: C.bgMuted, borderTop: `1px solid ${C.border}`, borderBottom: `1px solid ${C.border}`, padding: "20px 0", userSelect: "none" }}>
      <p style={{ textAlign: "center", fontSize: "10px", letterSpacing: "0.14em", color: C.muted, fontWeight: 600, textTransform: "uppercase", marginBottom: "14px", fontFamily: "DM Mono, monospace" }}>
        Impact & Innovation
      </p>
      <div style={{ overflow: "hidden" }}>
        <motion.div
          animate={{ x: ["100vw", "-100%"] }}
          transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
          style={{ display: "flex", gap: "72px", width: "max-content", alignItems: "center" }}
        >
          {LOGOS.map((item, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <span style={{ fontSize: "14px", fontWeight: 800, color: C.text, whiteSpace: "nowrap", fontFamily: "DM Sans, sans-serif" }}>
                {item.value}
              </span>
              <span style={{ fontSize: "13px", fontWeight: 500, color: C.muted, whiteSpace: "nowrap", fontFamily: "DM Sans, sans-serif" }}>
                {item.label}
              </span>
            </div>
          ))}
        </motion.div>
      </div>
    </div>
  );
}

// ─── Flowchart — view-triggered, snappy stagger ───────────────────────────────
function FlowchartSection() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-120px" });

  return (
    <section style={{ padding: "100px 24px 110px", background: C.bg, fontFamily: "DM Sans, sans-serif" }}>
      <FadeUp>
        <p style={{ textAlign: "center", fontSize: "11px", fontWeight: 700, letterSpacing: "0.14em", color: C.accent, textTransform: "uppercase", marginBottom: "12px", fontFamily: "DM Mono, monospace" }}>
          How it works
        </p>
        <h2 style={{ textAlign: "center", fontSize: "clamp(30px, 4vw, 52px)", fontWeight: 800, color: C.text, marginBottom: "60px", lineHeight: 1.1 }}>
          From upload to insight{" "}
          <span style={{ color: C.accent }}>in seconds</span>
        </h2>
      </FadeUp>

      {/* Flow */}
      <div ref={ref} style={{ display: "flex", alignItems: "flex-start", justifyContent: "center", maxWidth: "1000px", margin: "0 auto" }}>
        {FLOW_NODES.map((node, i) => (
          <div key={node.id} style={{ display: "flex", alignItems: "center", flex: i < FLOW_NODES.length - 1 ? "1 1 0" : "0 0 auto" }}>
            {/* Node */}
            <motion.div
              initial={{ opacity: 0, y: 18 }}
              animate={inView ? { opacity: 1, y: 0 } : {}}
              transition={{ duration: 0.45, delay: i * 0.12, ease: [0.22, 1, 0.36, 1] }}
              style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "12px", minWidth: "clamp(72px, 9vw, 100px)" }}
            >
              <div style={{ position: "relative" }}>
                <motion.div
                  initial={{ scale: 0.7, opacity: 0 }}
                  animate={inView ? { scale: 1, opacity: 1 } : {}}
                  transition={{ duration: 0.4, delay: i * 0.12, ease: [0.34, 1.56, 0.64, 1] }}
                  whileHover={{ scale: 1.08 }}
                  style={{
                    width: "clamp(52px, 5.5vw, 68px)", height: "clamp(52px, 5.5vw, 68px)",
                    borderRadius: "18px",
                    background: `linear-gradient(135deg, ${node.color}18, ${node.color}30)`,
                    border: `1.5px solid ${node.color}50`,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    boxShadow: `0 6px 20px ${node.color}20`,
                  }}
                >
                  <Icon name={node.icon} size={20} color={node.color} />
                </motion.div>
                {/* Step badge */}
                <div style={{
                  position: "absolute", top: "-7px", right: "-7px",
                  width: "17px", height: "17px", borderRadius: "50%",
                  background: node.color, display: "flex", alignItems: "center",
                  justifyContent: "center", fontSize: "9px", fontWeight: 800,
                  color: "#fff", fontFamily: "DM Mono, monospace",
                }}>
                  {node.id}
                </div>
              </div>
              <div style={{ textAlign: "center", padding: "0 4px" }}>
                <p style={{ fontWeight: 700, fontSize: "clamp(10px, 1vw, 12px)", color: C.text, marginBottom: "2px", lineHeight: 1.3 }}>{node.label}</p>
                <p style={{ fontSize: "clamp(9px, 0.85vw, 10px)", color: C.muted, lineHeight: 1.4 }}>{node.sub}</p>
              </div>
            </motion.div>

            {/* Connector */}
            {i < FLOW_NODES.length - 1 && (
              <div style={{ flex: 1, height: "1.5px", background: C.bgMuted, position: "relative", marginBottom: "40px", minWidth: "16px" }}>
                <motion.div
                  initial={{ scaleX: 0 }}
                  animate={inView ? { scaleX: 1 } : {}}
                  transition={{ duration: 0.35, delay: i * 0.12 + 0.22, ease: [0.22, 1, 0.36, 1] }}
                  style={{
                    position: "absolute", inset: 0,
                    background: `linear-gradient(90deg, ${node.color}, ${FLOW_NODES[i + 1].color})`,
                    transformOrigin: "left",
                  }}
                />
                {/* Arrowhead */}
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={inView ? { opacity: 1 } : {}}
                  transition={{ duration: 0.2, delay: i * 0.12 + 0.52 }}
                  style={{
                    position: "absolute", right: "-1px", top: "50%", transform: "translateY(-50%)",
                    width: 0, height: 0,
                    borderTop: "3.5px solid transparent", borderBottom: "3.5px solid transparent",
                    borderLeft: `5px solid ${FLOW_NODES[i + 1].color}`,
                  }}
                />
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

// ─── Features bento ───────────────────────────────────────────────────────────
function FeatureCard({ feature, index }: { feature: typeof FEATURES[0]; index: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 40 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.65, delay: index * 0.08, ease: [0.22, 1, 0.36, 1] }}
      whileHover={{ y: -5, transition: { duration: 0.2 } }}
      style={{
        gridColumn: `span ${feature.span}`,
        background: feature.dark ? C.bgDark : C.bgCard,
        borderRadius: "26px",
        border: `1px solid ${feature.dark ? C.borderDark : C.border}`,
        padding: "clamp(28px, 3vw, 44px)", position: "relative",
        overflow: "hidden", cursor: "default",
        boxShadow: feature.dark ? "0 4px 24px rgba(0,0,0,0.18)" : "0 2px 12px rgba(0,0,0,0.04)",
      }}
    >
      <div style={{ position: "absolute", top: "-50px", right: "-50px", width: "200px", height: "200px", borderRadius: "50%", background: `radial-gradient(circle, ${feature.accent}1a, transparent 70%)`, pointerEvents: "none" }} />

      <span style={{ display: "inline-block", fontSize: "10px", fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: feature.accent, background: `${feature.accent}18`, padding: "4px 10px", borderRadius: "6px", marginBottom: "20px", fontFamily: "DM Mono, monospace" }}>
        {feature.tag}
      </span>

      <div style={{ width: "44px", height: "44px", borderRadius: "12px", background: `${feature.accent}18`, border: `1.5px solid ${feature.accent}30`, display: "flex", alignItems: "center", justifyContent: "center", marginBottom: "18px" }}>
        <Icon name={feature.icon} size={20} color={feature.accent} />
      </div>

      <h3 style={{ fontSize: "clamp(22px, 2.4vw, 30px)", fontWeight: 800, color: feature.dark ? C.textInverted : C.text, marginBottom: "12px", lineHeight: 1.15, whiteSpace: "pre-line", fontFamily: "DM Sans, sans-serif" }}>
        {feature.title}
      </h3>
      <p style={{ fontSize: "clamp(14px, 1.2vw, 16px)", color: feature.dark ? "rgba(245,242,236,0.58)" : C.muted, lineHeight: 1.75, maxWidth: "460px" }}>
        {feature.body}
      </p>
    </motion.div>
  );
}

function FeaturesSection() {
  return (
    <section id="features-section" style={{ padding: "100px 24px 80px", background: C.bg, fontFamily: "DM Sans, sans-serif" }}>
      <div style={{ maxWidth: "1200px", margin: "0 auto" }}>
        <FadeUp>
          <p style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.14em", color: C.accent, textTransform: "uppercase", marginBottom: "12px", fontFamily: "DM Mono, monospace" }}>
            Meet Overwatch
          </p>
          <h2 style={{ fontSize: "clamp(36px, 5vw, 64px)", fontWeight: 800, color: C.text, marginBottom: "14px", lineHeight: 1.05 }}>
            Intelligence runs
            <br />
            <span style={{ color: C.accent }}>on Overwatch</span>
          </h2>
          <p style={{ fontSize: "clamp(15px, 1.4vw, 18px)", color: C.muted, maxWidth: "460px", marginBottom: "52px", lineHeight: 1.7 }}>
            One platform. Every asset. Total visibility.
          </p>
        </FadeUp>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(12, 1fr)", gap: "16px" }}>
          {FEATURES.map((f, i) => <FeatureCard key={i} feature={f} index={i} />)}
        </div>
      </div>
    </section>
  );
}

// ─── Team ─────────────────────────────────────────────────────────────────────
function TeamSection() {
  return (
    <section id="team" style={{ padding: "100px 24px", background: C.bgMuted, fontFamily: "DM Sans, sans-serif" }}>
      <div style={{ maxWidth: "1200px", margin: "0 auto" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "72px", alignItems: "start" }}>
          <FadeUp>
            <p style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.14em", color: C.accent, textTransform: "uppercase", marginBottom: "12px", fontFamily: "DM Mono, monospace" }}>Our Team</p>
            <h2 style={{ fontSize: "clamp(30px, 3.5vw, 48px)", fontWeight: 800, color: C.text, marginBottom: "16px", lineHeight: 1.1 }}>
              Trusted by builders,<br />built by believers
            </h2>
            <p style={{ fontSize: "16px", color: C.muted, lineHeight: 1.75, maxWidth: "380px", marginBottom: "44px" }}>
              A focused team solving content provenance and threat intelligence at enterprise scale.
            </p>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
              {STATS.map((s, i) => (
                <FadeUp key={i} delay={0.08 + i * 0.07}>
                  <div style={{ background: C.bgCard, borderRadius: "14px", padding: "18px 20px", border: `1px solid ${C.border}` }}>
                    <p style={{ fontSize: "26px", fontWeight: 800, color: C.text, lineHeight: 1, marginBottom: "4px" }}>{s.value}</p>
                    <p style={{ fontSize: "10px", color: C.muted, fontFamily: "DM Mono, monospace", letterSpacing: "0.07em" }}>{s.label}</p>
                  </div>
                </FadeUp>
              ))}
            </div>
          </FadeUp>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px" }}>
            {TEAM.map((member, i) => (
              <FadeUp key={i} delay={0.14 + i * 0.08}>
                <motion.div
                  whileHover={{ y: -5, boxShadow: "0 16px 40px rgba(0,0,0,0.09)", transition: { duration: 0.2 } }}
                  style={{ background: C.bgCard, borderRadius: "18px", border: `1px solid ${C.border}`, padding: "26px 22px", boxShadow: "0 2px 8px rgba(0,0,0,0.04)" }}
                >
                  <div style={{ width: "48px", height: "48px", borderRadius: "50%", background: `linear-gradient(135deg, ${member.color}, ${member.color}88)`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "13px", fontWeight: 800, color: "#fff", marginBottom: "14px", letterSpacing: "0.04em" }}>
                    {member.init}
                  </div>
                  <p style={{ fontSize: "15px", fontWeight: 700, color: C.text, marginBottom: "3px" }}>{member.name}</p>
                  <p style={{ fontSize: "12px", color: C.muted }}>{member.role}</p>
                  <p style={{ fontSize: "11px", color: `${C.muted}77`, marginTop: "10px", lineHeight: 1.6 }}>Bio coming soon.</p>
                </motion.div>
              </FadeUp>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── CTA ──────────────────────────────────────────────────────────────────────
function CtaSection({ onSignupClick }: { onSignupClick: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-80px" });

  return (
    <section ref={ref} style={{
      padding: "120px 24px", background: C.bgDark,
      textAlign: "center", position: "relative", overflow: "hidden",
      fontFamily: "DM Sans, sans-serif",
    }}>
      {/* Smooth transition from bgMuted above */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: "100px", background: `linear-gradient(to bottom, ${C.bgMuted}, transparent)`, pointerEvents: "none" }} />

      {/* Glow */}
      <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)", width: "600px", height: "300px", background: `radial-gradient(ellipse, ${C.accent}16, transparent 70%)`, pointerEvents: "none" }} />

      <motion.div
        initial={{ opacity: 0, y: 40 }} animate={inView ? { opacity: 1, y: 0 } : {}}
        transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        style={{ position: "relative" }}
      >
        <p style={{ fontSize: "11px", fontWeight: 700, letterSpacing: "0.14em", color: C.accent, textTransform: "uppercase", marginBottom: "18px", fontFamily: "DM Mono, monospace" }}>
          Get started today
        </p>
        <h2 style={{ fontSize: "clamp(36px, 5.5vw, 70px)", fontWeight: 800, color: C.textInverted, marginBottom: "18px", lineHeight: 1.05 }}>
          The future of asset
          <br />intelligence is here
        </h2>
        <p style={{ fontSize: "18px", color: "rgba(245,242,236,0.48)", maxWidth: "400px", margin: "0 auto 44px", lineHeight: 1.65 }}>
          Join teams already using Overwatch to protect their pipelines.
        </p>
        <motion.button type="button" onClick={onSignupClick}
          whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.97 }}
          style={{
            display: "inline-flex", alignItems: "center", gap: "10px",
            padding: "16px 36px", borderRadius: "12px", border: "none",
            cursor: "pointer", fontSize: "16px", fontWeight: 700,
            background: `linear-gradient(135deg, ${C.accent}, ${C.violet})`,
            color: "#fff", boxShadow: `0 8px 32px ${C.accent}44`,
            fontFamily: "DM Sans, sans-serif",
          }}
        >
          Get started — it's free
          <Icon name="arrow-r" size={16} color="#fff" />
        </motion.button>
      </motion.div>
    </section>
  );
}

// ─── Footer ───────────────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer style={{
      background: C.bgDark,
      borderTop: `1px solid ${C.borderDark}`,
      padding: "64px clamp(20px, 5vw, 72px) 40px",
      fontFamily: "DM Sans, sans-serif",
    }}>
      <div style={{ maxWidth: "1200px", margin: "0 auto" }}>
        <div style={{ display: "grid", gridTemplateColumns: "190px repeat(3, 1fr)", gap: "32px", marginBottom: "56px" }}>
          {/* Brand */}
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "14px" }}>
              <div style={{ width: "26px", height: "26px", borderRadius: "7px", background: `linear-gradient(135deg, ${C.accent}, ${C.violet})`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Icon name="shield" size={13} color="#fff" />
              </div>
              <span style={{ fontWeight: 800, fontSize: "14px", color: C.textInverted }}>Overwatch</span>
            </div>
            <p style={{ fontSize: "13px", color: "rgba(245,242,236,0.36)", lineHeight: 1.7 }}>
              Asset intelligence without blind spots.
            </p>
          </div>

          {/* Link columns */}
          {FOOTER_COLS.map((col) => (
            <div key={col.heading}>
              <p style={{ fontSize: "11px", fontWeight: 700, color: "rgba(245,242,236,0.5)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "14px", fontFamily: "DM Mono, monospace" }}>
                {col.heading}
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: "9px" }}>
                {col.links.map((link) => (
                  <a
                    key={link.name}
                    href={link.href}
                    target={link.href.startsWith("http") ? "_blank" : "_self"}
                    rel={link.href.startsWith("http") ? "noopener noreferrer" : undefined}
                    style={{ fontSize: "13px", color: "rgba(245,242,236,0.46)", textDecoration: "none", transition: "color 0.15s" }}
                    onMouseEnter={e => (e.target as HTMLAnchorElement).style.color = C.textInverted}
                    onMouseLeave={e => (e.target as HTMLAnchorElement).style.color = "rgba(245,242,236,0.46)"}
                  >
                    {link.name}
                  </a>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* Bottom */}
        <div style={{ borderTop: `1px solid ${C.borderDark}`, paddingTop: "28px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
          <p style={{ fontSize: "12px", color: "rgba(245,242,236,0.28)", fontFamily: "DM Mono, monospace" }}>
            © {new Date().getFullYear()} Overwatch. All rights reserved.
          </p>
          <div style={{ display: "flex", gap: "24px" }}>
            {["Privacy", "Terms", "Security Policy"].map((l) => (
              <a key={l} href="#" onClick={(e) => e.preventDefault()}
                style={{ fontSize: "12px", color: "rgba(245,242,236,0.28)", textDecoration: "none", transition: "color 0.15s", fontFamily: "DM Mono, monospace" }}
                onMouseEnter={e => (e.target as HTMLAnchorElement).style.color = "rgba(245,242,236,0.65)"}
                onMouseLeave={e => (e.target as HTMLAnchorElement).style.color = "rgba(245,242,236,0.28)"}
              >
                {l}
              </a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}

// ─── Root ─────────────────────────────────────────────────────────────────────
export default function LandingScreen({ onLoginClick, onSignupClick }: { onLoginClick: () => void; onSignupClick: () => void }) {
  useFonts();
  return (
    <div style={{ background: C.bg, fontFamily: "DM Sans, sans-serif", overflowX: "hidden" }}>
      <Navbar onLoginClick={onLoginClick} onSignupClick={onSignupClick} />
      <HeroSection onSignupClick={onSignupClick} />
      <Marquee />
      <FlowchartSection />
      <FeaturesSection />
      <TeamSection />
      <CtaSection onSignupClick={onSignupClick} />
      <Footer />
      <SystemStatusOverlay />
    </div>
  );
}
