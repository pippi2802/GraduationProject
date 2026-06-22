#!/usr/bin/env bash
# Build and push the rt-DRA NAS exporter image.
# Run on a machine with docker + push access to the registry (e.g. the control
# plane, like the driver image was built).
set -euo pipefail

REGISTRY="${REGISTRY:-pippina2}"
IMAGE="${IMAGE:-rtdra-nas-exporter}"
TAG="${TAG:-v0.1.0}"
REF="${REGISTRY}/${IMAGE}:${TAG}"

cd "$(dirname "$0")"

echo ">> building ${REF}"
docker build -t "${REF}" .

echo ">> pushing ${REF}"
docker push "${REF}"

echo ">> done: ${REF}"
