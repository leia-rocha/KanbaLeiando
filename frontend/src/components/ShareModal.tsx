import { useEffect, useState } from "react";
import { api } from "../api";
import type { Member, PublicLink } from "../types";
import { Modal, Spinner } from "./ui";

export function ShareModal({
  boardId,
  isOwner,
  onClose,
}: {
  boardId: string;
  isOwner: boolean;
  onClose: () => void;
}) {
  const [members, setMembers] = useState<Member[]>([]);
  const [ownerUid, setOwnerUid] = useState("");
  const [link, setLink] = useState<PublicLink | null>(null);
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    const m = await api.get<{ members: Member[]; ownerUid: string }>(
      `/boards/${boardId}/members`,
    );
    setMembers(m.members);
    setOwnerUid(m.ownerUid);
    const l = await api.get<PublicLink>(`/boards/${boardId}/public-link`);
    setLink(l);
  }

  useEffect(() => {
    load().catch(() => setError("Nao foi possivel carregar o compartilhamento."));
  }, [boardId]);

  async function grant(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    setError(null);
    try {
      const res = await api.post<{ message: string; guidance?: string }>(
        `/boards/${boardId}/members`,
        { email: email.trim(), idempotencyKey: crypto.randomUUID() },
      );
      setMsg(res.guidance ? `${res.message} ${res.guidance}` : res.message);
      setEmail("");
      await load();
    } catch (e: any) {
      setError(e?.message ?? "Nao foi possivel conceder acesso.");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(uid: string) {
    if (!confirm("Remover o acesso deste editor?")) return;
    await api.del(`/boards/${boardId}/members/${uid}`);
    await load();
  }

  async function rotate() {
    const l = await api.post<PublicLink>(`/boards/${boardId}/public-link/rotate`);
    setLink(l);
  }
  async function revokeLink() {
    const l = await api.post<PublicLink>(`/boards/${boardId}/public-link/revoke`);
    setLink(l);
  }

  return (
    <Modal title="Compartilhar" onClose={onClose}>
      <form onSubmit={grant}>
        <label htmlFor="shemail">Conceder edicao por e-mail</label>
        <div className="row">
          <input
            id="shemail"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{ flex: 1 }}
            placeholder="pessoa@exemplo.com"
          />
          <button className="primary" type="submit" disabled={busy}>
            {busy ? <Spinner /> : "Conceder"}
          </button>
        </div>
      </form>
      {msg && <p className="ok-text">{msg}</p>}
      {error && <p className="error-text">{error}</p>}

      <h3 style={{ marginTop: 18 }}>Membros com edicao</h3>
      {members.map((m) => (
        <div className="row" key={m.uid} style={{ justifyContent: "space-between", padding: "6px 0" }}>
          <span>
            {m.name} <span className="muted">({m.email})</span>{" "}
            <span className={`badge ${m.uid === ownerUid ? "owner" : ""}`}>
              {m.uid === ownerUid ? "Dono" : "Editor"}
            </span>
          </span>
          {isOwner && m.uid !== ownerUid && (
            <button className="danger icon-btn" onClick={() => revoke(m.uid)}>
              Remover
            </button>
          )}
        </div>
      ))}

      <h3 style={{ marginTop: 18 }}>Link publico de leitura</h3>
      {link === null ? (
        <Spinner />
      ) : link.enabled && link.url ? (
        <>
          <input readOnly value={link.url} onFocus={(e) => e.currentTarget.select()} />
          <div className="row" style={{ marginTop: 8 }}>
            <button onClick={() => navigator.clipboard?.writeText(link.url!)}>Copiar</button>
            {isOwner && (
              <>
                <button onClick={rotate}>Gerar novo link</button>
                <button className="danger" onClick={revokeLink}>
                  Desativar
                </button>
              </>
            )}
          </div>
        </>
      ) : (
        <>
          <p className="muted">O link publico esta desativado.</p>
          {isOwner && (
            <button className="primary" onClick={rotate}>
              Ativar link publico
            </button>
          )}
        </>
      )}
    </Modal>
  );
}
