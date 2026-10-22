#!/usr/bin/env python3
"""Soundness table, over-budget figure and appendix table of the RQ2 online validation (video, segmentation, audio, LiDAR).

    python3 make_rq2_validation_outputs.py

Writes, next to this script:
  tables/rq2_soundness.tex          soundness table (rate_ratio / window_ratio per cell)
  tables/rq2_validation_full.tex    appendix longtable, one row per cell
  figures/rq2_overbudget.pdf/.png   over-budget of every cell
  figures/rq2_overbudget.tex        \\includegraphics snippet with the caption
  rq2_validation_cells.csv          the numbers behind all three

Everything is computed from the per-run validation data (workload*/validation_p4/iter*/results) and the budget files of the same folders; no number is
copied from an existing table. The functions for overrun rate, violated windows, stalls and C_hat; the (m,k) window is counted on C > Q as in the derivation are those of p4_results_table.py
(loaded from the source up to its main loop, so importing it does not write its tables).

Final budgets: the newest budgets.csv entry of every cell, then the monotonicity rule (a stricter level never gets a smaller budget than a looser one).
A cell whose final budget differs from the one run online is replayed on the run's own trace: the overruns are the jobs with C > Q_final, and the
bursts of misses that contained an overrun at the online Q but none at Q_final are removed (those jobs would have met the deadline); the other misses stay.
Such cells are marked with a dagger.
"""
import pathlib, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches

HERE = pathlib.Path(__file__).resolve().parent
RQ2 = HERE.parent

# ---- reuse the functions of p4_results_table.py (everything before its main loop) ----
_src = (RQ2 / "p4_results_table.py").read_text().split("\nrows = []\n")[0]
_ns = {"__file__": str(RQ2 / "p4_results_table.py"), "__name__": "p4_results_table"}
_argv, sys.argv = sys.argv, [sys.argv[0]]
exec(compile(_src, "p4_results_table.py", "exec"), _ns)
sys.argv = _argv
read_run, window_violation, stalls, count_budget, EPS = (_ns[n] for n in ("read_run", "window_violation", "stalls", "count_budget", "EPS"))


def overrun_misses(bad, over):
    """misses of the bursts of consecutive misses that contain an overrun (used only to replay a raised budget on the lost releases)"""
    edges = np.diff(np.r_[0, bad.astype(int), 0])
    out = np.zeros(len(bad), bool)
    for s, e in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
        if over[s:e].any():
            out[s:e] = True
    return out

WORKLOADS = [("Video", "workload1", 41.667), ("Segmentation", "workload2", 100.0), ("LiDAR", "workload4", 50.0), ("Audio", "workload3", 10.0)]
ORDER = [("Video", "single"), ("Video", "multi"), ("Segmentation", "single"), ("LiDAR", "single"), ("LiDAR", "multi"), ("Audio", "single"), ("Audio", "multi")]
PERIOD_LABEL = {"Video": "41.7", "Segmentation": "100", "LiDAR": "50", "Audio": "10"}
VARIANT = {"route1": "Stress-based", "variant1": "Stress-based", "route2b": "Baseline-based", "variant2": "Baseline-based", "hwm": "High-water mark", "variant3": "High-water mark"}
VARIANTS = ["Stress-based", "Baseline-based", "High-water mark"]
LEVELS = ["relaxed", "strict"]
COLOR = {"Stress-based": "#2a78d6", "Baseline-based": "#eb6834", "High-water mark": "#1baf7a"}
MARKER = {("Stress-based", "relaxed"): "o", ("Baseline-based", "relaxed"): "o", ("Stress-based", "strict"): "^", ("Baseline-based", "strict"): "^", ("High-water mark", "strict"): "s"}
INTERFERENCES = ("none", "memory")
TABLES, FIGURES = HERE / "tables", HERE / "figures"
TABLES.mkdir(exist_ok=True); FIGURES.mkdir(exist_ok=True)


