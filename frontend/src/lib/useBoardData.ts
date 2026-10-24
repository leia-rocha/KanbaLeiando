import { useEffect, useRef, useState } from "react";
import {
  collection,
  onSnapshot,
  query,
  doc,
  type Firestore,
} from "firebase/firestore";
import type { CardSummary, Column } from "../types";

// Listeners do Firestore para metadados do quadro, colunas e cards da tela aberta
// (RF35). Remove listeners ao sair. Reverte estado em falha de permissao.

export interface BoardLive {
  columns: Column[];
  cards: CardSummary[];
  boardTitle: string;
  error: string | null;
  loading: boolean;
}

export function useBoardData(dbInstance: Firestore, boardId: string): BoardLive {
  const [columns, setColumns] = useState<Column[]>([]);
  const [cards, setCards] = useState<CardSummary[]>([]);
  const [boardTitle, setBoardTitle] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const loadedRef = useRef({ board: false, cols: false });

  useEffect(() => {
    setLoading(true);
    setError(null);
    loadedRef.current = { board: false, cols: false };

    const unsubBoard = onSnapshot(
      doc(dbInstance, "boards", boardId),
      (snap) => {
        const d = snap.data();
        if (d) setBoardTitle((d.title as string) ?? "");
        loadedRef.current.board = true;
        maybeDoneLoading();
      },
      () => setError("access_removed"),
    );

    const unsubCols = onSnapshot(
      query(collection(dbInstance, "boards", boardId, "columns")),
      (snap) => {
        const list: Column[] = snap.docs.map((d) => {
          const x = d.data();
          return {
            columnId: d.id,
            title: x.title ?? "",
            sortKey: x.sortKey ?? "",
            minimized: !!x.minimized,
            cardCount: Number(x.cardCount ?? 0),
            version: Number(x.version ?? 1),
          };
        });
        list.sort((a, b) => a.sortKey.localeCompare(b.sortKey));
        setColumns(list);
        loadedRef.current.cols = true;
        maybeDoneLoading();
      },
      () => setError("access_removed"),
    );

    const unsubCards = onSnapshot(
      query(collection(dbInstance, "boards", boardId, "cards")),
      (snap) => {
        const list: CardSummary[] = snap.docs.map((d) => {
          const x = d.data();
          return {
            cardId: d.id,
            title: x.title ?? "",
            columnId: x.columnId ?? "",
            sortKey: x.sortKey ?? "",
            contentVersion: Number(x.contentVersion ?? 1),
            positionVersion: Number(x.positionVersion ?? 1),
            visibleFieldsSnapshot: x.visibleFieldsSnapshot ?? [],
            overdue: !!x.overdue,
            createdAt: x.createdAt ?? "",
            updatedAt: x.updatedAt ?? "",
          };
        });
        setCards(list);
      },
      () => setError("access_removed"),
    );

    function maybeDoneLoading() {
      if (loadedRef.current.board && loadedRef.current.cols) setLoading(false);
    }

    return () => {
      unsubBoard();
      unsubCols();
      unsubCards();
    };
  }, [dbInstance, boardId]);

  return { columns, cards, boardTitle, error, loading };
}
