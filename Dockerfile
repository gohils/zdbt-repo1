# One Cloud Run service hosting all tutorial agents behind the ADK web UI.
# Built by: deploy/deploy_cloud_run.sh  (gcloud run deploy --source .)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    GENERATED_DIR=/tmp/generated

WORKDIR /app

COPY deploy/requirements-runtime.txt pyproject.toml ./
COPY de_context ./de_context
RUN pip install -r requirements-runtime.txt && pip install .

COPY agents ./agents

# Cloud Run provides $PORT. Credentials come from the service's service account.
CMD exec adk web --host 0.0.0.0 --port "${PORT:-8080}" --no-reload \
    --session_service_uri memory:// /app/agents
