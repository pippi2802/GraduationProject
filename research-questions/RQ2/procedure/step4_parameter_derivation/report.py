"""Output of the procedure: Report prints the tables, saves every table as CSV and every figure as PNG, and ends with a validity summary."""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def check(name, ok, detail=""):
    """one line of the validity summary: ok True = PASS, False = FAIL, None = information only"""
    return dict(check=name, result={True: "PASS", False: "FAIL", None: "info"}[ok], detail=detail)


class Report:
    def __init__(self, out_dir, show=False):
        self.out, self.show, self.checks, self.notes = Path(out_dir), show, [], []
        self.out.mkdir(parents=True, exist_ok=True)
        if not show:
            plt.switch_backend("Agg")

    def step(self, text):
        print(f"\n=== {text}")

    def table(self, name, df, title="", digits=3, show=True, sci=()):
        """saved as <name>.csv; printed unless show=False (columns in `sci` are printed in scientific notation)"""
        df.to_csv(self.out / f"{name}.csv")
        if show:
            shown = df.round({c: digits for c in df.select_dtypes('number').columns if c not in sci})      # the sci columns keep their precision
            print(f"\n[{name}] {title}\n{shown.to_string(formatters={c: '{:.1e}'.format for c in sci})}")

    def figure(self, name, fig):
        fig.savefig(self.out / f"{name}.png", dpi=110)
        print(f"\n[{name}] figure saved: {self.out / (name + '.png')}")
        if self.show:
            plt.show()
        plt.close(fig)

    def add_checks(self, checks):
        self.checks.extend(checks)

    def note(self, text):
        self.notes.append(text)
        print(f"note: {text}")

    def summary(self):
        """the validity summary: every check with its result"""
        t = pd.DataFrame(self.checks).set_index("check")
        self.table("validity_summary", t, "which checks the data and the bounds pass (PASS / FAIL; info = for your judgement)")
        fails = int((t.result == "FAIL").sum())
        print(f"\n{len(t)} checks: {int((t.result == 'PASS').sum())} PASS, {fails} FAIL, {int((t.result == 'info').sum())} info. Results in {self.out.resolve()}")
        return t
