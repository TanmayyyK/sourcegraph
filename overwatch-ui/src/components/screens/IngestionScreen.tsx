import { motion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";
import OverwatchIngestPortal from "@/components/screens/OverwatchIngestModel";
import ScrollReveal from "@/components/ui/ScrollReveal";

type Props = {
  role:     string | null;
  onDone?:  () => void;
};

export default function IngestionScreen({ role, onDone }: Props) {
  const isProducer = role === "PRODUCER";

  return (
    <div className="px-6 py-8 sm:px-10">

      {/* Page heading */}
      <ScrollReveal delay={0}>
        <div className="mb-8 flex flex-col gap-1.5">
          <span className="text-[11px] font-medium uppercase tracking-[0.18em] text-zinc-500">
            {isProducer ? "Golden library ingestion" : "Suspect file analysis"}
          </span>
          <h1 className="text-[28px] font-semibold tracking-tight text-zinc-100 sm:text-[34px]">
            {isProducer
              ? "Protect your original content."
              : "Detect similarity in seconds."}
          </h1>
          <p className="mt-1 max-w-lg text-[13.5px] leading-relaxed text-zinc-500">
            {isProducer
              ? "Drop a golden asset — it'll be fingerprinted at 512-D and stored in the protected library, ready for cross-media comparison."
              : "Drop a suspect file — our vector pipeline will compare it against the entire golden library and return a similarity verdict."}
          </p>
        </div>
      </ScrollReveal>

      {/* Ingest portal */}
      <ScrollReveal delay={0.06}>
        <section className="mb-10">
          <OverwatchIngestPortal onComplete={() => {}} />
        </section>
      </ScrollReveal>

      {/* CTA to Command Center */}
      {onDone && (
        <ScrollReveal delay={0.1}>
          <section className="mb-8 flex flex-col items-start gap-4 rounded-[12px] border border-white/[0.05] bg-white/[0.02] p-8 backdrop-blur-xl shadow-[0_0_40px_rgba(0,0,0,0.4)]">
            <span className="text-[11px] font-medium uppercase tracking-[0.18em] text-zinc-500">
              What's next
            </span>
            <h2 className="text-[22px] font-semibold leading-tight text-zinc-100">
              Monitor all assets in the Command Center
            </h2>
            <p className="max-w-md text-[13px] leading-relaxed text-zinc-500">
              View every ingested file, similarity scores, and verdict history in one unified dashboard.
            </p>
            <motion.button
              whileHover={{ y: -1 }}
              whileTap={{ scale: 0.98 }}
              onClick={onDone}
              className="group mt-1 inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.03] px-5 py-2.5 text-[13px] text-zinc-200 transition-colors hover:border-blue-400/40 hover:bg-blue-400/[0.08]"
            >
              Go to Command Center
              <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
            </motion.button>
          </section>
        </ScrollReveal>
      )}
    </div>
  );
}
