export type UserRole = "PRODUCER" | "AUDITOR";

export type AssetStatus = "processing" | "completed" | "failed";

export type AssetStatusResponse = {
  asset_id: string;
  filename: string;
  is_golden: boolean;
  status: AssetStatus;
  frame_count: number;
  created_at: string;
  trace_id: string;
};

export type SimilarityVerdict = "PIRACY_DETECTED" | "SUSPICIOUS" | "CLEAN" | "SAFE";

export type SimilarityResultResponse = {
  suspect_asset_id: string;
  golden_asset_id: string | null;
  matched_timestamp: number | null;
  visual_score: number;
  text_score: number;
  fused_score: number;
  verdict: SimilarityVerdict;
  trace_id: string;
};

export type AudioSegment = {
  start: number;
  end: number;
  text: string;
};

export type AudioSummary = {
  transcript: AudioSegment[];
  full_script: string;
};

export type ProducerAnalytics = {
  assetId: string;
  filename: string;
  totalFrames: number;
  visionNodeLatencyMs: number;
  contextNodeLatencyMs: number;
  successfulExtractions: number;
  databaseVectorsSynced: number;
};

export type AuditorForensics = {
  assetId: string;
  filename: string;
  fusedScore: number;
  visualScore: number;
  audioScore: number;
  verdict: SimilarityVerdict;
  matchedAssetId: string | null;
  matchedTimestamp: number | null;
};

// ── Nexus Graph Data Architecture ───────────────────────────────────────────

export type NexusNodeType = "suspect" | "golden";
export type NexusModality = "visual" | "audio" | "text";

export type NexusGraphNode = {
  id: string;
  label: string;
  type: NexusNodeType;
  score: number;
};

export type NexusGraphLink = {
  source: string;
  target: string;
  strength: number;
  modality: NexusModality;
};

export type NexusDTWPoint = {
  suspectTime: number;
  goldenTime: number;
  distance: number;
};

export type NexusGraphData = {
  nodes: NexusGraphNode[];
  links: NexusGraphLink[];
  dtw: Record<string, NexusDTWPoint[]>;
};
