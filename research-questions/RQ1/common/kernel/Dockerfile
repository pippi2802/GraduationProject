# Model 1_1 workload kernel image (deterministic matrix-multiply probe).
# Multi-stage: build a static-ish binary, ship on a tiny runtime with taskset.
# The pod entrypoint pins to $RT_CPUSET (KubeDeadline sets it) and runs matmul.

# ---- build stage ----
FROM ubuntu:24.04 AS build
RUN apt-get update -qq && apt-get install -y -qq gcc libc6-dev && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY matmul.c .
# -O2 (not -O3/-ffast-math): keep the FP work deterministic & not vectorised away.
# -static so the runtime image needs no libc matching.
RUN gcc -O2 -std=c11 -Wall -Wextra -static -o /matmul matmul.c

# ---- runtime stage ----
FROM ubuntu:24.04
# util-linux -> taskset/chrt; nothing else needed (matmul is static).
RUN apt-get update -qq && apt-get install -y -qq util-linux && rm -rf /var/lib/apt/lists/*
COPY --from=build /matmul /usr/local/bin/matmul
ENTRYPOINT ["/usr/local/bin/matmul"]
