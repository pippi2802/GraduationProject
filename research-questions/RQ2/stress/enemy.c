/* enemy.c - pinned cache/memory interference generator for RQ2 profiling.
 *
 * Allocates a buffer and loops over it with a configurable stride, either
 * reading, writing, or both, so it can model a cache enemy (buffer sized to
 * the LLC) or a memory enemy (buffer sized to ~10x the LLC) by choice of
 * --size-kb. Pinned to one CPU with sched_setaffinity so its interference is
 * reproducible and isolated to that core. Exits cleanly on SIGTERM/SIGINT so
 * campaign.py can stop it deterministically.
 */
#define _GNU_SOURCE
#include <sched.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef enum { MODE_READ, MODE_WRITE, MODE_RW } access_mode_t;

static volatile sig_atomic_t g_stop = 0;

static void on_signal(int signo) {
    (void)signo;
    g_stop = 1;
}

static void usage(const char *prog) {
    fprintf(stderr,
            "usage: %s --size-kb N [--stride-bytes N] [--mode read|write|rw] [--cpu N]\n",
            prog);
}

int main(int argc, char **argv) {
    long size_kb = -1;
    long stride_bytes = 64;
    access_mode_t mode = MODE_RW;
    int cpu = -1;

    static struct { const char *name; } noop; /* silence unused warnings on some toolchains */
    (void)noop;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--size-kb") == 0 && i + 1 < argc) {
            size_kb = atol(argv[++i]);
        } else if (strcmp(argv[i], "--stride-bytes") == 0 && i + 1 < argc) {
            stride_bytes = atol(argv[++i]);
        } else if (strcmp(argv[i], "--mode") == 0 && i + 1 < argc) {
            const char *m = argv[++i];
            if (strcmp(m, "read") == 0) mode = MODE_READ;
            else if (strcmp(m, "write") == 0) mode = MODE_WRITE;
            else if (strcmp(m, "rw") == 0) mode = MODE_RW;
            else { usage(argv[0]); return 2; }
        } else if (strcmp(argv[i], "--cpu") == 0 && i + 1 < argc) {
            cpu = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--help") == 0) {
            usage(argv[0]);
            return 0;
        } else {
            usage(argv[0]);
            return 2;
        }
    }

    if (size_kb <= 0 || stride_bytes <= 0) {
        usage(argv[0]);
        return 2;
    }

    if (cpu >= 0) {
        cpu_set_t set;
        CPU_ZERO(&set);
        CPU_SET(cpu, &set);
        if (sched_setaffinity(0, sizeof(set), &set) != 0) {
            perror("sched_setaffinity");
            /* not fatal: keep running unpinned so it still fails loudly on
             * misuse but doesn't silently swallow the process */
        }
    }

    signal(SIGTERM, on_signal);
    signal(SIGINT, on_signal);

    size_t size_bytes = (size_t)size_kb * 1024;
    volatile unsigned char *buf = malloc(size_bytes);
    if (buf == NULL) {
        perror("malloc");
        return 1;
    }

    /* touch every page once so it's actually backed by physical memory
     * before the timed interference loop starts */
    for (size_t i = 0; i < size_bytes; i++) {
        buf[i] = (unsigned char)(i & 0xFF);
    }

    unsigned char sink = 0;
    while (!g_stop) {
        for (size_t off = 0; off < size_bytes; off += (size_t)stride_bytes) {
            switch (mode) {
                case MODE_READ:
                    sink ^= buf[off];
                    break;
                case MODE_WRITE:
                    buf[off] = sink;
                    break;
                case MODE_RW:
                    sink ^= buf[off];
                    buf[off] = sink;
                    break;
            }
            if (g_stop) break;
        }
    }

    /* prevent the compiler from proving sink/buf are dead */
    fprintf(stderr, "enemy exiting, sink=%u\n", sink);
    free((void *)buf);
    return 0;
}
