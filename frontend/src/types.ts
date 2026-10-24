export type FieldType =
  | "TEXT_BLOCK"
  | "LINK"
  | "ATTACHMENT"
  | "DATE"
  | "DATETIME"
  | "CHECKLIST";

export type Role = "owner" | "editor";

export interface PublicConfig {
  firebaseApiKey: string;
  firebaseAuthDomain: string;
  firebaseProjectId: string;
  firebaseAppId: string;
  appTimezone: string;
  maxUploadBytes: number;
  appEnv: string;
  usingEmulators: boolean;
  firestoreEmulatorHost?: string | null;
  authEmulatorHost?: string | null;
}

export interface Me {
  uid: string;
  name: string;
  email: string;
  status: string;
}

export interface BoardSummary {
  boardId: string;
  title: string;
  role: Role;
  grantedAt?: string | null;
}

export interface Board {
  boardId: string;
  title: string;
  timezone: string;
  version: number;
  columnsOrderVersion: number;
  role: Role;
  createdAt: string;
  updatedAt: string;
}

export interface Column {
  columnId: string;
  title: string;
  sortKey: string;
  minimized: boolean;
  cardCount: number;
  version: number;
}

export interface ChecklistItem {
  itemId: string;
  text: string;
  checked: boolean;
  sortKey?: string;
}

export interface VisibleFieldSnapshot {
  fieldId: string;
  label: string;
  type: FieldType;
  value: unknown;
  isDeadline: boolean;
  attachments: { attachmentId: string; originalName: string }[];
}

export interface CardSummary {
  cardId: string;
  title: string;
  columnId: string;
  sortKey: string;
  contentVersion: number;
  positionVersion: number;
  visibleFieldsSnapshot: VisibleFieldSnapshot[];
  overdue: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface Field {
  fieldId?: string;
  label: string;
  type: FieldType;
  value: unknown;
  sortKey?: string;
  visibleOnBoard: boolean;
  isDeadline: boolean;
  semanticRole?: string | null;
}

export interface CardDetail {
  cardId: string;
  title: string;
  columnId: string;
  sortKey: string;
  contentVersion: number;
  positionVersion: number;
  fields: Field[];
  createdAt: string;
  updatedAt: string;
}

export interface Template {
  templateId: string;
  name: string;
  createdByUid: string;
  version: number;
  createdAt: string;
  updatedAt: string;
}

export interface Member {
  uid: string;
  name: string;
  email: string;
  role: Role;
  grantedAt: string;
}

export interface PublicLink {
  enabled: boolean;
  url: string | null;
  shareVersion: number;
}

export interface AuditEvent {
  eventId: string;
  action: string;
  entityType: string;
  entityId: string;
  actorUid: string;
  actorNameSnapshot: string;
  occurredAt: string;
  requestId: string;
  changedFields?: Record<string, unknown> | null;
}
