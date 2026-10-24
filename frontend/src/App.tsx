import { Navigate, Route, Routes } from "react-router-dom";
import { ConfigProvider } from "./config";
import { AuthProvider, useAuth } from "./auth";
import { Spinner } from "./components/ui";
import LoginPage from "./pages/LoginPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import AuthActionPage from "./pages/AuthActionPage";
import BoardsPage from "./pages/BoardsPage";
import BoardPage from "./pages/BoardPage";
import AuditPage from "./pages/AuditPage";
import PublicBoardPage from "./pages/PublicBoardPage";
import AdminPage from "./pages/AdminPage";
import type { JSX } from "react";

function RequireAuth({ children }: { children: JSX.Element }) {
  const { user, me, loading } = useAuth();
  if (loading) {
    return (
      <div className="center-page">
        <Spinner />
      </div>
    );
  }
  if (!user || !me) return <Navigate to="/login" replace />;
  return children;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/auth/action" element={<AuthActionPage />} />
      <Route path="/s/:boardId" element={<PublicBoardPage />} />
      <Route path="/admin" element={<AdminPage />} />
      <Route
        path="/kanbans"
        element={
          <RequireAuth>
            <BoardsPage />
          </RequireAuth>
        }
      />
      <Route
        path="/kanbans/:boardId"
        element={
          <RequireAuth>
            <BoardPage />
          </RequireAuth>
        }
      />
      <Route
        path="/kanbans/:boardId/audit"
        element={
          <RequireAuth>
            <AuditPage />
          </RequireAuth>
        }
      />
      <Route path="/" element={<Navigate to="/kanbans" replace />} />
      <Route path="*" element={<Navigate to="/kanbans" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <ConfigProvider>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </ConfigProvider>
  );
}
