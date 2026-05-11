#!/usr/bin/env bash
# Build the rt-contended image for the Raspberry Pi (linux/arm64).
#
# Two modes are supported:
#
# 1) Build *on* the Pi (simplest). The Pi is arm64 already, so a plain
#    `docker build` produces an arm64 image. If you run a single-node
#    k3s on the Pi, you can `docker save` + `k3s ctr images import` and
#    skip a registry entirely (see README.md).
#
# 2) Build on an x86 dev machine and cross-build for arm64 with
#    docker buildx. Requires:
#       docker buildx create --use
#       docker run --privileged --rm tonistiigi/binfmt --install all
#
# Usage:
#    ./build_image.sh <image_ref>           # builds + (optionally) pushes
#    PUSH=1 ./build_image.sh <image_ref>    # also push to registry
#    LOAD=1 ./build_image.sh <image_ref>    # load into local docker (single arch)

set -euo pipefail

IMAGE="${1:?image ref required, e.g. myregistry/rt-contended-pi:0.1 or rt-contended-pi:0.1}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

ARCH="$(uname -m)"
case "$ARCH" in
    aarch64|arm64)
        echo "[build] native arm64 build on this host"
        docker build -t "$IMAGE" .
        ;;
    x86_64|amd64)
        echo "[build] cross-building linux/arm64 via buildx"
        if ! docker buildx inspect >/dev/null 2>&1; then
            docker buildx create --use
        fi
        if [[ "${PUSH:-0}" = "1" ]]; then
            docker buildx build --platform linux/arm64 -t "$IMAGE" --push .
        elif [[ "${LOAD:-0}" = "1" ]]; then
            docker buildx build --platform linux/arm64 -t "$IMAGE" --load .
        else
            docker buildx build --platform linux/arm64 -t "$IMAGE" .
            echo "[build] note: image built but not loaded/pushed. Re-run with PUSH=1 or LOAD=1."
        fi
        ;;
    *)
        echo "unsupported host arch: $ARCH" >&2
        exit 1
        ;;
esac
echo "[build] done: $IMAGE"
