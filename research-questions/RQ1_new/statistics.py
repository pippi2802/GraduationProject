import pandas as pd
import numpy as np
from pathlib import Path


# -----------------------------
# CONFIG
# -----------------------------

BASE_DIR = Path("results")
STAT_DIR = Path("statistics")

MODELS = ["model1", "model2"]
MODES = ["soft", "tight"]



# -----------------------------
# LOAD DATA
# -----------------------------

def load_jobs(path):

    df = pd.read_csv(path, comment="#")

    df.columns = df.columns.str.strip()

    df["C"] = df["C_cputime_us"]
    df["R"] = df["R_wall_us"]
    df["delay"] = df["delay_us"]

    df["compute_ratio"] = df["C"] / df["R"]
    df["delay_ratio"] = df["delay"] / df["R"]

    return df



# -----------------------------
# STATISTICS
# -----------------------------

def describe_column(series):

    return {

        "count": len(series),

        "mean": series.mean(),

        "std": series.std(),

        "min": series.min(),

        "p50": np.percentile(series, 50),

        "p90": np.percentile(series, 90),

        "p95": np.percentile(series, 95),

        "p99": np.percentile(series, 99),

        "max": series.max()
    }



def compute_statistics(df, model, mode, U):

    result = {

        "model": model,
        "mode": mode,
        "utilization": U,

        "jobs": len(df),

        "deadline_miss_rate":
            df["deadline_miss"].mean()
    }


    metrics = [

        "C",
        "R",
        "delay",
        "tardiness_us",
        "compute_ratio",
        "delay_ratio"
    ]


    for metric in metrics:

        if metric in df.columns:

            stats = describe_column(df[metric])

            for name, value in stats.items():

                result[f"{metric}_{name}"] = value


    return result



# -----------------------------
# MAIN COLLECTION
# -----------------------------

def collect_statistics():

    all_results = []


    for model in MODELS:

        for mode in MODES:

            base = BASE_DIR / model / mode

            if not base.exists():
                continue


            for u_dir in sorted(base.glob("U*")):

                try:
                    U = float(
                        u_dir.name.replace("U", "")
                    )

                except:
                    continue


                jobs_file = u_dir / "jobs.csv"


                if not jobs_file.exists():
                    continue


                print(
                    f"Processing {model}/{mode}/U{U}"
                )


                df = load_jobs(jobs_file)


                stats = compute_statistics(
                    df,
                    model,
                    mode,
                    U
                )


                all_results.append(stats)


    return pd.DataFrame(all_results)



# -----------------------------
# SAVE RESULTS
# -----------------------------

if __name__ == "__main__":


    stats = collect_statistics()


    for model in MODELS:

        for mode in MODES:

            subset = stats[
                (stats["model"] == model)
                &
                (stats["mode"] == mode)
            ]


            if subset.empty:
                continue


            out_dir = (
                STAT_DIR /
                model /
                mode
            )

            out_dir.mkdir(
                parents=True,
                exist_ok=True
            )


            # all utilization points
            subset.to_csv(
                out_dir / "per_utilization.csv",
                index=False
            )


            # aggregated over all utilization points
            numeric = (
                subset
                .select_dtypes(include=np.number)
                .describe()
                .T
            )


            numeric.to_csv(
                out_dir / "summary.csv"
            )


    print("Statistics saved in:", STAT_DIR)