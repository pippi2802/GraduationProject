# The shared RQ1 probe. Build native for calibration, or as a container image
# for the cluster (see build.sh).
CC      ?= cc
CFLAGS  ?= -O2 -std=c11 -Wall -Wextra
LDFLAGS ?=

matmul: matmul.c
	$(CC) $(CFLAGS) -o $@ matmul.c $(LDFLAGS)

clean:
	rm -f matmul

.PHONY: clean
