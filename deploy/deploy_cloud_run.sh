#!/usr/bin/env bash
# Deploy all tutorial agents to Cloud Run behind Identity-Aware Proxy (IAP).
#
# Usage:
#   ./deploy/deploy_cloud_run.sh <access-member> [region]
#
#   <access-member>  who may open the UI, e.g. group:data-eng@example.com
#                    or user:you@example.com
#   [region]         Cloud Run region (default: us-central1)
#
# Reads project, datasets and model settings from .env.
set -euo pipefail

MEMBER="${1:?Pass the IAP access member, e.g. group:data-eng@example.com}"
REGION="${2:-us-central1}"
SERVICE="adk-de-agents"
SA_NAME="adk-de-agents-runner"

cd "$(dirname "$0")/.."
set -a; source .env; set +a

PROJECT="${GOOGLE_CLOUD_PROJECT:?GOOGLE_CLOUD_PROJECT missing in .env}"
SA="${SA_NAME}@${PROJECT}.iam.gserviceaccount.com"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"

echo "== Enabling APIs"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com iap.googleapis.com aiplatform.googleapis.com \
  bigquery.googleapis.com bigqueryconnection.googleapis.com --project "$PROJECT"

echo "== Service account $SA"
gcloud iam service-accounts describe "$SA" --project "$PROJECT" >/dev/null 2>&1 || \
  gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT" \
    --display-name "ADK data engineering agents (Cloud Run)"

echo "== Project roles: run queries, call Gemini, use the embedding connection"
for ROLE in roles/bigquery.jobUser roles/aiplatform.user roles/bigquery.connectionUser; do
  gcloud projects add-iam-policy-binding "$PROJECT" --member "serviceAccount:$SA" \
    --role "$ROLE" --condition=None --quiet --format=none
done

echo "== Dataset roles: read everything, write only to the sandbox"
for DS in "$BQ_SOURCE_DATASET" "$BQ_VAULT_DATASET" "$BQ_MART_DATASET" "$BQ_CONTEXT_DATASET" "$BQ_SANDBOX_VAULT_DATASET"; do
  bq add-iam-policy-binding --member="serviceAccount:$SA" \
    --role=roles/bigquery.dataViewer "${PROJECT}:${DS}" >/dev/null
done
bq add-iam-policy-binding --member="serviceAccount:$SA" \
  --role=roles/bigquery.dataEditor "${PROJECT}:${BQ_SANDBOX_DATASET}" >/dev/null

echo "== Environment variables for the service"
ENV_FILE="$(mktemp)"
python3 - "$ENV_FILE" <<'PY'
import os, sys
keys = ["GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION", "GOOGLE_GENAI_USE_VERTEXAI",
        "AGENT_MODEL", "EMBEDDING_ENDPOINT", "BQ_LOCATION", "BQ_SOURCE_DATASET",
        "BQ_VAULT_DATASET", "BQ_MART_DATASET", "BQ_CONTEXT_DATASET", "BQ_SANDBOX_DATASET",
        "BQ_SANDBOX_VAULT_DATASET", "BQ_CONNECTION", "MAX_BYTES_BILLED", "GRAPH_MODE", "GRAPH_NAME"]
with open(sys.argv[1], "w") as f:
    for k in keys:
        if os.environ.get(k):
            f.write(f'{k}: "{os.environ[k]}"\n')
PY

echo "== Deploying $SERVICE to $REGION (Cloud Build builds the Dockerfile)"
gcloud run deploy "$SERVICE" \
  --project "$PROJECT" \
  --region "$REGION" \
  --source . \
  --service-account "$SA" \
  --env-vars-file "$ENV_FILE" \
  --memory 1Gi \
  --max-instances 2 \
  --no-allow-unauthenticated \
  --iap \
  --quiet
rm -f "$ENV_FILE"

echo "== IAP: let the IAP service agent invoke the service"
gcloud run services add-iam-policy-binding "$SERVICE" --project "$PROJECT" --region "$REGION" \
  --member "serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com" \
  --role roles/run.invoker --quiet --format=none

echo "== IAP: grant UI access to $MEMBER"
gcloud iap web add-iam-policy-binding --project "$PROJECT" \
  --member "$MEMBER" --role roles/iap.httpsResourceAccessor \
  --region "$REGION" --resource-type cloud-run --service "$SERVICE" --quiet --format=none

URL="$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format='value(status.url)')"
echo
echo "Deployed: $URL"
echo "Open it in a browser signed in as $MEMBER. Pick an agent from the dropdown."
