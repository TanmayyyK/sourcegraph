import React, {
  useCallback, useEffect, useRef, useState, ReactNode,
} from "react";
import { motion, AnimatePresence } from "framer-motion";
import { auth } from "../../lib/api";
import {
  Upload, RefreshCw, Zap, Scissors, Eye, Cpu,
  Type as TypeIcon, CheckCircle, AlertTriangle, Clock, ChevronLeft,
  Mic,
} from "lucide-react";

/* ════════════════════════════════════════════════════════════════════════════
   API TYPES  (matching schemas.py exactly)
   ════════════════════════════════════════════════════════════════════════ */
interface UploadResponse {
  asset_id: string;
  filename:  string;
  is_golden: boolean;
  status:    string;
  message:   string;
  trace_id:  string;
}

interface AssetStatusResponse {
  asset_id:    string;
  filename:    string;
  is_golden:   boolean;
  status:      "processing" | "completed" | "failed";
  frame_count: number;
  created_at:  string;
  trace_id:    string;
}

/* ════════════════════════════════════════════════════════════════════════════
   TYPES
   ════════════════════════════════════════════════════════════════════════ */
// TASK 1 — §2: Added "ANALYZING_AUDIO" to the PipelineState union.
type PipelineState =
  | "IDLE" | "UPLOADING" | "EXTRACTING"
  | "BIFURCATING" | "ANALYZING" | "ANALYZING_AUDIO" | "COMPLETE" | "FAILED";
type Verdict = "CLEAN" | "THREAT" | "FAILED" | null;

export interface OverwatchIngestPortalProps {
  onComplete?: (verdict: Verdict, fileName: string, assetId?: string) => void;
  onBack?:     () => void;
  /** Bearer token for authenticated API calls (from your auth system) */
  authToken?:  string;
}

/* ════════════════════════════════════════════════════════════════════════════
   DESIGN TOKENS
   ════════════════════════════════════════════════════════════════════════ */
const C = {
  bg:         "#F5F3EF",
  ink:        "#18181B",
  muted:      "#9B9897",
  card:       "rgba(255,255,255,0.97)",
  cardBorder: "rgba(0,0,0,0.07)",
  blue:       "#4F6AFF",
  violet:     "#7C5CF7",
  coral:      "#F26B5B",
  green:      "#22C55E",
  amber:      "#F59E0B",
} as const;

const TS = 1.2;
const T  = (s: number) => s * TS;

/* ════════════════════════════════════════════════════════════════════════════
   VIRTUAL CANVAS  (everything uses these pixel coordinates; scaled to fit)
   ════════════════════════════════════════════════════════════════════════ */
const VW = 1380;
const VH = 520;

/* Card dimensions */
const CW = 200;   // card width
const CH = 100;   // card height

/* Orchestrator circle size */
const OS = 190;   // diameter   (radius = 95)

/* Node centres */
const N = {
  yogesh: { cx: 200,  cy: 260 },
  yug:    { cx: 660,  cy: 155 },
  rohit:  { cx: 660,  cy: 365 },
  orch:   { cx: 1155, cy: 260 },
} as const;

const E = {
  yogesh_r: { x: N.yogesh.cx + CW / 2, y: N.yogesh.cy },
  yug_l:    { x: N.yug.cx    - CW / 2, y: N.yug.cy    },
  yug_r:    { x: N.yug.cx    + CW / 2, y: N.yug.cy    },
  rohit_l:  { x: N.rohit.cx  - CW / 2, y: N.rohit.cy  },
  rohit_r:  { x: N.rohit.cx  + CW / 2, y: N.rohit.cy  },
  orch_l:   { x: N.orch.cx   - OS / 2, y: N.orch.cy   },
} as const;

const mx1 = (E.yogesh_r.x + E.yug_l.x)  / 2;
const mx2 = (E.yug_r.x    + E.orch_l.x) / 2;

const PATHS = {
  yogesh_yug:
    `M ${E.yogesh_r.x} ${E.yogesh_r.y} C ${mx1} ${E.yogesh_r.y}, ${mx1} ${E.yug_l.y},   ${E.yug_l.x}   ${E.yug_l.y}`,
  yogesh_rohit:
    `M ${E.yogesh_r.x} ${E.yogesh_r.y} C ${mx1} ${E.yogesh_r.y}, ${mx1} ${E.rohit_l.y}, ${E.rohit_l.x} ${E.rohit_l.y}`,
  yug_orch:
    `M ${E.yug_r.x}   ${E.yug_r.y}   C ${mx2} ${E.yug_r.y},   ${mx2} ${E.orch_l.y},  ${E.orch_l.x}  ${E.orch_l.y}`,
  rohit_orch:
    `M ${E.rohit_r.x} ${E.rohit_r.y} C ${mx2} ${E.rohit_r.y}, ${mx2} ${E.orch_l.y},  ${E.orch_l.x}  ${E.orch_l.y}`,
  upload:
    `M ${N.yogesh.cx - CW / 2 - 155} ${N.yogesh.cy} L ${N.yogesh.cx - CW / 2} ${N.yogesh.cy}`,
} as const;

/* ════════════════════════════════════════════════════════════════════════════
   HOOKS
   ════════════════════════════════════════════════════════════════════════ */
function useFonts() {
  useEffect(() => {
    if (document.getElementById("ow-fonts")) return;
    const l = document.createElement("link");
    l.id = "ow-fonts"; l.rel = "stylesheet";
    l.href = "https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap";
    document.head.appendChild(l);
  }, []);
}

function useScaledCanvas(vw: number, vh: number) {
  const ref   = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const update = () => {
      const { width, height } = el.getBoundingClientRect();
      setScale(Math.min(width / vw, height / vh) * 0.95);
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, [vw, vh]);
  return { ref, scale };
}

function useElapsed(running: boolean, startRef: React.MutableRefObject<number>) {
  const [txt, setTxt] = useState("00:00.00");
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => {
      const s  = Math.max(0, (performance.now() - startRef.current) / 1000);
      const m  = Math.floor(s / 60);
      const ss = Math.floor(s % 60);
      const cs = Math.floor((s - Math.floor(s)) * 100);
      setTxt(`${String(m).padStart(2,"0")}:${String(ss).padStart(2,"0")}.${String(cs).padStart(2,"0")}`);
    }, 80);
    return () => clearInterval(id);
  }, [running, startRef]);
  return txt;
}

/* ════════════════════════════════════════════════════════════════════════════
   PIPELINE STEPPER
   ════════════════════════════════════════════════════════════════════════ */
// TASK 1 — §3: Added "Audio" step between "Analyze" and "Synthesize".
const STEPS: { key: PipelineState; label: string }[] = [
  { key: "UPLOADING",       label: "Upload"    },
  { key: "EXTRACTING",      label: "Extract"   },
  { key: "BIFURCATING",     label: "Bifurcate" },
  { key: "ANALYZING",       label: "Analyze"   },
  { key: "ANALYZING_AUDIO", label: "Audio"     },
  { key: "COMPLETE",        label: "Synthesize"},
];

// TASK 1 — §3: ORDER now includes ANALYZING_AUDIO between ANALYZING and COMPLETE.
const ORDER: PipelineState[] = [
  "IDLE",
  "UPLOADING",
  "EXTRACTING",
  "BIFURCATING",
  "ANALYZING",
  "ANALYZING_AUDIO",
  "COMPLETE",
  "FAILED",
];