def budget_rows(path):
    b = pd.read_csv(path)
    return b.rename(columns={"variant": "route"}) if "variant" in b.columns else b


def folders_of(d, scenario, route, level):
    lv = "strict" if route in ("hwm", "variant3") else level
    return [d / "results" / scenario / route / f"{lv}_{i}" for i in INTERFERENCES]


def has_runs(folders):
    return any(list(f.glob("instance*.csv")) for f in folders)


def run_metrics(df, Q_online, Q_final, p, m, k, period_ms):
    """one run against the final budget. Guarantee: p and (m,k) on C > Q_final of the executed jobs, as in the derivation.
    Consequence: lost releases (R > D or skipped); when Q_final differs from the budget run online, the bursts of lost releases that held an
    overrun at Q_online but none at Q_final are removed (those jobs would have met the deadline), the others stay"""
    cpu = df.cpu_ns / 1e6                                              # NaN for skipped jobs
    c = cpu[df.skipped == 0].to_numpy()
    skip = (df.skipped == 1).to_numpy()
    bad = skip | (df.deadline_met == 0).to_numpy()
    if abs(Q_final - Q_online) < 1e-9:
        bad_f = bad
    else:
        om_on = overrun_misses(bad, (cpu > Q_online).to_numpy())
        om = overrun_misses(bad, (cpu > Q_final).to_numpy())
        bad_f = bad & ~(om_on & ~om)
    over = c > Q_final
    c_hat = max(np.quantile(c, 1 - p), count_budget(c, m, k, EPS))
    return dict(rate_ratio=float(over.mean()) / p, window_ratio=(window_violation(over, m, k) if len(over) >= k else 0.0) / EPS,
                lost_window_ratio=window_violation(bad_f, m, k) / EPS, miss=float((bad_f & ~skip).mean()), skip=float((bad_f & skip).mean()), lost=float(bad_f.mean()),
                stalls=stalls((df.wait_ns / 1e6).to_numpy(), bad, period_ms), over_budget=Q_final / c_hat - 1)


def cell_metrics(label, scenario, variant, level, folders, Q_online, Q_final, p, m, k, period_ms):
    runs = [run_metrics(read_run(f), Q_online, Q_final, p, m, k, period_ms) for d in folders for f in sorted(d.glob("instance*.csv"))]
    r = pd.DataFrame(runs)
    return dict(workload=label, deploy=scenario.replace("_core", ""), variant=variant, level=level, Q_ms=Q_final, Q_over_P=Q_final / period_ms, dagger=abs(Q_final - Q_online) > 1e-9,
                rate_ratio=r.rate_ratio.max(), window_ratio=r.window_ratio.max(), lost_window_ratio=r.lost_window_ratio.max(), miss=r.miss.max(), skip=r.skip.max(), lost=r.lost.max(), stalls=int(r.stalls.sum()),
                over_budget=r.over_budget.min(), runs=len(r))


