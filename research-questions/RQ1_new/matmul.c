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
// WARM-UP + CATCH-UP (harness robustness):
//   * The --warmup jobs run FIRST, un-timed and OFF the periodic schedule, to fault
//     in pages / warm caches / settle DVFS before the metronome is anchored. This
//     way a slow first activation cannot poison every subsequent release.
//   * The measured loop uses a missed-release CATCH-UP rule: if a job overruns its
//     period, the naive next release is already in the past; instead of letting an
//     unbounded backlog accumulate (which makes R diverge to seconds and poisons
//     every later job) we SKIP forward to the next FUTURE release boundary and
//     record how many releases were skipped (column skipped_before). Each skipped
//     release is a job that could not be started on time -> counted as a miss by the
//     analysis, while the completed jobs keep a bounded, meaningful R.
//
// WORKLOAD KINDS:
//   matmul  data-independent control flow, tiny in-cache working set, execution-
//           port-bound (dense FP loop). Per-job work is exactly K reps of a fixed
//           MxM multiply -- deterministic op count, near-zero intrinsic variance.
//   primes  trial-division primality test over a deterministic (seeded) stream of
//           candidate integers -- genuinely DATA-DEPENDENT control flow (early
//           exit on first factor found, so per-candidate cost varies with the
//           candidate's own value) while staying fully reproducible: the
//           candidate stream is generated from the same fixed --seed as matmul's
//           matrices, so a given K always tests the exact same sequence of
//           candidates, in the same order, every run. Per-job work is K batches
//           of PRIMES_CANDS_PER_K candidates; integer-divide/branch-predictor
//           bound rather than FP-execution-port bound. Replaces the earlier
//           ptrchase (memory/LLC pointer-chase) kind, removed 2026-08-14.
//
// Output: CSV to --logfile (or stdout). One '#'-commented header then one row/job
// (after --warmup). Columns match config.yaml per_job_columns.
//
// BATCH/MULTITHREAD MODE (--threads N, N>1, model4):
//   Every period releases a BATCH of N independent fixed-K jobs instead of one.
//   N persistent worker threads (each pinned to one cpu from --cpu-list, one
//   thread per reservation core) are woken together at the release instant via
//   a barrier, each does its own K-rep unit on its own private A/B/Cm (or
//   candidate-stream state), and the batch is logged as ONE row once every worker has
//   finished (a second barrier) -- C_cputime_us is the MAX across threads (the
//   critical-path thread, consistent with R being release-to-LAST-finish),
//   nonvol_ctxt is the SUM (total preemption events across the whole batch).
//   Row schema is otherwise identical to the single-thread case, so the
//   existing calibrate.py/run_job.sh/result.py pipeline needs no changes.
//   --threads 1 (default) is byte-for-byte the original single-thread path.
// =============================================================================
#define _GNU_SOURCE
#include <errno.h>
#include <getopt.h>
#include <pthread.h>
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
    "nonvol_ctxt,K_reps,matrix_M,skipped_before";

enum { KIND_MATMUL, KIND_PRIMES };
#define PRIMES_CANDS_PER_K 1024     // candidates tested per K-unit; calibration tunes K
// Candidates are odd integers drawn (deterministically, from --seed) out of this
// range. Large enough that trial division is real integer-divide work (worst
// case ~sqrt(hi) odd divisors for an actual prime), small enough that a single
// candidate's worst case stays well under a tight-scale (10ms) period.
#define PRIMES_CAND_LO 1000003ULL
#define PRIMES_CAND_HI 2000003ULL

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

// ---- data-dependent kernel: trial-division primality over a candidate stream --
// Each candidate gets real trial division (idx = 3,5,7,... up to sqrt(cand)),
// EARLY EXIT on the first factor found -- genuinely data-dependent control flow
// (a composite with a small factor is cheap; a prime pays the full sqrt(cand)
// trial), unlike matmul's fixed-iteration loop. Reproducibility comes from the
// candidate stream itself being deterministic (seeded xorshift64, same as
// matmul's A/B fill): a given K always tests the same candidates, in the same
// order, every run -- so total op count for that K is fixed run-to-run even
// though it is not a fixed closed-form count independent of the data.
static inline uint64_t next_candidate(uint64_t *state) {
    uint64_t x = *state;
    x ^= x << 13; x ^= x >> 7; x ^= x << 17;
    *state = x;
    uint64_t span = PRIMES_CAND_HI - PRIMES_CAND_LO;
    uint64_t v = PRIMES_CAND_LO + (x % span);
    return v | 1ULL;   // force odd
}
static inline int is_prime_trial(uint64_t n) {
    if (n < 2) return 0;
    if (n % 2 == 0) return n == 2;
    for (uint64_t d = 3; d * d <= n; d += 2) {
        if (n % d == 0) return 0;   // early exit: composite, first factor found
    }
    return 1;
}
// One K-unit = PRIMES_CANDS_PER_K candidates tested. Returns a sink value
// (count of primes found) so the compiler cannot dead-code-eliminate the loop.
static long primes_batch(uint64_t *state, long k_units) {
    long primes_found = 0;
    long total = k_units * PRIMES_CANDS_PER_K;
    for (long i = 0; i < total; i++) {
        uint64_t cand = next_candidate(state);
        if (is_prime_trial(cand)) primes_found++;
    }
    return primes_found;
}

