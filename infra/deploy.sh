#!/usr/bin/env bash
# Implantacao do KanbaLeiando no Cloud Run com escala a zero (RF39, secao 16).
# Parametriza projeto, regiao, nomes de recursos e segredos. Nenhum valor privado
# e inventado: segredos vem do Secret Manager.
set -euo pipefail

: "${PROJECT_ID:?defina PROJECT_ID}"
: "${REGION:?defina REGION (ex.: southamerica-east1)}"
SERVICE="${SERVICE:-kanbaleiando}"
REPO="${REPO:-kanbaleiando}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE}:$(date +%Y%m%d-%H%M%S)"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-kanbaleiando-run@${PROJECT_ID}.iam.gserviceaccount.com}"

echo ">> Habilitando APIs necessarias"
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  cloudbuild.googleapis.com \
  cloudtasks.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com \
  --project "${PROJECT_ID}"

echo ">> Criando repositorio Artifact Registry (ignora se ja existir)"
gcloud artifacts repositories create "${REPO}" \
  --repository-format=docker --location="${REGION}" \
  --project "${PROJECT_ID}" 2>/dev/null || true

echo ">> Build e push da imagem via Cloud Build"
gcloud builds submit --tag "${IMAGE}" --project "${PROJECT_ID}" .

echo ">> Deploy no Cloud Run (min-instances=0, max-instances=2)"
gcloud run deploy "${SERVICE}" \
  --image "${IMAGE}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --service-account "${SERVICE_ACCOUNT}" \
  --min-instances 0 \
  --max-instances 2 \
  --cpu 1 \
  --memory 1Gi \
  --concurrency 10 \
  --timeout 120 \
  --set-env-vars "APP_ENV=production,APP_TIMEZONE=America/Sao_Paulo,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},FIREBASE_PROJECT_ID=${PROJECT_ID}" \
  --set-secrets "ADMIN_USER=ADMIN_USER:latest,ADMIN_PASSWORD=ADMIN_PASSWORD:latest,ADMIN_SESSION_SECRET=ADMIN_SESSION_SECRET:latest,PUBLIC_LINK_SECRET=PUBLIC_LINK_SECRET:latest,SMTP_HOST=SMTP_HOST:latest,SMTP_PORT=SMTP_PORT:latest,SMTP_USER=SMTP_USER:latest,SMTP_PASSWORD=SMTP_PASSWORD:latest,SMTP_FROM=SMTP_FROM:latest,FIREBASE_WEB_API_KEY=FIREBASE_WEB_API_KEY:latest,FIREBASE_AUTH_DOMAIN=FIREBASE_AUTH_DOMAIN:latest,FIREBASE_WEB_APP_ID=FIREBASE_WEB_APP_ID:latest,GCS_BUCKET_NAME=GCS_BUCKET_NAME:latest"

echo ">> URL do servico:"
gcloud run services describe "${SERVICE}" --region "${REGION}" \
  --project "${PROJECT_ID}" --format "value(status.url)"

echo ">> Lembre de atualizar APP_BASE_URL e TASKS_AUDIENCE com a URL acima."
