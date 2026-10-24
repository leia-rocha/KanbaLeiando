import type { CardSummary, FieldType, ChecklistItem } from "../types";
import { formatDate, formatDateTime } from "../lib/format";

export function CardView({
  card,
  timezone,
  overdue,
  readOnly,
  onOpen,
  onEdit,
  onDuplicate,
}: {
  card: CardSummary;
  timezone: string;
  overdue: boolean;
  readOnly: boolean;
  onOpen: () => void;
  onEdit: () => void;
  onDuplicate: () => void;
}) {
  return (
    <div
      className={`kcard ${overdue ? "overdue" : ""}`}
      onDoubleClick={onOpen}
      role="group"
      aria-label={card.title}
    >
      <div className="card-title">{card.title}</div>
      <div className="card-actions">
        <button className="ghost icon-btn" onClick={onOpen} aria-label="Abrir">
          Abrir
        </button>
        {!readOnly && (
          <>
            <button className="ghost icon-btn" onClick={onEdit} aria-label="Editar" title="Editar">
              ✎
            </button>
            <button
              className="ghost icon-btn"
              onClick={onDuplicate}
              aria-label="Duplicar"
              title="Duplicar"
            >
              ⧉
            </button>
          </>
        )}
      </div>

      {card.visibleFieldsSnapshot.map((f) => (
        <div className="field-pill" key={f.fieldId}>
          <div className="flabel">{f.label}</div>
          <FieldSnapshotValue type={f.type} value={f.value} timezone={timezone} attachments={f.attachments} />
        </div>
      ))}

      {overdue && (
        <div className="overdue-badge">
          <span aria-hidden>⏰</span> Atrasado
        </div>
      )}
    </div>
  );
}

function FieldSnapshotValue({
  type,
  value,
  timezone,
  attachments,
}: {
  type: FieldType;
  value: unknown;
  timezone: string;
  attachments: { attachmentId: string; originalName: string }[];
}) {
  if (type === "CHECKLIST" && Array.isArray(value)) {
    const items = value as ChecklistItem[];
    return (
      <div>
        {items.map((it) => (
          <div key={it.itemId} className="checklist-item">
            <input type="checkbox" checked={it.checked} readOnly />
            <span style={{ textDecoration: it.checked ? "line-through" : "none" }}>{it.text}</span>
          </div>
        ))}
      </div>
    );
  }
  if (type === "ATTACHMENT") {
    return (
      <div>
        {attachments.length === 0 ? (
          <span className="muted">Sem arquivos</span>
        ) : (
          attachments.map((a) => <div key={a.attachmentId}>📎 {a.originalName}</div>)
        )}
      </div>
    );
  }
  if (type === "DATE" && typeof value === "string") return <span>{formatDate(value)}</span>;
  if (type === "DATETIME" && typeof value === "string")
    return <span>{formatDateTime(value, timezone)}</span>;
  if (type === "LINK" && typeof value === "string" && value)
    return (
      <a href={value} target="_blank" rel="noopener noreferrer nofollow">
        {value}
      </a>
    );
  if (typeof value === "string") return <span>{value}</span>;
  return <span className="muted">—</span>;
}
