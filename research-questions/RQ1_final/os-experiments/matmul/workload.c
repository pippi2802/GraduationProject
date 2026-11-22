// =============================================================================
// RQ1_final matmul workload -- dense matrix multiplication, periodic activation.
//
// Same harness as the sieve (workload.c): same CLI, same CSV schema, same clock
// handling, SCHED_FIFO, mlockall, warm-up, missed-release catch-up, in-thread
// per-job counters. ONLY the kernel differs.
//
// Kernel: C = A * B with three N x N matrices of doubles (3 * N^2 * 8 bytes),
// plain single-threaded i-k-j loop, compiled with -O2 (no BLAS, no OpenMP: they
// can start extra threads and change behaviour between runs). The matrices are
// allocated (cache-line aligned) and initialised ONCE at start-up with fixed
// values, so every job does exactly the same work. One K-unit (--K, "n_iter") =
// one full multiplication, with C zeroed at the start of each unit. A checksum
// of C is returned through a volatile sink so nothing can be optimised away.
//
// N = 256 -> 1.5 MiB, sized to sit inside a private 2 MiB L2 (check the L2 of the
// workers with lscpu). N is a runtime parameter (--matrix-n) and is
// scale-dependent in the configs (a 10 ms period cannot hold a 256 x 256
// multiplication, see config.yaml); it is logged in the matrix_M column.
//
// K (= n_iter) is calibrated per cell under full isolation so the median C is
// 70% of the budget Q (calibrate.py), as for the sieve.
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
    "nonvol_ctxt,K_reps,matrix_M,skipped_before,steal_us";
// "K_reps" = n_iter (multiplications per job), "matrix_M" = N (matrix dimension).

#define MATRIX_N_DEFAULT 256   // 3 * 256 * 256 * 8 B = 1.5 MiB

enum { CLOCK_CHOICE_MONOTONIC, CLOCK_CHOICE_REALTIME };
enum { ACT_PERIODIC, ACT_EVENT };

static inline int64_t ts_ns(const struct timespec *t) {
    return (int64_t)t->tv_sec * 1000000000LL + (int64_t)t->tv_nsec;
}
static inline void ns_to_ts(int64_t ns, struct timespec *t) {
    t->tv_sec = ns / 1000000000LL;
    t->tv_nsec = ns % 1000000000LL;
}

typedef struct { double *A, *B, *C; long n; } mm_t;

static int mm_init(mm_t *m, long n) {
    size_t bytes = (size_t)n * (size_t)n * sizeof(double);
    m->n = n;
    if (posix_memalign((void **)&m->A, 64, bytes) || posix_memalign((void **)&m->B, 64, bytes) ||
        posix_memalign((void **)&m->C, 64, bytes)) return -1;
    for (long i = 0; i < n * n; i++) {                       // fixed, data-independent values; initialised once
        m->A[i] = (double)((i * 7 + 3) % 101) / 101.0;
        m->B[i] = (double)((i * 13 + 5) % 103) / 103.0;
    }
    memset(m->C, 0, bytes);
    return 0;
}

// One K-unit = one full multiplication C = A*B (i-k-j order), C zeroed first. Returns a checksum so
// the compiler cannot dead-code-eliminate the loops.
static double matmul_batch(mm_t *m, long k_units) {
    const long n = m->n;
    const double *restrict A = m->A, *restrict B = m->B;
    double *restrict C = m->C;
    double sum = 0.0;
    for (long k = 0; k < k_units; k++) {
        memset(C, 0, (size_t)n * (size_t)n * sizeof(double));
        for (long i = 0; i < n; i++)
            for (long kk = 0; kk < n; kk++) {
                const double a = A[i * n + kk];
                for (long j = 0; j < n; j++) C[i * n + j] += a * B[kk * n + j];
            }
        sum += C[(k % n) * n + (k % n)] + C[n * n - 1];
    }
    return sum;
}

static long involuntary_ctxt(void) {
    struct rusage ru;
    if (getrusage(RUSAGE_THREAD, &ru) == 0) return ru.ru_nivcsw;
    return -1;
}

// Guest-visible hypervisor steal time for one vCPU, in USER_HZ ticks -- same
// mechanism/caveats as matmul.c's read_steal_ticks (coarse, ~10ms resolution).
static long read_steal_ticks(int cpu) {
    FILE *f = fopen("/proc/stat", "r");
    if (!f) return -1;
    char line[256];
    long steal = -1;
    while (fgets(line, sizeof(line), f)) {
        char label[32];
        long user, nice_, system_, idle, iowait, irq, softirq, st;
        if (sscanf(line, "%31s %ld %ld %ld %ld %ld %ld %ld %ld",
                   label, &user, &nice_, &system_, &idle, &iowait, &irq, &softirq, &st) == 9) {
            int n;
            if (sscanf(label, "cpu%d", &n) == 1 && n == cpu) { steal = st; break; }
        }
    }
    fclose(f);
    return steal;
}
static inline double steal_ticks_to_us(long ticks) {
    static double scale = 0.0;
    if (scale == 0.0) scale = 1.0e6 / (double)sysconf(_SC_CLK_TCK);
    return (double)ticks * scale;
}

