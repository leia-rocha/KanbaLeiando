import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { signInWithCustomToken } from "firebase/auth";
import { collection, onSnapshot, query, doc } from "firebase/firestore";
import { api } from "../api";
import { useConfig } from "../config";
import { initPublicFirebase } from "../firebase";
import type { CardSummary, Column } from "../types";
import { CardView } from "../components/CardView";
import { CardDetailModal } from "../components/CardDetail";
import { EmptyState, Logo, Spinner } from "../components/ui";
import { isDateOverdue, isDateTimeOverdue } from "../lib/overdue";
import { normalizeSearch } from "../lib/format";

// Leitura publica em tempo real (RF33). Usa instancia Firebase separada, token no
// fragmento (#token=...), sem substituir o login comum.
export default function PublicBoardPage() {
  const { boardId = "" } = useParams();
  const cfg = useConfig();
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [columns, setColumns] = useState<Column[]>([]);
  const [cards, setCards] = useState<CardSummary[]>([]);
  const [title, setTitle] = useState("");
  const [search, setSearch] = useState("");
  const [openCardId, setOpenCardId] = useState<string | null>(null);

  useEffect(() => {
    const token = new URLSearchParams(location.hash.replace(/^#/, "")).get("token");
    if (!token) {
      setError("Link invalido.");
      return;
    }
    const { auth, db } = initPublicFirebase(cfg);
    let unsub: Array<() => void> = [];

    (async () => {
      try {
        const sess = await api.post<{ customToken: string }>("/public/session", {
          boardId,
          token,
        });
        await signInWithCustomToken(auth, sess.customToken);

        unsub.push(
          onSnapshot(
            doc(db, "boards", boardId),
            (snap) => snap.data() && setTitle((snap.data()!.title as string) ?? ""),
            () => setError("access_removed"),
          ),
        );
        unsub.push(
          onSnapshot(
            query(collection(db, "boards", boardId, "columns")),
            (snap) => {
              const list = snap.docs.map((d) => ({ columnId: d.id, ...(d.data() as any) })) as Column[];
              list.sort((a, b) => a.sortKey.localeCompare(b.sortKey));
              setColumns(list);
              setReady(true);
            },
            () => setError("access_removed"),
          ),
        );
        unsub.push(
          onSnapshot(
            query(collection(db, "boards", boardId, "cards")),
            (snap) => {
              const list = snap.docs.map((d) => ({ cardId: d.id, ...(d.data() as any) })) as CardSummary[];
              setCards(list);
            },
            () => setError("access_removed"),
          ),
        );
      } catch {
        setError("Link publico invalido ou expirado.");
      }
    })();

    return () => unsub.forEach((u) => u());
  }, [boardId, cfg]);

  const tz = cfg.appTimezone;
  const overdueOf = (c: CardSummary) => {
    for (const f of c.visibleFieldsSnapshot ?? []) {
      if (!f.isDeadline) continue;
      if (f.type === "DATE" && typeof f.value === "string" && isDateOverdue(f.value, tz)) return true;
      if (f.type === "DATETIME" && typeof f.value === "string" && isDateTimeOverdue(f.value))
        return true;
    }
    return !!c.overdue;
  };

  const byColumn = useMemo(() => {
    const q = normalizeSearch(search);
    const map = new Map<string, CardSummary[]>();
    for (const c of cards) {
      if (q && !normalizeSearch(c.title).includes(q)) continue;
      const arr = map.get(c.columnId) ?? [];
      arr.push(c);
      map.set(c.columnId, arr);
    }
    for (const arr of map.values()) arr.sort((a, b) => a.sortKey.localeCompare(b.sortKey));
    return map;
  }, [cards, search]);

  if (error === "access_removed") {
    return <EmptyState title="Acesso indisponivel." hint="O link pode ter sido revogado." />;
  }
  if (error) {
    return (
      <div className="center-page">
        <div className="card-box">
          <Logo />
          <p className="error-text">{error}</p>
        </div>
      </div>
    );
  }
  if (!ready) {
    return (
      <div className="center-page">
        <Spinner />
      </div>
    );
  }

  return (
    <>
      <header className="app-header">
        <Logo className="header-logo" />
        <span className="title">{title}</span>
        <span className="read-only-tag">Somente leitura</span>
        <span className="spacer" />
        <input
          placeholder="Buscar..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 220 }}
        />
      </header>
      <div className="board-scroll">
        {columns.map((col) =>
          col.minimized ? (
            <div className="column minimized" key={col.columnId}>
              <div className="spine">{col.title}</div>
            </div>
          ) : (
            <section className="column" key={col.columnId}>
              <div className="column-head">
                <span className="col-title">{col.title}</span>
              </div>
              <div className="column-body">
                {(byColumn.get(col.columnId) ?? []).map((c) => (
                  <CardView
                    key={c.cardId}
                    card={c}
                    timezone={tz}
                    overdue={overdueOf(c)}
                    readOnly
                    onOpen={() => setOpenCardId(c.cardId)}
                    onEdit={() => {}}
                    onDuplicate={() => {}}
                  />
                ))}
              </div>
            </section>
          ),
        )}
      </div>
      {openCardId && (
        <CardDetailModal
          boardId={boardId}
          cardId={openCardId}
          timezone={tz}
          readOnly
          onClose={() => setOpenCardId(null)}
          onChanged={() => {}}
        />
      )}
    </>
  );
}
