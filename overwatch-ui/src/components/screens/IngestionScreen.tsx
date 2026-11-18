import { motion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";
import OverwatchIngestPortal from "@/components/screens/OverwatchIngestModel";

type Props = {
  role:     string | null;
  onDone?:  () => void;
};

export default function IngestionScreen({ role, onDone }: Props) {
  const isProducer = role === "PRODUCER";

  return (
    <div className="px-6 py-12 sm:px-12 max-w-7xl mx-auto">
      {/* Page heading */}
      <motion.div 
        initial={{ opacity: 0, y: 16 }} 
        animate={{ opacity: 1, y: 0 }} 
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
        className="mb-10 flex flex-col gap-2"
      >
        <span className="text-[10px] font-mono uppercase tracking-[0.18em] dark:text-gray-500 text-gray-400">
          {isProducer ? "Golden library ingestion" : "Suspect file analysis"}
        </span>
        <h1 className="text-3xl font-semibold tracking-tight dark:text-gray-100 text-gray-900 sm:text-4xl">
          {isProducer
            ? "Protect your original content."
            : "Detect similarity in seconds."}
        </h1>
        <p className="mt-2 max-w-lg text-sm leading-relaxed dark:text-gray-400 text-gray-500">
          {isProducer
            ? "Drop a golden asset — it'll be fingerprinted at 512-D and stored in the protected library, ready for cross-media comparison."
            : "Drop a suspect file — our vector pipeline will compare it against the entire golden library and return a similarity verdict."}
        </p>
      </motion.div>

      {/* Ingest portal */}
      <motion.section 
        initial={{ opacity: 0, y: 16 }} 
        animate={{ opacity: 1, y: 0 }} 
        transition={{ duration: 0.5, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
        className="mb-12"
      >
        <OverwatchIngestPortal onComplete={() => {}} />
      </motion.section>

      {/* CTA to Command Center */}
      {onDone && (
        <motion.section 
          initial={{ opacity: 0, y: 16 }} 
          animate={{ opacity: 1, y: 0 }} 
          transition={{ duration: 0.5, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
          className="mb-8 flex flex-col items-start gap-4 rounded-xl border dark:border-gray-800 border-gray-200 dark:bg-[#0A0A0A] bg-white p-8 shadow-sm"
        >
          <span className="text-[10px] font-mono uppercase tracking-[0.18em] dark:text-gray-500 text-gray-400">
            What's next
          </span>
          <h2 className="text-xl font-semibold leading-tight dark:text-gray-100 text-gray-900">
            Monitor all assets in the Command Center
          </h2>
          <p className="max-w-md text-sm leading-relaxed dark:text-gray-400 text-gray-500">
            View every ingested file, similarity scores, and verdict history in one unified dashboard.
          </p>
          <motion.button
            whileHover={{ y: -1 }}
            whileTap={{ scale: 0.98 }}
            onClick={onDone}
            className="group mt-2 inline-flex items-center gap-2 rounded-lg border dark:border-gray-800 border-gray-200 dark:bg-gray-100 bg-gray-900 px-5 py-2.5 text-sm font-medium dark:text-gray-900 text-white transition-colors hover:opacity-90"
          >
            Go to Command Center
            <ArrowUpRight className="h-4 w-4 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
          </motion.button>
        </motion.section>
      )}
    </div>
  );
}