# ---- collect the cells ----
cells = []
for label, folder, period_ms in WORKLOADS:
    base = RQ2 / folder / "validation_p4"
    iters = sorted(base.glob("iter*"), key=lambda d: int(d.name[4:]))
    latest, online = {}, {}                                            # (scenario, route, level): newest budget row / (budget run online, its folders)
    for d in iters:
        if not (d / "budgets.csv").exists():
            continue
        for b in budget_rows(d / "budgets.csv").itertuples():
            key = (b.scenario, VARIANT[b.route], b.level)
            latest[key] = b
            fl = folders_of(d, b.scenario, b.route, b.level)
            if has_runs(fl):
                online[key] = (b, fl)
    # monotonicity rule on the final budgets: a stricter level never below a looser one
    final = {}
    for (scen, var, lvl), b in latest.items():
        if var == "High-water mark":
            continue
        final[(scen, var, lvl)] = b.runtime_us / 1000
    for (scen, var, lvl) in list(final):
        if lvl == "strict":
            final[(scen, var, "strict")] = max(final[(scen, var, "strict")], final[(scen, var, "relaxed")])
    for scen in sorted({k[0] for k in final}):
        for var in VARIANTS[:2]:
            assert final[(scen, var, "strict")] >= final[(scen, var, "relaxed")], (label, scen, var)
    for (scen, var, lvl), (b, fl) in sorted(online.items()):
        if var == "High-water mark":
            if lvl != "strict":
                continue                                               # one run, judged on the strict level
            Q = b.runtime_us / 1000
            cells.append(cell_metrics(label, scen, var, "strict", fl, Q, Q, b.p, b.m, b.k, b.period_us / 1000))
        else:
            cells.append(cell_metrics(label, scen, var, lvl, fl, b.runtime_us / 1000, final[(scen, var, lvl)], b.p, b.m, b.k, b.period_us / 1000))
    # high-water mark of workloads 1-3: earlier validation (validation_p2), one budget for every tolerance, judged on the strict level
    if not any(c["workload"] == label and c["variant"] == "High-water mark" for c in cells):
        hb = RQ2 / folder / "validation_p2" / "iter0" / "budgets.csv"
        strict = latest[next(k for k in latest if k[2] == "strict")]
        if hb.exists():
            for b in pd.read_csv(hb).query("route == 'hwm'").itertuples():
                fl = [RQ2 / folder / "validation_p2" / "iter0" / "results" / b.scenario / "hwm" / f"all_{i}" for i in INTERFERENCES]
                if has_runs(fl):
                    Q = b.runtime_us / 1000
                    cells.append(cell_metrics(label, b.scenario, "High-water mark", "strict", fl, Q, Q, strict.p, strict.m, strict.k, b.period_us / 1000))

T = pd.DataFrame(cells)
T["deploy"] = pd.Categorical(T.deploy, ["single", "multi"])
T["within"] = (T.rate_ratio <= 1) & (T.window_ratio <= 1)
T.to_csv(HERE / "rq2_validation_cells.csv", index=False)
assert not T.duplicated(["workload", "deploy", "variant", "level"]).any()


def get(label, deploy, variant, level):
    s = T[(T.workload == label) & (T.deploy == deploy) & (T.variant == variant) & (T.level == level)]
    return s.iloc[0] if len(s) else None


# ---- number formats ----
def sig2(x):
    """ratios with two decimals; an exact zero is written 0"""
    return "0" if x == 0 else f"{x:.2f}"


def ratio_cell(r):
    if r is None:
        return "--"
    parts = [f"\\textbf{{{sig2(v)}}}" if v > 1 else sig2(v) for v in (r.rate_ratio, r.window_ratio)]
    return " / ".join(parts) + ("$^\\dagger$" if r.dagger else "")


# ---- Output 1: soundness table ----
cols = [("Stress-based", "relaxed"), ("Stress-based", "strict"), ("Baseline-based", "relaxed"), ("Baseline-based", "strict"), ("High-water mark", "strict")]
lines = [r"\begin{table}[ht]", r"\centering", r"\small", r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{llccccc}", r"\toprule",
         r"Workload ($P$) & Deploy. & \multicolumn{2}{c}{Stress-based} & \multicolumn{2}{c}{Baseline-based} & High-water mark \\",
         r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-7}", r" &  & relaxed & strict & relaxed & strict &  \\", r"\midrule"]
prev = None
for label, deploy in ORDER:
    if prev is not None and label != prev:
        lines.append(r"\midrule")
    first = "" if label == prev else f"{label} ($P={PERIOD_LABEL[label]}$\\,ms)"
    lines.append(f"{first} & {deploy} & " + " & ".join(ratio_cell(get(label, deploy, v, l)) for v, l in cols) + r" \\")
    prev = label
