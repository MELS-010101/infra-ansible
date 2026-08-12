#!/usr/bin/env bash
# Бутстрап remote state: MinIO (локальный S3) + бакет для стейта Terraform.
set -euo pipefail

if ! docker ps -a --format '{{.Names}}' | grep -q '^minio$'; then
  docker run -d --name minio --restart unless-stopped \
    -p 9000:9000 -p 9001:9001 \
    -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin \
    minio/minio server /data --console-address ":9001"
  sleep 3
fi

docker exec minio mc alias set local http://localhost:9000 minioadmin minioadmin >/dev/null
docker exec minio mc mb -p local/terraform-state >/dev/null 2>&1 || true
echo "MinIO ready: S3 API :9000, console :9001 (minioadmin/minioadmin)"
