#!/usr/bin/env python3
"""Copies KITTI Velodyne scans (float32 x, y, z, reflectance, .bin) into scans/, renamed 000000.bin, 000001.bin, ... in drive order.

    python3 prepare_scans.py <folder with the unzipped KITTI raw drives> [--n N]  (default: all)

KITTI raw data (CC BY-NC-SA 3.0, https://www.cvlibs.net/datasets/kitti/raw_data.php): the "synced+rectified" zip of a few city drives, e.g. 2011_09_26_drive_0001, _0005, _0011, _0013.
Each scan has about 120000 points; the scans are searched as <folder>/**/velodyne_points/data/*.bin.
"""
import argparse, glob, os, shutil

ap = argparse.ArgumentParser()
ap.add_argument("root")
ap.add_argument("--n", type=int, default=None)          # default: all scans
a = ap.parse_args()
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scans")
files = sorted(glob.glob(os.path.join(a.root, "**", "velodyne_points", "data", "*.bin"), recursive=True))[: a.n]
if not files:
    raise SystemExit(f"no velodyne_points/data/*.bin under {a.root}")
for k, f in enumerate(files):
    shutil.copyfile(f, os.path.join(out, f"{k:06d}.bin"))
print(f"{len(files)} scans in {out}")
