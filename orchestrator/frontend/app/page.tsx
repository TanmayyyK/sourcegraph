"use client";
import React, { useState } from 'react';

const HOST_NODE = { name: "Tanmay (M4 Host)", ip: "localhost", port: "8000" };

const WORKER_NODES = [
  { name: "Yogesh (M2)", ip: "100.103.180.14", port: "8003" },
  { name: "Rohit (3050)", ip: "100.119.250.125", port: "8001" },
  { name: "Yug (2050)", ip: "100.115.89.72", port: "8002" },
];

export default function NetworkTest() {
  const [statuses, setStatuses] = useState<any>({});

  const checkPing = async (node: any) => {
    setStatuses((prev: any) => ({ ...prev, [node.name]: "PENDING..." }));
    try {
      // Use a standard fetch. Worker nodes use no-cors if they don't have middleware yet.
      const res = await fetch(`http://${node.ip}:${node.port}/`, { 
        method: 'GET',
        mode: node.ip === 'localhost' ? 'cors' : 'no-cors' 
      });
      setStatuses((prev: any) => ({ ...prev, [node.name]: "ONLINE" }));
    } catch (err) {
      setStatuses((prev: any) => ({ ...prev, [node.name]: "OFFLINE" }));
    }
  };

  const checkAll = () => {
    checkPing(HOST_NODE);
    WORKER_NODES.forEach(checkPing);
  };

  return (
    <div className="p-10 bg-black min-h-screen text-white font-mono">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-end mb-8 border-b border-emerald-500/30 pb-4">
          <div>
            <h1 className="text-3xl font-bold text-emerald-400 italic">SOURCEGRAPH // COMMAND</h1>
            <p className="text-slate-400 text-xs mt-1">Distributed Vector Ingestion Network</p>
          </div>
          <button 
            onClick={checkAll}
            className="bg-emerald-600 hover:bg-emerald-500 text-black font-bold py-2 px-6 rounded-sm transition-all"
          >
            PING ALL SYSTEMS
          </button>
        </div>

        {/* HOST SECTION */}
        <div className="mb-10">
          <h2 className="text-sm text-slate-500 mb-3 uppercase tracking-widest">Central Orchestrator</h2>
          <NodeRow node={HOST_NODE} status={statuses[HOST_NODE.name]} onPing={() => checkPing(HOST_NODE)} isHost />
        </div>

        {/* WORKERS SECTION */}
        <div>
          <h2 className="text-sm text-slate-500 mb-3 uppercase tracking-widest">Worker Nodes (Tailscale)</h2>
          <div className="grid gap-3">
            {WORKER_NODES.map(node => (
              <NodeRow key={node.name} node={node} status={statuses[node.name]} onPing={() => checkPing(node)} />
            ))}
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
    <div className={`flex items-center justify-between p-4 rounded border ${
      isHost ? 'bg-emerald-950/20 border-emerald-500/50' : 'bg-slate-900 border-slate-800'
    }`}>
      <div>
        <p className={`font-bold ${isHost ? 'text-emerald-400' : 'text-slate-200'}`}>
          {node.name} {isHost && <span className="text-[10px] ml-2 px-1 border border-emerald-400">MASTER</span>}
        </p>
        <p className="text-xs text-slate-500">{node.ip}:{node.port}</p>
      </div>
      
      <div className="flex items-center gap-6">
        <button onClick={onPing} className="text-[10px] text-slate-400 hover:text-white underline">RE-SCAN</button>
        <div className="w-24 text-right">
          <span className={`text-xs font-black ${
            isOnline ? 'text-emerald-400' : isPending ? 'text-yellow-500' : status === "OFFLINE" ? 'text-red-500' : 'text-slate-700'
          }`}>
            {status || "READY"}
          </span>
        </div>
      </div>
    </div>
  );
}