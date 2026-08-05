import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# -----------------------------
# CONFIG
# -----------------------------
BASE_DIR = Path("results")
PLOT_DIR = Path("plot")

MODELS = ["model1", "model2"]
MODES = ["soft", "tight"]


# -----------------------------
# LOAD DATA
# -----------------------------
def load_jobs(path):

    df = pd.read_csv(path, comment="#")

    # Clean column names
    df.columns = df.columns.str.strip()

    print("Columns:", df.columns.tolist())

    df["C"] = df["C_cputime_us"]
    df["R"] = df["R_wall_us"]
    df["delay"] = df["delay_us"]

    df["compute_ratio"] = df["C"] / df["R"]
    df["delay_ratio"] = df["delay"] / df["R"]

    return df


def collect_all():

    data = {}

    for model in MODELS:

        data[model] = {}

        for mode in MODES:

            base = BASE_DIR / model / mode

            if not base.exists():
                continue

            data[model][mode] = {}

            for u_dir in sorted(base.glob("U*")):

                try:
                    U = float(u_dir.name.replace("U", ""))
                except:
                    continue

                jobs_file = u_dir / "jobs.csv"

                if not jobs_file.exists():
                    continue

                df = load_jobs(jobs_file)

                data[model][mode][U] = df

    return data



# -----------------------------
# PLOTS
# -----------------------------

def save_C_R_distribution(df, title, save_path):

    plt.figure(figsize=(6,4))

    plt.hist(
        df["C"],
        bins=50,
        alpha=0.5,
        label="Execution time (C)"
    )

    plt.hist(
        df["R"],
        bins=50,
        alpha=0.5,
        label="Response time (R)"
    )

    plt.xlabel("Time (us)")
    plt.ylabel("Count")
    plt.title(title)

    plt.legend()
    plt.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()



def save_delay_distribution(df, title, save_path):

    plt.figure(figsize=(6,4))

    plt.hist(
        df["delay"],
        bins=50,
        alpha=0.7,
        label="Delay"
    )

    plt.xlabel("Delay (us)")
    plt.ylabel("Count")
    plt.title(title)

    plt.legend()
    plt.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()



def save_ratios(df, title, save_path):

    plt.figure(figsize=(6,4))

    plt.hist(
        df["compute_ratio"],
        bins=50,
        alpha=0.5,
        label="C/R"
    )

    plt.hist(
        df["delay_ratio"],
        bins=50,
        alpha=0.5,
        label="Delay/R"
    )

    plt.xlabel("Ratio")
    plt.ylabel("Count")
    plt.title(title)

    plt.legend()
    plt.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()



# -----------------------------
# METRICS
# -----------------------------

def summary_metrics(df):

    return {

        "miss_rate":
            df["deadline_miss"].mean(),

        "R_p99":
            np.percentile(df["R"], 99),

        "C_p99":
            np.percentile(df["C"], 99),

        "delay_p99":
            np.percentile(df["delay"], 99),

        "tardiness_p99":
            np.percentile(df["tardiness_us"], 99),

        "compute_ratio_mean":
            df["compute_ratio"].mean(),

        "delay_ratio_mean":
            df["delay_ratio"].mean()
    }



def save_vs_util(data_model, mode, metric, ylabel, save_dir):

    xs = []
    ys = []

    for U, df in sorted(data_model[mode].items()):

        metrics = summary_metrics(df)

        xs.append(U)
        ys.append(metrics[metric])


    plt.figure(figsize=(6,4))

    plt.plot(
        xs,
        ys,
        marker="o"
    )

    plt.xlabel("Utilization")
    plt.ylabel(ylabel)

    plt.title(
        f"{ylabel} vs Utilization ({mode})"
    )

    plt.grid(alpha=0.3)

    plt.tight_layout()


    filename = (
        ylabel
        .replace(" ", "_")
        .replace("(", "")
        .replace(")", "")
        .replace("/", "_")
    )

    plt.savefig(
        save_dir / f"{filename}.png",
        dpi=300
    )

    plt.close()



# -----------------------------
# MAIN
# -----------------------------

if __name__ == "__main__":

    data = collect_all()


    # Select utilization for distribution plots
    U_target = 0.6


    for model in data:

        for mode in data[model]:


            # plot/model/mode
            plot_dir = (
                PLOT_DIR /
                model /
                mode
            )

            plot_dir.mkdir(
                parents=True,
                exist_ok=True
            )


            # -----------------------------
            # Distributions
            # -----------------------------

            if U_target in data[model][mode]:

                df = data[model][mode][U_target]


                save_C_R_distribution(
                    df,
                    f"{model} {mode} U={U_target}: C and R",
                    plot_dir /
                    f"U{U_target}_C_R_distribution.png"
                )


                save_delay_distribution(
                    df,
                    f"{model} {mode} U={U_target}: Delay",
                    plot_dir /
                    f"U{U_target}_delay_distribution.png"
                )


                save_ratios(
                    df,
                    f"{model} {mode} U={U_target}: Ratios",
                    plot_dir /
                    f"U{U_target}_ratios_distribution.png"
                )



            # -----------------------------
            # Curves
            # -----------------------------

            metrics = [

                (
                    "R_p99",
                    "Response Time p99 (us)"
                ),

                (
                    "delay_p99",
                    "Delay p99 (us)"
                ),

                (
                    "miss_rate",
                    "Deadline Miss Rate"
                ),

                (
                    "compute_ratio_mean",
                    "Mean Compute Ratio"
                ),

                (
                    "delay_ratio_mean",
                    "Mean Delay Ratio"
                )
            ]


            for metric, ylabel in metrics:

                save_vs_util(
                    data[model],
                    mode,
                    metric,
                    ylabel,
                    plot_dir
                )