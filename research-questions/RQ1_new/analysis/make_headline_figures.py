#!/usr/bin/env python3
"""
make_headline_figures.py — the two headline RQ1 figures, built directly from
analysis/<model>_pooled/{summary,provisioning_table}.csv.

  1. U_safe_collapse.png   grouped bar chart: p99 vs p999 U_safe, per model/scale.
                           This is the single clearest number in the whole
                           dataset (0.94 -> 0.20 -> 0.10) and it currently only
                           lives in a CSV -- this makes the collapse visible.
  2. miss_rate_vs_U.png    model1 vs model2 miss rate, overlaid, one panel per
                           scale. Replaces trying to compare two separate
                           per-model figures by eye.

  3. <model>_round_stability.csv / _round_stability.png
                           per-round (session) breakdown, NOT pooled -- median C,
                           cv, and miss rate for every (round, scale, U) cell,
                           ordered by when that round actually ran (earliest
                           jobs.csv mtime in the round). Stability check for
                           the pooling decision, not a time-of-day study.
  4. master_comparison_table.csv       one row per pooled model/arm.
  5. main_effects_interaction_table.csv Claim2's 2x2 decomposition (call with
                                         your real arm directory names once
                                         model3's 4 arms are pooled).
  6. budget_overrun_table.csv          observed C vs calibrated-expected C vs
                                        Q, per cell -- systematized version of
                                        the by-hand model2/model3-w2 check.
  7. job_level_mechanism_table.csv     dispatch_latency/preempt/ctxt-switch
                                        means per condition, from raw jobs.csv.

Usage (run from RQ1_new/):
    python3 analysis/make_headline_figures.py
Writes figures into analysis/figures_headline/, tables into analysis/.
"""
import glob
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
OUT = HERE / "figures_headline"
OUT.mkdir(exist_ok=True)

MODELS = ["model1_pooled", "model2_pooled"]
LABELS = {"model1_pooled": "model1 (isolated)", "model2_pooled": "model2 (SMT-sibling, reserved neighbour)"}
COLORS = {"model1_pooled": "#1f77b4", "model2_pooled": "#d62728"}


def fig_u_safe_collapse():
    rows = []
    for m in MODELS:
        p = HERE / m / "provisioning_table.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p)
        df["model"] = m
        rows.append(df)
    prov = pd.concat(rows, ignore_index=True)

    scales = sorted(prov["scale"].unique())
    fig, axes = plt.subplots(1, len(scales), figsize=(5.5 * len(scales), 4.5), sharey=True)
    if len(scales) == 1:
        axes = [axes]

    for ax, scale in zip(axes, scales):
        sub = prov[prov["scale"] == scale]
        x = range(len(MODELS))
        width = 0.35
        p99 = [sub[(sub.model == m) & (sub.confidence == "p99")]["U_safe"].values[0]
               if not sub[(sub.model == m) & (sub.confidence == "p99")].empty else 0 for m in MODELS]
        p999 = [sub[(sub.model == m) & (sub.confidence == "p999")]["U_safe"].values[0]
                if not sub[(sub.model == m) & (sub.confidence == "p999")].empty else 0 for m in MODELS]
        ax.bar([i - width / 2 for i in x], p99, width, label="p99", color="#2ca02c")
        ax.bar([i + width / 2 for i in x], p999, width, label="p999", color="#9467bd")
        for i, v in enumerate(p99):
            ax.text(i - width / 2, v + 0.02, f"{v:.2f}", ha="center", fontsize=9)
        for i, v in enumerate(p999):
            ax.text(i + width / 2, v + 0.02, f"{v:.2f}", ha="center", fontsize=9)
        ax.set_xticks(list(x))
        ax.set_xticklabels([LABELS[m].replace(" (", "\n(") for m in MODELS], fontsize=9)
        ax.set_title(f"{scale} scale")
        ax.set_ylim(0, 1.05)
        ax.axhline(1.0, color="k", ls=":", lw=1, alpha=0.5)
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("U_safe (max utilization meeting the confidence target)")
    axes[-1].legend(loc="upper right")
    fig.suptitle("Safe provisioning ceiling collapses once a reserved SMT-sibling neighbour is added", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "U_safe_collapse.png", dpi=150)
    print(f"[fig] wrote {OUT / 'U_safe_collapse.png'}")


