import { useState } from "react";
import { api } from "../api";
import { Logo, Spinner } from "../components/ui";

interface AdminUser {
  uid: string;
  name: string;
  email: string;
  status: string;
  lastWelcomeState?: string | null;
}

// Painel administrativo isolado (RF06-RF08). Sessao por cookie + CSRF; nunca
// acessa quadros com a sessao administrativa.
export default function AdminPage() {
  const [csrf, setCsrf] = useState<string | null>(null);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function login(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.post<{ csrfToken: string }>(
        "/admin/session",
        { username, password },
        { admin: true },
      );
      setCsrf(res.csrfToken);
    } catch {
      setError("Credenciais invalidas.");
    } finally {
      setBusy(false);
    }
  }

  if (!csrf) {
    return (
      <div className="center-page">
        <form className="card-box" onSubmit={login}>
          <Logo />
          <h1 style={{ textAlign: "center", fontSize: "1.2rem" }}>Administracao</h1>
          <div className="field">
            <label>Usuario</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div className="field">
            <label>Senha</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          {error && <p className="error-text">{error}</p>}
          <button className="primary" type="submit" disabled={busy} style={{ width: "100%" }}>
            {busy ? <Spinner /> : "Entrar"}
          </button>
        </form>
      </div>
    );
  }

  return <AdminPanel csrf={csrf} onLogout={() => setCsrf(null)} />;
}

function AdminPanel({ csrf, onLogout }: { csrf: string; onLogout: () => void }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [q, setQ] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    const data = await api.get<{ users: AdminUser[] }>(
      `/admin/users${q ? `?q=${encodeURIComponent(q)}` : ""}`,
      { admin: true },
    );
    setUsers(data.users);
    setLoaded(true);
  }

  if (!loaded) load().catch(() => setError("Nao foi possivel carregar usuarios."));

  async function createUser(e: React.FormEvent) {
    e.preventDefault();
    setMsg(null);
    setError(null);
    try {
      await api.post("/admin/users", { name: name.trim(), email: email.trim() }, { admin: true, csrf });
      setMsg("Usuario criado. E-mail de boas-vindas enviado (se SMTP configurado).");
      setName("");
      setEmail("");
      await load();
    } catch (e: any) {
      setError(e?.message ?? "Nao foi possivel criar o usuario.");
    }
  }

  async function toggleStatus(u: AdminUser) {
    const next = u.status === "disabled" ? "active" : "disabled";
    await api.patch(`/admin/users/${u.uid}`, { status: next }, { admin: true, csrf });
    await load();
  }
  async function resetPw(u: AdminUser) {
    await api.post(`/admin/users/${u.uid}/password-reset`, {}, { admin: true, csrf });
    setMsg(`Redefinicao enviada para ${u.email} (se SMTP configurado).`);
  }
  async function resend(u: AdminUser) {
    await api.post(`/admin/users/${u.uid}/welcome-resend`, {}, { admin: true, csrf });
    setMsg(`Boas-vindas reenviadas para ${u.email}.`);
  }
  async function removeUser(u: AdminUser) {
    if (!confirm(`Excluir ${u.email}? Esta acao e definitiva.`)) return;
    await api.del(`/admin/users/${u.uid}`, { admin: true, csrf });
    await load();
  }
  async function logout() {
    await api.del("/admin/session", { admin: true, csrf });
    onLogout();
  }

  return (
    <>
      <header className="app-header">
        <Logo className="header-logo" />
        <span className="title">Administracao de usuarios</span>
        <span className="spacer" />
        <button className="ghost" onClick={logout}>
          Sair
        </button>
      </header>

      <div style={{ padding: 16, maxWidth: 820, margin: "0 auto" }}>
        <form onSubmit={createUser} className="list-item">
          <strong>Adicionar usuario</strong>
          <div className="row">
            <input placeholder="Nome" value={name} onChange={(e) => setName(e.target.value)} />
            <input
              placeholder="E-mail"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <button className="primary" type="submit">
              Adicionar
            </button>
          </div>
        </form>

        {msg && <p className="ok-text">{msg}</p>}
        {error && <p className="error-text">{error}</p>}

        <div className="row" style={{ marginTop: 16 }}>
          <input
            placeholder="Pesquisar por nome ou e-mail"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && load()}
            style={{ flex: 1 }}
          />
          <button onClick={load}>Buscar</button>
        </div>

        <div style={{ marginTop: 12 }}>
          {users.map((u) => (
            <div className="list-item" key={u.uid} style={{ marginBottom: 10 }}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <div>
                  <strong>{u.name}</strong> <span className="muted">{u.email}</span>
                  <div>
                    <span className="badge">{statusLabel(u.status)}</span>
                  </div>
                </div>
                <div className="row">
                  {u.status === "pending_activation" && (
                    <button className="ghost icon-btn" onClick={() => resend(u)}>
                      Reenviar boas-vindas
                    </button>
                  )}
                  <button className="ghost icon-btn" onClick={() => resetPw(u)}>
                    Redefinir senha
                  </button>
                  <button className="ghost icon-btn" onClick={() => toggleStatus(u)}>
                    {u.status === "disabled" ? "Reativar" : "Desativar"}
                  </button>
                  <button className="danger icon-btn" onClick={() => removeUser(u)}>
                    Excluir
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}

function statusLabel(s: string): string {
  return (
    {
      pending_activation: "Pendente",
      active: "Ativo",
      disabled: "Desativado",
      deleting: "Em exclusao",
    }[s] ?? s
  );
}
