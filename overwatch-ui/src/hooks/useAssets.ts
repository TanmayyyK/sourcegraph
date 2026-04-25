import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import { Asset, adaptEntry, mockAssets } from "@/lib/adapters";

export function useAssets(connected: boolean) {
  const [assets, setAssets] = useState<Asset[]>([]);

  const fetchAssets = useCallback(async () => {
    if (!connected) {
      // Serve mock data when offline so the UI is always demonstrable
      setAssets(mockAssets());
      return;
    }
    const res = await apiFetch<Record<string, unknown>[]>("/api/v1/assets?limit=25");
    if (res.ok) {
      setAssets(res.data.map(adaptEntry));
    }
  }, [connected]);

  useEffect(() => {
    fetchAssets();
    const id = setInterval(fetchAssets, 3_000);
    return () => clearInterval(id);
  }, [fetchAssets]);

  /** Lazily enrich an asset's result scores */
  const fetchResult = useCallback(async (id: string) => {
    const res = await apiFetch<Record<string, unknown>>(`/api/v1/assets/${id}/result`);
    if (!res.ok) return;
    setAssets((prev) =>
      prev.map((a) =>
        a.id === id ? { ...a, ...adaptEntry({ ...a.raw as Record<string, unknown>, ...res.data }) } : a,
      ),
    );
  }, []);

  return { assets, fetchResult };
}
