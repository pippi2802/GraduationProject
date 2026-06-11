# syntax=docker/dockerfile:1
FROM debian:bookworm-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends stress-ng \
    && rm -rf /var/lib/apt/lists/*
COPY loadgen.sh /usr/local/bin/loadgen.sh
RUN chmod +x /usr/local/bin/loadgen.sh
ENTRYPOINT ["/usr/local/bin/loadgen.sh"]
