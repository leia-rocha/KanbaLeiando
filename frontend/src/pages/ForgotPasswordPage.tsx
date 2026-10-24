import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Logo, Spinner } from "../components/ui";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post("/auth/forgot-password", { email: email.trim() });
    } finally {
      // Resposta publica generica (RF04): sempre mostra confirmacao.
      setSent(true);
      setBusy(false);
    }
  }

  return (
    <div className="center-page">
      <form className="card-box" onSubmit={submit}>
        <Logo />
        <h1 style={{ textAlign: "center", fontSize: "1.2rem" }}>Recuperar acesso</h1>
        {sent ? (
          <>
            <p className="ok-text">
              Se o e-mail estiver cadastrado, enviaremos instrucoes para redefinir a senha.
            </p>
            <p style={{ textAlign: "center" }}>
              <Link to="/login">Voltar ao login</Link>
            </p>
          </>
        ) : (
          <>
            <div className="field">
              <label htmlFor="email">E-mail cadastrado</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            <button className="primary" type="submit" disabled={busy} style={{ width: "100%" }}>
              {busy ? <Spinner /> : "Enviar link"}
            </button>
            <p style={{ textAlign: "center", marginTop: 14 }}>
              <Link to="/login">Voltar ao login</Link>
            </p>
          </>
        )}
      </form>
    </div>
  );
}