// ---- event-triggered activation (--activation event), ported from matmul.c ---
// Deterministic uniform [0,1) draw from a xorshift64 stream, so trigger
// timing is reproducible given --seed like everything else.
static inline double uniform01(uint64_t *state) {
    uint64_t x = *state;
    x ^= x << 13; x ^= x >> 7; x ^= x << 17;
    *state = x;
    return (double)(x >> 11) / (double)(1ULL << 53);
}

// Shared trigger channel between the generator thread and the target thread.
// A condition variable is a real async OS wakeup path (futex-based
// block/wake), not a poll -- see matmul.c's own comment for the full
// rationale, identical here. One deliberate deviation from matmul.c: the
// generator here sleeps/timestamps on `clk` (the same --clock-selected
// clock the target uses), not a hardcoded CLOCK_MONOTONIC, so the
// --clock realtime|monotonic flag applies consistently to event mode too.
typedef struct {
    pthread_mutex_t mutex;
    pthread_cond_t cond;
    volatile int ready;
    volatile int target_done;
    volatile int64_t send_ns;
} trigger_t;

typedef struct {
    trigger_t *trig;
    clockid_t clk;
    int cpu, priority;
    int64_t period_ns;      // mean inter-trigger interval
    uint64_t seed_state;
} generator_args_t;

// Fires triggers at intervals uniformly jittered around period_ns (range
// [0.5, 1.5) x period_ns) -- see matmul.c's generator_main for the full
// rationale (bounded jitter, schedule advances from the planned time not
// the observed wake time, coalescing behavior). Ported unchanged in logic.
static void *generator_main(void *arg) {
    generator_args_t *g = (generator_args_t *)arg;
    if (g->cpu >= 0) {
        cpu_set_t set; CPU_ZERO(&set); CPU_SET(g->cpu, &set);
        if (sched_setaffinity(0, sizeof(set), &set) != 0)
            fprintf(stderr, "[workload] WARN generator sched_setaffinity(cpu=%d): %s\n",
                    g->cpu, strerror(errno));
    }
    if (g->priority > 0) {
        struct sched_param sp; memset(&sp, 0, sizeof(sp));
        sp.sched_priority = g->priority;
        if (sched_setscheduler(0, SCHED_FIFO, &sp) != 0)
            fprintf(stderr, "[workload] WARN generator sched_setscheduler(FIFO,%d): %s\n",
                    g->priority, strerror(errno));
    }
    struct timespec now, next;
    clock_gettime(g->clk, &now);
    int64_t next_ns = ts_ns(&now) + g->period_ns;
    for (;;) {
        ns_to_ts(next_ns, &next);
        clock_nanosleep(g->clk, TIMER_ABSTIME, &next, NULL);
        struct timespec fired; clock_gettime(g->clk, &fired);
        int64_t send_ns = ts_ns(&fired);
        pthread_mutex_lock(&g->trig->mutex);
        if (g->trig->target_done) { pthread_mutex_unlock(&g->trig->mutex); break; }
        g->trig->send_ns = send_ns;
        g->trig->ready = 1;
        pthread_cond_signal(&g->trig->cond);
        pthread_mutex_unlock(&g->trig->mutex);
        double jitter = 0.5 + uniform01(&g->seed_state);   // [0.5, 1.5)
        next_ns = next_ns + (int64_t)(g->period_ns * jitter);
    }
    return NULL;
}

// "0-3"/"0,2" -> {0,1,2,3} / {0,2} -- comma AND hyphen are both plain
// delimiters here, matching the DRA driver's own CDI convention exactly
// (see matmul.c's parse_cpu_list comment for the full rationale: hyphen is
// never a numeric range for RT_CPUSET, same bug/fix precedent applies here).
static int parse_cpu_list(const char *spec, int *out, int max_out) {
    char buf[256];
    strncpy(buf, spec, sizeof(buf) - 1);
    buf[sizeof(buf) - 1] = 0;
    int n = 0;
    char *save = NULL;
    char *tok = strtok_r(buf, ",-", &save);
    while (tok && n < max_out) {
        out[n++] = atoi(tok);
        tok = strtok_r(NULL, ",-", &save);
    }
    return n;
}

