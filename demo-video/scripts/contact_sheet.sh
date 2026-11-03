#!/usr/bin/env bash
# Contact sheet of a video: N evenly spaced frames (or the given times), labelled, tiled 3 wide.
# Usage: contact_sheet.sh <video.mp4> <out.png> [count=12 | t1 t2 ...]
set -euo pipefail
video=$1; out=$2; shift 2
dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$video")
if [ $# -le 1 ]; then
  n=${1:-12}; set --; for i in $(seq 0 $((n - 1))); do set -- "$@" "$(python3 -c "print(round($dur * ($i + .5) / $n, 1))")"; done
fi
tmp=$(mktemp -d); i=0
for t in "$@"; do
  ffmpeg -y -loglevel error -ss "$t" -i "$video" -frames:v 1 \
    -vf "scale=640:-2,drawtext=text='${t}s':x=8:y=8:fontcolor=yellow:fontsize=22:box=1:boxcolor=black@0.5" "$tmp/$(printf %03d $i).png"
  i=$((i + 1))
done
rows=$(( (i + 2) / 3 ))
ffmpeg -y -loglevel error -pattern_type glob -i "$tmp/*.png" -filter_complex "tile=3x$rows" "$out"
rm -rf "$tmp"; echo "$out ($i frames of ${dur%.*} s)"
