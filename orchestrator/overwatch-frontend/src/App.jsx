import { useState, useCallback } from "react";

/* ─── GLOBAL STYLES ─────────────────────────────────────────── */
function GlobalStyles() {
  return (
    <style>{`
      @import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap');
      *, *::before, *::after { box-sizing: border-box; }
      html, body { margin: 0; padding: 0; }
      body {
        background: #09090b; color: #f0ede8;
        font-family: 'DM Sans', -apple-system, sans-serif;
        -webkit-font-smoothing: antialiased; min-height: 100vh; overflow-x: hidden;
      }
      #grain {
        position: fixed; inset: 0; pointer-events: none; z-index: 9999; opacity: 0.032;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
        background-size: 160px;
      }
      @keyframes fadeUp   { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
      @keyframes fadeIn   { from { opacity: 0; } to { opacity: 1; } }
      @keyframes blink    { 0%,100% { opacity: 1; } 50% { opacity: 0.18; } }
      @keyframes slideDown { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: translateY(0); } }
      .fade-up  { animation: fadeUp  0.5s cubic-bezier(0.4,0,0.2,1) both; }
      .fade-in  { animation: fadeIn  0.3s ease both; }
      .s1 { animation-delay: 0.04s; } .s2 { animation-delay: 0.1s; }
      .s3 { animation-delay: 0.17s; } .s4 { animation-delay: 0.24s; }
      .s5 { animation-delay: 0.3s;  } .s6 { animation-delay: 0.38s; }
      .blink { animation: blink 2.6s ease-in-out infinite; }
      .slide-down { animation: slideDown 0.25s ease both; }
      button { cursor: pointer; border: none; outline: none; background: none; font-family: inherit; }
      ::-webkit-scrollbar { width: 5px; }
      ::-webkit-scrollbar-track { background: transparent; }
      ::-webkit-scrollbar-thumb { background: rgba(240,237,232,0.1); border-radius: 6px; }
      .btn-p {
        display: inline-flex; align-items: center; gap: 7px;
        background: #f0ede8; color: #09090b;
        border-radius: 8px; padding: 9px 18px;
        font-size: 13.5px; font-weight: 500;
        transition: opacity 0.15s, transform 0.15s; cursor: pointer;
      }
      .btn-p:hover { opacity: 0.86; transform: translateY(-1px); }
      .btn-o {
        display: inline-flex; align-items: center; gap: 7px;
        background: transparent; color: rgba(240,237,232,0.65);
        border: 1px solid rgba(240,237,232,0.1);
        border-radius: 8px; padding: 9px 18px;
        font-size: 13.5px; font-weight: 400;
        transition: border-color 0.15s, color 0.15s, background 0.15s; cursor: pointer;
      }
      .btn-o:hover { border-color: rgba(240,237,232,0.2); color: #f0ede8; background: rgba(240,237,232,0.04); }
      .nav-btn { color: rgba(240,237,232,0.45); font-size: 14px; transition: color 0.15s; padding: 4px 0; }
      .nav-btn:hover { color: #f0ede8; }
      .nav-btn.active { color: #f0ede8; }
      .card {
        background: #141418; border: 1px solid rgba(255,255,255,0.07);
        border-radius: 12px; transition: border-color 0.2s, background 0.2s;
      }
      .card:hover { border-color: rgba(255,255,255,0.11); }
      .row-hover:hover { background: rgba(255,255,255,0.025); }
      .expand-btn:hover { background: rgba(255,255,255,0.025) !important; }
    `}</style>
  );
}

/* ─── TOKENS ─────────────────────────────────────────────────── */
const A = "#7c6cf5";
const A_DIM = "rgba(124,108,245,0.12)";
const A_BORDER = "rgba(124,108,245,0.28)";

/* ─── MOCK DATA ──────────────────────────────────────────────── */
const detections = [
  { id:"DET-8821", asset:"Oppenheimer_FinalCut_4K.mp4",   score:0.947, visual:0.961, text:0.924, status:"confirmed", time:"2m",  stream:"Stream α" },
  { id:"DET-8820", asset:"podcast_ep44_unedited.mp3",      score:0.823, visual:null,  text:0.823, status:"review",    time:"7m",  stream:"Text Feed" },
  { id:"DET-8819", asset:"tutorial_screenrecord_hd.mp4",   score:0.541, visual:0.612, text:0.421, status:"cleared",   time:"12m", stream:"Stream β" },
  { id:"DET-8818", asset:"documentary_seg02_master.mp4",   score:0.991, visual:0.994, text:0.988, status:"confirmed", time:"23m", stream:"Stream α" },
  { id:"DET-8817", asset:"lecture_cs101_transcript.txt",   score:0.768, visual:null,  text:0.768, status:"review",    time:"31m", stream:"Text Feed" },
  { id:"DET-8816", asset:"movie_trailer_2024_final.mp4",   score:0.432, visual:0.389, text:0.512, status:"cleared",   time:"44m", stream:"Stream β" },
];

