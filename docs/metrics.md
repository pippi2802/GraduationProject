1. Your primary metrics (the "what breaks" layer)

These are the outputs — the guarantee and its variability. Each is measured per-job, then summarized as a distribution:

┌────────────────────────┬────────────────────────────────┬──────────┬────────────────────────────────────────────────────────────────────────────────┐
│ Metric                 │ Definition                     │ Source   │ Why                                                                            │
├────────────────────────┼────────────────────────────────┼──────────┼────────────────────────────────────────────────────────────────────────────────┤
│ C                      │ CLOCK_THREAD_CPUTIME_ID per    │ kernel   │ Compute demand; near-constant reference. Its variability = execution-layer     │
│                        │ job                            │ log      │ environment                                                                    │
├────────────────────────┼────────────────────────────────┼──────────┼────────────────────────────────────────────────────────────────────────────────┤
│ R                      │ CLOCK_MONOTONIC_RAW            │ kernel   │ The actual guarantee (response time)                                           │
│                        │ finish−release                 │ log      │                                                                                │
├────────────────────────┼────────────────────────────────┼──────────┼────────────────────────────────────────────────────────────────────────────────┤
│ delay = R − C          │ R minus C                      │ derived  │ The pure delay — where steal/IRQ/preempt live                                  │
├────────────────────────┼────────────────────────────────┼──────────┼────────────────────────────────────────────────────────────────────────────────┤
│ deadline miss /        │ R > P ? , R − P                │ derived  │ The binary guarantee outcome                                                   │
│ tardiness              │                                │          │                                                                                │
├────────────────────────┼────────────────────────────────┼──────────┼────────────────────────────────────────────────────────────────────────────────┤
│ slack                  │ P − R                          │ derived  │ Margin remaining                                                               │
└────────────────────────┴────────────────────────────────┴──────────┴────────────────────────────────────────────────────────────────────────────────┘

And crucially, you report each not as a mean but as a full distribution: median, p99, p99.9, max, CV, and the tail shape (ECDF/CCDF). "Normal distribution and variability" = you characterize the body (median, CV) separately from the tail (p99.9, max), because cloud factors live in the tail.

2. Your cloud factors (the "why it breaks" layer) — how each is represented

These are covariates: measured per time-window and joined to each job so you can regress delay against them. This is the heart of your question.

┌─────────────────────┬──────────────────────────────────────────────┬───────────────────────────────────────────────────────────────┬────────────────┐
│ Cloud factor        │ Concrete metric                              │ Source                                                        │ Which layer    │
├─────────────────────┼──────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┼────────────────┤
│ Steal time          │ st counter per vCPU; per-thread run-delay    │ /proc/stat (steal column); /proc/<tid>/schedstat field 2      │ delay          │
│                     │                                              │ (time runnable-but-not-running)                               │ (α-delivery)   │
├─────────────────────┼──────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┼────────────────┤
│ IRQ                 │ per-core IRQ + softIRQ CPU-time; per-line    │ /proc/stat (irq/softirq columns), /proc/interrupts,           │ delay (Δ)      │
│                     │ counts                                       │ /proc/softirqs                                                │                │
├─────────────────────┼──────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┼────────────────┤
│ Preemption /        │ involuntary context switches; run-delay      │ /proc/<tid>/status (nonvoluntary_ctxt_switches), schedstat,   │ delay (Δ)      │
│ scheduling latency  │ (schedstat); wakeup→run latency              │ optionally sched_switch tracepoint                            │                │
├─────────────────────┼──────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┼────────────────┤
│ DVFS / frequency    │ effective CPU frequency, aperf/mperf ratio   │ /proc/cpuinfo cur_freq, cpufreq, or MSRs (often restricted in │ execution      │
│                     │                                              │ Azure guest — record as limitation)                           │ (C-inflation)  │
├─────────────────────┼──────────────────────────────────────────────┼───────────────────────────────────────────────────────────────┼────────────────┤
│ HT contention       │ the M3 treatment itself + sibling activity   │ sibling core util                                             │ execution      │
│                     │                                              │                                                               │ (C-inflation)  │
└─────────────────────┴──────────────────────────────────────────────┴───────────────────────────────────────────────────────────────┴────────────────┘

