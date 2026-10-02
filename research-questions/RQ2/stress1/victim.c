/* victim.c - fixed-work probe for the enemy-effectiveness test.
 *
 * Does a FIXED amount of work (--passes full passes over a buffer of
 * --size-kb, stride --stride-bytes, read+write), pinned to --cpu, and
 * prints only the elapsed wall time in milliseconds to stdout - nothing
 * else - so a bash caller can capture it with a single command
 * substitution. Run alone vs. with enemies running to measure slowdown.
 */
#define _GNU_SOURCE
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static void usage(const char *prog) {
    fprintf(stderr, "usage: %s --size-kb N [--stride-bytes N] [--passes N] [--cpu N]\n", prog);
}

static long long now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long long)ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

int main(int argc, char **argv) {
    long size_kb = -1;
    long stride_bytes = 64;
    long passes = 50;
    int cpu = -1;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--size-kb") == 0 && i + 1 < argc) {
            size_kb = atol(argv[++i]);
        } else if (strcmp(argv[i], "--stride-bytes") == 0 && i + 1 < argc) {
            stride_bytes = atol(argv[++i]);
        } else if (strcmp(argv[i], "--passes") == 0 && i + 1 < argc) {
            passes = atol(argv[++i]);
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

    if (size_kb <= 0 || stride_bytes <= 0 || passes <= 0) {
        usage(argv[0]);
        return 2;
    }

    if (cpu >= 0) {
        cpu_set_t set;
        CPU_ZERO(&set);
        CPU_SET(cpu, &set);
        if (sched_setaffinity(0, sizeof(set), &set) != 0) {
            perror("sched_setaffinity");
        }
    }

    size_t size_bytes = (size_t)size_kb * 1024;
    volatile unsigned char *buf = malloc(size_bytes);
    if (buf == NULL) {
        perror("malloc");
        return 1;
    }
    for (size_t i = 0; i < size_bytes; i++) {
        buf[i] = (unsigned char)(i & 0xFF);
    }

    unsigned char sink = 0;
    long long t0 = now_ns();
    for (long pass = 0; pass < passes; pass++) {
        for (size_t off = 0; off < size_bytes; off += (size_t)stride_bytes) {
            sink ^= buf[off];
            buf[off] = sink;
        }
    }
    long long t1 = now_ns();

    free((void *)buf);
    if (sink == 0xFF) {
        /* never true in practice; keeps sink from being optimized away
         * without adding it to the timed printf */
        fprintf(stderr, "unreachable\n");
    }
    printf("%.3f\n", (t1 - t0) / 1e6);
    return 0;
}
