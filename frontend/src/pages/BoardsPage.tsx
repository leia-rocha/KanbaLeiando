import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Board, BoardSummary } from "../types";
import { AppHeader } from "../components/AppHeader";
import { EmptyState, Modal, Spinner } from "../components/ui";

export default function BoardsPage() {
  const navigate = useNavigate();
  const [boards, setBoards] = useState<BoardSummary[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    const data = await api.get<{ boards: BoardSummary[] }>("/boards");
    setBoards(data.boards);
  }

  useEffect(() => {
    load().catch(() => setError("Nao foi possivel carregar seus kanbans."));
  }, []);

  async function createBoard(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try {
      const board = await api.post<Board>("/boards", {
        name: name.trim(),
        idempotencyKey: crypto.randomUUID(),
      });
      navigate(`/kanbans/${board.boardId}`);
    } catch {
      setError("Nao foi possivel criar o kanban.");
      setBusy(false);
    }
  }

  return (
    <>
      <AppHeader title="Meus kanbans">
        <button className="primary" onClick={() => setCreating(true)}>
          + Novo kanban
        </button>
      </AppHeader>

      {error && <p className="error-text" style={{ padding: 16 }}>{error}</p>}

      {boards === null ? (
        <div className="center-page">
          <Spinner />
        </div>
      ) : boards.length === 0 ? (
        <EmptyState
          title="Voce ainda nao tem kanbans."
          hint="Crie o primeiro para comecar a organizar seus cards."
        />
      ) : (
        <div className="list-grid">
          {boards.map((b) => (
            <div
              key={b.boardId}
              className="list-item"
              role="button"
              tabIndex={0}
              onClick={() => navigate(`/kanbans/${b.boardId}`)}
              onKeyDown={(e) => e.key === "Enter" && navigate(`/kanbans/${b.boardId}`)}
            >
              <span className={`badge ${b.role === "owner" ? "owner" : ""}`}>
                {b.role === "owner" ? "Dono" : "Editor"}
              </span>
              <strong>{b.title}</strong>
            </div>
          ))}
        </div>
      )}

      {creating && (
        <Modal title="Novo kanban" onClose={() => setCreating(false)}>
          <form onSubmit={createBoard}>
            <div className="field">
              <label htmlFor="bname">Nome</label>
              <input
                id="bname"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
                maxLength={200}
                required
              />
            </div>
            <div className="row">
              <button className="primary" type="submit" disabled={busy}>
                {busy ? <Spinner /> : "Criar"}
              </button>
              <button type="button" className="ghost" onClick={() => setCreating(false)}>
                Cancelar
              </button>
            </div>
          </form>
        </Modal>
      )}
    </>
  );
}
