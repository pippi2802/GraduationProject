**On the isolated burst in model3-w4 (physical placement, reserved competitor), soft scale, U=0.6:**

One of the four collected rounds for this cell shows a run of 91 consecutive
deadline misses, an outlier against the near-zero miss rate this arm shows
everywhere else. Inspection of the raw per-job data shows this is not a
failure of the physical-placement isolation the arm is designed to test: the
target's execution time (`C_cputime_us`) during the affected jobs stays close
to its normal value, and `dispatch_latency_us` (time from release to actual
start) is unaffected -- the target is not being blocked from starting, and it
is not executing more slowly once running.

Instead, the delay appears *within* execution: `mid_job_preempt_us` --
computed as (finish − start) − C, i.e. wall-clock time between start and
finish not accounted for by measured CPU time -- jumps from a baseline of
roughly 1-2µs to a consistent ~39.7ms (std ≈ 9µs across the affected jobs)
for exactly this window, accompanied by a genuine OS-reported involuntary
context switch (`nonvol_ctxt=1`, versus 0 in unaffected jobs). This value is
close to P−Q for this cell (100,000µs period − 40,000µs budget at U=0.6 ≈
40,000µs remaining), consistent with the target's thread being blocked by the
kernel's own real-time bandwidth throttling (the `cpu.rt_runtime_us` cgroup
mechanism used to seed CBS-style budgets on this cluster) until the start of
the next scheduling period, rather than with contention from the co-located
competitor, which remains on a separate physical core throughout.

The same low-frequency pattern (affecting well under 1% of jobs) is present
across the solo baseline (model1) and the other physical-placement arm
(model3-w3) as well, which rules out the reserved competitor as the cause:
these are isolated instances of the reservation's own kernel-level budget
enforcement occasionally engaging, not a breakdown of the physical-core
isolation this arm is designed to demonstrate. The round in question is
otherwise consistent with the other three rounds collected for this arm and
is retained in the pooled dataset; this episode is noted here rather than
excluded, since it reflects a real (if rare) system behavior rather than a
measurement artifact.
