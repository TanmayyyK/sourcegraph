import { motion, AnimatePresence } from "framer-motion";
import {
  LayoutDashboard,
  UploadCloud,
  BarChart3,
  PanelLeftClose,
  PanelLeftOpen,
  Eye,
} from "lucide-react";


export type AppView = "ingest" | "command" | "insights";

type NavItem = {
  id: AppView;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  shortcut: string;
};

const NAV: NavItem[] = [
  { id: "ingest",   label: "Ingestion",      icon: UploadCloud,     shortcut: "I" },
  { id: "command",  label: "Command Center", icon: LayoutDashboard, shortcut: "C" },
  { id: "insights", label: "Insights",       icon: BarChart3,       shortcut: ";" },
];

type Props = {
  view:       AppView;
  onNav:      (v: AppView) => void;
  collapsed:  boolean;
  onToggle:   () => void;
  userName:   string;
  role:       string;
};

export default function Sidebar({ view, onNav, collapsed, onToggle, userName, role }: Props) {
  return (
    <motion.aside
      layout
      data-testid="app-sidebar"
      className="relative flex h-full flex-col border-r border-white/[0.05] bg-white/[0.02] backdrop-blur-xl"
      style={{ width: collapsed ? 64 : 220, flexShrink: 0, transition: "width 0.25s cubic-bezier(0.4,0,0.2,1)" }}
    >
      {/* Brand */}
      <motion.div layout className="flex h-14 items-center gap-3 border-b border-white/[0.05] px-4">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500/80 to-indigo-600/80 shadow-[0_0_24px_rgba(59,130,246,0.35)]">
          <Eye className="h-4 w-4 text-white" />
        </div>
        <AnimatePresence initial={false}>
          {!collapsed && (
            <motion.div
              key="brand-text"
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -6 }}
              transition={{ duration: 0.18 }}
              className="min-w-0"
            >
              <p className="truncate text-[13px] font-semibold tracking-tight text-zinc-100">Overwatch</p>
              <p className="truncate text-[11px] text-zinc-500">v3.0 · Midnight</p>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto px-2 py-3">
        <AnimatePresence initial={false}>
          {!collapsed && (
            <motion.p
              key="ws-label"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="px-2 pb-2 text-[10px] font-medium uppercase tracking-[0.14em] text-zinc-600"
            >
              Workspace
            </motion.p>
          )}
        </AnimatePresence>

        <ul className="flex flex-col gap-0.5">
          {NAV.map((item) => {
            const Icon     = item.icon;
            const isActive = view === item.id;
            return (
              <li key={item.id}>
                <motion.button
                  layout
                  onClick={() => onNav(item.id)}
                  whileHover={{ y: -1 }}
                  whileTap={{ scale: 0.98 }}
                  transition={{ type: "spring", stiffness: 400, damping: 25 }}
                  className={`group relative flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-[13px] transition-colors ${
                    isActive
                      ? "bg-white/[0.05] text-zinc-100"
                      : "text-zinc-400 hover:bg-white/[0.03] hover:text-zinc-200"
                  }`}
                  style={{ justifyContent: collapsed ? "center" : "flex-start" }}
                >
                  {isActive && (
                    <motion.span
                      layoutId="sidebar-active-pill"
                      className="absolute inset-y-1.5 left-0 w-[2px] rounded-full bg-blue-400 shadow-[0_0_10px_rgba(96,165,250,0.7)]"
                      transition={{ type: "spring", stiffness: 400, damping: 30 }}
                    />
                  )}
                  <Icon className={`h-[16px] w-[16px] shrink-0 ${isActive ? "text-blue-300" : ""}`} />
                  <AnimatePresence initial={false}>
                    {!collapsed && (
                      <motion.span
                        key="label"
                        initial={{ opacity: 0, x: -4 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -4 }}
                        transition={{ duration: 0.15 }}
                        className="flex-1 truncate"
                      >
                        {item.label}
                      </motion.span>
                    )}
                  </AnimatePresence>
                  <AnimatePresence initial={false}>
                    {!collapsed && (
                      <motion.kbd
                        key="kbd"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        className="rounded-[5px] border border-white/[0.06] bg-white/[0.02] px-1.5 py-0.5 font-mono text-[10px] text-zinc-600"
                      >
                        {item.shortcut}
                      </motion.kbd>
                    )}
                  </AnimatePresence>
                </motion.button>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Footer */}
      <div className="flex flex-col gap-2 border-t border-white/[0.05] p-2">
        {/* User chip */}
        <AnimatePresence initial={false}>
          {!collapsed && (
            <motion.div
              key="user-chip"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex items-center gap-2.5 rounded-lg px-2.5 py-2"
            >
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-gradient-to-br from-blue-500/60 to-indigo-600/60 text-[11px] font-semibold text-white">
                {userName.charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="truncate text-[12px] font-medium text-zinc-200">{userName}</p>
                <p className="truncate text-[10.5px] text-zinc-500">{role}</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Collapse toggle */}
        <motion.button
          layout
          onClick={onToggle}
          whileHover={{ y: -1 }}
          whileTap={{ scale: 0.98 }}
          className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[12px] text-zinc-400 transition-colors hover:bg-white/[0.04] hover:text-zinc-200"
          style={{ justifyContent: collapsed ? "center" : "flex-start" }}
        >
          {collapsed
            ? <PanelLeftOpen className="h-[15px] w-[15px]" />
            : (
              <>
                <PanelLeftClose className="h-[15px] w-[15px]" />
                <AnimatePresence initial={false}>
                  <motion.span
                    key="collapse-label"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                  >
                    Collapse
                  </motion.span>
                </AnimatePresence>
              </>
            )}
        </motion.button>
      </div>
    </motion.aside>
  );
}
