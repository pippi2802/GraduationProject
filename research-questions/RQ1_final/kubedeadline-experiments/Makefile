# The RQ1_final probe. Build native for calibration, or as a container image
# for the cluster (see build.sh).
CC      ?= cc
CFLAGS  ?= -O2 -std=c11 -Wall -Wextra
LDFLAGS ?= -lpthread

workload: workload.c
	$(CC) $(CFLAGS) -o $@ workload.c $(LDFLAGS)

clean:
	rm -f workload

.PHONY: clean
