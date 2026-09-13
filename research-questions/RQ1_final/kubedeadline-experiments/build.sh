#!/usr/bin/env bash
# Build + push the probe image. Override with  IMAGE=myrepo/myname:tag ./build.sh
set -euo pipefail
IMAGE="${IMAGE:-pippina2/rq1final-probe:v1}"
cd "$(dirname "$0")"
echo "[build] $IMAGE"
docker build -t "$IMAGE" .
docker push "$IMAGE"
echo "[build] pushed $IMAGE"
echo "Set image: $IMAGE in models/model1/config.yaml and job.yaml if you change it."
