export type LogLevel = "info" | "warn" | "error" | "success";

export type LogEntry = {
  id:      string;
  ts:      string;   // "14:02:08.412"
  level:   LogLevel;
  message: string;
};

/** Tailwind class merger (minimal — no clsx dep required) */
export function cn(...classes: (string | undefined | false | null)[]): string {
  return classes.filter(Boolean).join(" ");
}

/** Current time as HH:MM:SS.mmm */
export function timestamp(): string {
  const d = new Date();
  const pad = (n: number, z = 2) => String(n).padStart(z, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}.${pad(d.getMilliseconds(), 3)}`;
}

let _seq = 0;
/** Construct a LogEntry */
export function mkLog(level: LogLevel, message: string): LogEntry {
  return { id: `log-${++_seq}-${Date.now()}`, ts: timestamp(), level, message };
}