caption = (r"Soundness of the budgets in the online validation. Each cell gives the observed overrun rate relative to its tolerance $p$, and the share of sliding windows of $k$ jobs with more than $k-m$ overruns ($C>Q$) "
           r"relative to $\varepsilon = 1\%$ (worst run of the cell). Values $\le 1$ meet the requirement; values above 1 are in bold. Relaxed: $p = 10^{-2}$, at most two overruns per second; "
           r"strict: $p = 10^{-3}$, at most one overrun per second. Both requirements are judged on $C>Q$, as in the derivation; their consequence on the releases is in Table~\\ref{tab:rq2-lost}. The high-water mark is judged against the strict level. $^\dagger$ Budget raised by the monotonicity rule; evaluated by replaying the online trace.")
lines += [r"\bottomrule", r"\end{tabular}}", r"\caption{" + caption + "}", r"\label{tab:rq2-soundness}", r"\end{table}"]
(TABLES / "rq2_soundness.tex").write_text("\n".join(lines) + "\n")

# ---- Output 1b: lost-release table (consequence of the budgets, same layout as the soundness table) ----
def pct3(x):
    """percent with two decimals; an exact zero is written 0, a positive value below 0.005% is written <0.01"""
    return "0" if x == 0 else ("<0.01" if 100 * x < 0.005 else f"{100 * x:.2f}")


def lost_cell(r):
    if r is None:
        return "--"
    return pct3(r.lost) + ("$^\\dagger$" if r.dagger else "")


ll = [r"\begin{table}[ht]", r"\centering", r"\small", r"\resizebox{\textwidth}{!}{%", r"\begin{tabular}{llccccc}", r"\toprule",
      r"Workload ($P$) & Deploy. & \multicolumn{2}{c}{Stress-based} & \multicolumn{2}{c}{Baseline-based} & High-water mark \\",
      r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-7}", r" &  & relaxed & strict & relaxed & strict &  \\", r"\midrule"]
prev = None
for label, deploy in ORDER:
    if prev is not None and label != prev:
        ll.append(r"\midrule")
    first = "" if label == prev else f"{label} ($P={PERIOD_LABEL[label]}$\\,ms)"
    ll.append(f"{first} & {deploy} & " + " & ".join(lost_cell(get(label, deploy, v, l)) for v, l in cols) + r" \\")
    prev = label
lcap = (r"Lost releases in the online validation, the consequence of the budgets of Table~\ref{tab:rq2-soundness}. Each cell gives the miss rate: the share of releases lost, that is with a deadline miss ($R>D$) or skipped, "
        r"in percent of all releases (worst run of the cell); it does not depend on $p$ or $(m,k)$. These are reported, not judged: the tolerance $p$ bounds $P(C>Q)$ only, and misses caused by the platform "
        r"(stalls, late starts) are included. $^\dagger$ Budget raised by the monotonicity rule; the bursts of lost releases that held an overrun only at the online budget are removed from the replay.")
ll += [r"\bottomrule", r"\end{tabular}}", r"\caption{" + lcap + "}", r"\label{tab:rq2-lost}", r"\end{table}"]
(TABLES / "rq2_lost.tex").write_text("\n".join(ll) + "\n")

