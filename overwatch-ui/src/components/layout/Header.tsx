import { motion } from "framer-motion";
import { ChevronRight, Bell, GitBranch, CircleDot, Command, Search, Eye } from "lucide-react";
import { AppView } from "./Sidebar";

const VIEW_LABELS: Record<AppView, string> = {
  ingest:   "Ingestion",
  command:  "Command Center",
  insights: "Insights",
};

type Props = {
  view:      AppView;
  connected: boolean;
  userName:  string;
  role:      string;
};

export default function Header({ view, connected, userName, role }: Props) {
  return (
    <header
      data-testid="app-header"
      className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-4 border-b border-white/[0.05] bg-white/[0.02] px-5 backdrop-blur-xl"
    >
      {/* Breadcrumbs */}
      <nav className="flex min-w-0 items-center gap-1.5 text-[12.5px]">
        <Eye className="h-3 w-3 text-zinc-600" />
        <span className="text-zinc-500">overwatch</span>
        <ChevronRight className="h-3 w-3 text-zinc-700" />
        <span className="truncate font-medium text-zinc-200">{VIEW_LABELS[view]}</span>
      </nav>

      <div className="flex-1" />

      {/* Search */}
      <motion.button
        whileHover={{ y: -1 }}
        whileTap={{ scale: 0.98 }}
        transition={{ type: "spring", stiffness: 400, damping: 25 }}
        className="hidden h-9 items-center gap-2.5 rounded-lg border border-white/[0.05] bg-white/[0.02] px-3 text-[12.5px] text-zinc-400 transition-colors hover:border-white/[0.1] hover:bg-white/[0.04] hover:text-zinc-200 md:flex"
      >
        <Search className="h-[14px] w-[14px]" />
        <span>Search or jump to…</span>
        <kbd className="ml-4 flex items-center gap-0.5 rounded-[5px] border border-white/[0.07] bg-black/40 px-1.5 py-0.5 font-mono text-[10px] text-zinc-500">
          <Command className="h-[9px] w-[9px]" />K
        </kbd>
      </motion.button>

      {/* Connection status chip */}
      <div
        className={`hidden items-center gap-2 rounded-full border px-3 py-1 lg:flex ${
          connected
            ? "border-emerald-500/20 bg-emerald-500/[0.08]"
            : "border-rose-500/20 bg-rose-500/[0.08]"
        }`}
      >
        <span className="relative flex h-1.5 w-1.5">
          {connected && (
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400/70 opacity-75" />
          )}
          <span
            className={`relative inline-flex h-1.5 w-1.5 rounded-full ${
              connected ? "bg-emerald-400" : "bg-rose-400"
            }`}
          />
        </span>
        <span
          className={`text-[11.5px] font-medium ${
            connected ? "text-emerald-300" : "text-rose-300"
          }`}
        >
          {connected ? "All systems nominal" : "Backend offline"}
        </span>
      </div>

      {/* Branch chip */}
      <motion.div
        whileHover={{ y: -1 }}
        className="hidden items-center gap-1.5 rounded-md border border-white/[0.05] bg-white/[0.02] px-2.5 py-1 text-[11.5px] text-zinc-400 md:flex"
      >
        <GitBranch className="h-3 w-3" />
        <span className="font-mono">main</span>
        <CircleDot className="h-2.5 w-2.5 text-amber-400" />
      </motion.div>

      {/* Notifications */}
      <motion.button
        whileHover={{ y: -1 }}
        whileTap={{ scale: 0.98 }}
        className="relative flex h-9 w-9 items-center justify-center rounded-lg border border-white/[0.05] bg-white/[0.02] text-zinc-400 transition-colors hover:border-white/[0.1] hover:bg-white/[0.04] hover:text-zinc-200"
      >
        <Bell className="h-[15px] w-[15px]" />
        <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-blue-400 shadow-[0_0_6px_rgba(96,165,250,0.8)]" />
      </motion.button>

      {/* User avatar */}
      <motion.div
        whileHover={{ y: -1 }}
        className="flex h-9 items-center gap-2 rounded-lg border border-white/[0.05] bg-white/[0.02] pl-1 pr-2.5 text-[12.5px] text-zinc-300 transition-colors hover:border-white/[0.1] hover:bg-white/[0.04]"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-md bg-gradient-to-br from-blue-500/70 to-indigo-600/70 text-[11px] font-semibold text-white">
          {userName.charAt(0).toUpperCase()}
        </span>
        <span className="hidden sm:inline">{userName}</span>
        <span className="hidden rounded px-1 py-0.5 text-[10px] font-medium text-zinc-500 sm:inline">
          {role}
        </span>
      </motion.div>
    </header>
  );
}
