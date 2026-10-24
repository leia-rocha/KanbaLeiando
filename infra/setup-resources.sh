#!/usr/bin/env bash
# Provisiona recursos de infraestrutura do KanbaLeiando (secao 16.4).
# Conta de servico com minimo privilegio, bucket privado, fila de tarefas e
# segredos. Execute uma vez por projeto.
set -euo pipefail

: "${PROJECT_ID:?defina PROJECT_ID}"
: "${REGION:?defina REGION}"
BUCKET="${BUCKET:-kanbaleiando-anexos}"
QUEUE="${QUEUE:-kanbaleiando-tasks}"
RUN_SA="kanbaleiando-run@${PROJECT_ID}.iam.gserviceaccount.com"
TASKS_SA="kanbaleiando-tasks@${PROJECT_ID}.iam.gserviceaccount.com"

echo ">> Conta de servico da aplicacao (sem Owner/Editor)"
gcloud iam service-accounts create kanbaleiando-run \
  --display-name "KanbaLeiando Cloud Run" --project "${PROJECT_ID}" 2>/dev/null || true
gcloud iam service-accounts create kanbaleiando-tasks \
  --display-name "KanbaLeiando Tasks OIDC" --project "${PROJECT_ID}" 2>/dev/null || true

echo ">> Papeis minimos para a conta da aplicacao"
for ROLE in \
  roles/datastore.user \
  roles/firebaseauth.admin \
  roles/cloudtasks.enqueuer \
  roles/iam.serviceAccountTokenCreator \
  roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member "serviceAccount:${RUN_SA}" --role "${ROLE}" --condition=None >/dev/null
done

echo ">> Bucket privado com uniform bucket-level access e bloqueio publico"
gcloud storage buckets create "gs://${BUCKET}" \
  --project "${PROJECT_ID}" --location "${REGION}" \
  --uniform-bucket-level-access --public-access-prevention 2>/dev/null || true
# Sem versionamento/soft delete de objetos da aplicacao (politica de exclusao
# definitiva do produto, secao 12.1 / DT14).
gcloud storage buckets update "gs://${BUCKET}" --no-versioning || true
# Acesso do servico ao bucket.
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member "serviceAccount:${RUN_SA}" --role roles/storage.objectAdmin

echo ">> Fila do Cloud Tasks"
gcloud tasks queues create "${QUEUE}" \
  --location "${REGION}" --project "${PROJECT_ID}" 2>/dev/null || true

echo ">> Segredos (preencha os valores quando solicitado ou via arquivos)"
cat <<'NOTE'
Crie os segredos no Secret Manager (exemplo):

  printf '%s' "sua-senha-forte" | gcloud secrets create ADMIN_PASSWORD --data-file=- --project PROJECT_ID
  python -c "import secrets;print(secrets.token_urlsafe(48))" | gcloud secrets create ADMIN_SESSION_SECRET --data-file=- --project PROJECT_ID
  python -c "import secrets;print(secrets.token_urlsafe(48))" | gcloud secrets create PUBLIC_LINK_SECRET --data-file=- --project PROJECT_ID

Repita para: ADMIN_USER, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
SMTP_FROM, FIREBASE_WEB_API_KEY, FIREBASE_AUTH_DOMAIN, FIREBASE_WEB_APP_ID,
GCS_BUCKET_NAME.
NOTE

echo ">> Configure o alerta de orcamento manualmente no console (valor ajustavel)."
echo ">> Pronto. Agora rode infra/deploy.sh."
