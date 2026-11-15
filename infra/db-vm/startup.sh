#!/bin/bash
# Startup script for the Postgres VM (Container-Optimized OS, e2-micro Always Free).
# The VM has no public IP: it pulls the image from Artifact Registry via Private Google Access.
set -euo pipefail

meta() {
  curl -fs -H "Metadata-Flavor: Google" \
    "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"
}

PG_PASSWORD="$(meta pg-password)"
PG_IMAGE="$(meta pg-image)"
REGISTRY_HOST="${PG_IMAGE%%/*}"

# /mnt/disks is tmpfs on COS; the stateful partition lives on the boot disk and survives reboots.
DATA_DIR=/mnt/stateful_partition/pgdata
mkdir -p "$DATA_DIR"

# /root is read-only on COS: keep the docker client config in tmpfs (rewritten on every boot).
export HOME=/tmp
docker-credential-gcr configure-docker --registries="$REGISTRY_HOST"
docker pull "$PG_IMAGE"
docker rm -f postgres 2>/dev/null || true

# Tuned for 1 GB RAM: few connections (Cloud Run pools are small) and modest buffers.
docker run -d --name postgres --restart=always \
  -p 5432:5432 \
  -e POSTGRES_USER=biasbuster \
  -e POSTGRES_PASSWORD="$PG_PASSWORD" \
  -e POSTGRES_DB=biasbuster \
  -v "$DATA_DIR":/var/lib/postgresql/data \
  "$PG_IMAGE" \
  -c shared_buffers=128MB \
  -c effective_cache_size=384MB \
  -c work_mem=4MB \
  -c maintenance_work_mem=64MB \
  -c max_connections=40
