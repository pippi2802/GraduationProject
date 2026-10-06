import os, sys
import pandas as pd
R = sys.argv[1] if len(sys.argv) > 1 else "workload2/results/single_core"
conds = [c for c in ("baseline1", "cache", "memory", "baseline2") if os.path.exists(f"{R}/{c}/instance0.csv")]
d = {c: pd.read_csv(f"{R}/{c}/instance0.csv") for c in conds}
t = pd.DataFrame({c: dict(jobs=df.cpu_ns.notna().sum(), median=df.cpu_ns.median() / 1e6, p99=df.cpu_ns.quantile(.99) / 1e6,
                          p999=df.cpu_ns.quantile(.999) / 1e6, max=df.cpu_ns.max() / 1e6, cv=df.cpu_ns.std() / df.cpu_ns.mean()) for c, df in d.items()}).T
print("C in ms per condition:\n", t.round(3).to_string())
base = [c for c in ("baseline1", "baseline2") if c in t.index]
for s in ("cache", "memory"):
    if s in t.index and base:
        b = t.loc[base].mean()
        print(f"{s} / baseline: median x{t.loc[s, 'median'] / b['median']:.3f}   p99 x{t.loc[s, 'p99'] / b['p99']:.3f}   max x{t.loc[s, 'max'] / b['max']:.3f}")
print("\ncontent check (needs pictures repeated: n_images << jobs):")
for c, df in d.items():
    df = df.dropna(subset=["cpu_ns"]); g = df.groupby("frame_idx").cpu_ns
    if g.size().min() < 5:
        print(f"  {c}: fewer than 5 repetitions per picture, skipped"); continue
    content = g.median().std() / g.median().mean()          # spread between pictures
    noise = (df.cpu_ns / g.transform("median")).std()        # spread of the same picture over the run
    floor = noise / g.size().mean() ** 0.5                   # what the between-pictures CV would be from noise alone
    print(f"  {c}: between pictures CV {content:.4f}   (noise alone would give {floor:.4f})   same picture repeated CV {noise:.4f}"
          f"  -> content effect {'visible' if content > 2 * floor else 'not distinguishable from noise'}")
