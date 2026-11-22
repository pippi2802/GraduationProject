# matmul probe image: only the compiled workload (binary name kept as "workload" so calibrate.py / job manifests are unchanged).
FROM ubuntu:24.04 AS build
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev make \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY workload.c Makefile ./
RUN make

FROM ubuntu:24.04
# taskset (util-linux) re-pins onto RT_CPUSET inside the pod.
RUN apt-get update && apt-get install -y --no-install-recommends util-linux \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /src/workload /usr/local/bin/workload
ENTRYPOINT ["/usr/local/bin/workload"]
