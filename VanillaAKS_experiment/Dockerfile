# Minimal image for the periodic CPU-bound workload.
# Build:  docker build -t <registry>/rt-periodic:0.1 .
# Push:   docker push  <registry>/rt-periodic:0.1


# If docker is not available, build the image in the Azure Container Registry (ACR) with:
# if acr does not exit -> use this:
    # az acr create --resource-group <resource-group> --name <registry> --sku Basic
#   az acr build --registry <registry> --image rt-periodic:0.1 .
FROM ubuntu:24.04 AS build
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY rt_periodic.c .
RUN gcc -O2 -Wall -o /usr/local/bin/rt_periodic rt_periodic.c

FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates coreutils \
    && rm -rf /var/lib/apt/lists/*
COPY --from=build /usr/local/bin/rt_periodic /usr/local/bin/rt_periodic
COPY scripts/run_workload.sh /usr/local/bin/run_workload.sh

# Normalize file format inside container
RUN sed -i 's/\r$//' /usr/local/bin/run_workload.sh \
    && chmod +x /usr/local/bin/run_workload.sh

RUN chmod +x /usr/local/bin/run_workload.sh
ENTRYPOINT ["/bin/sh", "/usr/local/bin/run_workload.sh"]