# ---- Output 2: figure (two panels: relaxed on top, strict below) ----
plt.rcParams.update({"font.size": 9, "font.family": "serif", "svg.fonttype": "path"})
fig, axes = plt.subplots(2, 1, figsize=(6.5, 5.2), sharex=True, gridspec_kw=dict(height_ratios=[0.62, 1], hspace=0.12))
PANELS = [("relaxed", -12, 55, "relaxed"), ("strict", -70, 70, "strict")]
BAR_W = 0.26
for ax, (level, lo, hi, _) in zip(axes, PANELS):
    for gi, (label, deploy) in enumerate(ORDER):
        present = [(v, get(label, deploy, v, level)) for v in VARIANTS]
        present = [(v, r) for v, r in present if r is not None]
        for i, (v, r) in enumerate(present):
            x = gi + (i - (len(present) - 1) / 2) * (BAR_W + 0.02)
            val = 100 * r.over_budget
            top = min(max(val, lo), hi)
            ax.bar(x, top, width=BAR_W, color=COLOR[v], edgecolor="white", linewidth=0.6, zorder=3)
            txt = f"{val:+.0f}" if round(val) != 0 else "0"
            if val > hi:
                ax.annotate(f"{txt} \u2191", (x, hi), xytext=(0, 2), textcoords="offset points", ha="center", va="bottom", fontsize=7, clip_on=False)
            elif val >= 0:
                ax.annotate(txt, (x, val), xytext=(0, 2), textcoords="offset points", ha="center", va="bottom", fontsize=7)
            else:
                ax.annotate(txt, (x, val), xytext=(0, -2), textcoords="offset points", ha="center", va="top", fontsize=7)
    ax.set_ylim(lo, hi)
    ax.axhline(0, color="black", lw=0.8, zorder=4)
    ax.axhspan(lo, 0, color="#f4c7c3", alpha=0.35, zorder=1)
    ax.text(-0.46, lo * 0.5 if level == "strict" else lo * 0.5, "budget too small", ha="left", va="center", fontsize=7.5, color="#a33", style="italic", zorder=2)
    ax.set_ylabel(f"Over-budget [%] ({level})")
    ax.grid(axis="y", color="#dddddd", lw=0.6, zorder=0); ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.set_xlim(-0.55, len(ORDER) - 0.45)
axes[0].set_yticks([0, 20, 40]); axes[1].set_yticks([-60, -40, -20, 0, 20, 40, 60])
axes[1].set_xticks(range(len(ORDER))); axes[1].set_xticklabels([f"{a}\n{b} core" for a, b in ORDER], fontsize=8)
handles = [matplotlib.patches.Patch(facecolor=COLOR[v], edgecolor="white", label=v) for v in VARIANTS] + [matplotlib.patches.Patch(facecolor="none", edgecolor="none", label=" ")]
for w in ("Video", "Segmentation", "LiDAR", "Audio"):
    handles.append(matplotlib.patches.Patch(facecolor="none", edgecolor="none", label=f"{w}: $P$ = {PERIOD_LABEL[w]} ms"))
order = [handles[i] for i in (0, 4, 1, 5, 2, 6, 3, 7)]                 # column by column: variant above, period below
fig.legend(handles=order, loc="upper center", ncol=4, frameon=True, fancybox=False, edgecolor="#888888", fontsize=8, handlelength=1.4, handletextpad=0.5, columnspacing=1.2,
           bbox_to_anchor=(0.5, 1.0), borderpad=0.5)
fig.subplots_adjust(top=0.87, left=0.11, right=0.98, bottom=0.11)
fig.savefig(FIGURES / "rq2_overbudget.pdf"); fig.savefig(FIGURES / "rq2_overbudget.svg"); fig.savefig(FIGURES / "rq2_overbudget.png", dpi=200)
(FIGURES / "rq2_overbudget.tex").write_text("\n".join([
    r"\begin{figure}[ht]", r"\centering", r"\includegraphics[width=\textwidth]{figures/rq2_overbudget.pdf}",
    r"\caption{Over-budget of each budget in the online validation: the reserved budget relative to the smallest budget that would just have met both requirements on the same run "
    r"(worst run per cell). Top: relaxed level, bottom: strict level; the high-water mark is shown in the strict panel only. Values below zero are budgets that were too small; "
    r"bars beyond $+70\%$ are cut and their value is written above.}", r"\label{fig:rq2-overbudget}", r"\end{figure}"]) + "\n")

# ---- Output 3: appendix longtable ----
def pct(x):
    return f"{100 * x:+.0f}\\%"


rows = []
for label, deploy in ORDER:
    for v, l in [("Stress-based", "relaxed"), ("Stress-based", "strict"), ("Baseline-based", "relaxed"), ("Baseline-based", "strict"), ("High-water mark", "strict")]:
        r = get(label, deploy, v, l)
        if r is None:
            continue
        fmt = lambda x: f"\\textbf{{{sig2(x)}}}" if x > 1 else sig2(x)
        rows.append((label, deploy, v, "all (strict)" if v == "High-water mark" else l, f"{r.Q_ms:.2f}{'$^\\dagger$' if r.dagger else ''} / {r.Q_over_P:.2f}",
                     fmt(r.rate_ratio), fmt(r.window_ratio), pct3(r.miss), pct3(r.skip), fmt(r.lost_window_ratio), str(r.stalls), pct(r.over_budget), str(r.runs)))
