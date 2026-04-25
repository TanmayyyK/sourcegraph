import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import LandingScreen from "@/components/screens/LandingScreen";
import LoginScreen, { UserRole } from "@/components/screens/LoginScreen";
import CommandCentreHome from "@/components/screens/CommandCentreHome";
import OverwatchIngestPortal from "@/components/screens/OverwatchIngestModel";
import InsightsScreen from "@/components/screens/InsightsScreen";
import NexusScreen from "@/components/screens/NexusScreen";
import ProtectedRoute from "@/components/providers/ProtectedRoute";
import { useAuth } from "@/components/providers/AuthProvider";

export default function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, userName, userRole, refreshSession, logout } = useAuth();

  const handleLogin = async (_name: string, _selectedRole: UserRole) => {
    void _name;
    void _selectedRole;
    const ok = await refreshSession();
    if (ok) {
      navigate("/home", { replace: true });
    }
  };

  return (
    <Routes>
      <Route
        path="/"
        element={
          isAuthenticated ? (
            <Navigate to="/home" replace />
          ) : (
            <LandingScreen
              onLoginClick={() => {
                navigate("/login?mode=login");
              }}
              onSignupClick={() => {
                navigate("/login?mode=signup");
              }}
            />
          )
        }
      />
      <Route
        path="/login"
        element={
          isAuthenticated ? (
            <Navigate to="/home" replace />
          ) : (
            <LoginScreen
              initialMode={
                new URLSearchParams(location.search).get("mode")?.toUpperCase() === "SIGNUP"
                  ? "SIGNUP"
                  : "LOGIN"
              }
              onLogin={handleLogin}
              onBack={() => navigate("/")}
            />
          )
        }
      />
      <Route
        path="/home"
        element={
          <ProtectedRoute>
            <CommandCentreHome
              userName={userName || "Operator"}
              userRole={userRole || "AUDITOR"}
              onNavigate={(destination) => {
                if (destination.toUpperCase() === "INGEST") {
                  navigate("/ingest");
                  return;
                }
                navigate("/home");
              }}
              onLogout={() => {
                logout();
                navigate("/login?mode=login", { replace: true });
              }}
            />
          </ProtectedRoute>
        }
      />
      <Route
        path="/ingest"
        element={
          <ProtectedRoute>
            <OverwatchIngestPortal
              onComplete={() => navigate("/insights")}
              onBack={() => navigate("/home")}
            />
          </ProtectedRoute>
        }
      />
      <Route
        path="/insights"
        element={
          <ProtectedRoute>
            <InsightsScreen assets={[]} role={userRole} Maps={navigate} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/analysis/:assetId"
        element={
          <ProtectedRoute>
            <NexusScreen />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}