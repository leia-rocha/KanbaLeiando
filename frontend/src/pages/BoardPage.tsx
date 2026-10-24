import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  DndContext,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { api } from "../api";
import { db } from "../firebase";
import { useConfig } from "../config";
import { useBoardData } from "../lib/useBoardData";
import type { Board, CardDetail, CardSummary, Column, Template } from "../types";
import { AppHeader } from "../components/AppHeader";
import { CardView } from "../components/CardView";
import { CardDetailModal } from "../components/CardDetail";
import { ShareModal } from "../components/ShareModal";
import { EmptyState, Modal, Spinner } from "../components/ui";
import { isDateOverdue, isDateTimeOverdue } from "../lib/overdue";
import { normalizeSearch } from "../lib/format";

type Filter = { hasDeadline: boolean; overdueOnly: boolean; column: string };

export default function BoardPage() {
  const { boardId = "" } = useParams();
  const navigate = useNavigate();
  const cfg = useConfig();
  const [params, setParams] = useSearchParams();
  const [board, setBoard] = useState<Board | null>(null);
  const [tick, setTick] = useState(0); // recalculo de atraso por temporizador
  const live = useBoardData(db(), boardId);

  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<Filter>({ hasDeadline: false, overdueOnly: false, column: "" });
  const [openCardId, setOpenCardId] = useState<string | null>(params.get("card"));
  const [sharing, setSharing] = useState(false);
  const [addingTo, setAddingTo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sensors = useSensors(useSensor(PointerSensor), useSensor(KeyboardSensor));

  useEffect(() => {
    api
      .get<Board>(`/boards/${boardId}`)
      .then(setBoard)
      .catch(() => setError("Nao foi possivel abrir o kanban."));
  }, [boardId]);

  // Recalcula atraso periodicamente e ao voltar para a aba (RF30).
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 60000);
    const onVis = () => document.visibilityState === "visible" && setTick((n) => n + 1);
    document.addEventListener("visibilitychange", onVis);
    return () => {
      clearInterval(t);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, []);

  const tz = board?.timezone ?? cfg.appTimezone;

  const overdueOf = useMemo(() => {
    void tick;
    return (card: CardSummary): boolean => {
      for (const f of card.visibleFieldsSnapshot) {
        if (!f.isDeadline) continue;
        if (f.type === "DATE" && typeof f.value === "string" && isDateOverdue(f.value, tz))
          return true;
        if (f.type === "DATETIME" && typeof f.value === "string" && isDateTimeOverdue(f.value))
          return true;
      }
      // Campos de prazo nao visiveis: confia no overdue calculado pelo backend.
      return card.overdue;
    };
  }, [tz, tick]);

  const filtered = useMemo(() => {
    const q = normalizeSearch(search);
    return live.cards.filter((c) => {
      if (q && !normalizeSearch(c.title).includes(q)) return false;
      if (filter.column && c.columnId !== filter.column) return false;
      if (filter.hasDeadline && !c.visibleFieldsSnapshot.some((f) => f.isDeadline) && !c.overdue)
        return false;
      if (filter.overdueOnly && !overdueOf(c)) return false;
      return true;
    });
  }, [live.cards, search, filter, overdueOf]);

  const cardsByColumn = useMemo(() => {
    const map = new Map<string, CardSummary[]>();
    for (const c of filtered) {
      const arr = map.get(c.columnId) ?? [];
      arr.push(c);
      map.set(c.columnId, arr);
    }
    for (const arr of map.values()) arr.sort((a, b) => a.sortKey.localeCompare(b.sortKey));
    return map;
  }, [filtered]);

  if (live.error === "access_removed") {
    return (
      <>
        <AppHeader title="Kanban" />
        <EmptyState title="Acesso removido ou quadro indisponivel." hint="Volte aos seus kanbans." />
        <div style={{ textAlign: "center" }}>
          <button onClick={() => navigate("/kanbans")}>Voltar</button>
        </div>
      </>
    );
  }

  const isOwner = board?.role === "owner";

  function openCard(id: string) {
    setOpenCardId(id);
    setParams((p) => {
      p.set("card", id);
      return p;
    });
  }
  function closeCard() {
    setOpenCardId(null);
    setParams((p) => {
      p.delete("card");
      return p;
    });
  }

  async function onDragEnd(e: DragEndEvent) {
    const cardId = String(e.active.id);
    const overId = e.over?.id ? String(e.over.id) : null;
    if (!overId) return;
    const card = live.cards.find((c) => c.cardId === cardId);
    if (!card) return;
    const targetColumn = overId.startsWith("col:") ? overId.slice(4) : card.columnId;
    const siblings = (cardsByColumn.get(targetColumn) ?? []).filter((c) => c.cardId !== cardId);
    const afterCardId = siblings.length ? siblings[siblings.length - 1].cardId : null;
    await moveCard(card, targetColumn, afterCardId, null);
  }

  async function moveCard(
    card: CardSummary,
    targetColumnId: string,
    afterCardId: string | null,
    beforeCardId: string | null,
  ) {
    try {
      await api.post(`/boards/${boardId}/cards/${card.cardId}/move`, {
        targetColumnId,
        afterCardId,
        beforeCardId,
        positionVersion: card.positionVersion,
      });
    } catch (e: any) {
      if (e?.status === 409) setError("A posicao mudou. A tela foi atualizada.");
    }
  }

  async function duplicateCard(cardId: string) {
    await api.post(`/boards/${boardId}/cards/${cardId}/duplicate`, {
      idempotencyKey: crypto.randomUUID(),
    });
  }

  return (
    <>
      <AppHeader title={live.boardTitle || board?.title || "Kanban"}>
        <button onClick={() => navigate("/kanbans")}>Voltar</button>
        <button onClick={() => setSharing(true)} aria-label="Compartilhar">
          Compartilhar
        </button>
        <button onClick={() => navigate(`/kanbans/${boardId}/audit`)}>Auditoria</button>
        {isOwner && <RenameDelete boardId={boardId} board={board} onRenamed={setBoard} />}
      </AppHeader>

      <div className="toolbar">
        <input
          placeholder="Buscar por titulo..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 260 }}
        />
        <select
          value={filter.column}
          onChange={(e) => setFilter((f) => ({ ...f, column: e.target.value }))}
          style={{ width: "auto" }}
        >
          <option value="">Todas as colunas</option>
          {live.columns.map((c) => (
            <option key={c.columnId} value={c.columnId}>
              {c.title}
            </option>
          ))}
        </select>
        <label style={{ display: "flex", gap: 6, alignItems: "center", margin: 0 }}>
          <input
            type="checkbox"
            style={{ width: "auto", minHeight: "auto" }}
            checked={filter.hasDeadline}
            onChange={(e) => setFilter((f) => ({ ...f, hasDeadline: e.target.checked }))}
          />
          Com prazo
        </label>
        <label style={{ display: "flex", gap: 6, alignItems: "center", margin: 0 }}>
          <input
            type="checkbox"
            style={{ width: "auto", minHeight: "auto" }}
            checked={filter.overdueOnly}
            onChange={(e) => setFilter((f) => ({ ...f, overdueOnly: e.target.checked }))}
          />
          Atrasados
        </label>
        <button
          className="ghost"
          onClick={() => {
            setSearch("");
            setFilter({ hasDeadline: false, overdueOnly: false, column: "" });
          }}
        >
          Limpar filtros
        </button>
      </div>

      {error && <p className="error-text" style={{ padding: "0 16px" }}>{error}</p>}

      {live.loading ? (
        <div className="center-page">
          <Spinner />
        </div>
      ) : (
        <DndContext sensors={sensors} onDragEnd={onDragEnd}>
          <div className="board-scroll">
            {live.columns.map((col) => (
              <ColumnView
                key={col.columnId}
                boardId={boardId}
                column={col}
                columns={live.columns}
                cards={cardsByColumn.get(col.columnId) ?? []}
                timezone={tz}
                overdueOf={overdueOf}
                onAddCard={() => setAddingTo(col.columnId)}
                onOpenCard={openCard}
                onDuplicate={duplicateCard}
                onMoveCard={moveCard}
              />
            ))}
            <AddColumn boardId={boardId} />
          </div>
        </DndContext>
      )}

      {openCardId && (
        <CardDetailModal
          boardId={boardId}
          cardId={openCardId}
          timezone={tz}
          readOnly={false}
          onClose={closeCard}
          onChanged={() => {}}
        />
      )}
      {sharing && (
        <ShareModal boardId={boardId} isOwner={!!isOwner} onClose={() => setSharing(false)} />
      )}
      {addingTo && (
        <AddCardModal
          boardId={boardId}
          columnId={addingTo}
          onClose={() => setAddingTo(null)}
          onCreated={(id) => {
            setAddingTo(null);
            openCard(id);
          }}
        />
      )}
    </>
  );
}

