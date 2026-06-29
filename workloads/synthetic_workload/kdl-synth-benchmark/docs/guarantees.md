# KubeDeadline: Temporal Guarantees, Cloud Failure Modes, and Parameter Derivation

This document frames the conceptual backbone of the thesis: **what KubeDeadline
guarantees** (in temporal terms), **how cloud factors break those guarantees**, and
**the measurement-based challenge of deriving the reservation parameters**.

---

## 1. The supply abstraction

A `SCHED_DEADLINE`-enabled container implements a **virtual processor** for the
workloads running inside it. Each reservation `r_i` is characterised by the triplet

$$
r_i = (Q_i,\; P_i,\; m_i)
$$

- `Q_i` — budget (CPU time granted per period, per core)
- `P_i` — period (replenishment interval)
- `m_i` — number of cores assigned to the reservation

This triplet translates into the two quantities that *all* temporal reasoning is
built on:

- **Guaranteed CPU bandwidth**
  $$
  \alpha_i = \frac{m_i \, Q_i}{P_i}
  $$
  the long-run *rate* of CPU the container is promised ("how much").

- **Maximum CPU (supply) delay** $\Delta_i$
  the worst-case interval the container can be starved before the promised budget is
  guaranteed available again ("how late").

Together, $(\alpha_i, \Delta_i)$ form the **supply abstraction**: a guaranteed *rate*
with a bounded *latency*.

---

## 2. The guarantees (temporal terms)

KubeDeadline's promise reduces to **two** guarantees, linked by a third bridging
assumption.

### G1 — Supply guarantee
Each container is guaranteed its virtual-processor supply: a CPU bandwidth
$\alpha_i = m_i Q_i / P_i$ delivered with a bounded worst-case supply delay
$\Delta_i$. In any time window, the container receives **at least** the supply
promised by $(\alpha_i, \Delta_i)$.

### G2 — Deadline guarantee
Given that supply, **every task $\tau_i$ in the container meets its deadline**. This
holds because the supply-bound function dominates the demand-bound function under
fixed-priority scheduling.

> **G2 depends on G1.** Deadlines are met *because* the supply is delivered. If the
> supply degrades, deadlines fail.

### G3 (bridge) — Isolation / composability
The supply $(\alpha_i, \Delta_i)$ is delivered **regardless of what other containers
do**. This is what keeps G1 true under contention and lets each container be analysed
in isolation.

**The chain:** `supply delivered (G1) → deadlines met (G2)`, with isolation (G3) as
the assumption that keeps G1 true under neighbours.

---

## 3. Where the guarantees break in the cloud

The model assumes the kernel can actually *deliver* $(\alpha_i, \Delta_i)$. In a VM,
the kernel's notion of "CPU time" is itself virtualised, so the guarantees can erode.
There are **two distinct failure modes**:

| Cloud factor | Guarantee broken | Mechanism |
|---|---|---|
| **vCPU steal / host preemption** | **G1** (then G2) | The budget `Q_i` is accounted in *guest* time, but the host de-schedules the vCPU. Wall-clock delivers less than $\alpha_i$ and the supply delay exceeds $\Delta_i$ — the supply itself shrinks. |
| **LLC / memory-bandwidth contention** | **G2 directly** | CPU *time* is still delivered (G1 intact), but each job's *actual* execution time inflates due to cache/memory pressure. Demand exceeds what the supply was sized for → deadline miss. |

**The clean story:**
- One factor breaks **the supply itself** (G1) — the container literally gets less CPU
  than promised.
- The other breaks **the deadline through inflated demand** (G2) — even when the
  supply is fully delivered.

Two failure modes, two guarantees — not a long correctness checklist.

---

## 4. The parameter-derivation challenge

The theory needs a per-task execution time $c_i$ to build the demand-bound function.
But in the cloud the **WCET is unknown**, so it must be estimated from measurement.
This creates a **budget-sizing trade-off**:

$$
c_i^{\text{est}}
\;\longrightarrow\; \text{demand-bound function}
\;\longrightarrow\; \text{CARTS / MPR}
\;\longrightarrow\; (Q_i, P_i, m_i)
$$

- **Estimate too small** → derived $Q_i$ too small → supply under-provisioned →
  **deadline misses** (G2 broken even on a quiet host).
- **Estimate too large** → derived $Q_i$ too large → **wasted budget**, lower
  admittable density, fewer containers fit → poor utilisation / system inefficiency.

### Candidate execution-time statistics
What statistic of the measured execution-time distribution should feed CARTS?

- **Max observed** (empirical WCET) — safe-ish, wasteful.
- **High percentile** (p99 / p99.9) — tight, small miss probability.
- **Mean + k·σ**, or **EVT / pWCET** (extreme-value-theory tail bound) — principled
  tail estimate.
- **Measured WCET × safety margin** — engineering rule of thumb.

### The cloud twist
The measured distribution **itself shifts** under interference (steal, cache
pressure). A value derived on a quiet node may be optimistic in production — which is
precisely why the interference experiments matter for validating the derivation
method.

---

## 5. Thesis spine

1. **Derive** $(Q, P, m)$ from a measurement-based execution-time estimate — tight
   enough to avoid wasting budget, safe enough to meet deadlines.
2. **Evaluate** how cloud factors erode the guarantees the derivation assumed:
   - vCPU steal → **G1** (supply shrinks)
   - LLC / memory contention → **G2** (demand inflates)

The benchmark (vanilla CFS vs. RT-DRA, with/without interference) is the apparatus to
**quantify** which guarantees survive on the cloud host and by how much
(deadline-miss ratio, response-time tail).
