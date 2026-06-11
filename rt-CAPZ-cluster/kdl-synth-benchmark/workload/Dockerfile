# syntax=docker/dockerfile:1

# ---- build stage ----
FROM gcc:13 AS build
WORKDIR /app
COPY Makefile .
COPY src ./src
RUN make

# ---- runtime stage ----
FROM debian:bookworm-slim
COPY --from=build /app/rt-workload /usr/local/bin/rt-workload
# /out is mounted as an emptyDir by the pod templates.
ENTRYPOINT ["/usr/local/bin/rt-workload"]