def fig_miss_rate_vs_u():
    rows = []
    for m in MODELS:
        p = HERE / m / "summary.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p)
        df["model"] = m
        rows.append(df)
    summ = pd.concat(rows, ignore_index=True)

    scales = sorted(summ["scale"].unique())
    fig, axes = plt.subplots(1, len(scales), figsize=(6 * len(scales), 4.5), sharey=True)
    if len(scales) == 1:
        axes = [axes]

    for ax, scale in zip(axes, scales):
        for m in MODELS:
            sub = summ[(summ.model == m) & (summ.scale == scale)].sort_values("U")
            ax.plot(sub["U"], sub["miss_rate"], marker="o", label=LABELS[m], color=COLORS[m], lw=2)
        ax.set_xlabel("target utilization U")
        ax.set_title(f"{scale} scale")
        ax.set_ylim(-0.03, 1.03)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("deadline miss rate")
    axes[0].legend(loc="upper left", fontsize=9)
    fig.suptitle("Deadline miss rate vs utilization: isolated vs SMT-sibling contention", fontsize=11)
    fig.tight_layout()
    fig.savefig(OUT / "miss_rate_vs_U.png", dpi=150)
    print(f"[fig] wrote {OUT / 'miss_rate_vs_U.png'}")


def round_stability(model):
    """Per-round (not pooled) breakdown for one base model name, e.g. "model1".
    Finds every results/<model>_round*/ directory, reads each cell's jobs.csv
    directly (not the pooled summary), and orders rounds by the earliest
    jobs.csv mtime found in that round -- a proxy for when the session ran.
    """
    round_dirs = sorted(glob.glob(str(RESULTS / f"{model}_round*")))
    if not round_dirs:
        print(f"[round-stability] no results/{model}_round* directories found -- skipping {model}")
        return None

    rows = []
    for rd in round_dirs:
        rd = Path(rd)
        round_label = rd.name.replace(f"{model}_", "")
        jobs_files = list(rd.glob("*/U*/jobs.csv"))
        if not jobs_files:
            continue
        round_time = datetime.fromtimestamp(min(f.stat().st_mtime for f in jobs_files))
        for f in jobs_files:
            scale = f.parent.parent.name
            u = float(f.parent.name[1:])
            try:
                df = pd.read_csv(f, comment="#")
            except Exception:
                continue
            if df.empty or "C_cputime_us" not in df:
                continue
            c = df["C_cputime_us"].dropna()
            rows.append({
                "round": round_label, "round_time": round_time, "scale": scale, "U": u,
                "n": len(df), "median_C": c.median(),
                "cv": (c.std() / c.median()) if c.median() else float("nan"),
                "miss_rate": df["deadline_miss"].mean() if "deadline_miss" in df else float("nan"),
            })
    if not rows:
        print(f"[round-stability] found round dirs for {model} but no readable jobs.csv -- skipping")
        return None

    out = pd.DataFrame(rows).sort_values(["round_time", "scale", "U"])
    csv_path = HERE / f"{model}_round_stability.csv"
    out.to_csv(csv_path, index=False)
    print(f"[round-stability] wrote {csv_path}")

    # order rounds chronologically for the x-axis, label with round tag + date
    order = (out[["round", "round_time"]].drop_duplicates().sort_values("round_time"))
    order["label"] = order["round"] + "\n" + order["round_time"].dt.strftime("%m-%d %H:%M")
    label_map = dict(zip(order["round"], order["label"]))
    out["round_x"] = out["round"].map({r: i for i, r in enumerate(order["round"])})

    scales = sorted(out["scale"].unique())
    fig, axes = plt.subplots(2, len(scales), figsize=(5.5 * len(scales), 7), sharex=True)
    if len(scales) == 1:
        axes = axes.reshape(2, 1)

    for col, scale in enumerate(scales):
        sub = out[out.scale == scale]
        for u in sorted(sub["U"].unique()):
            line = sub[sub.U == u].sort_values("round_x")
            axes[0, col].plot(line["round_x"], line["median_C"], marker="o", lw=1.2, ms=4, label=f"U={u:g}")
            axes[1, col].plot(line["round_x"], line["miss_rate"], marker="o", lw=1.2, ms=4)
        axes[0, col].set_title(f"{scale} scale")
        axes[0, col].grid(alpha=0.3)
        axes[1, col].grid(alpha=0.3)
        axes[1, col].set_xticks(list(order["round"].map({r: i for i, r in enumerate(order["round"])})))
        axes[1, col].set_xticklabels(order["label"], fontsize=8, rotation=0)

    axes[0, 0].set_ylabel("median C_cputime_us")
    axes[1, 0].set_ylabel("miss rate")
    axes[0, -1].legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8, title="U")
    fig.suptitle(f"{model}: per-round stability (not pooled) -- do sessions agree?", fontsize=11)
    fig.tight_layout()
    fig_path = OUT / f"{model}_round_stability.png"
    fig.savefig(fig_path, dpi=150)
    print(f"[round-stability] wrote {fig_path}")
    return out


