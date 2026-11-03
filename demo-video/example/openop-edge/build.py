"""Storyboard of the OpenOP edge-deployment video → hf/index.html (then: cd hf && DO_NOT_TRACK=1 npm run render)."""

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "lib"))
from compose import Composer  # noqa: E402

HOST = "127.0.0.1:3100"
INTRO = "intro/media/{0}/videos/scenes/1080p60/{0}.mp4"

SEGMENTS = [
    {"kind": "full", "src": INTRO.format("Architecture")},
    {"kind": "full", "src": INTRO.format("Flow")},
    {"kind": "browser", "dir": "shots/a1", "from": "home", "host": HOST, "home": 0.76, "act": "Register an application profile"},
    {"kind": "browser", "dir": "shots/a2", "from": "instances", "host": HOST, "home": 0.76, "act": "Deploy it to an edge zone"},
    {"kind": "term", "src": "shots/t3.mp4", "act": "It runs on the edge cluster"},
    {"kind": "browser", "dir": "shots/a4", "from": "instances", "host": HOST, "home": 0.76, "act": "Remove it"},
    {"kind": "term", "src": "shots/t5.mp4"},
    {"kind": "end", "title": "Your app at the edge, through one API.", "sub": "<b>ETSI OpenOP</b> · Edge Application Management", "duration": 4.5},
]

if __name__ == "__main__":
    only = [s for s in SEGMENTS if s["kind"] in ("full", "end") or (HERE / s.get("dir", s.get("src", ""))).exists()]
    skipped = [s.get("dir") or s.get("src") for s in SEGMENTS if s not in only]
    out = Composer(HERE).build(only)
    print(f"{out}  ({len(only)} segments{', missing: ' + ', '.join(skipped) if skipped else ''})")
