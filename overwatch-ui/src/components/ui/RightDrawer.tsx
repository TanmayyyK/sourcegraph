import { motion, AnimatePresence } from "framer-motion";
import { X, Network, FileVideo, FileAudio, FileText, ShieldCheck, AlertTriangle } from "lucide-react";
import { Asset } from "@/lib/adapters";

type Props = {
  asset:   Asset;
  onClose: () => void;
  onNexus: () => void;
};

const FILE_ICONS = {
  video: FileVideo,
  audio: FileAudio,
  text:  FileText,
};

function ScoreBar({ label, value }: { label: string; value: number }) {
  const pct   = Math.round(value * 100);
  const color = value > 0.85 ? "#34d399" : value > 0.5 ? "#fb923c" : "#f87171";
  return (
    <div className="mb-3">
      <div className="mb-1.5 flex items-center justify-between text-[12px]">
        <span className="text-zinc-400">{label}</span>
        <span className="font-mono font-semibold" style={{ color }}>{pct}%</span>
      </div>
      <div className="h-[3px] overflow-hidden rounded-full bg-white/[0.06]">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.6, ease: "easeOut", delay: 0.1 }}
          className="h-full rounded-full"
          style={{ background: color }}
        />
      </div>
    </div>
  );
}

export default function RightDrawer({ asset, onClose, onNexus }: Props) {
  const FileIcon = FILE_ICONS[asset.type] ?? FileVideo;
  const isMatch  = asset.score !== null && asset.score > 0.85;

  return (
    <AnimatePresence>
      <motion.div
        key="drawer-backdrop"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[60]"
        style={{ background: "rgba(9,9,11,0.55)", backdropFilter: "blur(4px)" }}
        onClick={(e) => e.target === e.currentTarget && onClose()}
      />

      <motion.aside
        key="drawer-panel"
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ type: "spring", stiffness: 300, damping: 32 }}
        className="fixed inset-y-0 right-0 z-[61] flex w-[360px] flex-col border-l border-white/[0.06] bg-zinc-950/95 shadow-[-40px_0_80px_rgba(0,0,0,0.5)] backdrop-blur-2xl"
      >
        {/* Header */}
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-white/[0.05] px-5">
          <div className="min-w-0">
            <p className="text-[10.5px] font-medium uppercase tracking-[0.13em] text-zinc-600">Asset Detail</p>
            <p className="truncate font-mono text-[13px] font-medium text-zinc-200">{asset.name}</p>
          </div>
          <button
            onClick={onClose}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-white/[0.06] bg-white/[0.02] text-zinc-400 transition-colors hover:bg-white/[0.05] hover:text-zinc-200"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto scrollbar-sleek px-5 py-5">

          {/* Stream + status badges */}
          <div className="mb-5 flex gap-2">
            <span
              className={`rounded-md border px-2.5 py-1 text-[11px] font-medium ${
                asset.stream === "Golden Library"
                  ? "border-emerald-500/20 bg-emerald-500/[0.07] text-emerald-300"
                  : "border-amber-500/20 bg-amber-500/[0.07] text-amber-300"
              }`}
            >
              {asset.stream}
            </span>
            <span
              className={`rounded-md border px-2.5 py-1 text-[11px] font-medium ${
                asset.status === "completed"
                  ? "border-white/[0.07] bg-white/[0.02] text-zinc-400"
                  : asset.status === "failed"
                  ? "border-rose-500/20 bg-rose-500/[0.06] text-rose-300"
                  : "border-blue-500/20 bg-blue-500/[0.06] text-blue-300"
              }`}
            >
              {asset.status}
            </span>
          </div>

          {/* File info card */}
          <div className="mb-5 flex items-center gap-3 rounded-[10px] border border-white/[0.05] bg-white/[0.02] p-3.5">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-white/[0.04]">
              <FileIcon className="h-4 w-4 text-zinc-400" />
            </div>
            <div className="min-w-0">
              <p className="truncate font-mono text-[12.5px] text-zinc-200">{asset.name}</p>
              <p className="mt-0.5 text-[11.5px] capitalize text-zinc-500">{asset.type} · ingested {asset.ago} ago</p>
            </div>
          </div>

          {/* Verdict banner */}
          {asset.verdict && (
            <div className={`mb-5 flex items-center gap-3 rounded-[10px] border p-3.5 ${
              isMatch
                ? "border-rose-500/20 bg-rose-500/[0.06]"
                : "border-emerald-500/20 bg-emerald-500/[0.06]"
            }`}>
              {isMatch
                ? <AlertTriangle className="h-4 w-4 shrink-0 text-rose-300" />
                : <ShieldCheck className="h-4 w-4 shrink-0 text-emerald-300" />}
              <div>
                <p className={`text-[13px] font-medium ${isMatch ? "text-rose-200" : "text-emerald-200"}`}>
                  {asset.verdict}
                </p>
              </div>
            </div>
          )}

          {/* Score bars */}
          {asset.score !== null && (
            <div className="mb-5">
              <p className="mb-3 text-[10.5px] font-medium uppercase tracking-[0.13em] text-zinc-600">
                Similarity Scores
              </p>
              <div className="rounded-[10px] border border-white/[0.05] bg-white/[0.02] p-4">
                <ScoreBar label="Fused Score"   value={asset.score}          />
                <ScoreBar label="Visual"        value={asset.visual  ?? 0}   />
                <ScoreBar label="Text / Audio"  value={asset.text    ?? 0}   />
              </div>
            </div>
          )}

          {/* Metadata */}
          <div className="mb-5">
            <p className="mb-3 text-[10.5px] font-medium uppercase tracking-[0.13em] text-zinc-600">
              Metadata
            </p>
            <div className="rounded-[10px] border border-white/[0.05] bg-white/[0.02]">
              {[
                ["Asset ID",  asset.id],
                ["Stream",    asset.stream],
                ["Type",      asset.type],
                ["Frames",    asset.frames ? String(asset.frames) : "—"],
                ["Ingested",  `${asset.ago} ago`],
              ].map(([k, v]) => (
                <div key={k} className="flex items-center justify-between border-b border-white/[0.04] px-4 py-2.5 last:border-none">
                  <span className="text-[12px] text-zinc-500">{k}</span>
                  <span className="font-mono text-[12px] text-zinc-300">{v}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Nexus CTA */}
          {asset.status === "completed" && (
            <motion.button
              onClick={onNexus}
              whileHover={{ y: -1 }}
              whileTap={{ scale: 0.98 }}
              className="flex w-full items-center justify-center gap-2 rounded-[10px] border border-white/[0.08] bg-white/[0.03] py-3 text-[13px] font-medium text-zinc-300 transition-colors hover:border-blue-400/30 hover:bg-blue-400/[0.06] hover:text-blue-200"
            >
              <Network className="h-3.5 w-3.5" />
              Open Nexus Attribution Graph
            </motion.button>
          )}
        </div>
      </motion.aside>
    </AnimatePresence>
  );
}
