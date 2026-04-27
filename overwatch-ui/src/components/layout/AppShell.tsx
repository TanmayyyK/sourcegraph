import { useRef } from "react";
import Sidebar, { AppView } from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import NoiseOverlay from "@/components/layout/NoiseOverlay";
import BackgroundBlob from "@/components/layout/BackgroundBlob";
import SmoothScrollProvider from "@/components/providers/SmoothScrollProvider";
import OverwatchIngestPortal from "@/components/screens/OverwatchIngestModel";
import CommandCentreHome from "@/components/screens/CommandCentreHome";
import InsightsScreen from "@/components/screens/InsightsScreen";
import { Asset } from "@/lib/adapters";

type Props = {
  view:        AppView;
  onNav:       (v: AppView) => void;
  collapsed:   boolean;
  onToggle:    () => void;
  userName:    string;
  role:        string;
  connected:   boolean;
  assets:      Asset[];
  fetchResult: (id: string) => void;
};

export default function AppShell({
  view, onNav, collapsed, onToggle,
  userName, role, connected,
  assets, fetchResult,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  return (
    <div
      data-testid="app-shell"
      className="relative flex h-screen w-screen overflow-hidden bg-zinc-950 text-zinc-100"
    >
      {/* Atmospheric layers */}
      <BackgroundBlob scrollContainerRef={scrollRef} />
      <NoiseOverlay />

      {/* Foreground */}
      <div className="relative z-10 flex h-full w-full">
        {/* Sidebar */}
        {view !== "ingest" && view !== "command" && (
          <Sidebar
            view={view}
            onNav={onNav}
            collapsed={collapsed}
            onToggle={onToggle}
            userName={userName}
            role={role}
          />
        )}

        {/* Main pane */}
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {view !== "ingest" && view !== "command" && (
            <Header
              view={view}
              connected={connected}
              userName={userName}
              role={role}
            />
          )}
          {/* Ingest portal is a fixed-height canvas — skip Lenis / scrolling entirely */}
          {view === "ingest" && (
            <div className="flex-1 overflow-hidden" style={{ background: "#F5F3EF" }}>
              <OverwatchIngestPortal 
                onComplete={() => onNav("insights")} 
                onBack={() => onNav("command")}
              />
            </div>
          )}
          <SmoothScrollProvider ref={scrollRef} className={view === "ingest" ? "hidden" : "flex-1"}>
            {view === "command" && (
              <CommandCentreHome
                userName={userName}
                userRole={role}
                onNavigate={(dest) => onNav(dest.toLowerCase() as AppView)}
              />
            )}
            {view === "insights" && <InsightsScreen assets={assets} />}
          </SmoothScrollProvider>
        </div>
      </div>
    </div>
  );
}
