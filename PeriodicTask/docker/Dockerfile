FROM docker.io/gcc:latest as build
COPY . /PeriodicTask
WORKDIR /PeriodicTask
RUN make clean && make

FROM busybox:glibc AS periodic_task 
COPY --from=build /PeriodicTask /PeriodicTask
COPY --from=build /lib/x86_64-linux-gnu/libgcc_s.so.1 /lib/x86_64-linux-gnu/libgcc_s.so.1
WORKDIR /PeriodicTask
