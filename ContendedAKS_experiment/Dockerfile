# Multi-threaded periodic CPU-bound workload.
# Build/push (example with ACR):
#   az acr build --registry <registry> --image rt-contended:0.1 .
#
# Or with docker:
#   docker build -t <registry>/rt-contended:0.1 .
#   docker push  <registry>/rt-contended:0.1

FROM docker.io/gcc:latest AS build
WORKDIR /src
COPY rt_multi_periodic.c .
RUN gcc -O2 -Wall -pthread -o /usr/local/bin/rt_multi_periodic rt_multi_periodic.c

FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates coreutils \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/bin/rt_multi_periodic /usr/local/bin/rt_multi_periodic
COPY scripts/run_workload.sh /usr/local/bin/run_workload.sh

RUN sed -i 's/\r$//' /usr/local/bin/run_workload.sh \
    && chmod +x /usr/local/bin/run_workload.sh

ENTRYPOINT ["/bin/sh", "/usr/local/bin/run_workload.sh"]
