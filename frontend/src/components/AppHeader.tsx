import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { Logo } from "./ui";
import type { ReactNode } from "react";

export function AppHeader({ title, children }: { title?: ReactNode; children?: ReactNode }) {
  const { me, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <header className="app-header">
      <Logo className="header-logo" />
      {title && <span className="title">{title}</span>}
      <span className="spacer" />
      {children}
      {me && <span className="muted">{me.name}</span>}
      <button
        className="ghost"
        onClick={async () => {
          await logout();
          navigate("/login");
        }}
      >
        Sair
      </button>
    </header>
  );
}
