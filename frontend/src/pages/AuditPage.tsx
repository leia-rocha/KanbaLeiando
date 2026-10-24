import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { useConfig } from "../config";
import type { AuditEvent } from "../types";
import { AppHeader } from "../components/AppHeader";
import { EmptyState, Spinner } from "../components/ui";
import { formatDateTime } from "../lib/format";

const ACTION_LABEL: Record<string, string> = {
  "board.create": "Kanban criado",
  "board.rename": "Kanban renomeado",
  "column.create": "Coluna criada",
  "column.rename": "Coluna renomeada",
  "column.reorder": "Coluna reordenada",
  "column.minimize": "Coluna minimizada",
  "column.expand": "Coluna expandida",
  "column.delete": "Coluna excluida",
  "card.create": "Card criado",
  "card.edit": "Card editado",
  "card.move": "Card movido",
  "card.duplicate": "Card duplicado",
  "card.delete": "Card excluido",
  "template.create": "Modelo criado",
  "template.rename": "Modelo renomeado",
  "template.delete": "Modelo excluido",
  "member.grant": "Edicao concedida",
  "member.revoke": "Edicao revogada",
  "public_link.rotate": "Link publico atualizado",
  "public_link.revoke": "Link publico revogado",
};

export default function AuditPage() {
  const { boardId = "" } = useParams();
  const navigate = useNavigate();
  const cfg = useConfig();
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [cursor, setCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  async function load(next?: string | null) {
    const q = next ? `?cursor=${encodeURIComponent(next)}` : "";
    const data = await api.get<{ events: AuditEvent[]; nextCursor: string | null }>(
      `/boards/${boardId}/audit${q}`,
    );
    setEvents((prev) => (next ? [...(prev ?? []), ...data.events] : data.events));
    setCursor(data.nextCursor);
  }

  useEffect(() => {
    load().catch(() => setEvents([]));
  }, [boardId]);

  return (
    <>
      <AppHeader title="Auditoria">
        <button onClick={() => navigate(`/kanbans/${boardId}`)}>Voltar ao quadro</button>
      </AppHeader>
      {events === null ? (
        <div className="center-page">
          <Spinner />
        </div>
      ) : events.length === 0 ? (
        <EmptyState title="Nenhum evento registrado ainda." />
      ) : (
        <div>
          {events.map((e) => (
            <div className="audit-row" key={e.eventId}>
              <strong>{ACTION_LABEL[e.action] ?? e.action}</strong>{" "}
              <span className="muted">por {e.actorNameSnapshot}</span>
              <div className="when">{formatDateTime(e.occurredAt, cfg.appTimezone)}</div>
            </div>
          ))}
          {cursor && (
            <div style={{ textAlign: "center", padding: 16 }}>
              <button
                onClick={async () => {
                  setLoadingMore(true);
                  await load(cursor);
                  setLoadingMore(false);
                }}
              >
                {loadingMore ? <Spinner /> : "Carregar mais"}
              </button>
            </div>
          )}
        </div>
      )}
    </>
  );
}