function ColumnView({
  boardId,
  column,
  columns,
  cards,
  timezone,
  overdueOf,
  onAddCard,
  onOpenCard,
  onDuplicate,
  onMoveCard,
}: {
  boardId: string;
  column: Column;
  columns: Column[];
  cards: CardSummary[];
  timezone: string;
  overdueOf: (c: CardSummary) => boolean;
  onAddCard: () => void;
  onOpenCard: (id: string) => void;
  onDuplicate: (id: string) => void;
  onMoveCard: (
    card: CardSummary,
    target: string,
    after: string | null,
    before: string | null,
  ) => void;
}) {
  const [editingName, setEditingName] = useState(false);
  const [name, setName] = useState(column.title);

  async function toggleMin() {
    await api.patch(`/boards/${boardId}/columns/${column.columnId}`, {
      minimized: !column.minimized,
      baseVersion: column.version,
    });
  }
  async function rename() {
    await api.patch(`/boards/${boardId}/columns/${column.columnId}`, {
      title: name.trim(),
      baseVersion: column.version,
    });
    setEditingName(false);
  }
  async function del() {
    if (!confirm(`Excluir a coluna "${column.title}"? Ela precisa estar vazia.`)) return;
    try {
      await api.del(`/boards/${boardId}/columns/${column.columnId}`);
    } catch (e: any) {
      alert(e?.message ?? "Nao foi possivel excluir.");
    }
  }

  if (column.minimized) {
    return (
      <div
        className="column minimized"
        id={`col:${column.columnId}`}
        onDragOver={(e) => e.preventDefault()}
      >
        <button className="ghost icon-btn" onClick={toggleMin} title="Expandir">
          ⤢
        </button>
        <div className="spine">
          {column.title} ({cards.length})
        </div>
      </div>
    );
  }

  return (
    <section className="column" aria-label={column.title}>
      <div className="column-head">
        {editingName ? (
          <input value={name} onChange={(e) => setName(e.target.value)} onBlur={rename} autoFocus />
        ) : (
          <span className="col-title" onDoubleClick={() => setEditingName(true)}>
            {column.title} <span className="muted">({cards.length})</span>
          </span>
        )}
        <button className="ghost icon-btn" onClick={toggleMin} title="Minimizar">
          –
        </button>
        <button className="ghost icon-btn" onClick={del} title="Excluir coluna">
          🗑
        </button>
      </div>
      <div
        className="column-body"
        id={`col:${column.columnId}`}
        data-droppable="true"
        onDragOver={(e) => e.preventDefault()}
      >
        {cards.map((c) => (
          <DraggableCard key={c.cardId} cardId={c.cardId}>
            <CardView
              card={c}
              timezone={timezone}
              overdue={overdueOf(c)}
              readOnly={false}
              onOpen={() => onOpenCard(c.cardId)}
              onEdit={() => onOpenCard(c.cardId)}
              onDuplicate={() => onDuplicate(c.cardId)}
            />
            <MoveMenu
              card={c}
              columns={columns}
              onMove={(target) => onMoveCard(c, target, null, null)}
            />
          </DraggableCard>
        ))}
        <button className="ghost" onClick={onAddCard} style={{ width: "100%" }}>
          + Adicionar card
        </button>
      </div>
    </section>
  );
}