static void usage(const char *p) {
    fprintf(stderr,
        "usage: %s --K <int> --period-us <int> --n-jobs <int>\n"
        "          [--matrix-n <int>] [--warmup <int>] [--priority <int>]\n"
        "          [--cpu <int|env>] [--seed <uint>] [--logfile <path>]\n"
        "          [--no-lock-pages] [--clock monotonic|realtime]\n"
        "          [--activation periodic|event] [--generator-cpu <int>]\n"
        "  --matrix-n <int>  (default 256) matrix dimension N; three N x N double\n"
        "                    matrices (3*N*N*8 bytes). --K = multiplications per job.\n"
        "  --clock monotonic  (default) CLOCK_MONOTONIC -- immune to NTP steps,\n"
        "                     matches matmul.c's own choice.\n"
        "  --clock realtime   CLOCK_REALTIME -- matches the reference literature\n"
        "                     implementation's literal choice; NTP/chrony-\n"
        "                     adjustable on this platform.\n"
        "  --activation periodic  (default) release is a precomputed\n"
        "                          clock_nanosleep schedule.\n"
        "  --activation event      release is an async trigger from a second\n"
        "                          (generator) thread, requires --generator-cpu.\n"
        "  --generator-cpu <int|env>  cpu for the generator thread (--activation\n"
        "                          event only). env reads RT_CPUSET's SECOND\n"
        "                          cpu (a count=2 claim hands back both).\n"
        "  --cpu env  reads RT_CPUSET's first cpu for affinity; else no pinning.\n",
        p);
}

