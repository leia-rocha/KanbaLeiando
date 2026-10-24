"""Acesso ao Firestore e caminhos das colecoes (secao 13).

Centraliza referencias de documentos para evitar strings espalhadas e para
garantir que fields e attachments sao subcolecoes de boards/{boardId}, nunca
colecoes globais.
"""

from __future__ import annotations

from google.cloud import firestore

from app.clients import get_firestore_client


class Collections:
    USERS = "users"
    BOARDS = "boards"
    BOARD_SECURITY = "boardSecurity"
    BOARD_TEMPLATES = "boardTemplates"
    BOARD_AUDIT = "boardAudit"
    OPERATIONS = "operations"
    UPLOAD_SESSIONS = "uploadSessions"
    ADMIN_SESSIONS = "adminSessions"
    RATE_LIMITS = "rateLimits"
    IDEMPOTENCY = "idempotency"
    EMAIL_JOBS = "emailJobs"


class Repo:
    """Fachada fina sobre o client Firestore com referencias tipadas."""

    def __init__(self, db: firestore.Client | None = None) -> None:
        self.db = db or get_firestore_client()

    # --- Usuarios ---
    def user_ref(self, uid: str):
        return self.db.collection(Collections.USERS).document(uid)

    def board_refs_col(self, uid: str):
        return self.user_ref(uid).collection("boardRefs")

    def board_ref_doc(self, uid: str, board_id: str):
        return self.board_refs_col(uid).document(board_id)

    # --- Boards (conteudo publico/leitura) ---
    def board_ref(self, board_id: str):
        return self.db.collection(Collections.BOARDS).document(board_id)

    def columns_col(self, board_id: str):
        return self.board_ref(board_id).collection("columns")

    def column_ref(self, board_id: str, column_id: str):
        return self.columns_col(board_id).document(column_id)

    def cards_col(self, board_id: str):
        return self.board_ref(board_id).collection("cards")

    def card_ref(self, board_id: str, card_id: str):
        return self.cards_col(board_id).document(card_id)

    def fields_col(self, board_id: str, card_id: str):
        return self.card_ref(board_id, card_id).collection("fields")

    def field_ref(self, board_id: str, card_id: str, field_id: str):
        return self.fields_col(board_id, card_id).document(field_id)

    def attachments_col(self, board_id: str, card_id: str):
        return self.card_ref(board_id, card_id).collection("attachments")

    def attachment_ref(self, board_id: str, card_id: str, attachment_id: str):
        return self.attachments_col(board_id, card_id).document(attachment_id)

    # --- Seguranca do board (somente backend) ---
    def board_security_ref(self, board_id: str):
        return self.db.collection(Collections.BOARD_SECURITY).document(board_id)

    def members_col(self, board_id: str):
        return self.board_security_ref(board_id).collection("members")

    def member_ref(self, board_id: str, uid: str):
        return self.members_col(board_id).document(uid)

    # --- Modelos ---
    def templates_col(self, board_id: str):
        return (
            self.db.collection(Collections.BOARD_TEMPLATES)
            .document(board_id)
            .collection("templates")
        )

    def template_ref(self, board_id: str, template_id: str):
        return self.templates_col(board_id).document(template_id)

    # --- Auditoria ---
    def audit_col(self, board_id: str):
        return (
            self.db.collection(Collections.BOARD_AUDIT).document(board_id).collection("events")
        )

    def audit_ref(self, board_id: str, event_id: str):
        return self.audit_col(board_id).document(event_id)

    # --- Operacoes duraveis ---
    def operation_ref(self, operation_id: str):
        return self.db.collection(Collections.OPERATIONS).document(operation_id)

    # --- Uploads ---
    def upload_ref(self, upload_id: str):
        return self.db.collection(Collections.UPLOAD_SESSIONS).document(upload_id)

    # --- Admin / infra ---
    def admin_session_ref(self, session_hash: str):
        return self.db.collection(Collections.ADMIN_SESSIONS).document(session_hash)

    def rate_limit_ref(self, key_hash: str):
        return self.db.collection(Collections.RATE_LIMITS).document(key_hash)

    def idempotency_ref(self, key_hash: str):
        return self.db.collection(Collections.IDEMPOTENCY).document(key_hash)

    def email_job_ref(self, job_id: str):
        return self.db.collection(Collections.EMAIL_JOBS).document(job_id)