/* ─── NAVBAR ─────────────────────────────────────────────────── */
function Navbar({ page, nav }) {
  const isDash = ["dashboard","insights"].includes(page);
  return (
    <nav style={{
      position:"fixed", top:0, left:0, right:0, zIndex:100, height:54,
      borderBottom:"1px solid rgba(255,255,255,0.055)",
      background:"rgba(9,9,11,0.82)", backdropFilter:"blur(14px)",
      display:"flex", alignItems:"center", padding:"0 28px",
    }}>
      <div style={{ display:"flex", alignItems:"center", justifyContent:"space-between", width:"100%", maxWidth:1180, margin:"0 auto" }}>
        <button onClick={() => nav("landing")} style={{ display:"flex", alignItems:"center", gap:8 }}>
          <div style={{ width:22, height:22, borderRadius:6, background:A, display:"flex", alignItems:"center", justifyContent:"center" }}>
            <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
              <circle cx="5.5" cy="5.5" r="1.8" fill="white"/>
              <circle cx="5.5" cy="5.5" r="4.5" stroke="white" strokeWidth="1.1" fill="none"/>
            </svg>
          </div>
          <span style={{ fontSize:14, fontWeight:600, color:"#f0ede8", letterSpacing:"-0.02em" }}>Overwatch</span>
        </button>

        <div style={{ display:"flex", gap:26, alignItems:"center" }}>
          {isDash ? (
            <>
              <button className={`nav-btn ${page==="dashboard"?"active":""}`} onClick={() => nav("dashboard")}>Dashboard</button>
              <button className={`nav-btn ${page==="insights"?"active":""}`}  onClick={() => nav("insights")}>Insights</button>
            </>
          ) : (
            <>
              <button className="nav-btn" onClick={() => nav("landing")}>Overview</button>
              <button className="nav-btn" onClick={() => nav("dashboard")}>Dashboard</button>
            </>
          )}
        </div>

        <div style={{ display:"flex", alignItems:"center", gap:14 }}>
          {isDash && (
            <div style={{ display:"flex", alignItems:"center", gap:6, fontSize:12, color:"rgba(240,237,232,0.38)" }}>
              <div className="blink" style={{ width:6, height:6, borderRadius:"50%", background:"#5fca8e" }}/>
              <span>Live</span>
            </div>
          )}
          <button className="btn-p" style={{ padding:"7px 15px", fontSize:13 }} onClick={() => nav("upload")}>
            + Ingest
          </button>
        </div>
      </div>
    </nav>
  );
}

