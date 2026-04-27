export type AssetStream = "Golden Library" | "Suspect Queue";
export type AssetStatus = "pending" | "processing" | "completed" | "failed";
export type AssetType   = "video" | "audio" | "text";

export type Asset = {
  id:      string;
  name:    string;
  stream:  AssetStream;
  status:  AssetStatus;
  type:    AssetType;
  score:   number | null;
  verdict: string | null;
  visual:  number | null;
  text:    number | null;
  frames:  number | null;
  ago:     string;           // "2m", "14s" etc.
  raw:     unknown;
};

/** ISO timestamp → relative "Xs / Xm / Xh" */
export function formatAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const s    = Math.floor(diff / 1000);
  if (s < 60)   return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  return `${Math.floor(s / 3600)}h`;
}

/** Map raw API entry → Asset */
export function adaptEntry(raw: Record<string, unknown>): Asset {
  const stream: AssetStream =
    (raw.stream as string) === "golden" ? "Golden Library" : "Suspect Queue";

  const ext = ((raw.filename as string) ?? "").split(".").pop()?.toLowerCase() ?? "";
  const type: AssetType =
    ["mp4", "mov", "mkv"].includes(ext) ? "video" :
    ["mp3", "wav"].includes(ext)        ? "audio" : "text";

  return {
    id:      String(raw.id ?? raw.asset_id ?? ""),
    name:    String(raw.filename ?? raw.name ?? "unknown"),
    stream,
    status:  (raw.status as AssetStatus) ?? "pending",
    type,
    score:   raw.fused_score != null ? Number(raw.fused_score) : null,
    verdict: raw.verdict ? String(raw.verdict) : null,
    visual:  raw.visual_score != null ? Number(raw.visual_score) : null,
    text:    raw.text_score   != null ? Number(raw.text_score)   : null,
    frames:  raw.frames       != null ? Number(raw.frames)       : null,
    ago:     formatAgo(String(raw.created_at ?? raw.ingested_at ?? new Date().toISOString())),
    raw,
  };
}

/** Generate mock assets for offline / demo mode */
export function mockAssets(): Asset[] {
  const now = new Date();
  const t = (minusMs: number) => new Date(now.getTime() - minusMs).toISOString();

  return [
    {
      id: "a1", name: "cinema_reel_2024.mp4", stream: "Golden Library", status: "completed",
      type: "video", score: null, verdict: null, visual: null, text: null, frames: 248,
      ago: "12m", raw: {},
    },
    {
      id: "a2", name: "suspect_copy_final.mp4", stream: "Suspect Queue", status: "completed",
      type: "video", score: 0.994, verdict: "HIGH RISK — 99.4% match to golden source",
      visual: 0.998, text: 0.91, frames: 241, ago: "8m", raw: {},
    },
    {
      id: "a3", name: "broadcast_clip_edited.mov", stream: "Suspect Queue", status: "completed",
      type: "video", score: 0.62, verdict: "MODERATE — partial similarity detected",
      visual: 0.65, text: 0.58, frames: 180, ago: "3m", raw: {},
    },
    {
      id: "a4", name: "original_soundtrack.wav", stream: "Golden Library", status: "completed",
      type: "audio", score: null, verdict: null, visual: null, text: null, frames: null,
      ago: "1h", raw: {},
    },
    {
      id: "a5", name: "uploading_now.mp4", stream: "Suspect Queue", status: "processing",
      type: "video", score: null, verdict: null, visual: null, text: null, frames: null,
      ago: "12s", raw: {},
    },
  ];
}
