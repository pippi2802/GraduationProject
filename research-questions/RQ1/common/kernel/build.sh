#!/usr/bin/env bash
# Build + push the SHARED RQ1 workload kernel image to Docker Hub.
# This is the single workload used by model1_1 / model2 / model3 / model4
# (model1 is independent and NOT part of this). Requires `docker login`.
#
# The image ref is fixed here (all participating models' config.yaml reference the
# SAME ref via image.full_ref). Override with the IMAGE env var if you cut a new
# tag; then update image.full_ref in each participating model's config.yaml.
#
# NOTE: the image is historically named "model1-kernel" (first pushed by model1_1);
# the name is kept stable so already-validated pulls keep working. It is the shared
# deterministic matmul probe, not specific to any one model.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
IMAGE="${IMAGE:-pippina2/model1-kernel:v0.1.0}"
echo "[build] image = $IMAGE"
docker build -t "$IMAGE" "$HERE"
echo "[build] pushing $IMAGE (needs: docker login)"
docker push "$IMAGE"
echo "[build] done: $IMAGE"
