import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  verifyPasswordResetCode,
  confirmPasswordReset,
  signInWithEmailAndPassword,
} from "firebase/auth";
import { auth } from "../firebase";
import { api } from "../api";
import { Logo, Spinner } from "../components/ui";

type Phase = "verifying" | "form" | "done" | "invalid";

// Trata primeiro acesso e recuperacao pela mesma pagina (RF03, RF04).
export default function AuthActionPage() {
  const [params] = useSearchParams();
  const oobCode = params.get("oobCode") ?? "";
  const mode = params.get("mode") ?? "resetPassword";

  const [phase, setPhase] = useState<Phase>("verifying");
  const [email, setEmail] = useState("");
  const [pw1, setPw1] = useState("");
  const [pw2, setPw2] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!oobCode || mode !== "resetPassword") {
      setPhase("invalid");
      return;
    }
    verifyPasswordResetCode(auth(), oobCode)
      .then((em) => {
        setEmail(em);
        setPhase("form");
      })
      .catch(() => setPhase("invalid"));
  }, [oobCode, mode]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (pw1.length < 8) {
      setError("A senha deve ter ao menos 8 caracteres.");
      return;
    }
    if (pw1 !== pw2) {
      setError("As senhas nao conferem.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await confirmPasswordReset(auth(), oobCode, pw1);
      // Autentica e chama a rota de ativacao (promove perfil a active).
      await signInWithEmailAndPassword(auth(), email, pw1);
      try {
        await api.post("/auth/activate", { confirm: true });
      } catch {
        // Recuperacao de senha de conta ja ativa tambem passa aqui; ignora 403.
      }
      setPhase("done");
    } catch {
      setError("Nao foi possivel concluir. O link pode ter expirado.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="center-page">
      <div className="card-box">
        <Logo />
        {phase === "verifying" && (
          <p className="row">
            <Spinner /> <span className="muted">Validando link...</span>
          </p>
        )}
        {phase === "invalid" && (
          <>
            <p className="error-text">Link invalido, expirado ou ja utilizado.</p>
            <p>Solicite um novo link de acesso ao administrador ou pela recuperacao de senha.</p>
            <Link to="/login">Voltar ao login</Link>
          </>
        )}
        {phase === "form" && (
          <form onSubmit={submit}>
            <h1 style={{ fontSize: "1.2rem" }}>Definir senha</h1>
            <p className="muted">Conta: {email}</p>
            <div className="field">
              <label htmlFor="pw1">Nova senha</label>
              <input
                id="pw1"
                type="password"
                value={pw1}
                onChange={(e) => setPw1(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            <div className="field">
              <label htmlFor="pw2">Confirmar senha</label>
              <input
                id="pw2"
                type="password"
                value={pw2}
                onChange={(e) => setPw2(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            {error && <p className="error-text">{error}</p>}
            <button className="primary" type="submit" disabled={busy} style={{ width: "100%" }}>
              {busy ? <Spinner /> : "Salvar senha"}
            </button>
          </form>
        )}
        {phase === "done" && (
          <>
            <p className="ok-text">Senha definida com sucesso.</p>
            <Link to="/kanbans">
              <button className="primary" style={{ width: "100%" }}>
                Ir para meus kanbans
              </button>
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