def master_comparison_table():
    """One row per pooled model/arm: miss rate at the lowest tested U (usually
    0.1, present almost everywhere so it's the one comparable point across
    different U-grids), U_safe at p99/p999, and the p99 U_safe ratio against
    model1 (if present) as a plain-language "how much headroom did you lose"
    number. Auto-discovers every analysis/*_pooled directory -- add new arms
    by pooling them the same way, no code change needed here.
    """
    pooled_dirs = sorted(HERE.glob("*_pooled"))
    rows = []
    model1_u_safe = {}  # scale -> p99 U_safe, for the ratio column

    for d in pooled_dirs:
        summ_p, prov_p = d / "summary.csv", d / "provisioning_table.csv"
        if not summ_p.exists() or not prov_p.exists():
            continue
        summ = pd.read_csv(summ_p)
        prov = pd.read_csv(prov_p)
        for scale in sorted(summ["scale"].unique()):
            s = summ[summ.scale == scale]
            u_min = s["U"].min()
            miss_at_umin = s[s.U == u_min]["miss_rate"].values[0]
            p = prov[prov.scale == scale]
            u_safe_p99 = p[p.confidence == "p99"]["U_safe"].values
            u_safe_p999 = p[p.confidence == "p999"]["U_safe"].values
            u_safe_p99 = u_safe_p99[0] if len(u_safe_p99) else float("nan")
            u_safe_p999 = u_safe_p999[0] if len(u_safe_p999) else float("nan")
            if d.name == "model1_pooled":
                model1_u_safe[scale] = u_safe_p99
            rows.append({
                "model": d.name, "scale": scale, "U_min_tested": u_min,
                "miss_rate_at_U_min": miss_at_umin,
                "U_safe_p99": u_safe_p99, "U_safe_p999": u_safe_p999,
            })

    out = pd.DataFrame(rows)
    out["U_safe_p99_vs_model1"] = out.apply(
        lambda r: (r["U_safe_p99"] / model1_u_safe[r["scale"]])
        if r["scale"] in model1_u_safe and model1_u_safe[r["scale"]] else float("nan"), axis=1)
    csv_path = HERE / "master_comparison_table.csv"
    out.to_csv(csv_path, index=False)
    print(f"[master-comparison] wrote {csv_path}")
    return out


