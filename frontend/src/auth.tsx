import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { onAuthStateChanged, signOut, type User } from "firebase/auth";
import { auth } from "./firebase";
import { api, ApiError } from "./api";
import type { Me } from "./types";

interface AuthState {
  user: User | null;
  me: Me | null;
  loading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthCtx = createContext<AuthState | null>(null);

export function useAuth(): AuthState {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("AuthProvider ausente.");
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  async function loadMe() {
    try {
      const profile = await api.get<Me>("/me");
      setMe(profile);
    } catch (e) {
      // Perfil nao provisionado/ativo: desloga para nao prender em tela quebrada.
      if (e instanceof ApiError && (e.status === 403 || e.status === 401)) {
        setMe(null);
      }
    }
  }

  useEffect(() => {
    return onAuthStateChanged(auth(), async (u) => {
      setUser(u);
      if (u) {
        await loadMe();
      } else {
        setMe(null);
      }
      setLoading(false);
    });
  }, []);

  const value: AuthState = {
    user,
    me,
    loading,
    refresh: loadMe,
    logout: async () => {
      await signOut(auth());
      setMe(null);
    },
  };
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}
