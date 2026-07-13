// =============================================================================
// Model 1_1 workload kernel — DETERMINISTIC constant-work probe.
//
// A fixed dense double-precision matrix multiply  C = A x B  (M x M), with A,B
// generated ONCE from a fixed seed and REUSED every job. Data-independent control
// flow + tiny in-cache working set => execution time C has very low intrinsic
// variance. The per-job compute demand is tuned by the repetition count K (NOT by
// the data). NO allocations / syscalls / I/O inside the hot matmul loop.
//
// Two clocks per job (the delay decomposition):
//   C = CLOCK_THREAD_CPUTIME_ID delta over the compute  (CPU time actually used;
//       does NOT advance during steal/preemption -> execution-layer reference)
//   R = wall-clock finish - release (CLOCK_MONOTONIC)     (the guarantee)
// delay = R - C, split into:
//   dispatch_latency = start  - release           (front-loaded: scheduler/CBS)
//   mid_job_preempt  = (finish - start) - C        (intrusion during execution)
//
// NOTE ON CLOCKS: the periodic release is driven by clock_nanosleep, which cannot
// use CLOCK_MONOTONIC_RAW, so the wall clock here is CLOCK_MONOTONIC (its sleepable
// sibling). Over a bounded cell the MONOTONIC vs _RAW difference is NTP slew only
// and does not affect any intra-job delta. C is CLOCK_THREAD_CPUTIME_ID as spec'd.
//
// Output: CSV to --logfile (or stdout). One '#'-commented header then one row/job
// (after --warmup). Columns match config.yaml per_job_columns.
// =============================================================================
#define _GNU_SOURCE
#include <errno.h>
#include <getopt.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <time.h>
#include <unistd.h>

static const char *CSV_HEADER =
    "job_index,release_us,start_us,finish_us,C_cputime_us,R_wall_us,delay_us,"
    "dispatch_latency_us,mid_job_preempt_us,slack_us,deadline_miss,tardiness_us,"
    "nonvol_ctxt,K_reps,matrix_M";

static inline int64_t ts_ns(const struct timespec *t) {
    return (int64_t)t->tv_sec * 1000000000LL + (int64_t)t->tv_nsec;
}
static inline void ns_to_ts(int64_t ns, struct timespec *t) {
    t->tv_sec = ns / 1000000000LL;
    t->tv_nsec = ns % 1000000000LL;
}

// Deterministic pseudo-random fill (xorshift64) from a fixed seed -> reproducible
// A,B independent of libc rand(). Done ONCE, outside the hot loop.
static void fill_matrix(double *m, int n, uint64_t *state) {
    for (int i = 0; i < n; i++) {
        uint64_t x = *state;
        x ^= x << 13; x ^= x >> 7; x ^= x << 17;
        *state = x;
        // map to [-1,1)
        m[i] = ((double)(x >> 11) / (double)(1ULL << 53)) * 2.0 - 1.0;
    }
}

// Naive dense matmul: C = A x B (row-major, M x M). Data-independent control flow.
static void matmul(const double *restrict A, const double *restrict B,
                   double *restrict C, int M) {
    for (int i = 0; i < M; i++) {
        for (int j = 0; j < M; j++) {
            double s = 0.0;
            for (int k = 0; k < M; k++) s += A[i * M + k] * B[k * M + j];
            C[i * M + j] = s;
        }
    }
}

static long involuntary_ctxt(void) {
    struct rusage ru;
    if (getrusage(RUSAGE_THREAD, &ru) == 0) return ru.ru_nivcsw;
    return -1;
}

static void usage(const char *p) {
    fprintf(stderr,
        "usage: %s --M <int> --K <int> --period-us <int> --n-jobs <int>\n"
        "          [--warmup <int>] [--priority <int>] [--cpu <int|env>]\n"
        "          [--seed <uint>] [--logfile <path>] [--no-lock-pages]\n"
        "  --cpu env  reads RT_CPUSET (first cpu) for affinity; else no pinning.\n",
        p);
}

