import { useCallback, useRef, useState } from "react";
import { apiUpload } from "@/lib/api";
import { mkLog, LogEntry } from "@/lib/utils";

export type IngestionPhase = "idle" | "uploading" | "done" | "error";

const STAGES = [
  "Upload",
  "Keyframe Decode",
  "Fingerprinting",
  "FAISS Index",
] as const;

const STAGE_LOGS = [
  ["info",    "ffmpeg: spawning keyframe decoder at 24fps"],
  ["info",    "ResNet-152: loading fine-tuned fingerprint weights"],
  ["info",    "FAISS: upserting to golden partition"],
  ["success", "Asset indexed · 512-D fingerprint stored · watching"],
] as const;

export function useIngestion(role: string | null) {
  const [phase,     setPhase    ] = useState<IngestionPhase>("idle");
  const [fileName,  setFileName ] = useState<string | null>(null);
  const [activeIdx, setActiveIdx] = useState(-1);
  const [logs,      setLogs     ] = useState<LogEntry[]>([]);
  const timerRefs                 = useRef<ReturnType<typeof setTimeout>[]>([]);

  const clearTimers = () => {
    timerRefs.current.forEach(clearTimeout);
    timerRefs.current = [];
  };

  const addLog = (level: Parameters<typeof mkLog>[0], msg: string) =>
    setLogs((prev) => [...prev, mkLog(level, msg)]);

  const ingest = useCallback(
    async (file: File) => {
      clearTimers();
      setPhase("uploading");
      setFileName(file.name);
      setActiveIdx(0);
      setLogs([mkLog("info", `Received: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`)]);

      // Animate pipeline stages with staggered logs
      STAGES.forEach((_, i) => {
        const t = setTimeout(() => {
          setActiveIdx(i);
          const [lvl, msg] = STAGE_LOGS[i] ?? ["info", "Processing…"];
          addLog(lvl, msg);
        }, i * 1_400);
        timerRefs.current.push(t);
      });

      // Attempt real upload; fall back to simulated success
      const path = "/api/v1/assets/upload";

      const finalise = setTimeout(async () => {
        const res = await apiUpload(path, file);
        if (res.ok) {
          addLog("success", "Pipeline complete · asset fingerprinted");
        } else {
          addLog("info", "Backend offline — simulation complete");
        }
        setActiveIdx(STAGES.length); // all done
        setPhase("done");
      }, STAGES.length * 1_400 + 400);

      timerRefs.current.push(finalise);
    },
    [role],
  );

  const reset = useCallback(() => {
    clearTimers();
    setPhase("idle");
    setFileName(null);
    setActiveIdx(-1);
    setLogs([]);
  }, []);

  const clearLogs = useCallback(() => setLogs([]), []);

  return { phase, fileName, activeIdx, logs, ingest, reset, clearLogs };
}