/* ─── LANDING ────────────────────────────────────────────────── */
function Landing({ nav }) {
  return (
    <div style={{ paddingTop:54, minHeight:"100vh" }}>
      {/* Hero */}
      <section style={{ padding:"108px 28px 88px", maxWidth:1180, margin:"0 auto", position:"relative", textAlign:"center" }}>
        <div style={{ position:"absolute", top:"15%", left:"50%", transform:"translateX(-50%)", width:640, height:420, background:`radial-gradient(ellipse, ${A_DIM} 0%, transparent 68%)`, pointerEvents:"none" }}/>

        <div className="fade-up s1">
          <div style={{ display:"inline-flex", alignItems:"center", gap:8, background:A_DIM, border:`1px solid ${A_BORDER}`, borderRadius:20, padding:"5px 14px", fontSize:12, color:A, marginBottom:30, fontWeight:500, letterSpacing:"0.01em" }}>
            <div style={{ width:5, height:5, borderRadius:"50%", background:A }}/>
            Distributed Anti-Piracy Intelligence Engine
          </div>
        </div>

        <h1 className="fade-up s2" style={{ fontFamily:"Instrument Serif, serif", fontSize:"clamp(44px,6.5vw,76px)", fontWeight:400, lineHeight:1.08, letterSpacing:"-0.025em", color:"#f0ede8", marginBottom:22 }}>
          Intelligence that watches<br/>
          <em style={{ color:A }}>every copy.</em>
        </h1>

        <p className="fade-up s3" style={{ fontSize:17, color:"rgba(240,237,232,0.48)", maxWidth:500, margin:"0 auto 44px", lineHeight:1.7, fontWeight:300 }}>
          Multi-modal vector similarity across 512-D visual streams and 384-D text embeddings — detecting structural piracy the moment it surfaces.
        </p>

        <div className="fade-up s4" style={{ display:"flex", gap:10, justifyContent:"center", flexWrap:"wrap" }}>
          <button className="btn-p" onClick={() => nav("upload")}>
            Start Ingesting
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M2.5 6.5h8M7 2.5l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>
          </button>
          <button className="btn-o" onClick={() => nav("dashboard")}>View Command Center</button>
        </div>
      </section>

      {/* Stats strip */}
      <div style={{ borderTop:"1px solid rgba(255,255,255,0.055)", borderBottom:"1px solid rgba(255,255,255,0.055)" }}>
        <div style={{ maxWidth:1180, margin:"0 auto", display:"grid", gridTemplateColumns:"repeat(4,1fr)" }}>
          {[["512-D","Visual vector space"],["384-D","Text embedding space"],["<50ms","Avg. match latency"],["99.97%","Detection precision"]].map(([v,l],i)=>(
            <div key={i} style={{ padding:"26px 30px", borderRight:i<3?"1px solid rgba(255,255,255,0.055)":"none" }}>
              <div style={{ fontFamily:"Instrument Serif, serif", fontSize:30, color:"#f0ede8", marginBottom:4 }}>{v}</div>
              <div style={{ fontSize:12, color:"rgba(240,237,232,0.38)", fontWeight:300 }}>{l}</div>
            </div>
          ))}
        </div>
      </div>

      {/* How it works */}
      <section style={{ maxWidth:1180, margin:"0 auto", padding:"88px 28px" }}>
        <div style={{ marginBottom:56 }}>
          <div style={{ fontSize:11, color:A, fontWeight:500, letterSpacing:"0.1em", textTransform:"uppercase", marginBottom:10 }}>How it works</div>
          <h2 style={{ fontFamily:"Instrument Serif, serif", fontSize:34, fontWeight:400, color:"#f0ede8", letterSpacing:"-0.015em" }}>Three phases. Zero gaps.</h2>
        </div>
        <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:14 }}>
          {[
            { n:"01", t:"Ingest",   d:"Upload video, audio, or transcript. The system extracts frame-level visual embeddings and text vectors asynchronously via isolated buffer workers.",     icon:<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 12V4M4 8l4-4 4 4" stroke={A} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><path d="M2 14h12" stroke={A} strokeWidth="1.5" strokeLinecap="round"/></svg> },
            { n:"02", t:"Analyze",  d:"Dimensional reduction maps each asset into shared vector space. Cosine and Euclidean distances are computed against the protected golden source library.", icon:<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6" stroke={A} strokeWidth="1.5"/><circle cx="8" cy="8" r="2" fill={A}/></svg> },
            { n:"03", t:"Surface",  d:"Fused similarity scores above threshold trigger instant alerts. Attribution lineage traces each match back to its exact source frame with confidence.",    icon:<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="5.5" stroke={A} strokeWidth="1.5"/><path d="M8 5v3.5l2 2" stroke={A} strokeWidth="1.5" strokeLinecap="round"/></svg> },
          ].map((s,i)=>(
            <div key={i} className="card" style={{ padding:"26px 24px" }}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", marginBottom:18 }}>
                <span style={{ fontSize:11, color:"rgba(240,237,232,0.2)", fontWeight:500, letterSpacing:"0.05em" }}>{s.n}</span>
                {s.icon}
              </div>
              <h3 style={{ fontSize:16, fontWeight:500, color:"#f0ede8", marginBottom:8, letterSpacing:"-0.01em" }}>{s.t}</h3>
              <p style={{ fontSize:13.5, color:"rgba(240,237,232,0.43)", lineHeight:1.72, fontWeight:300, margin:0 }}>{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA footer */}
      <div style={{ borderTop:"1px solid rgba(255,255,255,0.055)", padding:"72px 28px" }}>
        <div style={{ maxWidth:440, margin:"0 auto", textAlign:"center" }}>
          <h2 style={{ fontFamily:"Instrument Serif, serif", fontSize:34, fontWeight:400, color:"#f0ede8", marginBottom:14, letterSpacing:"-0.015em" }}>Ready to deploy.</h2>
          <p style={{ fontSize:15, color:"rgba(240,237,232,0.43)", marginBottom:30, lineHeight:1.68, fontWeight:300 }}>
            Connect your media pipeline and protect assets in under five minutes.
          </p>
          <button className="btn-p" onClick={() => nav("upload")}>Begin Ingestion</button>
        </div>
      </div>
    </div>
  );
}

/* ─── UPLOAD ─────────────────────────────────────────────────── */
function Upload({ nav }) {
  const [drag, setDrag]   = useState(false);
  const [phase, setPhase] = useState("idle");
  const [file, setFile]   = useState("");
  const [prog, setProg]   = useState(0);

  const simulate = (name) => {
    setFile(name); setPhase("uploading"); setProg(0);
    let p = 0;
    const iv = setInterval(() => {
      p += Math.random() * 16;
      if (p >= 100) { p = 100; clearInterval(iv); setTimeout(() => setPhase("done"), 280); }
      setProg(Math.min(p, 100));
    }, 160);
  };

  const onDrop = useCallback((e) => {
    e.preventDefault(); setDrag(false);
    const f = e.dataTransfer.files[0]; if (f) simulate(f.name);
  }, []);

  return (
    <div style={{ minHeight:"100vh", display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", padding:"80px 28px", background:"#09090b" }}>
      <div style={{ position:"fixed", top:0, left:0, right:0, height:54, display:"flex", alignItems:"center", padding:"0 28px" }}>
        <button onClick={() => nav("landing")} style={{ display:"flex", alignItems:"center", gap:8 }}>
          <div style={{ width:22, height:22, borderRadius:6, background:A, display:"flex", alignItems:"center", justifyContent:"center" }}>
            <svg width="11" height="11" viewBox="0 0 11 11" fill="none"><circle cx="5.5" cy="5.5" r="1.8" fill="white"/><circle cx="5.5" cy="5.5" r="4.5" stroke="white" strokeWidth="1.1" fill="none"/></svg>
          </div>
          <span style={{ fontSize:14, fontWeight:600, color:"#f0ede8", letterSpacing:"-0.02em" }}>Overwatch</span>
        </button>
      </div>

      <div style={{ width:"100%", maxWidth:500 }} className="fade-up s1">
        {phase === "idle" && (
          <>
            <div style={{ textAlign:"center", marginBottom:36 }}>
              <h1 style={{ fontFamily:"Instrument Serif, serif", fontSize:30, fontWeight:400, color:"#f0ede8", marginBottom:8, letterSpacing:"-0.015em" }}>Ingest an Asset</h1>
              <p style={{ fontSize:14, color:"rgba(240,237,232,0.38)", fontWeight:300 }}>Drop a file to begin vectorization and piracy analysis</p>
            </div>
            <label
              onDragOver={(e)=>{ e.preventDefault(); setDrag(true); }}
              onDragLeave={()=>setDrag(false)}
              onDrop={onDrop}
              style={{ display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", gap:12, height:230, border:`1px dashed ${drag?A:"rgba(255,255,255,0.11)"}`, borderRadius:14, background:drag?A_DIM:"rgba(255,255,255,0.015)", cursor:"pointer", transition:"all 0.2s ease" }}
            >
              <input type="file" onChange={(e)=>{ const f=e.target.files[0]; if(f) simulate(f.name); }} style={{ display:"none" }} accept=".mp4,.mov,.mp3,.pdf,.txt,.srt"/>
              <div style={{ width:42, height:42, borderRadius:10, background:"rgba(255,255,255,0.06)", display:"flex", alignItems:"center", justifyContent:"center" }}>
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M9 13V5M5 9l4-4 4 4" stroke="rgba(240,237,232,0.55)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/><path d="M2 15h14" stroke="rgba(240,237,232,0.28)" strokeWidth="1.5" strokeLinecap="round"/></svg>
              </div>
              <div style={{ textAlign:"center" }}>
                <div style={{ fontSize:14, color:"rgba(240,237,232,0.58)", marginBottom:4 }}>Drop file or <span style={{ color:A }}>browse</span></div>
                <div style={{ fontSize:12, color:"rgba(240,237,232,0.24)" }}>MP4, MOV, MP3, PDF, TXT, SRT</div>
              </div>
            </label>
          </>
        )}

        {phase === "uploading" && (
          <div style={{ textAlign:"center" }}>
            <div style={{ fontSize:13, color:"rgba(240,237,232,0.45)", marginBottom:26, fontWeight:300 }}>
              Vectorizing <span style={{ color:"#f0ede8" }}>{file}</span>
            </div>
            <div style={{ height:2, background:"rgba(255,255,255,0.08)", borderRadius:2, overflow:"hidden", marginBottom:10 }}>
              <div style={{ height:"100%", background:A, width:`${prog}%`, transition:"width 0.16s ease", borderRadius:2 }}/>
            </div>
            <div style={{ fontSize:12, color:"rgba(240,237,232,0.28)" }}>{Math.floor(prog)}% — Extracting embeddings</div>
          </div>
        )}

        {phase === "done" && (
          <div style={{ textAlign:"center" }} className="fade-up">
            <div style={{ width:52, height:52, borderRadius:"50%", background:"rgba(95,202,142,0.1)", border:"1px solid rgba(95,202,142,0.22)", display:"flex", alignItems:"center", justifyContent:"center", margin:"0 auto 18px" }}>
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none"><path d="M4 10l5 5 8-8" stroke="#5fca8e" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></svg>
            </div>
            <h2 style={{ fontFamily:"Instrument Serif, serif", fontSize:26, fontWeight:400, color:"#f0ede8", marginBottom:8 }}>Asset Ingested</h2>
            <p style={{ fontSize:13.5, color:"rgba(240,237,232,0.4)", marginBottom:26, fontWeight:300 }}>{file} is now in the analysis pipeline.</p>
            <div style={{ display:"flex", gap:10, justifyContent:"center" }}>
              <button className="btn-p" onClick={() => nav("dashboard")}>View in Dashboard</button>
              <button className="btn-o" onClick={() => { setPhase("idle"); setFile(""); }}>Ingest Another</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── DASHBOARD ──────────────────────────────────────────────── */
function Dashboard({ nav }) {
  const statusStyle = (s) => ({
    confirmed: { c:"#e87070", bg:"rgba(232,112,112,0.1)", b:"rgba(232,112,112,0.18)" },
    review:    { c:"#c8a96e", bg:"rgba(200,169,110,0.1)", b:"rgba(200,169,110,0.18)" },
    cleared:   { c:"rgba(240,237,232,0.3)", bg:"rgba(255,255,255,0.04)", b:"rgba(255,255,255,0.08)" },
  }[s]);
  const scoreColor = (s) => s>=0.85?"#e87070":s>=0.65?"#c8a96e":"rgba(240,237,232,0.32)";

  return (
    <div style={{ paddingTop:54, minHeight:"100vh" }}>
      <div style={{ maxWidth:1180, margin:"0 auto", padding:"48px 28px 60px" }}>
        {/* Header */}
        <div className="fade-up s1" style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-end", marginBottom:36 }}>
          <div>
            <div style={{ fontSize:11, color:"rgba(240,237,232,0.28)", marginBottom:5, letterSpacing:"0.08em", textTransform:"uppercase" }}>Command Center</div>
            <h1 style={{ fontFamily:"Instrument Serif, serif", fontSize:28, fontWeight:400, color:"#f0ede8", letterSpacing:"-0.015em" }}>Detection Feed</h1>
          </div>
          <div style={{ display:"flex", alignItems:"center", gap:7, fontSize:12, color:"rgba(240,237,232,0.32)", paddingBottom:4 }}>
            <div className="blink" style={{ width:6, height:6, borderRadius:"50%", background:"#5fca8e" }}/>
            2 active streams · Updated 4s ago
          </div>
        </div>

        {/* Stat cards */}
        <div className="fade-up s2" style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:12, marginBottom:24 }}>
          {[
            { l:"Active Streams", v:"2",    sub:"α + β running" },
            { l:"Detections Today", v:"47", sub:"+12 from yesterday" },
            { l:"Match Rate", v:"68%",      sub:"Of analyzed assets" },
            { l:"Queue Depth", v:"3",       sub:"Assets pending" },
          ].map((c,i)=>(
            <div key={i} className="card" style={{ padding:"18px 22px" }}>
              <div style={{ fontSize:12, color:"rgba(240,237,232,0.32)", marginBottom:8 }}>{c.l}</div>
              <div style={{ fontFamily:"Instrument Serif, serif", fontSize:30, color:"#f0ede8", marginBottom:3 }}>{c.v}</div>
              <div style={{ fontSize:12, color:"rgba(240,237,232,0.26)" }}>{c.sub}</div>
            </div>
          ))}
        </div>

        {/* Table */}
        <div className="card fade-up s3" style={{ overflow:"hidden" }}>
          <div style={{ padding:"16px 22px", borderBottom:"1px solid rgba(255,255,255,0.055)", display:"flex", justifyContent:"space-between", alignItems:"center" }}>
            <span style={{ fontSize:14, fontWeight:500, color:"#f0ede8" }}>Recent Detections</span>
            <span style={{ fontSize:12, color:"rgba(240,237,232,0.28)" }}>Last 6 events</span>
          </div>
          <div style={{ display:"grid", gridTemplateColumns:"1fr 108px 82px 104px 60px", padding:"9px 22px", borderBottom:"1px solid rgba(255,255,255,0.04)", fontSize:11, color:"rgba(240,237,232,0.22)", fontWeight:500, letterSpacing:"0.06em", textTransform:"uppercase" }}>
            <span>Asset</span><span>Score</span><span>Status</span><span>Stream</span><span>Time</span>
          </div>
          {detections.map((d,i)=>{
            const st = statusStyle(d.status);
            return (
              <div key={d.id} className="row-hover" style={{ display:"grid", gridTemplateColumns:"1fr 108px 82px 104px 60px", padding:"13px 22px", borderBottom:i<detections.length-1?"1px solid rgba(255,255,255,0.04)":"none", transition:"background 0.14s", cursor:"pointer" }}>
                <div>
                  <div style={{ fontSize:13, color:"#f0ede8", marginBottom:2 }}>{d.asset}</div>
                  <div style={{ fontSize:11, color:"rgba(240,237,232,0.22)" }}>{d.id}</div>
                </div>
                <div style={{ display:"flex", alignItems:"center" }}>
                  <span style={{ fontFamily:"Instrument Serif, serif", fontSize:16, color:scoreColor(d.score) }}>{d.score.toFixed(3)}</span>
                </div>
                <div style={{ display:"flex", alignItems:"center" }}>
                  <span style={{ fontSize:11, fontWeight:500, padding:"3px 8px", borderRadius:4, color:st.c, background:st.bg, border:`1px solid ${st.b}`, textTransform:"capitalize" }}>{d.status}</span>
                </div>
                <div style={{ display:"flex", alignItems:"center", fontSize:12, color:"rgba(240,237,232,0.32)" }}>{d.stream}</div>
                <div style={{ display:"flex", alignItems:"center", fontSize:12, color:"rgba(240,237,232,0.22)" }}>{d.time} ago</div>
              </div>
            );
          })}
        </div>

        <div style={{ marginTop:18, textAlign:"center" }}>
          <button className="btn-o" style={{ fontSize:13 }} onClick={() => nav("insights")}>Explore Deep Insights →</button>
        </div>
      </div>
    </div>
  );
}

/* ─── INSIGHTS ───────────────────────────────────────────────── */
function Insights() {
  const [open, setOpen] = useState({});
  const toggle = (k) => setOpen(p=>({ ...p, [k]:!p[k] }));

  const sections = [
    {
      key:"math",
      title:"Vector Similarity Mathematics",
      preview:"Euclidean & Cosine distance across 512-D and 384-D spaces.",
      body: (
        <div style={{ fontSize:13.5, color:"rgba(240,237,232,0.52)", lineHeight:1.78, fontWeight:300 }}>
          <p style={{ marginBottom:14 }}>Each visual frame is encoded into a <strong style={{ color:"#f0ede8", fontWeight:500 }}>512-dimensional vector</strong> via a fine-tuned vision transformer. Text transcripts produce <strong style={{ color:"#f0ede8", fontWeight:500 }}>384-dimensional embeddings</strong> via a sentence-level language model.</p>
          <div style={{ background:"rgba(255,255,255,0.03)", border:"1px solid rgba(255,255,255,0.07)", borderRadius:8, padding:"14px 18px", marginBottom:16, fontFamily:"monospace", fontSize:12 }}>
            <div style={{ color:"rgba(240,237,232,0.28)", marginBottom:6, fontSize:11 }}>{/* Cosine similarity */}</div>
            <div style={{ color:"#c8a96e" }}>cosine(A, B) = (A · B) / (‖A‖ × ‖B‖)</div>
            <div style={{ color:"rgba(240,237,232,0.28)", marginTop:10, marginBottom:6, fontSize:11 }}>{/* Euclidean distance */}</div>
            <div style={{ color:A }}>euclidean(A, B) = √Σ(Aᵢ − Bᵢ)²</div>
          </div>
          <p>Cosine similarity measures angular alignment — orientation-invariant, ideal for semantic matching. Euclidean captures absolute spatial proximity, catching near-exact structural copies. Both are computed per asset and fed into the fused scoring model.</p>
        </div>
      ),
    },
    {
      key:"fused",
      title:"Fused Scoring Model",
      preview:"How visual and text scores are weighted into a single match confidence.",
      body: (
        <div style={{ fontSize:13.5, color:"rgba(240,237,232,0.52)", lineHeight:1.78, fontWeight:300 }}>
          <p style={{ marginBottom:14 }}>Final match confidence blends visual and text modalities via a weighted sum, with α tuned per asset type:</p>
          <div style={{ background:"rgba(255,255,255,0.03)", border:"1px solid rgba(255,255,255,0.07)", borderRadius:8, padding:"14px 18px", marginBottom:18, fontFamily:"monospace", fontSize:12 }}>
            <div style={{ color:"#5fca8e" }}>S_fused = α · S_visual + (1−α) · S_text</div>
            <div style={{ color:"rgba(240,237,232,0.3)", marginTop:8, fontSize:11 }}>α = 0.65 for video · α = 0.0 for text-only assets</div>
          </div>
          {[["Visual weight (α)","65%",A],["Text weight (1−α)","35%","#c8a96e"],["Confirmation threshold","80%","#e87070"]].map(([l,p,c])=>(
            <div key={l} style={{ marginBottom:14 }}>
              <div style={{ display:"flex", justifyContent:"space-between", marginBottom:6, fontSize:12 }}>
                <span style={{ color:"rgba(240,237,232,0.45)" }}>{l}</span>
                <span style={{ color:c }}>{p}</span>
              </div>
              <div style={{ height:3, background:"rgba(255,255,255,0.07)", borderRadius:2, overflow:"hidden" }}>
                <div style={{ height:"100%", width:p, background:c, borderRadius:2, transition:"width 0.8s cubic-bezier(0.4,0,0.2,1)" }}/>
              </div>
            </div>
          ))}
        </div>
      ),
    },
    {
      key:"buffer",
      title:"Stream Buffer Architecture",
      preview:"Async worker model isolating ML computation from the FastAPI event loop.",
      body: (
        <div style={{ fontSize:13.5, color:"rgba(240,237,232,0.52)", lineHeight:1.78, fontWeight:300 }}>
          <p style={{ marginBottom:14 }}>
            <code style={{ background:"rgba(255,255,255,0.08)", padding:"1px 6px", borderRadius:3, color:"#f0ede8", fontSize:12 }}>buffer_service.py</code> maintains isolated async worker queues per stream. Heavy ML inference is offloaded to a thread pool executor, keeping the FastAPI event loop fully non-blocking.
          </p>
          <div style={{ display:"grid", gridTemplateColumns:"1fr auto 1fr auto 1fr", gap:8, alignItems:"center", marginBottom:16 }}>
            {["Ingest Queue","→","Worker Pool","→","Vector Store"].map((n,i)=>(
              <div key={i} style={{ textAlign:"center", ...(i%2===0?{ padding:"9px 10px", background:"rgba(255,255,255,0.04)", border:"1px solid rgba(255,255,255,0.07)", borderRadius:7, fontSize:12, color:"#f0ede8" }:{ color:A, fontSize:15 }) }}>{n}</div>
            ))}
          </div>
          <p>Streams α and β operate fully independently — a stall in one does not affect the other. Max buffer depth is configurable (default: 256 frames) with automatic backpressure signaling to the ingestion controller.</p>
        </div>
      ),
    },
    {
      key:"nexus",
      title:"Nexus Attribution Graph",
      preview:"Visual lineage connecting each detected copy to its exact golden source frame.",
      soon: true,
      body: (
        <div style={{ textAlign:"center", padding:"18px 0", fontSize:13.5, color:"rgba(240,237,232,0.35)", fontWeight:300 }}>
          <div style={{ width:42, height:42, borderRadius:"50%", background:A_DIM, border:`1px solid ${A_BORDER}`, display:"flex", alignItems:"center", justifyContent:"center", margin:"0 auto 14px" }}>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none"><circle cx="9" cy="9" r="2" fill={A}/><path d="M9 2v3M9 13v3M2 9h3M13 9h3" stroke={A} strokeWidth="1.4" strokeLinecap="round"/><path d="M4.22 4.22l2.12 2.12M11.66 11.66l2.12 2.12M11.66 4.22l2.12-2.12M4.22 11.66l-2.12 2.12" stroke={A} strokeWidth="1.2" strokeLinecap="round" opacity="0.5"/></svg>
          </div>
          <p>The Nexus Graph using <strong style={{ color:"rgba(240,237,232,0.5)", fontWeight:500 }}>React Flow</strong> is in development.</p>
          <p style={{ marginTop:6 }}>It will visualize exact attribution lineage between pirated assets and their golden source frames.</p>
        </div>
      ),
    },
  ];

  return (
    <div style={{ paddingTop:54, minHeight:"100vh" }}>
      <div style={{ maxWidth:780, margin:"0 auto", padding:"48px 28px 60px" }}>
        <div className="fade-up s1" style={{ marginBottom:38 }}>
          <div style={{ fontSize:11, color:"rgba(240,237,232,0.28)", marginBottom:5, letterSpacing:"0.08em", textTransform:"uppercase" }}>Insights</div>
          <h1 style={{ fontFamily:"Instrument Serif, serif", fontSize:28, fontWeight:400, color:"#f0ede8", letterSpacing:"-0.015em", marginBottom:8 }}>System Intelligence</h1>
          <p style={{ fontSize:14, color:"rgba(240,237,232,0.38)", fontWeight:300, maxWidth:460 }}>Deep technical breakdowns of the algorithms powering Overwatch. Click any section to expand.</p>
        </div>

        <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
          {sections.map((s,i)=>(
            <div key={s.key} className={`card fade-up s${i+2}`} style={{ overflow:"hidden" }}>
              <button
                className="expand-btn"
                onClick={() => toggle(s.key)}
                style={{ width:"100%", padding:"18px 22px", display:"flex", alignItems:"center", justifyContent:"space-between", background:"none", textAlign:"left", transition:"background 0.14s" }}
              >
                <div>
                  <div style={{ display:"flex", alignItems:"center", gap:10, marginBottom:4 }}>
                    <span style={{ fontSize:14, fontWeight:500, color:"#f0ede8" }}>{s.title}</span>
                    {s.soon && <span style={{ fontSize:10, color:A, background:A_DIM, border:`1px solid ${A_BORDER}`, padding:"2px 7px", borderRadius:4, fontWeight:500 }}>Soon</span>}
                  </div>
                  <div style={{ fontSize:12, color:"rgba(240,237,232,0.33)", fontWeight:300 }}>{s.preview}</div>
                </div>
                <div style={{ width:24, height:24, borderRadius:6, background:"rgba(255,255,255,0.06)", display:"flex", alignItems:"center", justifyContent:"center", flexShrink:0, marginLeft:16, transition:"transform 0.2s ease", transform:open[s.key]?"rotate(180deg)":"rotate(0deg)" }}>
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none"><path d="M2 4l3 3 3-3" stroke="rgba(240,237,232,0.45)" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg>
                </div>
              </button>
              {open[s.key] && (
                <div className="slide-down" style={{ padding:"0 22px 22px", borderTop:"1px solid rgba(255,255,255,0.055)", paddingTop:18 }}>
                  {s.body}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ─── APP ────────────────────────────────────────────────────── */
export default function App() {
  const [page, setPage] = useState("landing");
  const nav = (p) => setPage(p);
  const noNav = page === "upload";

  return (
    <div style={{ background:"#09090b", minHeight:"100vh" }}>
      <GlobalStyles/>
      <div id="grain"/>
      {!noNav && <Navbar page={page} nav={nav}/>}
      <div key={page} className="fade-in">
        {page === "landing"   && <Landing   nav={nav}/>}
        {page === "upload"    && <Upload    nav={nav}/>}
        {page === "dashboard" && <Dashboard nav={nav}/>}
        {page === "insights"  && <Insights/>}
      </div>
    </div>
  );
}