const PipelineStepper: React.FC<{ state: PipelineState; failedAt?: PipelineState | null }> = ({ state, failedAt }) => {
  const effectiveState = state === "FAILED" ? (failedAt ?? "UPLOADING") : state;
  const idx = ORDER.indexOf(effectiveState) - 1;
  return (
    <div className="flex items-center gap-0">
      {STEPS.map((s, i) => {
        const done    = i < idx;
        const active  = i === idx;
        const pending = i > idx;
        return (
          <React.Fragment key={s.key}>
            <div className="flex items-center gap-1.5">
              <motion.div
                className="w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0"
                style={{
                  background: done ? C.green : active ? (state === "FAILED" ? C.coral : C.blue) : "rgba(0,0,0,0.07)",
                }}
                animate={active ? { scale:[1,1.15,1] } : {}}
                transition={{ duration:T(1.1), repeat:Infinity }}
              >
                {done && <CheckCircle size={9} style={{ color:"#fff" }} strokeWidth={3} />}
                {active && state === "FAILED" && <AlertTriangle size={10} style={{ color:"#fff" }} strokeWidth={2.6} />}
                {active && state !== "FAILED" && (
                  <motion.div
                    style={{ width:5, height:5, borderRadius:"50%", background:"#fff" }}
                    animate={{ scale:[1,0.5,1] }} transition={{ duration:T(0.7), repeat:Infinity }}
                  />
                )}
              </motion.div>
              <span style={{
                fontSize:10, fontFamily:"DM Mono, monospace",
                letterSpacing:"0.1em", textTransform:"uppercase",
                color: done ? C.green : active ? C.blue : C.muted,
                fontWeight: active ? 600 : 400,
                opacity: pending ? 0.4 : 1,
              }}>{s.label}</span>
            </div>
            {i < STEPS.length - 1 && (
              <div style={{
                width:24, height:1, margin:"0 5px",
                background: done ? `${C.green}80` : "rgba(0,0,0,0.1)",
                transition:"background 0.4s",
              }} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};

/* ════════════════════════════════════════════════════════════════════════════
   FLOW EDGE  —  animated SVG path
   ════════════════════════════════════════════════════════════════════════ */
interface FlowEdgeProps {
  d: string; color: string; visible: boolean; delay?: number;
}
const FlowEdge: React.FC<FlowEdgeProps> = ({ d, color, visible, delay = 0 }) => (
  <>
    <path d={d} fill="none" stroke={`${color}18`} strokeWidth={2} />
    <AnimatePresence>
      {visible && (
        <motion.path
          key={`fe-${d.slice(0,14)}-${delay}`}
          d={d} fill="none" stroke={color} strokeWidth={2.5} strokeLinecap="round"
          initial={{ pathLength:0, opacity:0 }}
          animate={{ pathLength:1, opacity:0.72 }}
          exit={{ opacity:0 }}
          transition={{ duration:T(0.9), delay, ease:[0.4,0,0.2,1] }}
        />
      )}
    </AnimatePresence>
  </>
);

/* ════════════════════════════════════════════════════════════════════════════
   FLOW DOT  —  particle that travels along an SVG path via animateMotion
   ════════════════════════════════════════════════════════════════════════ */
interface FlowDotProps {
  d: string; color: string;
  dur?: number; delay?: number; repeatCount?: string;
}
const FlowDot: React.FC<FlowDotProps> = ({ d, color, dur=1.0, delay=0, repeatCount="indefinite" }) => (
  <motion.g initial={{ opacity:0 }} animate={{ opacity:[0,1,1,0] }}
    transition={{ duration:T(dur), delay, ease:"easeInOut", repeat:Infinity }}>
    <circle r={4} fill={color} filter={`drop-shadow(0 0 5px ${color})`}>
      <animateMotion dur={`${T(dur)}s`} repeatCount={repeatCount} begin={`${delay}s`} path={d} />
    </circle>
  </motion.g>
);

/* ════════════════════════════════════════════════════════════════════════════
   NODE CARD  —  absolutely positioned in the virtual canvas
   ════════════════════════════════════════════════════════════════════════ */
interface NodeCardProps {
  cx: number; cy: number;
  title: string; role: string; subtitle: string;
  icon: ReactNode; accent: string;
  pulsing: boolean; delay?: number;
}
const NodeCard: React.FC<NodeCardProps> = ({
  cx, cy, title, role, subtitle, icon, accent, pulsing, delay=0,
}) => (
  <motion.div
    className="absolute"
    style={{ left: cx - CW/2, top: cy - CH/2, width: CW, height: CH }}
    initial={{ opacity:0, scale:0.78, y:8 }}
    animate={{ opacity:1, scale:1, y:0 }}
    exit={{ opacity:0, scale:0.8 }}
    transition={{ duration:T(0.38), delay, ease:[0.4,0,0.2,1] }}
  >
    <AnimatePresence>
      {pulsing && (
        <motion.div
          className="absolute rounded-[22px] pointer-events-none"
          style={{ inset:-8, border:`1.5px solid ${accent}50`,
            boxShadow:`0 0 20px 0 ${accent}30` }}
          initial={{ opacity:0 }} animate={{ opacity:[0.25,1,0.25] }} exit={{ opacity:0 }}
          transition={{ duration:T(1.2), repeat:Infinity }}
        />
      )}
    </AnimatePresence>

    <div style={{
      width:"100%", height:"100%",
      background: C.card,
      borderRadius: 16,
      border: `1px solid ${pulsing ? accent + "45" : C.cardBorder}`,
      boxShadow: pulsing
        ? `0 0 0 1px ${accent}20, 0 8px 32px rgba(0,0,0,0.1)`
        : "0 4px 22px rgba(0,0,0,0.07)",
      display:"flex", alignItems:"center",
      gap:10, paddingLeft:20, paddingRight:14,
      position:"relative", overflow:"hidden",
      transition:"border-color 0.3s, box-shadow 0.3s",
    }}>
      <motion.div style={{
        position:"absolute", left:0, top:16, bottom:16,
        width:3, borderRadius:3, background:accent,
      }}
        animate={pulsing ? { opacity:[1,0.35,1] } : { opacity:1 }}
        transition={{ duration:T(0.95), repeat: pulsing ? Infinity : 0 }}
      />
      <div style={{
        width:36, height:36, borderRadius:10, flexShrink:0,
        background:`${accent}13`, color:accent,
        display:"flex", alignItems:"center", justifyContent:"center",
        marginLeft:4,
      }}>
        {icon}
      </div>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{
          fontSize:8.5, fontWeight:700, letterSpacing:"0.15em",
          textTransform:"uppercase", color:accent,
          fontFamily:"DM Mono, monospace", marginBottom:2,
        }}>{role}</div>
        <div style={{
          fontSize:15, fontWeight:700, color:C.ink,
          fontFamily:"DM Sans, sans-serif", lineHeight:1.2,
          whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis",
        }}>{title}</div>
        <div style={{
          fontSize:9.5, color:C.muted, marginTop:3,
          fontFamily:"DM Mono, monospace", lineHeight:1.3,
          whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis",
        }}>{subtitle}</div>
      </div>
    </div>
  </motion.div>
);

/* ════════════════════════════════════════════════════════════════════════════
   ORCHESTRATOR  —  circular card with SVG progress ring
   ════════════════════════════════════════════════════════════════════════ */
interface OrchProps {
  cx: number; cy: number;
  progress: number; verdict: Verdict; pulsing: boolean;
  onSeeInsights?: () => void;
}
const OrchestratorCard: React.FC<OrchProps> = ({ cx, cy, progress, verdict, pulsing, onSeeInsights }) => {
  const R        = OS / 2 || 0;
  const trackR   = Math.max(0, (R - 10) || 0);
  const circ     = 2 * Math.PI * trackR;
  const verdColor = verdict==="CLEAN" ? C.green : verdict==="THREAT" ? C.coral : C.blue;

  return (
    <motion.div
      className="absolute flex flex-col items-center"
      style={{ left: cx - R, top: cy - R }}
      initial={{ opacity:0, scale:0.72 }}
      animate={{ opacity:1, scale:1 }}
      exit={{ opacity:0, scale:0.8 }}
      transition={{ duration:T(0.48), ease:[0.4,0,0.2,1] }}
    >
      <div style={{ position:"relative", width:OS, height:OS }}>
        <svg width={OS} height={OS} viewBox={`0 0 ${OS} ${OS}`}
          style={{ position:"absolute", inset:0 }}>
          {pulsing && (
            <motion.circle cx={R} cy={R} r={(R + 10) || 0}
              fill="none" stroke={verdColor} strokeWidth={0.8}
              animate={{ r:[(R+10)||0,(R+18)||0,(R+10)||0], opacity:[0.2,0.6,0.2] }}
              transition={{ duration:T(1.4), repeat:Infinity }}
            />
          )}
          <circle cx={R} cy={R} r={R || 0}
            fill={C.card} stroke={C.cardBorder} strokeWidth={1} />
          <circle cx={R} cy={R} r={trackR || 0}
            fill="none" stroke="rgba(0,0,0,0.06)" strokeWidth={7} />
          {progress > 0 && (
            <motion.circle
              cx={R} cy={R} r={trackR || 0} fill="none"
              stroke={verdColor} strokeWidth={7} strokeLinecap="round"
              strokeDasharray={circ}
              style={{ rotate:-90, transformOrigin:`${R}px ${R}px` }}
              animate={{ strokeDashoffset: circ * (1 - progress) }}
              transition={{ duration:T(0.5), ease:"easeOut" }}
            />
          )}
        </svg>

        <div style={{
          position:"absolute", inset:0,
          display:"flex", flexDirection:"column",
          alignItems:"center", justifyContent:"center", gap:4,
        }}>
          <motion.div
            style={{ color: progress > 0 ? verdColor : C.muted }}
            animate={pulsing ? { scale:[1,1.1,1] } : {}}
            transition={{ duration:T(1.0), repeat:Infinity }}
          >
            {verdict==="CLEAN"   ? <CheckCircle   size={28} strokeWidth={2}   />
            : verdict==="THREAT" ? <AlertTriangle size={28} strokeWidth={2}   />
            :                      <Cpu           size={28} strokeWidth={1.8} />}
          </motion.div>

          {verdict && (
            <motion.div
              initial={{ opacity:0, y:3 }} animate={{ opacity:1, y:0 }}
              style={{ fontSize:8, fontWeight:700, letterSpacing:"0.13em",
                textTransform:"uppercase", color:verdColor, fontFamily:"DM Mono, monospace" }}
            >
              {verdict === "CLEAN" ? "Analysis Complete" : verdict}
            </motion.div>
          )}
          {!verdict && progress > 0 && progress < 1 && (
            <div style={{ fontSize:10, color:C.muted, fontFamily:"DM Mono, monospace" }}>
              {Math.round(progress * 100)}%
            </div>
          )}
          {verdict && onSeeInsights && (
            <motion.button
              initial={{ opacity:0, y:5 }} animate={{ opacity:1, y:0 }}
              onClick={onSeeInsights}
              style={{
                marginTop: 8, padding: "4px 10px", borderRadius: 6,
                background: verdColor, color: "white", fontSize: 9,
                fontWeight: 700, fontFamily: "DM Mono, monospace",
                border: "none", cursor: "pointer"
              }}
            >
              SEE INSIGHTS
            </motion.button>
          )}
        </div>
      </div>

      <div style={{ marginTop:9, fontSize:8.5, fontFamily:"DM Mono, monospace",
        letterSpacing:"0.18em", textTransform:"uppercase", color:C.muted }}>
        Orchestrator
      </div>
    </motion.div>
  );
};

/* ════════════════════════════════════════════════════════════════════════════
   CLOSED MODULE  —  shown during UPLOADING / EXTRACTING at Yogesh position
   ════════════════════════════════════════════════════════════════════════ */
const ClosedModule: React.FC<{ cx:number; cy:number; state:PipelineState }> = ({ cx,cy,state }) => (
  <motion.div
    className="absolute"
    style={{ left:cx-CW/2, top:cy-CH/2, width:CW, height:CH }}
    initial={{ opacity:0, scale:0.86 }}
    animate={{ opacity:1, scale:1 }}
    exit={{ opacity:0, scale:0.86 }}
    transition={{ duration:T(0.32) }}
  >
    <div style={{
      width:"100%", height:"100%",
      background:C.card, borderRadius:16, border:`1px solid ${C.cardBorder}`,
      boxShadow:"0 4px 22px rgba(0,0,0,0.08)",
      display:"flex", flexDirection:"column",
      alignItems:"center", justifyContent:"center", gap:8,
    }}>
      <motion.div style={{ color:C.coral }}
        animate={{ rotate:[0,12,-12,0] }} transition={{ duration:T(1.0), repeat:Infinity }}>
        <Scissors size={22} strokeWidth={2} />
      </motion.div>
      <div style={{ fontSize:9.5, fontFamily:"DM Mono, monospace",
        color:C.muted, letterSpacing:"0.14em", textTransform:"uppercase" }}>
        {state==="UPLOADING" ? "Buffering…" : "Extracting…"}
      </div>
      <div style={{ width:72, height:2, borderRadius:2, background:"rgba(0,0,0,0.07)", overflow:"hidden" }}>
        <motion.div style={{ height:2, borderRadius:2, background:C.coral }}
          animate={{ x:["-100%","100%"] }}
          transition={{ duration:T(1.1), repeat:Infinity, ease:"easeInOut" }}
        />
      </div>
    </div>
  </motion.div>
);

/* ════════════════════════════════════════════════════════════════════════════
   FILE CHIP  —  travels from left edge into Yogesh
   ════════════════════════════════════════════════════════════════════════ */
interface FileChipProps {
  visible:boolean; label:string;
  fromX:number; fromY:number; toX:number; toY:number;
  moving:boolean; onArrive?:()=>void;
}
const FileChip: React.FC<FileChipProps> = ({
  visible, label, fromX, fromY, toX, toY, moving, onArrive,
}) => {
  const arrived = useRef(false);
  useEffect(()=>{ if(!visible) arrived.current=false; },[visible]);
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className="absolute z-20" style={{ transform:"translate(-50%,-50%)" }}
          initial={{ left:fromX, top:fromY, opacity:0, scale:0.5 }}
          animate={{ left:moving?toX:fromX, top:moving?toY:fromY, opacity:1, scale:1 }}
          onAnimationComplete={() => {
            if (moving && !arrived.current) {
              arrived.current = true;
              onArrive?.();
            }
          }}
          exit={{ opacity:0, scale:0.6 }}
          transition={{
            opacity:{ duration:T(0.2) },
            scale:{ type:"spring", stiffness:280, damping:22 },
            left:{ duration:T(1.1), ease:[0.4,0,0.2,1] },
            top:{ duration:T(1.1), ease:[0.4,0,0.2,1] },
          }}
        >
          <div style={{
            display:"flex", alignItems:"center", gap:7, padding:"7px 13px",
            borderRadius:10, background:C.card,
            border:`1px solid ${C.blue}30`,
            boxShadow:`0 4px 18px ${C.blue}20`,
            fontFamily:"DM Mono, monospace", fontSize:11, color:C.ink, whiteSpace:"nowrap",
          }}>
            <motion.div style={{ color:C.blue }}
              animate={{ y:[-1,1,-1] }} transition={{ duration:T(0.8), repeat:Infinity }}>
              <Upload size={12} strokeWidth={2.2} />
            </motion.div>
            <span style={{ maxWidth:115, overflow:"hidden", textOverflow:"ellipsis" }}>{label}</span>
            <motion.div style={{ width:5, height:5, borderRadius:"50%", background:C.blue }}
              animate={{ opacity:[1,0.2,1] }} transition={{ duration:T(0.7), repeat:Infinity }} />
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

/* ════════════════════════════════════════════════════════════════════════════
   IDLE DROPZONE
   ════════════════════════════════════════════════════════════════════════ */
interface IdleDropzoneProps { onPick:(f:File)=>void }
const IdleDropzone: React.FC<IdleDropzoneProps> = ({ onPick }) => {
  const inputRef   = useRef<HTMLInputElement|null>(null);
  const [hover, setHover]       = useState(false);
  const [dragDepth, setDDep]    = useState(0);
  const active = hover || dragDepth>0;
  const handle = (files:FileList|null)=>{ if(files?.[0]) onPick(files[0]); };
  return (
    <motion.div className="absolute inset-0 flex items-center justify-center"
      initial={{ opacity:0 }} animate={{ opacity:1 }}
      exit={{ opacity:0 }} transition={{ duration:T(0.2) }}
      onDragEnter={e=>{ e.preventDefault(); setDDep(d=>d+1); }}
      onDragLeave={e=>{ e.preventDefault(); setDDep(d=>Math.max(0,d-1)); }}
      onDragOver={e=>e.preventDefault()}
      onDrop={e=>{ e.preventDefault(); setDDep(0); handle(e.dataTransfer.files); }}
    >
      <motion.button
        type="button"
        onClick={()=>inputRef.current?.click()}
        onMouseEnter={()=>setHover(true)} onMouseLeave={()=>setHover(false)}
        className="relative flex flex-col items-center justify-center focus:outline-none"
        style={{
          width:520, height:256, borderRadius:20,
          background: active
            ? `linear-gradient(145deg,${C.blue}10 0%,rgba(124,92,247,0.07) 100%)`
            : "rgba(255,255,255,0.9)",
          border:`1.5px dashed ${active ? C.blue : "rgba(0,0,0,0.13)"}`,
          backdropFilter:"blur(14px)",
          boxShadow: active
            ? `0 0 0 10px ${C.blue}09, 0 24px 60px ${C.blue}1c`
            : "0 8px 40px rgba(0,0,0,0.07)",
          cursor:"pointer", gap:18,
          transition:"background 200ms, border-color 200ms, box-shadow 260ms",
        }}
        initial={{ y:18, opacity:0, scale:0.97 }}
        animate={{ y:0, opacity:1, scale:1 }}
        exit={{ y:-10, opacity:0 }}
        transition={{ duration:T(0.42), ease:[0.4,0,0.2,1] }}
      >
        {[1.055,1.11].map((s,i)=>(
          <motion.span key={i} className="absolute inset-0 pointer-events-none"
            style={{ borderRadius:20, border:`1px solid ${C.blue}14` }}
            animate={{ scale:[1,s], opacity:[0.45,0] }}
            transition={{ duration:T(2.7), repeat:Infinity, ease:"easeOut", delay:i*0.78 }}
          />
        ))}
        <motion.div className="flex items-center justify-center rounded-[14px]"
          style={{ width:56, height:56, background:`${C.blue}0e`, color:C.blue }}
          animate={active?{ y:[-1.5,1.5,-1.5] }:{ y:0 }}
          transition={{ duration:T(0.9), repeat:active?Infinity:0 }}>
          <Upload size={24} strokeWidth={1.9} />
        </motion.div>
        <div className="text-center" style={{ pointerEvents:"none" }}>
          <div style={{ fontSize:18, fontWeight:700, color:C.ink, fontFamily:"DM Sans, sans-serif" }}>
            {dragDepth>0 ? "Release to ingest" : "Drop your file here"}
          </div>
          <div style={{ fontSize:13, color:C.muted, marginTop:5, fontFamily:"DM Mono, monospace" }}>
            or click to browse
          </div>
        </div>
        <div style={{ display:"flex", gap:8 }}>
          {["MP4","MOV","WEBM"].map(f=>(
            <span key={f} style={{ padding:"3px 10px", borderRadius:6, fontSize:10,
              fontFamily:"DM Mono, monospace", letterSpacing:"0.12em", textTransform:"uppercase",
              background:"rgba(0,0,0,0.055)", color:C.muted, border:"1px solid rgba(0,0,0,0.09)" }}>
              {f}
            </span>
          ))}
          <span style={{ padding:"3px 10px", borderRadius:6, fontSize:10,
            fontFamily:"DM Mono, monospace", letterSpacing:"0.12em",
            background:`${C.blue}0e`, color:C.blue, border:`1px solid ${C.blue}26` }}>
            max 5 GB
          </span>
        </div>
      </motion.button>
      <input ref={inputRef} type="file" className="hidden"
        accept="video/mp4,video/quicktime,video/webm"
        onChange={e=>handle(e.target.files)} />
    </motion.div>
  );
};

/* ════════════════════════════════════════════════════════════════════════════
   PIPELINE CANVAS
   ════════════════════════════════════════════════════════════════════════ */
interface PipelineCanvasProps {
  state:PipelineState; fileName:string;
  orchProgress:number; verdict:Verdict;
  chipMoving:boolean; chipVisible:boolean; onChipArrive:()=>void;
  onComplete?: () => void;
}
const PipelineCanvas: React.FC<PipelineCanvasProps> = ({
  state, fileName, orchProgress, verdict,
  chipMoving, chipVisible, onChipArrive, onComplete,
}) => {
  const { ref, scale } = useScaledCanvas(VW, VH);

  // Keep the whole circuit mounted for any active pipeline state.
  const activePipeline = state !== "IDLE";
  const showNodes   = activePipeline;
  const showEdgesI  = activePipeline;
  const showOrch    = activePipeline;
  const showUpEdge  = [
    "UPLOADING","EXTRACTING","BIFURCATING","ANALYZING","ANALYZING_AUDIO","COMPLETE",
  ].includes(state);
  const showClosed  = ["UPLOADING","EXTRACTING"].includes(state);

  // TASK 1 — §4: pulseYug is FALSE during ANALYZING_AUDIO (only Rohit pulses then).
  const pulseYug    = state === "ANALYZING";
  // TASK 1 — §4: pulseRohit is TRUE during both ANALYZING and ANALYZING_AUDIO.
  const pulseRohit  = state === "ANALYZING" || state === "ANALYZING_AUDIO";
  const pulseOrch   = state === "COMPLETE" || state === "FAILED";

  // Standard bifurcation dots (both yug + rohit paths) only during ANALYZING.
  const showDots      = state === "ANALYZING";
  // TASK 1 — §5: During ANALYZING_AUDIO only the rohit→orch path carries audio data.
  const showAudioDots = state === "ANALYZING_AUDIO";

  const failed  = state === "FAILED";
  const waiting = ["UPLOADING","EXTRACTING"].includes(state);

  // TASK 1 — §4: Rohit's NodeCard gets amber accent + ghost-node subtitle during ANALYZING_AUDIO.
  const rohitAccent   = state === "ANALYZING_AUDIO" ? C.amber : C.blue;
  const rohitSubtitle = state === "ANALYZING_AUDIO"
    ? "Whisper 16kHz · Transcribing"
    : "512D CLIP ViT-L/14";

  const chipFrom = { x: N.yogesh.cx - CW/2 - 145, y: N.yogesh.cy };
  const chipTo   = { x: N.yogesh.cx - CW/2,         y: N.yogesh.cy };

  return (
    <div ref={ref} className="absolute inset-0 flex items-center justify-center overflow-hidden">
      <div style={{
        width:VW, height:VH, position:"relative", flexShrink:0,
        transform:`scale(${scale})`, transformOrigin:"center center",
      }}>
        <svg width={VW} height={VH} viewBox={`0 0 ${VW} ${VH}`}
          style={{ position:"absolute", inset:0, overflow:"visible" }}>
          <path d={PATHS.yogesh_yug}   fill="none" stroke={`${C.blue}18`}   strokeWidth={2} />
          <path d={PATHS.yogesh_rohit} fill="none" stroke={`${C.violet}18`} strokeWidth={2} />
          <path d={PATHS.yug_orch}     fill="none" stroke={`${C.blue}18`}   strokeWidth={2} />
          <path d={PATHS.rohit_orch}   fill="none" stroke={`${C.violet}18`} strokeWidth={2} />
          <path d={PATHS.upload}       fill="none" stroke={`${C.blue}18`}   strokeWidth={2} />

          <FlowEdge d={PATHS.upload}       color={C.blue}   visible={showUpEdge}  delay={0}   />
          <FlowEdge d={PATHS.yogesh_yug}   color={C.blue}   visible={showEdgesI}  delay={0.05}/>
          <FlowEdge d={PATHS.yogesh_rohit} color={C.violet} visible={showEdgesI}  delay={0.12}/>
          <FlowEdge d={PATHS.yug_orch}     color={C.blue}   visible={showEdgesI}  delay={0.20}/>
          <FlowEdge d={PATHS.rohit_orch}   color={C.violet} visible={showEdgesI}  delay={0.28}/>

          {/* Standard bifurcation dots — both nodes active */}
          {showDots && (<>
            <FlowDot d={PATHS.yogesh_yug}   color={C.blue}   dur={0.95} delay={0}    />
            <FlowDot d={PATHS.yogesh_yug}   color={C.blue}   dur={0.95} delay={0.48} />
            <FlowDot d={PATHS.yogesh_rohit} color={C.violet} dur={0.95} delay={0.22} />
            <FlowDot d={PATHS.yogesh_rohit} color={C.violet} dur={0.95} delay={0.70} />
            <FlowDot d={PATHS.yug_orch}     color={C.blue}   dur={1.05} delay={0.1}  />
            <FlowDot d={PATHS.rohit_orch}   color={C.violet} dur={1.05} delay={0.35} />
          </>)}

          {/*
            TASK 1 — §5: ANALYZING_AUDIO — Ghost Node (Whisper) active on Rohit only.
            Audio flows exclusively through the rohit→orch path; amber colour signals
            the Ghost Node transcription pass, distinct from the CLIP violet.
          */}
          {showAudioDots && (<>
            <FlowDot d={PATHS.rohit_orch} color={C.amber} dur={1.1} delay={0}    />
            <FlowDot d={PATHS.rohit_orch} color={C.amber} dur={1.1} delay={0.55} />
          </>)}

          {showEdgesI && (<>
            <circle cx={E.yogesh_r.x} cy={E.yogesh_r.y} r={4} fill={C.card}   stroke={C.blue}   strokeWidth={2} />
            <circle cx={E.yug_l.x}    cy={E.yug_l.y}    r={4} fill={C.card}   stroke={C.blue}   strokeWidth={2} />
            <circle cx={E.yug_r.x}    cy={E.yug_r.y}    r={4} fill={C.card}   stroke={C.blue}   strokeWidth={2} />
            <circle cx={E.rohit_l.x}  cy={E.rohit_l.y}  r={4} fill={C.card}   stroke={C.violet} strokeWidth={2} />
            <circle cx={E.rohit_r.x}  cy={E.rohit_r.y}  r={4} fill={C.card}   stroke={C.violet} strokeWidth={2} />
            <circle cx={E.orch_l.x}   cy={E.orch_l.y}   r={4} fill={C.card}   stroke={C.blue}   strokeWidth={2} />
          </>)}
        </svg>

        <div style={{ position:"absolute", inset:0 }}>
          <div style={{ opacity: failed ? 0.55 : 1, transition: "opacity 220ms ease" }}>
          <AnimatePresence mode="wait">
            {showClosed && (
              <ClosedModule key="closed"
                cx={N.yogesh.cx} cy={N.yogesh.cy} state={state} />
            )}
          </AnimatePresence>

          <AnimatePresence>
            {showNodes && (<>
              <div style={{ opacity: 1, transition:"opacity 200ms ease" }}>
                <NodeCard key="yog" cx={N.yogesh.cx} cy={N.yogesh.cy}
                  title="Yogesh" role="Extractor"
                  subtitle="SHA-256 · frame extract"
                  icon={<Scissors size={15} strokeWidth={2} />}
                  accent={C.coral} pulsing={state === "EXTRACTING"} delay={0} />
              </div>

              {/* Yug dims during audio phase — GPU Idle handshake is complete */}
              <div style={{
                opacity: waiting || state === "ANALYZING_AUDIO" ? 0.4 : 1,
                transition:"opacity 200ms ease",
              }}>
                <NodeCard key="yug" cx={N.yug.cx} cy={N.yug.cy}
                  title="Yug" role="Text & OCR Engine"
                  subtitle="384D BPE Tokenizer"
                  icon={<TypeIcon size={15} strokeWidth={2} />}
                  accent={C.violet} pulsing={pulseYug} delay={0.1} />
              </div>

              {/*
                TASK 1 — §4: Rohit's NodeCard receives:
                  • accent={C.amber}  during ANALYZING_AUDIO  (Ghost Node active)
                  • subtitle="Whisper 16kHz · Transcribing"   (Ghost Node label)
                  • pulsing=true  during both ANALYZING and ANALYZING_AUDIO
                The base <NodeCard> structure and animations are left completely untouched.
              */}
              <div style={{ opacity: waiting ? 0.4 : 1, transition:"opacity 200ms ease" }}>
                <NodeCard key="roh" cx={N.rohit.cx} cy={N.rohit.cy}
                  title="Rohit" role="Vision Engine"
                  subtitle={rohitSubtitle}
                  icon={
                    state === "ANALYZING_AUDIO"
                      ? <Mic size={15} strokeWidth={2} />
                      : <Eye size={15} strokeWidth={2} />
                  }
                  accent={rohitAccent}
                  pulsing={pulseRohit} delay={0.18} />
              </div>
            </>)}
          </AnimatePresence>

          <AnimatePresence>
            {showOrch && (
              <div style={{ opacity: waiting ? 0.45 : 1, transition:"opacity 200ms ease" }}>
                <OrchestratorCard key="orch"
                  cx={N.orch.cx} cy={N.orch.cy}
                  progress={orchProgress} verdict={verdict} pulsing={pulseOrch}
                  onSeeInsights={onComplete} />
              </div>
            )}
          </AnimatePresence>
          </div>

          <FileChip
            visible={chipVisible} label={fileName||"stream.bin"}
            fromX={chipFrom.x} fromY={chipFrom.y}
            toX={chipTo.x}   toY={chipTo.y}
            moving={chipMoving} onArrive={onChipArrive}
          />
        </div>
      </div>
    </div>
  );
};

/* ════════════════════════════════════════════════════════════════════════════
   STATUS CHIP
   ════════════════════════════════════════════════════════════════════════ */
// TASK 1 — §2 / §4: Added ANALYZING_AUDIO to the state → display map.
const SM: Record<PipelineState,{label:string;color:string}> = {
  IDLE:            { label:"Idle · awaiting payload",   color:C.muted  },
  UPLOADING:       { label:"Uploading",                 color:C.blue   },
  EXTRACTING:      { label:"Extracting",                color:C.coral  },
  BIFURCATING:     { label:"Bifurcating",               color:C.violet },
  ANALYZING:       { label:"Analyzing",                 color:C.blue   },
  ANALYZING_AUDIO: { label:"Audio · Ghost Node",        color:C.amber  },
  COMPLETE:        { label:"Complete",                  color:C.green  },
  FAILED:          { label:"Failed",                    color:C.coral  },
};
const StatusChip: React.FC<{state:PipelineState}> = ({ state }) => {
  const { label, color } = SM[state];
  return (
    <div style={{
      display:"flex", alignItems:"center", gap:7,
      padding:"6px 14px", borderRadius:9999,
      background:C.card, border:`1px solid ${C.cardBorder}`,
      fontFamily:"DM Mono, monospace",
    }}>
      <motion.span
        style={{ width:6, height:6, borderRadius:"50%", background:color, display:"inline-block" }}
        animate={state!=="IDLE" ? { opacity:[0.3,1,0.3], scale:[1,1.2,1] } : {}}
        transition={{ duration:T(0.95), repeat:Infinity }}
      />
      <span style={{ fontSize:10.5, fontWeight:500, letterSpacing:"0.1em",
        textTransform:"uppercase", color }}>{label}</span>
    </div>
  );
};

/* ════════════════════════════════════════════════════════════════════════════
   FINAL REPORT  —  slides up from bottom
   ════════════════════════════════════════════════════════════════════════ */
const ReportCard: React.FC<{
  verdict:Verdict;
  backendStatus: AssetStatusResponse["status"] | "timeout" | null;
  fileName:string;
  fileSize:number;
  latencyText: string | null;
  errorHint: string | null;
  confidence: number | null;
  frameCount: number | null;
  onReset:()=>void;
  onSeeInsights:()=>void;
}> = ({ verdict, backendStatus, fileName, fileSize, latencyText, errorHint, confidence, frameCount, onReset, onSeeInsights }) => {
  const clean = verdict==="CLEAN";
  const failed = verdict==="FAILED" || backendStatus === "failed" || backendStatus === "timeout";
  const vc    = clean ? C.green : C.coral;
  const headline =
    clean ? "Golden Asset Registered"
    : failed ? (errorHint ?? (backendStatus === "timeout" ? "System Timeout" : "Pipeline Aborted"))
    : "Analysis Complete";
  const badgeText =
    clean ? "Success"
    : failed ? "Failed"
    : "Complete";
  const subheading =
    backendStatus === "failed" || backendStatus === "timeout"
      ? "Pipeline Aborted"
      : "Analysis Complete";
  return (
    <motion.div
      key="report"
      initial={{ y:64, opacity:0 }} animate={{ y:0, opacity:1 }} exit={{ y:44, opacity:0 }}
      transition={{ type:"spring", stiffness:230, damping:28 }}
      className="absolute left-7 right-7 bottom-5 z-30 rounded-[20px] overflow-hidden"
      style={{
        background:C.card,
        border:`1px solid ${vc}2a`,
        boxShadow:`0 20px 60px rgba(0,0,0,0.09), 0 0 0 1px ${vc}16`,
      }}
    >
      <div className="flex items-stretch" style={{ borderColor:"rgba(0,0,0,0.06)" }}>
        <div className="flex-1 p-6 flex items-center gap-5"
          style={{ background: clean ? `${C.green}07` : `${C.coral}08` }}>
          <div style={{ width:50, height:50, borderRadius:13, flexShrink:0,
            background: clean ? `${C.green}16` : `${C.coral}14`,
            color:vc, display:"flex", alignItems:"center", justifyContent:"center" }}>
            {clean ? <CheckCircle size={24} strokeWidth={2} /> : <AlertTriangle size={24} strokeWidth={2} />}
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div style={{ fontSize:8.5, fontFamily:"DM Mono, monospace",
                letterSpacing:"0.14em", textTransform:"uppercase", color:vc }}>
                {subheading}
              </div>
              <div style={{ padding:"2px 6px", borderRadius:4, background:`${C.green}18`, color:C.green,
                fontSize:8, fontWeight:700, letterSpacing:"0.05em", textTransform:"uppercase" }}>
                {badgeText}
              </div>
            </div>
            <div style={{ fontSize:8.5, fontFamily:"DM Mono, monospace",
              letterSpacing:"0.14em", textTransform:"uppercase", color:C.muted, marginBottom:4 }}>
              Final Analysis Verdict
            </div>
            <div style={{ fontSize:21, fontWeight:800, color:C.ink, fontFamily:"DM Sans, sans-serif" }}>
              {headline}
            </div>
            {failed && errorHint && (
              <div style={{ fontSize:10.5, color:C.muted, fontFamily:"DM Mono, monospace", marginTop:6 }}>
                {errorHint}
              </div>
            )}
            <div style={{ fontSize:10.5, color:C.muted, fontFamily:"DM Mono, monospace", marginTop:2 }}>
              {fileName} · {fileSize>0 ? `${(fileSize/1024).toFixed(1)} KB` : "—"}
            </div>
          </div>
        </div>

        <div style={{ width:1, background:"rgba(0,0,0,0.06)" }} />

        {[
          { label:"Latency",    value: latencyText ?? "—", sub:"end-to-end"  },
          { label:"Frames",     value: (frameCount ?? 0) > 0 ? frameCount!.toLocaleString() : "—", sub:"@ 1080p" },
          { label:"Confidence", value: confidence == null ? "—" : `${confidence.toFixed(1)}%`, sub:"fusion"      },
        ].map((m,i)=>(
          <React.Fragment key={m.label}>
            <div className="px-8 py-5 flex flex-col justify-center gap-1">
              <div style={{ fontSize:8.5, fontFamily:"DM Mono, monospace",
                letterSpacing:"0.14em", textTransform:"uppercase", color:C.muted }}>
                {m.label}
              </div>
              <div style={{ fontSize:22, fontWeight:700, color:C.ink, fontFamily:"DM Sans, sans-serif" }}>
                {m.value}
              </div>
              <div style={{ fontSize:9.5, color:C.muted, fontFamily:"DM Mono, monospace" }}>
                {m.sub}
              </div>
            </div>
            {i < 2 && <div style={{ width:1, background:"rgba(0,0,0,0.06)" }} />}
          </React.Fragment>
        ))}

        <div style={{ width:1, background:"rgba(0,0,0,0.06)" }} />
        <div className="px-6 flex items-center gap-3">
          <motion.button
            onClick={onReset}
            style={{ padding:"10px 16px", borderRadius:10,
              border:`1px solid ${C.cardBorder}`, background:"transparent",
              cursor:"pointer", fontSize:12, fontWeight:600, color:C.ink,
              fontFamily:"DM Sans, sans-serif",
              display:"flex", alignItems:"center", gap:6 }}
            whileHover={{ background:"rgba(0,0,0,0.03)", scale:1.02 }} whileTap={{ scale:0.98 }}
          >
            <RefreshCw size={13} strokeWidth={2.2} /> Reset
          </motion.button>

          {backendStatus === "completed" && (
            <motion.button
              onClick={onSeeInsights}
              style={{ padding:"10px 20px", borderRadius:10,
                background:C.ink, color:C.bg,
                cursor:"pointer", fontSize:12, fontWeight:700,
                fontFamily:"DM Sans, sans-serif",
                display:"flex", alignItems:"center", gap:7,
                boxShadow:"0 8px 20px rgba(0,0,0,0.12)" }}
              whileHover={{ scale:1.04, filter:"brightness(1.1)" }} whileTap={{ scale:0.96 }}
            >
              See the insights <Zap size={13} fill="currentColor" />
            </motion.button>
          )}
        </div>
      </div>
    </motion.div>
  );
};

/* ════════════════════════════════════════════════════════════════════════════
   API HELPERS
   ════════════════════════════════════════════════════════════════════════ */
const BASE_URL = "http://127.0.0.1:8000";

async function uploadGoldenAsset(
  file: File,
  authToken?: string,
): Promise<UploadResponse> {
  if (!authToken) {
    throw new Error("Not authenticated: missing auth token");
  }
  const form = new FormData();
  form.append("file", file);

  const headers: HeadersInit = {};
  headers["Authorization"] = `Bearer ${authToken}`;

  const res = await fetch(`${BASE_URL}/api/v1/golden/upload`, {
    method: "POST",
    headers,
    body: form,
    credentials: "include",
  });

  if (!res.ok) {
    const txt = await res.text().catch(() => res.statusText);
    throw new Error(`Upload failed (${res.status}): ${txt}`);
  }

  return res.json() as Promise<UploadResponse>;
}

async function fetchAssetStatus(
  assetId: string,
  authToken?: string,
): Promise<AssetStatusResponse> {
  if (!authToken) {
    throw new Error("Not authenticated: missing auth token");
  }
  const headers: HeadersInit = {};
  headers["Authorization"] = `Bearer ${authToken}`;

  const res = await fetch(`${BASE_URL}/api/v1/assets/${assetId}/status`, {
    headers,
    credentials: "include",
  });

  if (!res.ok) throw new Error(`Status fetch failed (${res.status})`);
  return res.json() as Promise<AssetStatusResponse>;
}

/* ════════════════════════════════════════════════════════════════════════════
   MAIN COMPONENT
   ════════════════════════════════════════════════════════════════════════ */
const OverwatchIngestPortal: React.FC<OverwatchIngestPortalProps> = ({
  onComplete,
  onBack,
  authToken,
}) => {
  useFonts();

  const [state,    setState]    = useState<PipelineState>("IDLE");
  const [fileName, setFileName] = useState("");
  const [fileSize, setFileSize] = useState(0);
  const [verdict,  setVerdict]  = useState<Verdict>(null);
  const [orchProg, setOrchProg] = useState(0);
  const [chipMov,  setChipMov]  = useState(false);
  const [chipVis,  setChipVis]  = useState(false);
  const [latencyText, setLatencyText] = useState<string | null>(null);
  const [backendStatus, setBackendStatus] = useState<AssetStatusResponse["status"] | "timeout" | null>(null);
  const [errorHint, setErrorHint] = useState<string | null>(null);
  const [failedAt, setFailedAt] = useState<PipelineState | null>(null);
  const confidenceRef           = useRef<number | null>(null);
  const assetIdRef              = useRef<string>("");
  const frameCountRef           = useRef<number>(0);
  const pollStartedAtRef        = useRef<number>(0);
  const uploadStartMsRef        = useRef<number>(0);
  const startedAtPerfRef        = useRef(0);
  const stateRef                = useRef<PipelineState>("IDLE");
  const activeAuthTokenRef      = useRef<string | null>(null);

  /*
   * TASK 1 — §5: Track frame-count stability to detect the ANALYZING_AUDIO phase.
   * When frame_count stops increasing across consecutive polls while status is still
   * "processing", the GPU Idle Handshake is done and the Ghost Node is active.
   */
  const lastFrameCountRef      = useRef<number>(-1);
  const stableFramePollsRef    = useRef<number>(0);

  // Number of consecutive polls with the same non-zero frame_count before we
  // consider frame extraction finished and transition to ANALYZING_AUDIO.
  const STABLE_POLLS_THRESHOLD = 2;

  const pollTimer = useRef<number | null>(null);
  const isRunning = !["IDLE","COMPLETE","FAILED"].includes(state);
  const elapsed   = useElapsed(isRunning, startedAtPerfRef);

  const stopPolling = useCallback(()=>{
    if (pollTimer.current !== null) {
      clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
  },[]);

  const reset = useCallback(()=>{
    stopPolling();
    setState("IDLE"); setFileName(""); setFileSize(0);
    setVerdict(null); setOrchProg(0);
    setChipMov(false); setChipVis(false);
    setLatencyText(null);
    setBackendStatus(null);
    setErrorHint(null);
    setFailedAt(null);
    assetIdRef.current = "";
    frameCountRef.current = 0;
    confidenceRef.current = null;
    uploadStartMsRef.current = 0;
    lastFrameCountRef.current = -1;
    stableFramePollsRef.current = 0;
  },[stopPolling]);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  const finalize = useCallback((v: Exclude<Verdict, null>, finalBackendStatus: AssetStatusResponse["status"] | "timeout")=>{
    stopPolling();
    setOrchProg(1.0);
    setVerdict(v);
    setBackendStatus(finalBackendStatus);
    if (v === "FAILED") {
      setFailedAt(stateRef.current);
      setState("FAILED");
    } else {
      setState("COMPLETE");
    }
    setChipVis(false);
    if (uploadStartMsRef.current) {
      setLatencyText(`${((Date.now() - uploadStartMsRef.current) / 1000).toFixed(2)}s`);
    }
  },[stopPolling]);

  /**
   * Start polling GET /api/v1/assets/{assetId}/status every 2 s.
   * When the backend transitions to 'completed' or 'failed', finalize.
   *
   * TASK 1 — §1: Timeout raised from 60_000 ms → 300_000 ms (5 minutes) to match
   *   the backend's own 300-second GPU idle handshake timeout.
   *
   * TASK 1 — §5: Polling now detects the ANALYZING_AUDIO phase by watching for
   *   frame_count stability — once frame extraction is done (count stops growing)
   *   but status is still "processing", the Ghost Node is active on Rohit.
   */
  const startPolling = useCallback((assetId: string, token: string)=>{
    stopPolling();
    pollStartedAtRef.current = performance.now();
    // Reset frame-stability trackers for the new poll session.
    lastFrameCountRef.current   = -1;
    stableFramePollsRef.current = 0;

    pollTimer.current = window.setInterval(async ()=>{
      try {
        // TASK 1 — §1: Hard timeout increased to 300_000 ms (5 min) to accommodate
        //   the full GPU Idle Handshake + audio transcription window.
        if (performance.now() - pollStartedAtRef.current > 600_000) {
          setErrorHint("System Timeout");
          finalize("FAILED", "timeout");
          return;
        }

        const status = await fetchAssetStatus(assetId, token);
        frameCountRef.current = status.frame_count;
        setBackendStatus(status.status);

        if (status.status === "processing") {
          const fc = status.frame_count;

          if (fc === 0) {
            // Still extracting — no frames have arrived yet.
            setState("EXTRACTING");
            setOrchProg(0.42);
            lastFrameCountRef.current   = 0;
            stableFramePollsRef.current = 0;
            return;
          }

          // Frames are flowing in — check stability to detect audio phase.
          if (fc === lastFrameCountRef.current) {
            stableFramePollsRef.current += 1;
          } else {
            // Count is still growing — frame extraction is still active.
            stableFramePollsRef.current = 0;
            lastFrameCountRef.current   = fc;
          }

          /*
           * TASK 1 — §5: Once the frame_count has been stable for STABLE_POLLS_THRESHOLD
           * consecutive polls, the Extractor has sent its /finish signals and the
           * GPU Idle Handshake is underway.  Transition to ANALYZING_AUDIO so Rohit's
           * NodeCard pulses in amber and shows the Ghost Node label.
           */
          if (stableFramePollsRef.current >= STABLE_POLLS_THRESHOLD) {
            setState("ANALYZING_AUDIO");
            setOrchProg(0.88);
          } else {
            setState("ANALYZING");
            setOrchProg(0.78);
          }
          return;
        }

        if (status.status === "completed") {
          finalize("CLEAN", "completed");
        } else if (status.status === "failed") {
          finalize("FAILED", "failed");
        }
      } catch {
        // Transient network error — keep polling, don't surface to UI
      }
    }, 2000);
  },[stopPolling, finalize]);

  /**
   * Real pipeline: uploads the file to the FastAPI backend,
   * then polls status while running cosmetic visual stage transitions.
   */
  const startRealPipeline = useCallback(async (file: File)=>{
    stopPolling();
    startedAtPerfRef.current = performance.now();
    uploadStartMsRef.current = Date.now();
    setFileName(file.name);
    setFileSize(file.size);
    setVerdict(null);
    setOrchProg(0);
    setLatencyText(null);
    setBackendStatus(null);
    setErrorHint(null);
    setFailedAt(null);
    frameCountRef.current = 0;
    confidenceRef.current = null;
    lastFrameCountRef.current = -1;
    stableFramePollsRef.current = 0;

    setState("UPLOADING");
    setChipVis(true);
    setChipMov(false);
    setChipMov(true);
    setOrchProg(0.18);

    try {
      const token = authToken ?? auth.getToken();
      if (!token) {
        setErrorHint("Not authenticated");
        finalize("FAILED", "failed");
        return;
      }
      activeAuthTokenRef.current = token;

      // ── Real POST to the backend ────────────────────────────────────────
      const uploadResp = await uploadGoldenAsset(file, token);
      assetIdRef.current = uploadResp.asset_id;

      // Backend now owns pipeline state; start in EXTRACTING until frames arrive.
      setState("EXTRACTING");
      setOrchProg(0.42);

      // Begin polling the backend for real completion signal
      startPolling(uploadResp.asset_id, token);

    } catch (err) {
      console.error("[OverwatchIngest] Upload error:", err);
      const msg = err instanceof Error ? err.message : String(err);
      if (/Not authenticated/i.test(msg)) {
        setErrorHint("Not authenticated");
      } else if (/ECONNREFUSED|ERR_CONNECTION_REFUSED|Failed to fetch/i.test(msg)) {
        setErrorHint("Backend Unreachable");
      } else {
        setErrorHint("Network Error");
      }
      setOrchProg(1.0);
      finalize("FAILED", "failed");
    }
  },[stopPolling, startPolling, authToken, finalize]);

  useEffect(()=>()=>{ stopPolling(); },[stopPolling]);

  const handleFile = useCallback((f:File)=>{
    if(!["IDLE","COMPLETE","FAILED"].includes(state)) return;
    startRealPipeline(f);
  },[state, startRealPipeline]);

  return (
    <div className="w-full min-h-screen relative flex flex-col overflow-hidden"
      style={{ background:C.bg, fontFamily:"DM Sans, sans-serif", color:C.ink }}>

      {/* ─── HEADER ─── */}
      <header className="flex-shrink-0 px-8 pt-5 pb-2 flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-6">
          {onBack && (
            <motion.button
              onClick={onBack}
              whileHover={{ x: -2, scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="flex h-9 w-9 items-center justify-center rounded-full border border-black/5 bg-white shadow-sm"
            >
              <ChevronLeft size={18} strokeWidth={2.5} color={C.ink} />
            </motion.button>
          )}
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span style={{ fontSize:9.5, fontFamily:"DM Mono, monospace",
                letterSpacing:"0.2em", textTransform:"uppercase", color:C.blue }}>
                Ingest Portal · Live Pipeline
              </span>
              {isRunning && (
                <span style={{ fontSize:9.5, fontFamily:"DM Mono, monospace",
                  color:C.muted, display:"flex", alignItems:"center", gap:4 }}>
                  <Clock size={9} strokeWidth={2} /> {elapsed}
                </span>
              )}
            </div>
            <h1 style={{ fontSize:24, fontWeight:700, lineHeight:1.1,
              letterSpacing:"-0.02em", color:C.ink, margin:0 }}>
              Watch a file liquidate{" "}
              <span style={{ color:C.muted, fontWeight:500 }}>into intelligence.</span>
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <StatusChip state={state} />
          <AnimatePresence>
            {(state==="COMPLETE" || state==="FAILED") && (
              <motion.button type="button" onClick={reset}
                className="flex items-center gap-2 rounded-full px-4 py-2.5 focus:outline-none"
                style={{ fontSize:12, fontWeight:600, background:C.card, color:C.ink,
                  border:`1px solid ${C.cardBorder}`, cursor:"pointer" }}
                initial={{ opacity:0, x:8 }} animate={{ opacity:1, x:0 }} exit={{ opacity:0 }}
                whileHover={{ scale:1.03 }} whileTap={{ scale:0.97 }}>
                <RefreshCw size={12} strokeWidth={2.3} /> Reset
              </motion.button>
            )}
          </AnimatePresence>
        </div>
      </header>

      {/* ─── PIPELINE STEPPER ─── */}
      <AnimatePresence>
        {state!=="IDLE" && (
          <motion.div
            initial={{ opacity:0, y:-6 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0 }}
            className="flex-shrink-0 mx-8 mb-2 px-5 py-2.5 rounded-[14px] flex items-center gap-3"
            style={{ background:C.card, border:`1px solid ${C.cardBorder}` }}>
            <span style={{ fontSize:9.5, fontFamily:"DM Mono, monospace",
              letterSpacing:"0.14em", textTransform:"uppercase", color:C.muted, flexShrink:0 }}>
              Pipeline
            </span>
            <PipelineStepper state={state} failedAt={failedAt} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── CANVAS AREA ─── */}
      <div className="flex-1 min-h-0 relative overflow-hidden" style={{ background:C.bg }}>

        {/* Ambient glow */}
        <div className="absolute inset-0 pointer-events-none" style={{ backgroundImage:
          `radial-gradient(circle at 72% 44%, ${C.blue}0b 0%, transparent 42%),
           radial-gradient(circle at 30% 70%, ${C.violet}09 0%, transparent 40%)` }} />

        {/* Dot grid */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ opacity:0.4 }}>
          <defs>
            <pattern id="ow-dots" x="0" y="0" width="28" height="28" patternUnits="userSpaceOnUse">
              <circle cx="1" cy="1" r="1" fill="rgba(0,0,0,0.07)" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#ow-dots)" />
        </svg>

        {/* IDLE: centered dropzone */}
        <AnimatePresence>
          {state==="IDLE" && <IdleDropzone onPick={handleFile} />}
        </AnimatePresence>

        {/* ACTIVE: pipeline canvas */}
        <AnimatePresence>
          {state!=="IDLE" && (
            <motion.div key="pipeline" className="absolute inset-0"
              initial={{ opacity:0 }} animate={{ opacity:1 }}
              exit={{ opacity:0 }}
              transition={{ opacity:{ duration:T(0.28) } }}>
              <PipelineCanvas
                state={state} fileName={fileName}
                orchProgress={orchProg} verdict={verdict}
                chipMoving={chipMov} chipVisible={chipVis}
                onChipArrive={()=>setChipMov(false)}
                onComplete={
                  backendStatus === "completed"
                    ? ()=>onComplete?.(verdict, fileName, assetIdRef.current)
                    : undefined
                }
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* FINAL REPORT */}
        <AnimatePresence>
          {(state==="COMPLETE" || state==="FAILED") && (
            <ReportCard
              verdict={verdict} fileName={fileName} fileSize={fileSize}
              backendStatus={backendStatus}
              latencyText={latencyText}
              errorHint={errorHint}
              confidence={confidenceRef.current}
              frameCount={frameCountRef.current || null}
              onReset={reset}
              onSeeInsights={()=>onComplete?.(verdict, fileName, assetIdRef.current)}
            />
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default OverwatchIngestPortal;