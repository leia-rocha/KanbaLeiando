import { useEffect, useState } from "react";
import { api } from "../api";
import type { CardDetail, ChecklistItem, Field, FieldType, Template } from "../types";
import { Modal, Spinner } from "./ui";
import { formatDateTime } from "../lib/format";

const FIELD_TYPES: { value: FieldType; label: string }[] = [
  { value: "TEXT_BLOCK", label: "Texto" },
  { value: "LINK", label: "Link" },
  { value: "ATTACHMENT", label: "Anexo" },
  { value: "DATE", label: "Data" },
  { value: "DATETIME", label: "Data/Hora" },
  { value: "CHECKLIST", label: "Checklist" },
];

const CAN_DEADLINE: FieldType[] = ["DATE", "DATETIME"];

export function CardDetailModal({
  boardId,
  cardId,
  timezone,
  readOnly,
  onClose,
  onChanged,
}: {
  boardId: string;
  cardId: string;
  timezone: string;
  readOnly: boolean;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [card, setCard] = useState<CardDetail | null>(null);
  const [title, setTitle] = useState("");
  const [fields, setFields] = useState<Field[]>([]);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [templateName, setTemplateName] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<CardDetail>(`/boards/${boardId}/cards/${cardId}`)
      .then((c) => {
        setCard(c);
        setTitle(c.title);
        setFields(c.fields.map((f) => ({ ...f })));
      })
      .catch(() => setError("Nao foi possivel abrir o card."));
  }, [boardId, cardId]);

  function markDirty() {
    setDirty(true);
  }

  function updateField(index: number, patch: Partial<Field>) {
    setFields((prev) => prev.map((f, i) => (i === index ? { ...f, ...patch } : f)));
    markDirty();
  }

  function addField() {
    setFields((prev) => [
      ...prev,
      { label: "Novo campo", type: "TEXT_BLOCK", value: null, visibleOnBoard: false, isDeadline: false },
    ]);
    markDirty();
  }

  function removeField(index: number) {
    setFields((prev) => prev.filter((_, i) => i !== index));
    markDirty();
  }

  function moveField(index: number, dir: -1 | 1) {
    setFields((prev) => {
      const next = [...prev];
      const j = index + dir;
      if (j < 0 || j >= next.length) return prev;
      [next[index], next[j]] = [next[j], next[index]];
      return next;
    });
    markDirty();
  }

  const visibleCount = fields.filter((f) => f.visibleOnBoard).length;

  async function save() {
    if (!card) return;
    if (!title.trim()) {
      setError("O titulo e obrigatorio.");
      return;
    }
    if (visibleCount > 2) {
      setError("No maximo dois campos podem ser visiveis no quadro.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const payload = {
        title: title.trim(),
        contentVersion: card.contentVersion,
        fields: fields.map((f) => ({
          fieldId: f.fieldId ?? null,
          label: f.label,
          type: f.type,
          value: f.value ?? null,
          visibleOnBoard: f.visibleOnBoard,
          isDeadline: CAN_DEADLINE.includes(f.type) ? f.isDeadline : false,
        })),
      };
      const updated = await api.patch<CardDetail>(
        `/boards/${boardId}/cards/${cardId}`,
        payload,
      );
      setCard(updated);
      setDirty(false);
      onChanged();
    } catch (e: any) {
      if (e?.status === 409) setError("O card foi alterado por outra pessoa. Recarregue.");
      else setError(e?.message ?? "Nao foi possivel salvar.");
    } finally {
      setBusy(false);
    }
  }

  async function duplicate() {
    setBusy(true);
    try {
      await api.post(`/boards/${boardId}/cards/${cardId}/duplicate`, {
        idempotencyKey: crypto.randomUUID(),
      });
      onChanged();
      onClose();
    } finally {
      setBusy(false);
    }
  }

  async function saveAsTemplate() {
    const name = prompt("Nome do modelo:");
    if (!name?.trim()) return;
    if (dirty) {
      await save();
    }
    try {
      await api.post<Template>(`/boards/${boardId}/templates`, {
        name: name.trim(),
        fromCardId: cardId,
        replaceExisting: false,
      });
      setTemplateName(name.trim());
    } catch (e: any) {
      setError(e?.message ?? "Nao foi possivel criar o modelo.");
    }
  }

  function requestClose() {
    if (dirty && !confirm("Ha alteracoes nao salvas. Descartar?")) return;
    onClose();
  }

  if (error && !card) {
    return (
      <Modal title="Card" onClose={onClose}>
        <p className="error-text">{error}</p>
      </Modal>
    );
  }
  if (!card) {
    return (
      <Modal title="Card" onClose={onClose}>
        <Spinner />
      </Modal>
    );
  }

  return (
    <Modal
      title={readOnly ? "Card (somente leitura)" : "Detalhe do card"}
      onClose={requestClose}
      actions={
        !readOnly && (
          <>
            <button className="ghost icon-btn" onClick={duplicate} title="Duplicar">
              Duplicar
            </button>
            <button className="ghost icon-btn" onClick={saveAsTemplate}>
              Utilizar como modelo
            </button>
          </>
        )
      }
    >
      <div className="field">
        <label>Nome</label>
        <input
          value={title}
          disabled={readOnly}
          onChange={(e) => {
            setTitle(e.target.value);
            markDirty();
          }}
          maxLength={200}
        />
      </div>

      {templateName && <p className="ok-text">Modelo "{templateName}" criado.</p>}

      {fields.map((f, i) => (
        <FieldEditor
          key={f.fieldId ?? `new-${i}`}
          field={f}
          index={i}
          total={fields.length}
          readOnly={readOnly}
          timezone={timezone}
          onChange={(patch) => updateField(i, patch)}
          onRemove={() => removeField(i)}
          onMove={(dir) => moveField(i, dir)}
        />
      ))}

      {!readOnly && (
        <button className="ghost" onClick={addField} style={{ width: "100%" }}>
          + Adicionar campo
        </button>
      )}

      <p className="muted" style={{ marginTop: 10 }}>
        Campos visiveis no quadro: {visibleCount}/2
      </p>
      <p className="muted">Criado: {formatDateTime(card.createdAt, timezone)}</p>

      {error && <p className="error-text">{error}</p>}

      {!readOnly && (
        <div className="row" style={{ marginTop: 12 }}>
          <button className="primary" onClick={save} disabled={busy || !dirty}>
            {busy ? <Spinner /> : "Salvar"}
          </button>
          <button className="ghost" onClick={requestClose}>
            Fechar
          </button>
        </div>
      )}
    </Modal>
  );
}