int main(int argc, char **argv) {
    int K = 1, priority = 90, warmup = 0;
    long matrix_n = MATRIX_N_DEFAULT;
    long n_jobs = 5000;
    int64_t period_ns = 10 * 1000000LL;  // default 10 ms
    uint64_t seed = 20260713ULL;         // accepted for cli/logging consistency;
                                          // the matmul kernel itself is deterministic
                                          // regardless of seed (see header comment)
    int cpu = -1;
    int cpu_env = 0;
    int generator_cpu = -1;
    int generator_cpu_env = 0;
    int lock_pages = 1;
    const char *logfile = NULL;
    int clock_choice = CLOCK_CHOICE_MONOTONIC;
    int activation = ACT_PERIODIC;

    static struct option opts[] = {
        {"K", required_argument, 0, 'K'},
        {"period-us", required_argument, 0, 'P'},
        {"n-jobs", required_argument, 0, 'n'},
        {"warmup", required_argument, 0, 'w'},
        {"priority", required_argument, 0, 'r'},
        {"cpu", required_argument, 0, 'c'},
        {"seed", required_argument, 0, 's'},
        {"logfile", required_argument, 0, 'o'},
        {"no-lock-pages", no_argument, 0, 'L'},
        {"clock", required_argument, 0, 1001},
        {"matrix-n", required_argument, 0, 1002},
        {"activation", required_argument, 0, 1003},
        {"generator-cpu", required_argument, 0, 1004},
        {"help", no_argument, 0, 'h'},
        {0, 0, 0, 0}};
    int ci;
    while ((ci = getopt_long(argc, argv, "K:P:n:w:r:c:s:o:Lh", opts, NULL)) != -1) {
        switch (ci) {
        case 'K': K = atoi(optarg); break;
        case 'P': period_ns = (int64_t)atoll(optarg) * 1000LL; break;
        case 'n': n_jobs = atol(optarg); break;
        case 'w': warmup = atoi(optarg); break;
        case 'r': priority = atoi(optarg); break;
        case 's': seed = strtoull(optarg, NULL, 10); break;
        case 'o': logfile = optarg; break;
        case 'L': lock_pages = 0; break;
        case 1001: clock_choice = (strcmp(optarg, "realtime") == 0) ? CLOCK_CHOICE_REALTIME : CLOCK_CHOICE_MONOTONIC; break;
        case 1002: matrix_n = atol(optarg); break;
        case 1003: activation = (strcmp(optarg, "event") == 0) ? ACT_EVENT : ACT_PERIODIC; break;
        case 1004:
            if (strcmp(optarg, "env") == 0) {
                generator_cpu_env = 1;
            } else {
                generator_cpu = atoi(optarg);
            }
            break;
        case 'c':
            if (strcmp(optarg, "env") == 0) {
                cpu_env = 1;
            } else {
                cpu = atoi(optarg);
            }
            break;
        case 'h': default: usage(argv[0]); return 2;
        }
    }
    // Resolve any "env" cpu requests from ONE RT_CPUSET read/parse -- a
    // count=2 claim (model4's target+generator) hands back BOTH cpus in one
    // comma/hyphen-separated string, e.g. "2,3"; --cpu env takes the first,
    // --generator-cpu env takes the second, matching the DRA driver's own
    // claimed-cpuset ordering.
    if (cpu_env || generator_cpu_env) {
        const char *e = getenv("RT_CPUSET");
        int ids[8], n = (e && *e) ? parse_cpu_list(e, ids, 8) : 0;
        if (cpu_env) {
            if (n >= 1) cpu = ids[0];
            else fprintf(stderr, "[workload] WARN --cpu env but RT_CPUSET unset/empty\n");
        }
        if (generator_cpu_env) {
            if (n >= 2) generator_cpu = ids[1];
            else fprintf(stderr, "[workload] WARN --generator-cpu env but RT_CPUSET has <2 cpus\n");
        }
    }
    if (K < 1 || n_jobs < 1 || matrix_n < 2) { usage(argv[0]); return 2; }
    if (activation == ACT_EVENT && generator_cpu < 0) {
        fprintf(stderr, "[workload] --activation event requires --generator-cpu\n");
        usage(argv[0]); return 2;
    }
    clockid_t clk = (clock_choice == CLOCK_CHOICE_REALTIME) ? CLOCK_REALTIME : CLOCK_MONOTONIC;

    // --- affinity (best effort; KubeDeadline usually pins already) --------------
    if (cpu >= 0) {
        cpu_set_t set; CPU_ZERO(&set); CPU_SET(cpu, &set);
        if (sched_setaffinity(0, sizeof(set), &set) != 0)
            fprintf(stderr, "[workload] WARN sched_setaffinity(cpu=%d): %s\n", cpu, strerror(errno));
    }
    // --- SCHED_FIFO (best effort; needs CAP_SYS_NICE) ---------------------------
    if (priority > 0) {
        struct sched_param sp; memset(&sp, 0, sizeof(sp));
        sp.sched_priority = priority;
        if (sched_setscheduler(0, SCHED_FIFO, &sp) != 0)
            fprintf(stderr, "[workload] WARN sched_setscheduler(FIFO,%d): %s "
                            "(C still valid; run continues)\n", priority, strerror(errno));
    }
    // --- lock pages -------------------------------------------------------------
    if (lock_pages && mlockall(MCL_CURRENT | MCL_FUTURE) != 0)
        fprintf(stderr, "[workload] WARN mlockall: %s\n", strerror(errno));

    FILE *out = stdout;
    if (logfile) { out = fopen(logfile, "w"); if (!out) { perror("fopen"); return 1; } }

    mm_t mm;
    if (mm_init(&mm, matrix_n) != 0) { fprintf(stderr, "[workload] alloc failed\n"); return 1; }
    volatile double sink = 0;
    sink += matmul_batch(&mm, 1);   // touch pages / warm cache before timing

    if (activation == ACT_EVENT) {
        fprintf(out, "# probe kind=matmul activation=event clock=%s matrix_n=%ld K=%d "
                     "period_us=%lld priority=%d target_cpu=%d generator_cpu=%d "
                     "seed=%llu n_jobs=%ld warmup=%d\n",
                clock_choice == CLOCK_CHOICE_REALTIME ? "realtime" : "monotonic",
                matrix_n, K, (long long)(period_ns / 1000), priority, cpu, generator_cpu,
                (unsigned long long)seed, n_jobs, warmup);
    } else {
        fprintf(out, "# probe kind=matmul activation=periodic clock=%s matrix_n=%ld K=%d "
                     "period_us=%lld priority=%d cpu=%d seed=%llu n_jobs=%ld warmup=%d\n",
                clock_choice == CLOCK_CHOICE_REALTIME ? "realtime" : "monotonic",
                matrix_n, K, (long long)(period_ns / 1000), priority, cpu,
                (unsigned long long)seed, n_jobs, warmup);
    }
    fprintf(out, "%s\n", CSV_HEADER);

    // --- WARM-UP: un-timed, OFF the periodic/trigger schedule -------------------
    for (long w = 0; w < warmup; w++) sink += matmul_batch(&mm, K);

    if (activation == ACT_EVENT) {
    // ============================ event-triggered path (model4) ================
    // Target does the same compute as the periodic path; the difference is
    // purely how release_ns is obtained -- see generator_main's header
    // comment. skipped_before is always 0 here (unlike periodic's explicit
    // catch-up counter), matching matmul.c's own model4 design exactly.
    trigger_t trig; memset(&trig, 0, sizeof(trig));
    pthread_mutex_init(&trig.mutex, NULL);
    pthread_cond_init(&trig.cond, NULL);

    generator_args_t gargs = { &trig, clk, generator_cpu, priority, period_ns,
                                seed + 0x9e3779b97f4a7c15ULL };
    pthread_t gtid;
    if (pthread_create(&gtid, NULL, generator_main, &gargs) != 0) {
        fprintf(stderr, "[workload] pthread_create (generator) failed\n"); return 1;
    }

    for (long i = 0; i < n_jobs; i++) {
        pthread_mutex_lock(&trig.mutex);
        while (!trig.ready) pthread_cond_wait(&trig.cond, &trig.mutex);
        int64_t release_ns = trig.send_ns;
        trig.ready = 0;
        pthread_mutex_unlock(&trig.mutex);

        long nv0 = involuntary_ctxt();
        long sv0 = read_steal_ticks(cpu);
        struct timespec t_start, t_finish, cc0, cc1;
        clock_gettime(clk, &t_start);
        clock_gettime(CLOCK_THREAD_CPUTIME_ID, &cc0);

        sink += matmul_batch(&mm, K);

        clock_gettime(CLOCK_THREAD_CPUTIME_ID, &cc1);
        clock_gettime(clk, &t_finish);
        long nv1 = involuntary_ctxt();
        long sv1 = read_steal_ticks(cpu);
        double steal_us = steal_ticks_to_us((sv0 >= 0 && sv1 >= 0) ? (sv1 - sv0) : 0);

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

        fprintf(out,
            "%ld,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%d,%.3f,%ld,%d,%ld,%ld,%.3f\n",
            i,
            release_ns / 1000.0, start_ns / 1000.0, finish_ns / 1000.0,
            C_ns / 1000.0, R_ns / 1000.0, delay_ns / 1000.0,
            dispatch_ns / 1000.0, midjob_ns / 1000.0, slack_ns / 1000.0,
            miss, tard_ns / 1000.0, nv, K, matrix_n, 0L, steal_us);
    }
    if (out != stdout) fclose(out);
    (void)sink;
    pthread_mutex_lock(&trig.mutex);
    trig.target_done = 1;
    pthread_mutex_unlock(&trig.mutex);
    pthread_join(gtid, NULL);
    pthread_mutex_destroy(&trig.mutex);
    pthread_cond_destroy(&trig.cond);
    free(mm.A); free(mm.B); free(mm.C);
    return 0;

    }
    // --- periodic loop (measured, with missed-release CATCH-UP) -----------------
    struct timespec now, t_start, t_finish, cc0, cc1, next;
    clock_gettime(clk, &now);
    int64_t next_ns = ts_ns(&now) + period_ns;   // first release one period out

    for (long i = 0; i < n_jobs; i++) {
        ns_to_ts(next_ns, &next);
        clock_nanosleep(clk, TIMER_ABSTIME, &next, NULL);
        int64_t release_ns = next_ns;                 // scheduled activation instant
        long nv0 = involuntary_ctxt();
        long sv0 = read_steal_ticks(cpu);
        clock_gettime(clk, &t_start);
        clock_gettime(CLOCK_THREAD_CPUTIME_ID, &cc0);

        sink += matmul_batch(&mm, K);

        clock_gettime(CLOCK_THREAD_CPUTIME_ID, &cc1);
        clock_gettime(clk, &t_finish);
        long nv1 = involuntary_ctxt();
        long sv1 = read_steal_ticks(cpu);
        double steal_us = steal_ticks_to_us((sv0 >= 0 && sv1 >= 0) ? (sv1 - sv0) : 0);

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

        // Advance one period; catch up on overrun exactly as matmul.c does.
        next_ns += period_ns;
        long skipped = 0;
        if (period_ns > 0 && next_ns <= finish_ns) {
            int64_t behind = finish_ns - next_ns;
            skipped = (long)(behind / period_ns) + 1;
            next_ns += (int64_t)skipped * period_ns;
        }

        fprintf(out,
            "%ld,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%d,%.3f,%ld,%d,%ld,%ld,%.3f\n",
            i,
            release_ns / 1000.0, start_ns / 1000.0, finish_ns / 1000.0,
            C_ns / 1000.0, R_ns / 1000.0, delay_ns / 1000.0,
            dispatch_ns / 1000.0, midjob_ns / 1000.0, slack_ns / 1000.0,
            miss, tard_ns / 1000.0, nv, K, matrix_n, skipped, steal_us);
    }
    if (out != stdout) fclose(out);
    (void)sink;
    free(mm.A); free(mm.B); free(mm.C);
    return 0;
}