def main_effects_interaction_table(arms):
    """Claim2's 2x2 decomposition. `arms` = dict mapping
    {"sib_cfs": <analysis dir name>, "sib_res": ..., "phys_cfs": ..., "phys_res": ...}
    -- pass whatever your actual pooled directory names are, e.g.
    {"sib_cfs": "model3_sib_cfs_pooled", "sib_res": "model3-w2_sib_res_pooled",
     "phys_cfs": "model3-w3_phys_cfs_pooled", "phys_res": "model3-w4_phys_res_pooled"}.
    Computed directly from each arm's summary.csv (mean miss_rate over the U
    values common to all four), not from comparisons.csv, so it doesn't
    depend on having already run `result.py compare` on the exact right pairs.
    """
    needed = ["sib_cfs", "sib_res", "phys_cfs", "phys_res"]
    missing_keys = [k for k in needed if k not in arms]
    if missing_keys:
        print(f"[main-effects] missing arm mapping for {missing_keys} -- skipping")
        return None

    summaries = {}
    for k, dirname in arms.items():
        p = HERE / dirname / "summary.csv"
        if not p.exists():
            print(f"[main-effects] {p} not found -- skipping table")
            return None
        summaries[k] = pd.read_csv(p)

    rows = []
    for scale in sorted(set.intersection(*[set(df["scale"]) for df in summaries.values()])):
        common_u = set.intersection(*[set(summaries[k][summaries[k].scale == scale]["U"]) for k in needed])
        if not common_u:
            print(f"[main-effects] no common U values across all 4 arms for scale={scale} -- skipping")
            continue
        mean_miss = {}
        for k in needed:
            df = summaries[k]
            sub = df[(df.scale == scale) & (df.U.isin(common_u))]
            mean_miss[k] = sub["miss_rate"].mean()

        pair_effect_cfs = mean_miss["sib_cfs"] - mean_miss["phys_cfs"]
        pair_effect_res = mean_miss["sib_res"] - mean_miss["phys_res"]
        comp_effect_sib = mean_miss["sib_res"] - mean_miss["sib_cfs"]
        comp_effect_phys = mean_miss["phys_res"] - mean_miss["phys_cfs"]
        interaction = pair_effect_res - pair_effect_cfs  # equivalently comp_effect_sib - comp_effect_phys

        rows.append({
            "scale": scale, "common_U_values": sorted(common_u),
            "mean_miss_sib_cfs": mean_miss["sib_cfs"], "mean_miss_sib_res": mean_miss["sib_res"],
            "mean_miss_phys_cfs": mean_miss["phys_cfs"], "mean_miss_phys_res": mean_miss["phys_res"],
            "PAIR_TYPE_effect_unreserved_competitor": pair_effect_cfs,
            "PAIR_TYPE_effect_reserved_competitor": pair_effect_res,
            "COMPETITOR_TYPE_effect_sibling": comp_effect_sib,
            "COMPETITOR_TYPE_effect_physical": comp_effect_phys,
            "interaction": interaction,
        })

    out = pd.DataFrame(rows)
    csv_path = HERE / "main_effects_interaction_table.csv"
    out.to_csv(csv_path, index=False)
    print(f"[main-effects] wrote {csv_path}")
    return out


def budget_overrun_table(entries):
    """`entries` = list of (label, analysis_dir_name, config_model_name), e.g.
    [("model1", "model1_pooled", "model1"), ("model2", "model2_pooled", "model2")]
    -- config_model_name is whichever models/<name>/config.yaml holds the real
    headroom_frac and scales for that arm (base model, not the _pooled/_roundN
    suffix). Systematizes the by-hand C-vs-Q calculation from model2/model3-w2:
    observed median C (already in summary.csv) vs the calibration TARGET
    (headroom_frac * Q) vs the actual budget Q itself.
    """
    rows = []
    for label, analysis_dir, config_model in entries:
        cfg_path = HERE.parent / "models" / config_model / "config.yaml"
        summ_path = HERE / analysis_dir / "summary.csv"
        if not cfg_path.exists() or not summ_path.exists():
            print(f"[budget-overrun] missing {cfg_path} or {summ_path} -- skipping {label}")
            continue
        cfg = yaml.safe_load(cfg_path.read_text())
        headroom = cfg.get("headroom_frac", 0.7)
        scales = cfg["scales"]
        summ = pd.read_csv(summ_path)
        for _, r in summ.iterrows():
            period = scales.get(r["scale"])
            if period is None:
                continue
            Q = r["U"] * period
            expected_C = headroom * Q
            observed_C = r["C_p50"]
            rows.append({
                "label": label, "scale": r["scale"], "U": r["U"],
                "Q_budget_us": Q, "expected_C_us": expected_C, "observed_C_p50_us": observed_C,
                "inflation_vs_calibrated": observed_C / expected_C if expected_C else float("nan"),
                "pct_over_budget": (observed_C / Q - 1) * 100 if Q else float("nan"),
                "exceeds_budget": observed_C > Q,
            })
    out = pd.DataFrame(rows)
    csv_path = HERE / "budget_overrun_table.csv"
    out.to_csv(csv_path, index=False)
    print(f"[budget-overrun] wrote {csv_path}")
    return out