function FieldEditor({
  field,
  index,
  total,
  readOnly,
  timezone,
  onChange,
  onRemove,
  onMove,
}: {
  field: Field;
  index: number;
  total: number;
  readOnly: boolean;
  timezone: string;
  onChange: (patch: Partial<Field>) => void;
  onRemove: () => void;
  onMove: (dir: -1 | 1) => void;
}) {
  const canDeadline = CAN_DEADLINE.includes(field.type);

  function changeType(newType: FieldType) {
    if (field.value != null && field.value !== "" && newType !== field.type) {
      if (!confirm("Mudar o tipo descarta o valor atual. Continuar?")) return;
    }
    onChange({ type: newType, value: null, isDeadline: false });
  }

  return (
    <div className="field-editor">
      <div className="row">
        <input
          style={{ flex: 2 }}
          value={field.label}
          disabled={readOnly}
          onChange={(e) => onChange({ label: e.target.value })}
          maxLength={120}
          placeholder="Nome do campo"
        />
        <select
          value={field.type}
          disabled={readOnly || field.semanticRole === "creation"}
          onChange={(e) => changeType(e.target.value as FieldType)}
          style={{ flex: 1, width: "auto" }}
        >
          {FIELD_TYPES.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </select>
        {!readOnly && (
          <>
            <button className="ghost icon-btn" onClick={() => onMove(-1)} disabled={index === 0}>
              ↑
            </button>
            <button
              className="ghost icon-btn"
              onClick={() => onMove(1)}
              disabled={index === total - 1}
            >
              ↓
            </button>
            <button className="danger icon-btn" onClick={onRemove}>
              Remover
            </button>
          </>
        )}
      </div>

      <div style={{ marginTop: 8 }}>
        <FieldValue field={field} readOnly={readOnly} timezone={timezone} onChange={onChange} />
      </div>

      {!readOnly && (
        <div className="row" style={{ marginTop: 8 }}>
          <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input
              type="checkbox"
              style={{ width: "auto", minHeight: "auto" }}
              checked={field.visibleOnBoard}
              onChange={(e) => onChange({ visibleOnBoard: e.target.checked })}
            />
            Visivel no quadro
          </label>
          {canDeadline && (
            <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <input
                type="checkbox"
                style={{ width: "auto", minHeight: "auto" }}
                checked={field.isDeadline}
                onChange={(e) => onChange({ isDeadline: e.target.checked })}
              />
              Prazo
            </label>
          )}
        </div>
      )}
    </div>
  );
}

function FieldValue({
  field,
  readOnly,
  onChange,
}: {
  field: Field;
  readOnly: boolean;
  timezone: string;
  onChange: (patch: Partial<Field>) => void;
}) {
  switch (field.type) {
    case "TEXT_BLOCK":
      return (
        <textarea
          value={(field.value as string) ?? ""}
          disabled={readOnly}
          onChange={(e) => onChange({ value: e.target.value })}
        />
      );
    case "LINK":
      return (
        <input
          type="url"
          placeholder="https://..."
          value={(field.value as string) ?? ""}
          disabled={readOnly}
          onChange={(e) => onChange({ value: e.target.value })}
        />
      );
    case "DATE":
      return (
        <input
          type="date"
          value={(field.value as string) ?? ""}
          disabled={readOnly}
          onChange={(e) => onChange({ value: e.target.value })}
        />
      );
    case "DATETIME":
      return (
        <input
          type="datetime-local"
          value={toLocalInput((field.value as string) ?? "")}
          disabled={readOnly}
          onChange={(e) => onChange({ value: fromLocalInput(e.target.value) })}
        />
      );
    case "CHECKLIST":
      return <ChecklistEditor field={field} readOnly={readOnly} onChange={onChange} />;
    case "ATTACHMENT":
      return (
        <p className="muted">
          Anexos sao gerenciados ao salvar. Arquivos ate 20 MB cada.
        </p>
      );
    default:
      return null;
  }
}

function ChecklistEditor({
  field,
  readOnly,
  onChange,
}: {
  field: Field;
  readOnly: boolean;
  onChange: (patch: Partial<Field>) => void;
}) {
  const items: ChecklistItem[] = Array.isArray(field.value) ? (field.value as ChecklistItem[]) : [];

  function update(next: ChecklistItem[]) {
    onChange({ value: next });
  }

  return (
    <div>
      {items.map((it, i) => (
        <div className="checklist-item" key={it.itemId ?? i}>
          <input
            type="checkbox"
            checked={it.checked}
            disabled={readOnly}
            onChange={(e) =>
              update(items.map((x, j) => (j === i ? { ...x, checked: e.target.checked } : x)))
            }
          />
          <input
            value={it.text}
            disabled={readOnly}
            onChange={(e) =>
              update(items.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))
            }
          />
          {!readOnly && (
            <button
              className="danger icon-btn"
              onClick={() => update(items.filter((_, j) => j !== i))}
            >
              x
            </button>
          )}
        </div>
      ))}
      {!readOnly && (
        <button
          className="ghost icon-btn"
          onClick={() =>
            update([
              ...items,
              { itemId: crypto.randomUUID(), text: "", checked: false },
            ])
          }
        >
          + Item
        </button>
      )}
    </div>
  );
}

function toLocalInput(iso: string): string {
  if (!iso) return "";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const d = new Date(t);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function fromLocalInput(local: string): string | null {
  if (!local) return null;
  const d = new Date(local);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}