function DraggableCard({ cardId, children }: { cardId: string; children: React.ReactNode }) {
  // dnd-kit via atributos nativos simplificados: usamos draggable HTML para
  // compatibilidade ampla, com alternativa por menu (MoveMenu) para teclado.
  return (
    <div
      draggable
      onDragStart={(e) => e.dataTransfer.setData("text/plain", cardId)}
      data-card-id={cardId}
    >
      {children}
    </div>
  );
}

function MoveMenu({
  card,
  columns,
  onMove,
}: {
  card: CardSummary;
  columns: Column[];
  onMove: (target: string) => void;
}) {
  return (
    <div className="row" style={{ marginTop: 6 }}>
      <label style={{ margin: 0, fontSize: "0.78rem" }}>Mover para:</label>
      <select
        aria-label="Mover card para coluna"
        value={card.columnId}
        onChange={(e) => onMove(e.target.value)}
        style={{ width: "auto", minHeight: 32 }}
      >
        {columns.map((c) => (
          <option key={c.columnId} value={c.columnId}>
            {c.title}
          </option>
        ))}
      </select>
    </div>
  );
}

function AddColumn({ boardId }: { boardId: string }) {
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  async function create() {
    if (!name.trim()) return;
    await api.post(`/boards/${boardId}/columns`, { title: name.trim() });
    setName("");
    setAdding(false);
  }
  return (
    <div className="column" style={{ background: "transparent", borderStyle: "dashed" }}>
      <div className="column-body">
        {adding ? (
          <>
            <input value={name} onChange={(e) => setName(e.target.value)} autoFocus maxLength={120} />
            <div className="row">
              <button className="primary" onClick={create}>
                Criar
              </button>
              <button className="ghost" onClick={() => setAdding(false)}>
                Cancelar
              </button>
            </div>
          </>
        ) : (
          <button className="ghost" onClick={() => setAdding(true)}>
            + Nova coluna
          </button>
        )}
      </div>
    </div>
  );
}