int main(int argc, char **argv) {
    int M = 48, K = 1, priority = 90, warmup = 0;
    long n_jobs = 5000;
    int64_t period_ns = 10 * 1000000LL;  // default 10 ms
    uint64_t seed = 20260713ULL;
    int cpu = -1;                 // -1 => no explicit pinning (driver/taskset did it)
    int lock_pages = 1;
    const char *logfile = NULL;

    static struct option opts[] = {
        {"M", required_argument, 0, 'M'},
        {"K", required_argument, 0, 'K'},
        {"period-us", required_argument, 0, 'P'},
        {"n-jobs", required_argument, 0, 'n'},
        {"warmup", required_argument, 0, 'w'},
        {"priority", required_argument, 0, 'r'},
        {"cpu", required_argument, 0, 'c'},
        {"seed", required_argument, 0, 's'},
        {"logfile", required_argument, 0, 'o'},
        {"no-lock-pages", no_argument, 0, 'L'},
        {"help", no_argument, 0, 'h'},
        {0, 0, 0, 0}};
    int ci;
    while ((ci = getopt_long(argc, argv, "M:K:P:n:w:r:c:s:o:Lh", opts, NULL)) != -1) {
        switch (ci) {
        case 'M': M = atoi(optarg); break;
        case 'K': K = atoi(optarg); break;
        case 'P': period_ns = (int64_t)atoll(optarg) * 1000LL; break;
        case 'n': n_jobs = atol(optarg); break;
        case 'w': warmup = atoi(optarg); break;
        case 'r': priority = atoi(optarg); break;
        case 's': seed = strtoull(optarg, NULL, 10); break;
        case 'o': logfile = optarg; break;
        case 'L': lock_pages = 0; break;
        case 'c':
            if (strcmp(optarg, "env") == 0) {
                const char *e = getenv("RT_CPUSET");
                if (e && *e) cpu = atoi(e);  // atoi stops at ',' or '-' -> first cpu
            } else {
                cpu = atoi(optarg);
            }
            break;
        case 'h': default: usage(argv[0]); return 2;
        }
    }
    if (M < 1 || K < 1 || n_jobs < 1) { usage(argv[0]); return 2; }

    // --- affinity (best effort; KubeDeadline usually pins already) --------------
    if (cpu >= 0) {
        cpu_set_t set; CPU_ZERO(&set); CPU_SET(cpu, &set);
        if (sched_setaffinity(0, sizeof(set), &set) != 0)
            fprintf(stderr, "[matmul] WARN sched_setaffinity(cpu=%d): %s\n", cpu, strerror(errno));
    }
    // --- SCHED_FIFO (best effort; needs CAP_SYS_NICE) ---------------------------
    if (priority > 0) {
        struct sched_param sp; memset(&sp, 0, sizeof(sp));
        sp.sched_priority = priority;
        if (sched_setscheduler(0, SCHED_FIFO, &sp) != 0)
            fprintf(stderr, "[matmul] WARN sched_setscheduler(FIFO,%d): %s "
                            "(C still valid; run continues)\n", priority, strerror(errno));
    }
    // --- lock pages -------------------------------------------------------------
    if (lock_pages && mlockall(MCL_CURRENT | MCL_FUTURE) != 0)
        fprintf(stderr, "[matmul] WARN mlockall: %s\n", strerror(errno));

    // --- allocate + init A,B,C ONCE (outside the hot loop) ----------------------
    size_t nelem = (size_t)M * M;
    double *A = aligned_alloc(64, nelem * sizeof(double));
    double *B = aligned_alloc(64, nelem * sizeof(double));
    double *Cm = aligned_alloc(64, nelem * sizeof(double));
    if (!A || !B || !Cm) { fprintf(stderr, "[matmul] alloc failed\n"); return 1; }
    uint64_t st = seed ? seed : 0x9e3779b97f4a7c15ULL;
    fill_matrix(A, (int)nelem, &st);
    fill_matrix(B, (int)nelem, &st);
    matmul(A, B, Cm, M);            // touch pages / warm caches before timing
    volatile double sink = 0.0;

    FILE *out = stdout;
    if (logfile) { out = fopen(logfile, "w"); if (!out) { perror("fopen"); return 1; } }
    fprintf(out, "# matmul M=%d K=%d period_us=%lld priority=%d cpu=%d seed=%llu "
                 "n_jobs=%ld warmup=%d\n",
            M, K, (long long)(period_ns / 1000), priority, cpu,
            (unsigned long long)seed, n_jobs, warmup);
    fprintf(out, "%s\n", CSV_HEADER);

    // --- periodic loop ----------------------------------------------------------
    struct timespec now, t_start, t_finish, cc0, cc1, next;
    clock_gettime(CLOCK_MONOTONIC, &now);
    int64_t next_ns = ts_ns(&now) + period_ns;   // first release one period out
    long total = n_jobs + warmup;

    for (long i = 0; i < total; i++) {
        ns_to_ts(next_ns, &next);
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &next, NULL);
        int64_t release_ns = next_ns;                 // scheduled activation instant
        long nv0 = involuntary_ctxt();
        clock_gettime(CLOCK_MONOTONIC, &t_start);
        clock_gettime(CLOCK_THREAD_CPUTIME_ID, &cc0);

        for (int k = 0; k < K; k++) { matmul(A, B, Cm, M); }
        sink += Cm[0];

        clock_gettime(CLOCK_THREAD_CPUTIME_ID, &cc1);
        clock_gettime(CLOCK_MONOTONIC, &t_finish);
        long nv1 = involuntary_ctxt();

        int64_t start_ns = ts_ns(&t_start);
        int64_t finish_ns = ts_ns(&t_finish);
        int64_t C_ns = ts_ns(&cc1) - ts_ns(&cc0);
        int64_t R_ns = finish_ns - release_ns;
        int64_t delay_ns = R_ns - C_ns;
        int64_t dispatch_ns = start_ns - release_ns;
        int64_t midjob_ns = (finish_ns - start_ns) - C_ns;
        int64_t slack_ns = period_ns - R_ns;
        int miss = (R_ns > period_ns) ? 1 : 0;
        int64_t tard_ns = miss ? (R_ns - period_ns) : 0;
        long nv = (nv0 >= 0 && nv1 >= 0) ? (nv1 - nv0) : -1;

        if (i >= warmup) {
            fprintf(out,
                "%ld,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%d,%.3f,%ld,%d,%d\n",
                i - warmup,
                release_ns / 1000.0, start_ns / 1000.0, finish_ns / 1000.0,
                C_ns / 1000.0, R_ns / 1000.0, delay_ns / 1000.0,
                dispatch_ns / 1000.0, midjob_ns / 1000.0, slack_ns / 1000.0,
                miss, tard_ns / 1000.0, nv, K, M);
        }
        next_ns += period_ns;   // strict period; if we overran, next release is in
                                // the past -> next sleep returns immediately (this is
                                // the overload/divergence we deliberately measure).
    }
    if (out != stdout) fclose(out);
    (void)sink;
    free(A); free(B); free(Cm);
    return 0;
}
