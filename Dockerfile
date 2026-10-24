# syntax=docker/dockerfile:1

# ----------------------------------------------------------------------------
# Etapa 1: compila o frontend React com Node (apenas para o build).
# ----------------------------------------------------------------------------
FROM node:20-bookworm-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci || npm install
COPY frontend/ ./
# O logo em frontend/assets/logo.png e importado pelo build do Vite.
RUN npm run build

# ----------------------------------------------------------------------------
# Etapa 2: imagem final Python que serve a API e os estaticos.
# Inclui LibreOffice headless para previa de DOC/DOCX/XLS/XLSX (secao 8.3).
# ----------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

# Dependencias de sistema para conversao de Office e imagens.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libreoffice-calc \
      libreoffice-writer \
      libreoffice-impress \
      fonts-liberation \
      libmagic1 \
      curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencias Python a partir do pyproject (versoes fixadas).
COPY backend/pyproject.toml ./backend/pyproject.toml
RUN pip install --upgrade pip && pip install ./backend

# Codigo da aplicacao.
COPY backend/app ./backend/app

# Estaticos compilados do frontend.
COPY --from=frontend /app/frontend/dist ./backend/static

# Usuario sem privilegios.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

WORKDIR /app/backend
EXPOSE 8080

# Encerramento gracioso em SIGTERM e escuta em 0.0.0.0:$PORT.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --timeout-graceful-shutdown 25"]
