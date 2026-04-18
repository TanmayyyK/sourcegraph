"use client";
import React, { useState, useEffect } from 'react';

const HOST_NODE = { name: "Tanmay (M4 Host)", ip: "localhost", port: "8000" };

const WORKER_NODES = [
  { name: "Yogesh (M2)", ip: "100.103.180.14", port: "8003" },
  { name: "Rohit (3050)", ip: "100.119.250.125", port: "8001" },
  { name: "Yug (2050)", ip: "100.115.89.72", port: "8002" },
];

export default function SourceGraphDashboard() {
  const [statuses, setStatuses] = useState<any>({});
  const [logs, setLogs] = useState<any[]>([]);
  const [isUploading, setIsUploading] = useState(false);

  // 1. PING LOGIC
  const checkPing = async (node: any) => {
    setStatuses((prev: any) => ({ ...prev, [node.name]: "PENDING..." }));
    try {
      await fetch(`http://${node.ip}:${node.port}/`, { method: 'GET' });
      setStatuses((prev: any) => ({ ...prev, [node.name]: "ONLINE" }));
    } catch (err) {
      setStatuses((prev: any) => ({ ...prev, [node.name]: "OFFLINE" }));
    }
  };

  const checkAll = () => {
    checkPing(HOST_NODE);
    WORKER_NODES.forEach(checkPing);
  };

  // 2. MASTER FILE INGEST (Sends actual file to M2)
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append("video", file);

    try {
      const res = await fetch(`http://${WORKER_NODES[0].ip}:${WORKER_NODES[0].port}/extract`, {
        method: 'POST',
        body: formData,
      });
      if (res.ok) alert(`🚀 ${file.name} sent to Yogesh's M2!`);
    } catch (err) {
      alert("❌ M2 Extractor Unreachable over Tailscale.");
    }
    setIsUploading(false);
  };

  // 3. LIVE FEED POLLING (From M4 Backend)
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`http://localhost:8000/feed`);
        const data = await res.json();
        setLogs(data.reverse());
      } catch (e) { /* Backend silent */ }
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-8 bg-black min-h-screen text-white font-mono selection:bg-emerald-500 selection:text-black">
      <div className="max-w-5xl mx-auto space-y-6">
        
        {/* HEADER */}
        <div className="flex justify-between items-end border-b border-emerald-500/30 pb-6">
          <div>
            <h1 className="text-4xl font-black text-emerald-400 tracking-tighter italic">SOURCEGRAPH // COMMAND</h1>
            <p className="text-slate-500 text-[10px] mt-1 tracking-widest uppercase">Distributed Media Pipeline Control</p>
          </div>
          <button onClick={checkAll} className="border border-emerald-500/50 hover:bg-emerald-500/10 text-emerald-500 text-[10px] px-4 py-2 uppercase">Refresh Network</button>
        </div>

        {/* MASTER UPLOAD ZONE */}
        <div className="group relative border-2 border-dashed border-emerald-500/20 bg-emerald-500/5 p-10 rounded-sm flex flex-col items-center justify-center transition-all hover:border-emerald-500/60">
          <input type="file" id="master-file" className="hidden" onChange={handleFileUpload} />
          <div className="text-center space-y-4">
            <div className="inline-block p-4 bg-emerald-500/10 rounded-full group-hover:scale-110 transition-transform">
              <svg className="w-8 h-8 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
            </div>
            <div>
              <p className="text-emerald-400 font-bold tracking-widest text-sm uppercase">Drop Source Media</p>
              <p className="text-slate-500 text-[10px] mt-1 uppercase tracking-tighter">Direct Path: Tanmay M4 → Yogesh M2 (FFmpeg)</p>
            </div>
            <label htmlFor="master-file" className={`inline-block cursor-pointer px-8 py-2 text-xs font-bold transition-all ${isUploading ? 'bg-slate-800 text-slate-500' : 'bg-emerald-500 text-black hover:bg-white'}`}>
              {isUploading ? "UPLOADING..." : "SELECT FILE"}
            </label>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* SYSTEM TOPOLOGY */}
          <div className="lg:col-span-1 space-y-4">
            <h2 className="text-[10px] text-slate-500 uppercase tracking-widest px-1">Network Mesh</h2>
            <NodeRow node={HOST_NODE} status={statuses[HOST_NODE.name]} onPing={() => checkPing(HOST_NODE)} isHost />
            {WORKER_NODES.map(node => (
              <NodeRow key={node.name} node={node} status={statuses[node.name]} onPing={() => checkPing(node)} />
            ))}
          </div>

          {/* INGESTION FEED */}
          <div className="lg:col-span-2 flex flex-col h-[450px] bg-slate-900/40 border border-slate-800 rounded-sm">
            <div className="p-3 border-b border-slate-800 flex justify-between items-center bg-slate-900/60">
              <span className="text-[10px] text-emerald-400 font-bold uppercase tracking-widest">Global Ingestion Log</span>
              <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-2">
              {logs.length === 0 ? (
                <div className="text-slate-700 text-[10px] text-center mt-20 uppercase tracking-widest">Awaiting GPU data packets...</div>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className="flex gap-4 text-[10px] border-l border-emerald-500/30 pl-3 py-1 items-center">
                    <span className="text-slate-500 font-bold">{log.time}</span>
                    <span className="bg-emerald-500/10 text-emerald-400 px-1 font-black">INGEST</span>
                    <span className="text-slate-300 truncate w-32">{log.video}</span>
                    <span className={log.has_visual ? "text-emerald-500" : "text-slate-700"}>VISUAL_DATA</span>
                    <span className={log.has_text ? "text-blue-400" : "text-slate-700"}>TEXT_DATA</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function NodeRow({ node, status, onPing, isHost = false }: any) {
  const isOnline = status === "ONLINE";
  const isPending = status === "PENDING...";
  return (
    <div className={`flex items-center justify-between p-4 rounded-sm border transition-all ${isHost ? 'bg-emerald-950/20 border-emerald-500/40' : 'bg-slate-900/60 border-slate-800'}`}>
      <div className="overflow-hidden">
        <p className={`font-bold text-xs truncate ${isHost ? 'text-emerald-400' : 'text-slate-200'}`}>{node.name}</p>
        <p className="text-[9px] text-slate-600 mt-1 uppercase">{node.ip}:{node.port}</p>
      </div>
      <div className="flex flex-col items-end gap-1">
        <span className={`text-[10px] font-black ${isOnline ? 'text-emerald-400' : isPending ? 'text-yellow-500' : status === "OFFLINE" ? 'text-red-600' : 'text-slate-800'}`}>{status || "READY"}</span>
        <button onClick={onPing} className="text-[8px] text-slate-500 hover:text-emerald-400 uppercase tracking-tighter">Rescan</button>
      </div>
    </div>
  );
}