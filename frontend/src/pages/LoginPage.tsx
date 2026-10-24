import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { signInWithEmailAndPassword } from "firebase/auth";
import { auth } from "../firebase";
import { useAuth } from "../auth";
import { Logo, Spinner } from "../components/ui";

export default function LoginPage() {
  const { user, me, loading } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!loading && user && me) return <Navigate to="/kanbans" replace />;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signInWithEmailAndPassword(auth(), email.trim(), password);
      navigate("/kanbans");
    } catch {
      setError("E-mail ou senha incorretos.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="center-page">
      <form className="card-box" onSubmit={submit}>
        <Logo />
        <h1 style={{ textAlign: "center", fontSize: "1.3rem" }}>KanbaLeiando</h1>
        <div className="field">
          <label htmlFor="email">E-mail</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="password">Senha</label>
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        {error && <p className="error-text">{error}</p>}
        <button className="primary" type="submit" disabled={busy} style={{ width: "100%" }}>
          {busy ? <Spinner /> : "Entrar"}
        </button>
        <p style={{ textAlign: "center", marginTop: 14 }}>
          <Link to="/forgot-password">Esqueci minha senha</Link>
        </p>
      </form>
    </div>
  );
}
