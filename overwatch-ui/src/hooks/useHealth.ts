import { useEffect, useState } from "react";
import { apiFetch, HealthResponse } from "@/lib/api";

export function useHealth() {
  const [connected, setConnected] = useState(false);
  const [health,    setHealth   ] = useState<HealthResponse | null>(null);

  useEffect(() => {
    let alive = true;

    const check = async () => {
      const res = await apiFetch<HealthResponse>("/");
      if (!alive) return;
      if (res.ok) {
        setConnected(true);
        setHealth(res.data);
      } else {
        setConnected(false);
        setHealth(null);
      }
    };

    check();
    const id = setInterval(check, 5_000);
    return () => { alive = false; clearInterval(id); };
  }, []);

  return { connected, health };
}
