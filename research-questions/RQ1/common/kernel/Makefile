# Local build of the matmul probe (used by the calibrator on the host/node).
# The container image is built via ./build.sh (Docker). This Makefile is for a
# native binary used during isolated-core calibration.
CC ?= gcc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra
matmul: matmul.c
	$(CC) $(CFLAGS) -o matmul matmul.c
clean:
	rm -f matmul
.PHONY: clean
