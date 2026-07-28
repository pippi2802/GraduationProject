#!/usr/bin/env bash
# Build + push the shared probe image. All models reference this one ref.
# Override the ref with  IMAGE=myrepo/myname:tag ./build.sh
set -euo pipefail
IMAGE="${IMAGE:-pippina2/rq1-probe:v1}"
cd "$(dirname "$0")"
echo "[build] $IMAGE"
docker build -t "$IMAGE" .
docker push "$IMAGE"
echo "[build] pushed $IMAGE"
echo "Set image.ref: $IMAGE in models/*/config.yaml (or the shared default)."
