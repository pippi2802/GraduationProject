# OPTIONAL: containerized sampler image.
#
# The chosen strategy is "install at runtime, no custom image" (see the
# DaemonSet, which apt-installs python3 and mounts sampler.py from a ConfigMap).
# This Dockerfile is provided ONLY for the case where you later prefer a
# prebuilt image (faster pod start, air-gapped nodes). Build + push, then set
# the DaemonSet image to your reference.
FROM ubuntu:24.04
RUN apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 \
    && rm -rf /var/lib/apt/lists/*
COPY sampler.py /usr/local/bin/sampler.py
ENTRYPOINT ["python3", "/usr/local/bin/sampler.py"]