head = ["Workload", "Deploy.", "Variant", "Level", "$Q$ [ms] / $Q/P$", "rate ratio", "window ratio", "miss [\\%]", "skipped [\\%]", "lost-window ratio", "stalls", "over-budget", "runs"]
ncol = len(head)
lt = [r"\begin{longtable}{lllllrrrrrrrr}",
      r"\caption{Online validation of the budgets, one row per workload, deployment, variant and level (worst run of the cell over instances and interference conditions). "
      r"Rate ratio: observed overrun rate relative to $p$. Window ratio: share of sliding windows of $k$ jobs (one second) with more than $k-m$ overruns ($C>Q$) relative to $\varepsilon=1\%$ (both requirements are judged on $C>Q$, as in the derivation). "
      r"Miss, skipped: share of releases with $R>D$ and share skipped; lost-window ratio: share of windows with more than $k-m$ lost releases ($R>D$ or skipped) relative to $\varepsilon$; "
      r"stalls: platform stalls and late starts, which the budget does not control. These four are reported, not judged. Over-budget: reserved budget relative to the smallest budget that would just have met both "
      r"requirements on the run; negative means too small. The high-water mark is judged against the strict level. $^\dagger$ Budget raised by the monotonicity rule, evaluated by replaying "
      r"the online trace.} \label{tab:rq2-validation-full} \\",
      r"\toprule", " & ".join(head) + r" \\", r"\midrule", r"\endfirsthead",
      r"\toprule", " & ".join(head) + r" \\", r"\midrule", r"\endhead",
      r"\midrule \multicolumn{" + str(ncol) + r"}{r}{\emph{continued on the next page}} \\ \endfoot", r"\bottomrule", r"\endlastfoot"]
prev = None
for row in rows:
    g = (row[0], row[1])
    if prev is not None and g != prev:
        lt.append(r"\midrule")
    shown = list(row)
    if g == prev:
        shown[0] = shown[1] = ""
    lt.append(" & ".join(shown) + r" \\")
    prev = g
lt.append(r"\end{longtable}")
(TABLES / "rq2_validation_full.tex").write_text("\n".join(lt) + "\n")

# ---- checks and console summary ----
assert len(rows) == len(T), "table, figure and appendix must show the same cells"
n_fig = sum(1 for label, deploy in ORDER for v, l in [(v, l) for v in VARIANTS for l in LEVELS] if get(label, deploy, v, l) is not None)
assert n_fig == len(T) == len(rows)
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
print(T.drop(columns=["within"]).round(4).to_string(index=False))
print(f"\ncells within both requirements: {int(T.within.sum())} of {len(T)}")
bad = T[~T.within]
print("failing cells:" if len(bad) else "failing cells: none")
for r in bad.itertuples():
    print(f"  {r.workload} {r.deploy} {r.variant} {r.level}: rate_ratio {r.rate_ratio:.2g}, window_ratio {r.window_ratio:.2g}")
print("daggers (budget raised by the monotonicity rule):", [f"{r.workload} {r.deploy} {r.variant} {r.level}" for r in T[T.dagger].itertuples()])
print("\nover_budget range per variant:")
for v in VARIANTS:
    s = T[T.variant == v].over_budget
    print(f"  {v}: {100 * s.min():+.0f}% to {100 * s.max():+.0f}% ({len(s)} cells)")
print(f"\nwritten {TABLES / 'rq2_soundness.tex'}, {TABLES / 'rq2_lost.tex'}, {TABLES / 'rq2_validation_full.tex'}, {FIGURES / 'rq2_overbudget.pdf'} (+ svg, png, tex), {HERE / 'rq2_validation_cells.csv'}")