def job_level_mechanism_table(entries):
    """`entries` = list of (label, base_model_for_results_glob), e.g.
    [("model1", "model1"), ("model2", "model2")] -- globs
    results/<base_model>_round*/<scale>/U<u>/jobs.csv (raw, unpooled, since
    dispatch_latency_us/mid_job_preempt_us/nonvol_ctxt aren't in summary.csv)
    and reports mean C_cputime_us, dispatch_latency_us, mid_job_preempt_us,
    nonvol_ctxt per (label, scale, U), pooled across every round found. This
    is the systematic version of the manual burst-diagnosis check: which
    mechanism (execution inflation vs dispatch delay vs preemption) dominates,
    per condition, not just for one cell you happened to check by hand.
    """
    cols = ["C_cputime_us", "dispatch_latency_us", "mid_job_preempt_us", "nonvol_ctxt"]
    rows = []
    for label, base_model in entries:
        jobs_files = list(RESULTS.glob(f"{base_model}_round*/*/U*/jobs.csv"))
        if not jobs_files:
            print(f"[job-mechanism] no results/{base_model}_round*/.../jobs.csv found -- skipping {label}")
            continue
        by_cell = {}
        for f in jobs_files:
            scale = f.parent.parent.name
            u = float(f.parent.name[1:])
            try:
                df = pd.read_csv(f, comment="#")
            except Exception:
                continue
            present = [c for c in cols if c in df]
            if not present:
                continue
            by_cell.setdefault((scale, u), []).append(df[present])
        for (scale, u), dfs in by_cell.items():
            allrows = pd.concat(dfs, ignore_index=True)
            row = {"label": label, "scale": scale, "U": u, "n": len(allrows)}
            for c in cols:
                if c in allrows:
                    row[f"mean_{c}"] = allrows[c].mean()
            rows.append(row)
    out = pd.DataFrame(rows).sort_values(["label", "scale", "U"])
    csv_path = HERE / "job_level_mechanism_table.csv"
    out.to_csv(csv_path, index=False)
    print(f"[job-mechanism] wrote {csv_path}")
    return out


if __name__ == "__main__":
    fig_u_safe_collapse()
    fig_miss_rate_vs_u()
    for base_model in ["model1", "model2"]:
        round_stability(base_model)

    master_comparison_table()

    # EDIT these mappings to match your actual pooled directory names once
    # model3's arms are pooled -- left as an explicit, visible TODO rather
    # than guessing names that might not exist yet.
    # main_effects_interaction_table({
    #     "sib_cfs": "model3_sib_cfs_pooled", "sib_res": "model3-w2_sib_res_pooled",
    #     "phys_cfs": "model3-w3_phys_cfs_pooled", "phys_res": "model3-w4_phys_res_pooled",
    # })

    budget_overrun_table([
        ("model1", "model1_pooled", "model1"),
        ("model2", "model2_pooled", "model2"),
    ])

    job_level_mechanism_table([
        ("model1", "model1"),
        ("model2", "model2"),
    ])
