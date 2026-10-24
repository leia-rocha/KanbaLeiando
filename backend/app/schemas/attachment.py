"""Contratos de anexos e uploads (secao 8, 14.1)."""

from __future__ import annotations

from pydantic import Field

from app.schemas.common import StrictModel


class UploadCreateRequest(StrictModel):
    fieldId: str | None = None
    draftId: str | None = None
    cardId: str | None = None
    originalName: str = Field(min_length=1, max_length=512)
    expectedSize: int = Field(ge=0)
    contentType: str = Field(default="application/octet-stream", max_length=255)
    idempotencyKey: str | None = Field(default=None, max_length=200)


class UploadCreateResponse(StrictModel):
    uploadId: str
    uploadUrl: str
    method: str = "PUT"
    headers: dict[str, str] = Field(default_factory=dict)
    objectKey: str
    expiresAt: str


class UploadCompleteResponse(StrictModel):
    uploadId: str
    attachmentId: str
    status: str
    originalName: str
    sizeBytes: int
    detectedMimeType: str


class AttachmentOut(StrictModel):
    attachmentId: str
    fieldId: str
    originalName: str
    sizeBytes: int
    detectedMimeType: str
    previewState: str


class SignedUrlResponse(StrictModel):
    url: str
    expiresAt: str


class PreviewResponse(StrictModel):
    status: str  # ready | processing | unavailable
    kind: str  # image | pdf | pages | download
    url: str | None = None
    pages: list[str] | None = None
    reason: str | None = None
