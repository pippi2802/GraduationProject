# RQ1_final matmul probe. Plain -O2, no BLAS/OpenMP (no extra threads).
CC      ?= cc
CFLAGS  ?= -O2 -std=c11 -Wall -Wextra
LDFLAGS ?= -lpthread

workload: workload.c
	$(CC) $(CFLAGS) -o $@ workload.c $(LDFLAGS)

clean:
	rm -f workload
