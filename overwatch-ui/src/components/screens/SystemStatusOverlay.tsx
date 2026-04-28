import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, X } from "lucide-react";

export default function SystemStatusOverlay() {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (!isOpen) return;

    const previousOverflow = document.body.style.overflow;
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    };

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleEscape);

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleEscape);
    };
  }, [isOpen]);

  return (
    <>
      <motion.button
        type="button"
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-[120] inline-flex h-14 w-14 items-center justify-center rounded-full border border-amber-300/70 bg-amber-400/90 text-slate-950 shadow-[0_0_30px_rgba(251,191,36,0.35)] backdrop-blur-md transition-transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-amber-300 focus:ring-offset-2 focus:ring-offset-slate-950"
        animate={{
          scale: [1, 1.06, 1],
          boxShadow: [
            "0 0 0 rgba(251,191,36,0.25)",
            "0 0 28px rgba(251,191,36,0.55)",
            "0 0 0 rgba(251,191,36,0.25)",
          ],
        }}
        transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
        aria-label="Open system status notice"
      >
        <motion.span
          className="absolute inset-0 rounded-full border border-amber-200/60"
          animate={{ scale: [1, 1.35], opacity: [0.55, 0] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut" }}
        />
        <AlertTriangle className="relative h-6 w-6" strokeWidth={2.2} />
      </motion.button>

      <AnimatePresence>
        {isOpen ? (
          <motion.div
            className="fixed inset-0 z-[130] flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-md sm:p-6"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              className="relative w-full max-w-2xl overflow-hidden rounded-2xl border border-amber-400/50 bg-slate-950/95 shadow-[0_0_60px_rgba(245,158,11,0.18)]"
              initial={{ opacity: 0, y: 20, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 16, scale: 0.98 }}
              transition={{ duration: 0.24, ease: "easeOut" }}
            >
              <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_bottom,rgba(251,191,36,0.08),transparent_30%,transparent_70%,rgba(251,191,36,0.06))]" />
              <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-amber-300/70" />

              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="absolute right-4 top-4 z-10 inline-flex h-10 w-10 items-center justify-center rounded-full border border-amber-400/30 bg-slate-900/80 text-amber-100 transition-colors hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-amber-300"
                aria-label="Close system status notice"
              >
                <X className="h-5 w-5" strokeWidth={2.2} />
              </button>

              <div className="relative flex flex-col gap-6 p-6 sm:p-8">
                <div className="flex items-start gap-4">
                  <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl border border-amber-400/40 bg-amber-400/10 text-amber-300">
                    <AlertTriangle className="h-6 w-6" strokeWidth={2.2} />
                  </div>
                  <div className="min-w-0">
                    <p className="text-xs font-semibold uppercase tracking-[0.3em] text-amber-300/80">
                      Status Broadcast
                    </p>
                    <h2 className="mt-2 text-2xl font-semibold text-amber-50 sm:text-3xl">
                      SYSTEM NOTICE: Infrastructure Quota Review
                    </h2>
                  </div>
                </div>

                <div className="space-y-4 border-l border-amber-400/30 pl-4 text-sm leading-7 text-slate-200 sm:text-base">
                  <p>
                    The Titan Protocol live GPU infrastructure is currently pending Google Cloud enterprise
                    quota approvals. Real-time video processing is temporarily offline.
                  </p>
                  <p className="font-medium text-amber-300">
                    Expected Resolution: By May 1st, 2026.
                  </p>
                  <p className="text-slate-300">
                    Please refer to our architectural Demo Video to see the system operating at full capacity.
                  </p>
                </div>
              </div>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </>
  );
}