function RenameDelete({
  boardId,
  board,
  onRenamed,
}: {
  boardId: string;
  board: Board | null;
  onRenamed: (b: Board) => void;
}) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState(board?.title ?? "");
  if (!board) return null;

  async function rename() {
    const b = await api.patch<Board>(`/boards/${boardId}`, {
      name: name.trim(),
      baseVersion: board!.version,
    });
    onRenamed(b);
    setOpen(false);
  }
  async function del() {
    if (!confirm("Excluir este kanban e todos os seus dados? Esta acao e definitiva.")) return;
    await api.del(`/boards/${boardId}`);
    navigate("/kanbans");
  }

  return (
    <>
      <button className="ghost" onClick={() => setOpen(true)}>
        Opcoes
      </button>
      {open && (
        <Modal title="Opcoes do kanban" onClose={() => setOpen(false)}>
          <div className="field">
            <label>Renomear</label>
            <div className="row">
              <input value={name} onChange={(e) => setName(e.target.value)} style={{ flex: 1 }} />
              <button className="primary" onClick={rename}>
                Salvar
              </button>
            </div>
          </div>
          <hr style={{ borderColor: "var(--border)" }} />
          <button className="danger" onClick={del}>
            Excluir kanban
          </button>
        </Modal>
      )}
    </>
  );
}

function AddCardModal({
  boardId,
  columnId,
  onClose,
  onCreated,
}: {
  boardId: string;
  columnId: string;
  onClose: () => void;
  onCreated: (id: string) => void;
}) {
  const [templates, setTemplates] = useState<Template[] | null>(null);
  const [title, setTitle] = useState("");
  const [templateId, setTemplateId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<Template[]>(`/boards/${boardId}/templates`)
      .then(setTemplates)
      .catch(() => setTemplates([]));
  }, [boardId]);

  async function create() {
    if (!title.trim()) {
      setError("Informe o nome do card.");
      return;
    }
    setBusy(true);
    try {
      const card = await api.post<CardDetail>(`/boards/${boardId}/cards`, {
        title: title.trim(),
        columnId,
        templateId,
        idempotencyKey: crypto.randomUUID(),
      });
      onCreated(card.cardId);
    } catch (e: any) {
      setError(e?.message ?? "Nao foi possivel criar o card.");
      setBusy(false);
    }
  }

  return (
    <Modal title="Adicionar card" onClose={onClose}>
      <div className="field">
        <label>Nome</label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} autoFocus maxLength={200} />
      </div>
      {templates && templates.length > 0 && (
        <div className="field">
          <label>Estrutura</label>
          <select
            value={templateId ?? ""}
            onChange={(e) => setTemplateId(e.target.value || null)}
            style={{ width: "100%" }}
          >
            <option value="">Card em branco</option>
            {templates.map((t) => (
              <option key={t.templateId} value={t.templateId}>
                Modelo: {t.name}
              </option>
            ))}
          </select>
        </div>
      )}
      {error && <p className="error-text">{error}</p>}
      <div className="row">
        <button className="primary" onClick={create} disabled={busy}>
          {busy ? <Spinner /> : "Criar"}
        </button>
        <button className="ghost" onClick={onClose}>
          Cancelar
        </button>
      </div>
    </Modal>
  );
}