The key insight on representation:  schedstat  field 2 (run-delay) is your single most valuable covariate, because it directly measures "time the task was runnable but not running" — which is exactly R − C from the kernel's own view. Steal and involuntary-preemption both flow into it. So run-delay is your bridge between the observed delay and its causes.

The attribution identity you're building:

R − C  ≈  I_steal  +  I_IRQ  +  I_preempt  +  ε
         (schedstat run-delay accounts for most of this)

Each covariate explains a share of the per-job delay; ε (unattributable residual) is itself a finding — it's the "non-determinism you can't name," which supports the "no stable bound" claim.

3. What you might be missing

Here's my honest assessment of the factor list, including your two candidates:

Network communication — mostly NO (for RQ1 as scoped), but with one important caveat.
Your workload is a CPU-bound, self-contained matrix multiply. It does no network I/O, so network latency/bandwidth does not directly affect C or R. So as a direct factor: not relevant, and including it would dilute your CPU-focused story. BUT network traffic is the cause of IRQs — NIC interrupts are the dominant steerable interrupt source, which is exactly why Model 4 optionally adds a network-I/O generator. So network appears indirectly, as the driver of the IRQ factor, not as a metric of its own. That's the right place for it. (If your real-world KubeDeadline use-case involved networked RT tasks — media streaming, control loops over the network — then network jitter would become a first-class factor. Worth one sentence in "limitations/future work.")

Dispatch — YES, and you're partly already capturing it; worth making explicit.
By "dispatch" I read scheduling/dispatch latency: the gap between when a job should run (release/wakeup) and when the CPU actually dispatches it. This is real and important in RT, and it's already inside your R − C — but you can surface it as its own sub-metric:

• start − release = dispatch latency (how late the job got picked up)
• finish − start − C = mid-job preemption (interruptions once running)

Splitting R−C into these two gives you a sharper picture: dispatch latency is front-loaded delay (scheduler/CBS replenishment timing), while mid-job preemption is intrusion (IRQ/steal during execution). I'd add both as derived columns — you already log release/start/finish, so it's free.

Two more genuine cloud factors you haven't named:

1. CBS replenishment / admission timing (Δ itself). When the budget is replenished relative to the period boundary is a scheduler behavior that directly sets dispatch latency. You measure it via cgroup  cpu.stat  (nr_throttled, throttled_usec) — this is your Δ_eff, already in the plan. Just recognize it as a "factor," not only a metric.
2. NUMA / memory-placement effects — on a 2-core D4s_v5 this is negligible (single NUMA node), so safely excluded; mention once.

Summary: the refined factor→metric map

• Steal →  /proc/stat  steal + schedstat run-delay → delay
• IRQ → per-core irq/softirq time + per-line counts (driven by network traffic) → delay
• Preemption → involuntary ctxt-switches + schedstat run-delay → delay
• Dispatch latency (make explicit) → start − release → delay
• Mid-job preemption (make explicit) → (finish − start) − C → delay
• Replenishment/Δ → cgroup cpu.stat throttled_usec → delay
• HT / DVFS → M3 treatment / frequency counters → execution (C-inflation)
• Network → not a direct metric; enters as the source of IRQ (M4) + a limitations note
• NUMA → excluded (single-node), noted

My recommendation: add dispatch latency (start−release) and mid-job preemption ((finish−start)−C) as explicit derived per-job columns, and add involuntary context switches and schedstat run-delay as covariates (run-delay is the big one). Keep network only as the IRQ driver in M4. That makes your R−C decomposition fully accountable factor-by-factor.