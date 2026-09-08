# Single, tiny image that carries only the compiled workload.c probe.
FROM ubuntu:24.04 AS build
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev make \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY workload.c Makefile ./
RUN make

FROM ubuntu:24.04
# taskset (util-linux) is used by the pod to re-pin onto RT_CPUSET.
RUN apt-get update && apt-get install -y --no-install-recommends util-linux \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/workload /usr/local/bin/workload
ENTRYPOINT ["/usr/local/bin/workload"]
