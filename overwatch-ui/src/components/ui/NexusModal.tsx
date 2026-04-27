import { motion, AnimatePresence } from "framer-motion";
import { X, Network } from "lucide-react";
import { Asset } from "@/lib/adapters";

type Props = {
  asset:   Asset;
  onClose: () => void;
};

// Minimal SVG nexus graph — nodes + animated edges
function NexusGraph({ assetName }: { assetName: string }) {
  const nodes = [
    { id: "golden", x: 120, y: 100, label: "Golden\nSource", color: "#34d399", ring: "rgba(52,211,153,0.3)" },
    { id: "suspect", x: 380, y: 100, label: assetName.slice(0, 14), color: "#fb923c", ring: "rgba(251,146,60,0.3)" },
    { id: "frame1", x: 80,  y: 230, label: "Frame 48",  color: "#60a5fa", ring: "rgba(96,165,250,0.2)" },
    { id: "frame2", x: 200, y: 240, label: "Frame 112", color: "#60a5fa", ring: "rgba(96,165,250,0.2)" },
    { id: "frame3", x: 340, y: 230, label: "Frame 51",  color: "#818cf8", ring: "rgba(129,140,248,0.2)" },
    { id: "score",  x: 240, y: 350, label: "99.4%\nMatch",   color: "#f87171", ring: "rgba(248,113,113,0.3)" },
  ];
  const edges = [
    ["golden","frame1"],["golden","frame2"],["suspect","frame3"],
    ["frame1","score"],["frame2","score"],["frame3","score"],
  ];

  return (
    <svg viewBox="0 0 460 420" className="h-full w-full" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <marker id="arrow" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="rgba(255,255,255,0.15)" />
        </marker>
      </defs>
      {edges.map(([a, b], i) => {
        const na = nodes.find(n => n.id === a)!;
        const nb = nodes.find(n => n.id === b)!;
        return (
          <motion.line
            key={i}
            x1={na.x} y1={na.y} x2={nb.x} y2={nb.y}
            stroke="rgba(255,255,255,0.12)" strokeWidth="1"
            markerEnd="url(#arrow)"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.2 + i * 0.08 }}
          />
        );
      })}
      {nodes.map((node, i) => (
        <motion.g
          key={node.id}
          initial={{ opacity: 0, scale: 0.5 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: "spring", stiffness: 260, damping: 22, delay: i * 0.07 }}
          style={{ transformOrigin: `${node.x}px ${node.y}px` }}
        >
          <circle cx={node.x} cy={node.y} r={28} fill="rgba(0,0,0,0.5)" stroke={node.ring} strokeWidth="1" />
          <circle cx={node.x} cy={node.y} r={20} fill={`${node.color}18`} stroke={node.color} strokeWidth="1.5" />
          {node.label.split("\n").map((line, li) => (
            <text
              key={li}
              x={node.x} y={node.y + (node.label.includes("\n") ? (li - 0.3) * 11 : 0)}
              textAnchor="middle" dominantBaseline="middle"
              fontSize="9" fontFamily="monospace" fill={node.color} fontWeight="500"
            >{line}</text>
          ))}
        </motion.g>
      ))}
    </svg>
  );
}

export default function NexusModal({ asset, onClose }: Props) {
  return (
    <AnimatePresence>
      <motion.div
        key="nexus-backdrop"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[80] flex items-center justify-center p-6"
        style={{ background: "rgba(9,9,11,0.82)", backdropFilter: "blur(10px)" }}
        onClick={(e) => e.target === e.currentTarget && onClose()}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.93, y: 12 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.93, y: 12 }}
          transition={{ type: "spring", stiffness: 280, damping: 28 }}
          className="flex w-full max-w-[560px] flex-col rounded-[14px] border border-white/[0.07] bg-zinc-950/95 shadow-[0_0_80px_rgba(0,0,0,0.7)] backdrop-blur-2xl"
          style={{ height: "auto", maxHeight: "80vh" }}
        >
          <div className="flex h-14 shrink-0 items-center justify-between border-b border-white/[0.05] px-5">
            <div className="flex items-center gap-2.5">
              <Network className="h-3.5 w-3.5 text-blue-300" />
              <p className="text-[13.5px] font-medium text-zinc-200">Nexus Attribution Graph</p>
              <span className="rounded-md border border-white/[0.06] bg-white/[0.02] px-1.5 py-0.5 font-mono text-[10px] text-zinc-500">
                {asset.name.slice(0, 20)}
              </span>
            </div>
            <button
              onClick={onClose}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.06] bg-white/[0.02] text-zinc-400 hover:bg-white/[0.05] hover:text-zinc-200"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="flex-1 p-4" style={{ height: 380 }}>
            <NexusGraph assetName={asset.name} />
          </div>

          <div className="flex items-center gap-4 border-t border-white/[0.05] px-5 py-3">
            {[
              { color: "#34d399", label: "Golden Source" },
              { color: "#fb923c", label: "Suspect File"  },
              { color: "#60a5fa", label: "Frame Match"   },
              { color: "#f87171", label: "Verdict Node"  },
            ].map(({ color, label }) => (
              <div key={label} className="flex items-center gap-1.5 text-[11px] text-zinc-500">
                <span className="h-2 w-2 rounded-full" style={{ background: color }} />
                {label}
              </div>
            ))}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
