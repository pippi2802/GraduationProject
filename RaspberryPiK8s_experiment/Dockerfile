# Multi-threaded periodic CPU-bound workload, built for ARM64 (Raspberry Pi).
#
# The Pi is an arm64 board, so build the image for linux/arm64.
# If you build on the Pi itself, a plain `docker build` is enough.
# If you build on an x86 dev machine, use buildx (see scripts/build_image.sh).

FROM --platform=$BUILDPLATFORM docker.io/gcc:latest AS build
WORKDIR /src
COPY rt_multi_periodic.c .
# Cross-compile to the target arch if needed. BuildKit sets TARGETARCH.
ARG TARGETARCH
RUN case "$TARGETARCH" in \
        arm64) apt-get update && apt-get install -y --no-install-recommends gcc-aarch64-linux-gnu && \
               aarch64-linux-gnu-gcc -O2 -Wall -pthread -o /out/rt_multi_periodic rt_multi_periodic.c ;; \
        amd64|"") gcc -O2 -Wall -pthread -o /out/rt_multi_periodic rt_multi_periodic.c ;; \
        *)     echo "unsupported TARGETARCH=$TARGETARCH" && exit 1 ;; \
    esac

FROM --platform=$TARGETPLATFORM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates coreutils \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /out/rt_multi_periodic /usr/local/bin/rt_multi_periodic
COPY scripts/run_workload.sh /usr/local/bin/run_workload.sh
RUN sed -i 's/\r$//' /usr/local/bin/run_workload.sh \
    && chmod +x /usr/local/bin/run_workload.sh

ENTRYPOINT ["/bin/sh", "/usr/local/bin/run_workload.sh"]
