#!/bin/sh
# usage: render.sh <file.py> <Scene> [quality flag, default -ql] [extra...]   (same setup as the 6G-RUPA videos)
cd "$(dirname "$0")"
f=$1; s=$2; q=${3:--ql}; shift 3 2>/dev/null
exec docker run --rm --user $(id -u):$(id -g) -e HOME=/tmp \
  -v "$PWD":/manim -v /usr/share/fonts/opentype/inter:/usr/share/fonts/inter:ro \
  manimcommunity/manim:v0.19.0 manim $q --disable_caching --media_dir /manim/media/$s "$f" "$s" "$@"
