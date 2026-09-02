# Single, tiny image that carries ONLY the compiled probe. All four RQ1 models run this same binary, only the reservation / neighbours / node differ.
# matmul contains both types of workloadss
FROM ubuntu:24.04 AS build
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev make \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY matmul.c Makefile ./
RUN make

FROM ubuntu:24.04
# taskset (util-linux) is used by the pod to re-pin onto RT_CPUSET.
RUN apt-get update && apt-get install -y --no-install-recommends util-linux \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/matmul /usr/local/bin/matmul
ENTRYPOINT ["/usr/local/bin/matmul"]
