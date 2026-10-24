import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";
import { initFirebase } from "./firebase";
import type { PublicConfig } from "./types";
import { Spinner } from "./components/ui";

const ConfigCtx = createContext<PublicConfig | null>(null);

export function useConfig(): PublicConfig {
  const cfg = useContext(ConfigCtx);
  if (!cfg) throw new Error("Config nao carregada.");
  return cfg;
}

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [cfg, setCfg] = useState<PublicConfig | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<PublicConfig>("/config")
      .then((c) => {
        initFirebase(c);
        setCfg(c);
      })
      .catch(() => setError("Nao foi possivel carregar a configuracao do servidor."));
  }, []);

  if (error) {
    return (
      <div className="center-page">
        <div className="card-box">
          <p className="error-text">{error}</p>
          <button onClick={() => location.reload()}>Tentar novamente</button>
        </div>
      </div>
    );
  }
  if (!cfg) {
    return (
      <div className="center-page">
        <div className="row">
          <Spinner /> <span className="muted">Carregando...</span>
        </div>
      </div>
    );
  }
  return <ConfigCtx.Provider value={cfg}>{children}</ConfigCtx.Provider>;
}
