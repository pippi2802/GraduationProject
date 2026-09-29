#!/usr/bin/env bash
# prepare_clip.sh - extract the downloaded Sintel trailer archive and cut
# the excerpt rt_video.py uses as --input: 600 frames starting at frame
# 300, full 720p (no resize), high-quality H.264 (frames are decoded once
# at start-up, not during the periodic loop, so compression doesn't affect
# measurements).
#
# Usage:
#   workload/videos/prepare_clip.sh <archive.tar.gz|archive.y4m[.xz]> \
#       [--start-frame N] [--frames N] [--output-name NAME.mp4]
#
# Output: workload/videos/<NAME>.mp4 (next to this script) + a
# <NAME>.clip_metadata.json sidecar recording clip provenance/licence/
# resolution/frame rate - the "record in the metadata and the thesis"
# requirement.
set -euo pipefail

CLIPS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SOURCE="${1:?usage: prepare_clip.sh <archive.tar.gz|.y4m[.xz]> [--start-frame N] [--frames N] [--output-name NAME.mp4]}"
shift || true
START_FRAME=300
FRAMES=600
OUT_NAME="sintel_720p_600.mp4"

while [ $# -gt 0 ]; do
    case "$1" in
        --start-frame) START_FRAME="$2"; shift 2 ;;
        --frames) FRAMES="$2"; shift 2 ;;
        --output-name) OUT_NAME="$2"; shift 2 ;;
        *) echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ERROR: ffmpeg not found. Install it first (e.g. sudo apt install ffmpeg)." >&2
    exit 1
fi
if ! command -v ffprobe >/dev/null 2>&1; then
    echo "ERROR: ffprobe not found (usually ships with ffmpeg)." >&2
    exit 1
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

echo "[prepare_clip] extracting $SOURCE ..."
case "$SOURCE" in
    *.tar.gz|*.tgz)
        tar -xzf "$SOURCE" -C "$WORKDIR"
        ;;
    *.y4m.xz)
        xz -dk -c "$SOURCE" > "$WORKDIR/$(basename "${SOURCE%.xz}")"
        ;;
    *.y4m)
        cp "$SOURCE" "$WORKDIR/"
        ;;
    *)
        echo "ERROR: unrecognized archive type: $SOURCE (expected .tar.gz/.tgz/.y4m/.y4m.xz)" >&2
        exit 2
        ;;
esac

Y4M="$(find "$WORKDIR" -iname '*.y4m' | head -1)"
if [ -z "$Y4M" ]; then
    echo "ERROR: no .y4m file found after extracting $SOURCE" >&2
    exit 1
fi
echo "[prepare_clip] found source: $Y4M ($(du -h "$Y4M" | cut -f1))"

mkdir -p "$CLIPS_DIR"
OUT_PATH="$CLIPS_DIR/$OUT_NAME"

echo "[prepare_clip] cutting $FRAMES frames starting at frame $START_FRAME, full 720p, no resize..."
ffmpeg -y -i "$Y4M" -vf "select='gte(n\,$START_FRAME)'" \
    -frames:v "$FRAMES" -an -c:v libx264 -crf 12 -pix_fmt yuv420p "$OUT_PATH"

echo "[prepare_clip] wrote $OUT_PATH ($(du -h "$OUT_PATH" | cut -f1))"

# Read back what ffprobe actually reports (frame count/resolution/fps),
# rather than trusting the intended values, so the metadata is ground truth.
FFPROBE_JSON="$(ffprobe -v error -select_streams v:0 \
    -show_entries stream=width,height,r_frame_rate,nb_frames \
    -of json "$OUT_PATH")"

python3 - "$OUT_PATH" "$SOURCE" "$START_FRAME" "$FRAMES" "$FFPROBE_JSON" <<'PYEOF'
import datetime
import hashlib
import json
import sys

out_path, source, start_frame, frames, ffprobe_json = sys.argv[1:6]
probe = json.loads(ffprobe_json)["streams"][0]
num, den = (probe["r_frame_rate"].split("/") + ["1"])[:2]
fps = float(num) / float(den)
period_ms = 1000.0 / fps

sha256 = hashlib.sha256()
with open(out_path, "rb") as f:
    for chunk in iter(lambda: f.read(1 << 20), b""):
        sha256.update(chunk)

meta = {
    "clip_name": "Sintel trailer (Blender Foundation)",
    "licence": "CC BY 3.0 (Blender Foundation, as stated in the Sintel project readme)",
    "source_archive": source,
    "excerpt_start_frame": int(start_frame),
    "excerpt_frames_requested": int(frames),
    "excerpt_frames_actual": int(probe.get("nb_frames", frames)),
    "resolution": f"{probe['width']}x{probe['height']}",
    "frame_rate_fps": fps,
    "period_ms_native": round(period_ms, 3),
    "output_path": out_path,
    "sha256": sha256.hexdigest(),
    "prepared_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "note": "Tail-analysis block size: clip-aligned, b=600 or b=1200 (this excerpt's own length, or 2x it).",
}
meta_path = out_path.rsplit(".", 1)[0] + ".clip_metadata.json"
with open(meta_path, "w") as f:
    json.dump(meta, f, indent=2)
print(f"[prepare_clip] wrote {meta_path}")
print(json.dumps(meta, indent=2))
PYEOF