static long involuntary_ctxt(void) {
    struct rusage ru;
    if (getrusage(RUSAGE_THREAD, &ru) == 0) return ru.ru_nivcsw;
    return -1;
}

// ---- batch/multithread mode (--threads N) -------------------------------------
// "cpu-list" is a comma list of ints and/or "a-b" ranges (or "env" to read
// RT_CPUSET, the same driver-provided env var --cpu env already reads), e.g.
// "2,3" or "2-3". Expanded left-to-right; the first `threads` entries are used
// (one cpu per worker), matching the reservation's claimed cpuset order.
static int parse_cpu_list(const char *spec, int *out, int max_out) {
    char buf[256];
    strncpy(buf, spec, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = 0;
    int n = 0;
    char *save = NULL;
    char *tok = strtok_r(buf, ",", &save);
    while (tok && n < max_out) {
        char *dash = strchr(tok, '-');
        if (dash) {
            int a = atoi(tok), b = atoi(dash + 1);
            for (int c = a; c <= b && n < max_out; c++) out[n++] = c;
        } else {
            out[n++] = atoi(tok);
        }
        tok = strtok_r(NULL, ",", &save);
    }
    return n;
}

typedef struct {
    int cpu, kind, M, K, priority, warmup;
    double *A, *B, *Cm;
    uint64_t prime_state;
    pthread_barrier_t *bar_start, *bar_done;
    volatile int64_t C_ns;
    volatile long nv_delta;
    volatile int stop;
} worker_t;

static void *worker_main(void *arg) {
    worker_t *w = (worker_t *)arg;
    if (w->cpu >= 0) {
        cpu_set_t set; CPU_ZERO(&set); CPU_SET(w->cpu, &set);
        if (sched_setaffinity(0, sizeof(set), &set) != 0)
            fprintf(stderr, "[matmul] WARN worker sched_setaffinity(cpu=%d): %s\n",
                    w->cpu, strerror(errno));
    }
    if (w->priority > 0) {
        struct sched_param sp; memset(&sp, 0, sizeof(sp));
        sp.sched_priority = w->priority;
        if (sched_setscheduler(0, SCHED_FIFO, &sp) != 0)
            fprintf(stderr, "[matmul] WARN worker sched_setscheduler(FIFO,%d): %s\n",
                    w->priority, strerror(errno));
    }
    // un-timed self-warmup, same rationale as the single-thread path -- fault
    // in pages / warm caches before this worker starts taking part in any
    // barrier-synchronized (timed) batch.
    for (int i = 0; i < w->warmup; i++) {
        if (w->kind == KIND_PRIMES)
            primes_batch(&w->prime_state, w->K);
        else
            for (int k = 0; k < w->K; k++) matmul(w->A, w->B, w->Cm, w->M);
    }
    for (;;) {
        pthread_barrier_wait(w->bar_start);
        if (w->stop) return NULL;
        long nv0 = involuntary_ctxt();
        struct timespec c0, c1;
        clock_gettime(CLOCK_THREAD_CPUTIME_ID, &c0);
        if (w->kind == KIND_PRIMES)
            primes_batch(&w->prime_state, w->K);
        else
            for (int k = 0; k < w->K; k++) matmul(w->A, w->B, w->Cm, w->M);
        clock_gettime(CLOCK_THREAD_CPUTIME_ID, &c1);
        long nv1 = involuntary_ctxt();
        w->C_ns = ts_ns(&c1) - ts_ns(&c0);
        w->nv_delta = (nv0 >= 0 && nv1 >= 0) ? (nv1 - nv0) : 0;
        pthread_barrier_wait(w->bar_done);
    }
}

static void usage(const char *p) {
    fprintf(stderr,
        "usage: %s --M <int> --K <int> --period-us <int> --n-jobs <int>\n"
        "          [--kind matmul|primes] [--buf-kb <int>]\n"
        "          [--warmup <int>] [--priority <int>] [--cpu <int|env>]\n"
        "          [--seed <uint>] [--logfile <path>] [--no-lock-pages]\n"
        "          [--threads <int> --cpu-list <c0,c1,...|env>]\n"
        "  --kind primes   trial-division primality test over a deterministic\n"
        "                  candidate stream -- data-dependent (early-exit) control\n"
        "                  flow, integer-divide/branch-predictor bound. --buf-kb\n"
        "                  is accepted but unused (kept for cli compatibility).\n"
        "  --cpu env  reads RT_CPUSET (first cpu) for affinity; else no pinning.\n"
        "  --threads N  batch/multithread mode (model4): every period releases a\n"
        "               batch of N jobs run concurrently, one per --cpu-list entry.\n"
        "  --cpu-list env  reads RT_CPUSET (comma/range list), one cpu per thread.\n",
        p);
}

int main(int argc, char **argv) {
    int M = 48, K = 1, priority = 90, warmup = 0;
    long n_jobs = 5000;
    int64_t period_ns = 10 * 1000000LL;  // default 10 ms
    uint64_t seed = 20260713ULL;
    int cpu = -1;                 // -1 => no explicit pinning (driver/taskset did it)
    int lock_pages = 1;
    int kind = KIND_MATMUL;       // matmul (FP, in-cache) | primes (data-dependent, integer-divide)
    long buf_kb = 131072;         // accepted but unused by primes; kept for cli compatibility
    const char *logfile = NULL;
    int threads = 1;              // 1 = original single-thread path, unchanged
    char cpu_list_spec[256] = "";

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
        {"kind", required_argument, 0, 1001},
        {"buf-kb", required_argument, 0, 1002},
        {"threads", required_argument, 0, 1003},
        {"cpu-list", required_argument, 0, 1004},
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
        case 1001: kind = (strcmp(optarg, "primes") == 0) ? KIND_PRIMES : KIND_MATMUL; break;
        case 1002: buf_kb = atol(optarg); break;
        case 1003: threads = atoi(optarg); break;
        case 1004: strncpy(cpu_list_spec, optarg, sizeof(cpu_list_spec) - 1); break;
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
    if (M < 1 || K < 1 || n_jobs < 1 || threads < 1) { usage(argv[0]); return 2; }
    (void)buf_kb;  // accepted for cli compatibility; unused by any current --kind
    int cpu_ids[64];
    int n_cpu_ids = 0;
    if (threads > 1) {
        if (threads > 64) { fprintf(stderr, "[matmul] --threads too large (max 64)\n"); return 2; }
        if (!cpu_list_spec[0]) { fprintf(stderr, "[matmul] --threads %d requires --cpu-list\n", threads); return 2; }
        const char *spec = cpu_list_spec;
        char envbuf[256];
        if (strcmp(cpu_list_spec, "env") == 0) {
            const char *e = getenv("RT_CPUSET");
            if (!e || !*e) { fprintf(stderr, "[matmul] --cpu-list env but RT_CPUSET unset\n"); return 2; }
            strncpy(envbuf, e, sizeof(envbuf) - 1); envbuf[sizeof(envbuf) - 1] = 0;
            spec = envbuf;
        }
        n_cpu_ids = parse_cpu_list(spec, cpu_ids, 64);
        if (n_cpu_ids < threads) {
            fprintf(stderr, "[matmul] --cpu-list resolved %d cpu(s), need %d for --threads %d\n",
                    n_cpu_ids, threads, threads);
            return 2;
        }
    }

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

    uint64_t st = seed ? seed : 0x9e3779b97f4a7c15ULL;
    FILE *out = stdout;
    if (logfile) { out = fopen(logfile, "w"); if (!out) { perror("fopen"); return 1; } }

    if (threads <= 1) {
    // =========================== single-thread path ===========================
    // --- allocate + init A,B,C ONCE (outside the hot loop) ----------------------
    size_t nelem = (size_t)M * M;
    double *A = aligned_alloc(64, nelem * sizeof(double));
    double *B = aligned_alloc(64, nelem * sizeof(double));
    double *Cm = aligned_alloc(64, nelem * sizeof(double));
    if (!A || !B || !Cm) { fprintf(stderr, "[matmul] alloc failed\n"); return 1; }
    fill_matrix(A, (int)nelem, &st);
    fill_matrix(B, (int)nelem, &st);
    matmul(A, B, Cm, M);            // touch pages / warm caches before timing
    volatile double sink = 0.0;

    // data-dependent kernel: candidate stream state, seeded from the same
    // deterministic seed as A/B (continues across warmup+jobs -> never repeats
    // within a run, but identical run-to-run for the same --seed).
    uint64_t prime_state = st;

    fprintf(out, "# probe kind=%s M=%d K=%d period_us=%lld priority=%d "
                 "cpu=%d seed=%llu n_jobs=%ld warmup=%d\n",
            kind == KIND_PRIMES ? "primes" : "matmul", M, K,
            (long long)(period_ns / 1000), priority, cpu,
            (unsigned long long)seed, n_jobs, warmup);
    fprintf(out, "%s\n", CSV_HEADER);

    // --- WARM-UP: un-timed, OFF the periodic schedule --------------------------
    // Fault in pages / warm caches / settle DVFS and get past first-scheduling
    // transients BEFORE anchoring the metronome, so a slow first job cannot poison
    // every subsequent release. These jobs are neither timed nor logged.
    for (long w = 0; w < warmup; w++) {
        if (kind == KIND_PRIMES) {
            sink += (double)primes_batch(&prime_state, K);
        } else {
            for (int k = 0; k < K; k++) { matmul(A, B, Cm, M); }
            sink += Cm[0];
        }
    }

    // --- periodic loop (measured, with missed-release CATCH-UP) -----------------
    struct timespec now, t_start, t_finish, cc0, cc1, next;
    clock_gettime(CLOCK_MONOTONIC, &now);
    int64_t next_ns = ts_ns(&now) + period_ns;   // first release one period out

    for (long i = 0; i < n_jobs; i++) {
        ns_to_ts(next_ns, &next);
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &next, NULL);
        int64_t release_ns = next_ns;                 // scheduled activation instant
        long nv0 = involuntary_ctxt();
        clock_gettime(CLOCK_MONOTONIC, &t_start);
        clock_gettime(CLOCK_THREAD_CPUTIME_ID, &cc0);

        if (kind == KIND_PRIMES) {
            sink += (double)primes_batch(&prime_state, K);
        } else {
            for (int k = 0; k < K; k++) { matmul(A, B, Cm, M); }
            sink += Cm[0];
        }

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

        // Advance one period. If we overran, next_ns is now in the PAST -> skip
        // forward to the next FUTURE release boundary (catch-up) and record how
        // many releases we skipped instead of accumulating an unbounded backlog.
        next_ns += period_ns;
        long skipped = 0;
        if (period_ns > 0 && next_ns <= finish_ns) {
            int64_t behind = finish_ns - next_ns;
            skipped = (long)(behind / period_ns) + 1;
            next_ns += (int64_t)skipped * period_ns;   // strictly in the future
        }

        fprintf(out,
            "%ld,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%d,%.3f,%ld,%d,%d,%ld\n",
            i,
            release_ns / 1000.0, start_ns / 1000.0, finish_ns / 1000.0,
            C_ns / 1000.0, R_ns / 1000.0, delay_ns / 1000.0,
            dispatch_ns / 1000.0, midjob_ns / 1000.0, slack_ns / 1000.0,
            miss, tard_ns / 1000.0, nv, K, M, skipped);
    }
    if (out != stdout) fclose(out);
    (void)sink;
    free(A); free(B); free(Cm);

    } else {
    // ============================ batch/multithread path (model4) =============
    worker_t workers[64];
    pthread_t tid[64];
    pthread_barrier_t bar_start, bar_done;
    pthread_barrier_init(&bar_start, NULL, (unsigned)threads + 1);
    pthread_barrier_init(&bar_done, NULL, (unsigned)threads + 1);
    size_t nelem = (size_t)M * M;
    for (int t = 0; t < threads; t++) {
        worker_t *w = &workers[t];
        memset(w, 0, sizeof(*w));
        w->cpu = cpu_ids[t]; w->kind = kind; w->M = M; w->K = K;
        w->priority = priority; w->warmup = warmup;
        w->bar_start = &bar_start; w->bar_done = &bar_done;
        uint64_t tst = st + (uint64_t)(t + 1) * 0x9e3779b97f4a7c15ULL;  // per-thread deterministic offset
        if (kind == KIND_PRIMES) {
            w->prime_state = tst;
        } else {
            w->A = aligned_alloc(64, nelem * sizeof(double));
            w->B = aligned_alloc(64, nelem * sizeof(double));
            w->Cm = aligned_alloc(64, nelem * sizeof(double));
            if (!w->A || !w->B || !w->Cm) { fprintf(stderr, "[matmul] alloc failed (thread %d)\n", t); return 1; }
            fill_matrix(w->A, (int)nelem, &tst);
            fill_matrix(w->B, (int)nelem, &tst);
            matmul(w->A, w->B, w->Cm, M);
        }
        if (pthread_create(&tid[t], NULL, worker_main, w) != 0) {
            fprintf(stderr, "[matmul] pthread_create failed (thread %d)\n", t); return 1;
        }
    }

    fprintf(out, "# probe kind=%s M=%d K=%d period_us=%lld priority=%d "
                 "threads=%d seed=%llu n_jobs=%ld warmup=%d\n",
            kind == KIND_PRIMES ? "primes" : "matmul", M, K,
            (long long)(period_ns / 1000), priority,
            threads, (unsigned long long)seed, n_jobs, warmup);
    fprintf(out, "%s\n", CSV_HEADER);

    // warmup batches: each worker does its own internal --warmup rounds before
    // ever reaching bar_start (see worker_main), so these rounds just let the
    // ALREADY-warmed-up workers run a few more untimed, unlogged batches while
    // main settles into the barrier rendezvous itself.
    for (int w = 0; w < warmup; w++) {
        pthread_barrier_wait(&bar_start);
        pthread_barrier_wait(&bar_done);
    }

    struct timespec now, t_start, t_finish, next;
    clock_gettime(CLOCK_MONOTONIC, &now);
    int64_t next_ns = ts_ns(&now) + period_ns;

    for (long i = 0; i < n_jobs; i++) {
        ns_to_ts(next_ns, &next);
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &next, NULL);
        int64_t release_ns = next_ns;

        pthread_barrier_wait(&bar_start);          // release the whole batch together
        clock_gettime(CLOCK_MONOTONIC, &t_start);
        pthread_barrier_wait(&bar_done);            // wait for the LAST thread to finish
        clock_gettime(CLOCK_MONOTONIC, &t_finish);

        int64_t C_ns = 0; long nv = 0;
        for (int t = 0; t < threads; t++) {
            if (workers[t].C_ns > C_ns) C_ns = workers[t].C_ns;  // critical-path thread
            nv += workers[t].nv_delta;                            // total preemptions in the batch
        }

        int64_t start_ns = ts_ns(&t_start);
        int64_t finish_ns = ts_ns(&t_finish);
        int64_t R_ns = finish_ns - release_ns;
        int64_t delay_ns = R_ns - C_ns;
        int64_t dispatch_ns = start_ns - release_ns;
        int64_t midjob_ns = (finish_ns - start_ns) - C_ns;
        int64_t slack_ns = period_ns - R_ns;
        int miss = (R_ns > period_ns) ? 1 : 0;
        int64_t tard_ns = miss ? (R_ns - period_ns) : 0;

        next_ns += period_ns;
        long skipped = 0;
        if (period_ns > 0 && next_ns <= finish_ns) {
            int64_t behind = finish_ns - next_ns;
            skipped = (long)(behind / period_ns) + 1;
            next_ns += (int64_t)skipped * period_ns;
        }

        fprintf(out,
            "%ld,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%d,%.3f,%ld,%d,%d,%ld\n",
            i,
            release_ns / 1000.0, start_ns / 1000.0, finish_ns / 1000.0,
            C_ns / 1000.0, R_ns / 1000.0, delay_ns / 1000.0,
            dispatch_ns / 1000.0, midjob_ns / 1000.0, slack_ns / 1000.0,
            miss, tard_ns / 1000.0, nv, K, M, skipped);
    }
    if (out != stdout) fclose(out);

    // signal stop and release the workers one last time so they exit; each
    // returns right after bar_start on seeing w->stop, no matching bar_done.
    for (int t = 0; t < threads; t++) workers[t].stop = 1;
    pthread_barrier_wait(&bar_start);
    for (int t = 0; t < threads; t++) {
        pthread_join(tid[t], NULL);
        free(workers[t].A); free(workers[t].B); free(workers[t].Cm);
    }
    pthread_barrier_destroy(&bar_start);
    pthread_barrier_destroy(&bar_done);
    }

    return 0;
}
