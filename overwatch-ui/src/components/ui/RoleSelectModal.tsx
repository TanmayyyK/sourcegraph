import { motion, AnimatePresence } from "framer-motion";
import { X, Shield, Crosshair, ArrowRight } from "lucide-react";

export type UserRole = "PRODUCER" | "AUDITOR";

type Props = {
  onSelect: (role: UserRole) => void;
  onClose:  () => void;
};

const ROLES = [
  {
    role:    "PRODUCER" as UserRole,
    icon:    Shield,
    title:   "Content Producer",
    desc:    "Ingest golden assets into the protected library",
    accent:  { bg: "rgba(96,165,250,0.1)", border: "rgba(96,165,250,0.25)", tint: "#60a5fa" },
  },
  {
    role:    "AUDITOR" as UserRole,
    icon:    Crosshair,
    title:   "Auditor / Analyst",
    desc:    "Submit suspect files for similarity detection",
    accent:  { bg: "rgba(129,140,248,0.1)", border: "rgba(129,140,248,0.22)", tint: "#818cf8" },
  },
];

export default function RoleSelectModal({ onSelect, onClose }: Props) {
  return (
    <AnimatePresence>
      <motion.div
        key="role-modal-backdrop"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[100] flex items-center justify-center p-6"
        style={{ background: "rgba(9,9,11,0.72)", backdropFilter: "blur(8px)" }}
        onClick={(e) => e.target === e.currentTarget && onClose()}
      >
        <motion.div
          key="role-modal-panel"
          initial={{ opacity: 0, scale: 0.95, y: 8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 8 }}
          transition={{ type: "spring", stiffness: 300, damping: 28 }}
          className="w-full max-w-[420px] rounded-[14px] border border-white/[0.06] bg-white/[0.02] p-7 shadow-[0_0_60px_rgba(0,0,0,0.6)] backdrop-blur-2xl"
        >
          {/* Header */}
          <div className="mb-6 flex items-center justify-between">
            <div>
              <p className="mb-1 text-[10.5px] font-medium uppercase tracking-[0.15em] text-zinc-600">
                Access Control
              </p>
              <h2 className="text-[19px] font-semibold tracking-tight text-zinc-100">
                Select your role
              </h2>
            </div>
            <button
              onClick={onClose}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.06] bg-white/[0.02] text-zinc-500 transition-colors hover:bg-white/[0.05] hover:text-zinc-200"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Role cards */}
          <div className="flex flex-col gap-3">
            {ROLES.map(({ role, icon: Icon, title, desc, accent }) => (
              <motion.button
                key={role}
                onClick={() => onSelect(role)}
                whileHover={{ y: -1, scale: 1.005 }}
                whileTap={{ scale: 0.98 }}
                transition={{ type: "spring", stiffness: 400, damping: 25 }}
                className="flex w-full items-center gap-4 rounded-[10px] p-4 text-left transition-colors"
                style={{ background: accent.bg, border: `1px solid ${accent.border}` }}
              >
                <div
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[9px] bg-white/[0.04]"
                  style={{ color: accent.tint }}
                >
                  <Icon className="h-[18px] w-[18px]" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-[13.5px] font-medium text-zinc-100">{title}</p>
                  <p className="mt-0.5 text-[12px] font-light text-zinc-500">{desc}</p>
                </div>
                <ArrowRight className="h-3.5 w-3.5 shrink-0 text-zinc-600" />
              </motion.button>
            ))}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
