#!/usr/bin/env bash
# Build, migrate and deploy api + worker to Cloud Run, then the frontend to Firebase Hosting.
# Requires the one-time setup in infra/README.md. Usage: PROJECT_ID=my-proj ./infra/scripts/deploy.sh
set -euo pipefail

: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-biasbuster}"
TAG="${TAG:-$(git rev-parse --short HEAD)}"
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPO/backend:$TAG"
NETWORK="${NETWORK:-default}"
SUBNET="${SUBNET:-default}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "▶ building $IMAGE"
gcloud builds submit backend --project "$PROJECT_ID" --region "$REGION" --tag "$IMAGE"

COMMON_SECRETS="DATABASE_URL=database-url:latest,OPENROUTER_API_KEY=openrouter-api-key:latest,TAVILY_API_KEY=tavily-api-key:latest"
VPC_FLAGS=(--network "$NETWORK" --subnet "$SUBNET" --vpc-egress private-ranges-only)

echo "▶ running migrations"
gcloud run jobs deploy biasbuster-migrate --project "$PROJECT_ID" --region "$REGION" \
  --image "$IMAGE" --service-account "biasbuster-api@$PROJECT_ID.iam.gserviceaccount.com" \
  "${VPC_FLAGS[@]}" --set-secrets "DATABASE_URL=database-url:latest" \
  --command alembic --args upgrade,head --max-retries 0
gcloud run jobs execute biasbuster-migrate --project "$PROJECT_ID" --region "$REGION" --wait

echo "▶ deploying worker"
gcloud run deploy biasbuster-worker --project "$PROJECT_ID" --region "$REGION" \
  --image "$IMAGE" --service-account "biasbuster-worker@$PROJECT_ID.iam.gserviceaccount.com" \
  "${VPC_FLAGS[@]}" --ingress internal --no-allow-unauthenticated \
  --timeout 1800 --concurrency 4 --cpu 1 --memory 1Gi --min-instances 0 --max-instances 3 \
  --set-env-vars "APP_ROLE=worker,ENVIRONMENT=prod" \
  --set-secrets "$COMMON_SECRETS"
WORKER_URL="$(gcloud run services describe biasbuster-worker --project "$PROJECT_ID" \
  --region "$REGION" --format 'value(status.url)')"

echo "▶ deploying api"
gcloud run deploy biasbuster-api --project "$PROJECT_ID" --region "$REGION" \
  --image "$IMAGE" --service-account "biasbuster-api@$PROJECT_ID.iam.gserviceaccount.com" \
  "${VPC_FLAGS[@]}" --allow-unauthenticated \
  --timeout 60 --concurrency 40 --cpu 1 --memory 512Mi --min-instances 0 --max-instances 4 \
  --set-env-vars "^|^APP_ROLE=api|ENVIRONMENT=prod|TASKS_BACKEND=cloudtasks|GCP_PROJECT=$PROJECT_ID|GCP_LOCATION=$REGION|WORKER_URL=$WORKER_URL|TASKS_SERVICE_ACCOUNT=biasbuster-tasks@$PROJECT_ID.iam.gserviceaccount.com|CORS_ORIGINS=[\"https://$PROJECT_ID.web.app\"]" \
  --set-secrets "DATABASE_URL=database-url:latest"

echo "▶ deploying frontend"
(cd frontend && npm ci && npm run build)
firebase deploy --only hosting --project "$PROJECT_ID"

echo "✓ done: https://$PROJECT_ID.web.app"
