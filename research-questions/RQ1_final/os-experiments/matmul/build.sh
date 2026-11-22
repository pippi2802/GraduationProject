#!/usr/bin/env bash
# build.sh -- build and push the matmul probe image (once, from the laptop; needs docker login to the registry).
# Every node pulls it on first use (imagePullPolicy IfNotPresent). Tag: pippina2/rq1final-matmul:v1
set -euo pipefail
cd "$(dirname "$0")"
IMG="${IMG:-pippina2/rq1final-matmul:v1}"
docker build -t "$IMG" .
docker push "$IMG"
echo "pushed $IMG"
