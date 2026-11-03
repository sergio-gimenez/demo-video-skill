"""Turn a list of segments into a HyperFrames composition (index.html), Screen Studio style.

Segments play one after another:
  {"kind": "full",    "src": "intro/Architecture.mp4"}                     full-frame clip (manim, title card…)
  {"kind": "browser", "dir": "shots/a1", "act": "Create a lab", "from": "projects", "host": "…"}
  {"kind": "term",    "src": "shots/t2.mp4", "act": "…", "title": "dev@laptop: ~/demo"}
  {"kind": "end",     "title": "…", "sub": "…", "duration": 4}

Browser segments use take.json from lib/take.py: the take is shown in a framed window, a
camera eases into each logged beat, the pointer is redrawn from the logged path with a ripple
per click, waits marked with cut_start/cut_end are removed and replaced by a pill, toasts
appear top right. The page itself is never retouched. Coordinates stay in take pixels: the
stage keeps the take's size and is scaled into the window.

HyperFrames rules learned the hard way: a <video data-start> must not sit inside another
timed element; use tl.set/tl.to/fromTo with immediateRender:false (fromTo renders its start
state at t=0 otherwise); render with DO_NOT_TRACK=1.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

W, H = 1920, 1080
SW, SH, BAR = 1536, 864, 38           # browser window: screen size and title bar
WX, WY = (W - SW) // 2, 52
FADE = 0.45                           # crossfade between segments


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True)
    return float(out.stdout)


def size(path: Path) -> tuple[int, int]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    w, h = out.stdout.strip().split(",")
    return int(w), int(h)


def sync_offset(path: Path, magenta_at: float) -> float:
    """Video seconds minus take seconds, from the first magenta frame."""
    w, h, fps = 16, 9, 25
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-t", "8", "-i", str(path), "-vf",
                          f"fps={fps},scale={w}:{h},format=rgb24", "-f", "rawvideo", "-"],
                         capture_output=True, check=True).stdout
    frame, centre = w * h * 3, (h // 2 * w + w // 2) * 3
    for k in range(len(raw) // frame):
        r, g, b = raw[k * frame + centre: k * frame + centre + 3]
        if r > 200 and g < 60 and b > 200:
            return k / fps - magenta_at
    raise SystemExit(f"no magenta sync frame in {path}")


def fit(region: dict, vw: float, vh: float, pad: float = 90, min_w: float = 0.5) -> tuple:
    """A 16:9 camera box around a region, padded, kept inside the frame."""
    w = max(region["width"] + 2 * pad, (region["height"] + 2 * pad) * 16 / 9, vw * min_w)
    w = min(w, vw)
    h = w * 9 / 16
    cx, cy = region["x"] + region["width"] / 2, region["y"] + region["height"] / 2
    return (round(min(max(cx - w / 2, 0), vw - w), 1), round(min(max(cy - h / 2, 0), vh - h), 1), round(w, 1))


def cam(box, vw) -> dict:
    x, y, w = box
    s = vw / w
    return {"x": round(-x * s, 2), "y": round(-y * s, 2), "scale": round(s, 4)}



def prompt_title(src: Path) -> str:
    """Window title for a terminal clip: the prompt term.py recorded it with (user@host: path)."""
    spec = src.with_suffix(".spec.json")
    if spec.exists():
        prompt = re.sub(r"\x1b\[[0-9;]*m", "", json.loads(spec.read_text())["prompt"])
        return prompt.rstrip().rstrip("$").strip()
    return "terminal"


class Composer:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.t = 0.0
        self.html: list[str] = []
        self.overlay: list[str] = []
        self.js: list[str] = []
        self.n = 0
        self.acts = 0

    def _id(self, prefix: str) -> str:
        self.n += 1
        return f"{prefix}{self.n}"

    def _show(self, el: str, start: float, end: float) -> None:
        self.js.append(f'tl.to("#{el}", {{opacity: 1, duration: {FADE}, ease: "power1.out"}}, {max(start, 0):.3f});')
        self.js.append(f'tl.to("#{el}", {{opacity: 0, duration: {FADE}, ease: "power1.in"}}, {end - FADE:.3f});')

    def _act(self, text: str | None, at: float) -> None:
        if not text:
            return
        k = self._id("act")
        self.overlay.append(f'<div class="act" id="{k}">{text}</div>')
        self.js.append(f'tl.fromTo("#{k}", {{opacity: 0, y: 14}}, {{opacity: 1, y: 0, duration: 0.5, ease: "power2.out", immediateRender: false}}, {at + 0.3:.3f});')
        self.js.append(f'tl.to("#{k}", {{opacity: 0, duration: 0.5, ease: "power1.in"}}, {at + 4.6:.3f});')

    def _toast(self, text: str, kind: str, at: float, until: float | None = None) -> None:
        """A result chip top right; it leaves before `until` (its segment's end) if given."""
        k = self._id("toast")
        hide = at + 2.8 if until is None else max(min(at + 2.8, until - 0.6), at + 1.2)
        self.overlay.append(f'<div class="toast {kind}" id="{k}"><i></i>{text}</div>')
        self.js.append(f'tl.fromTo("#{k}", {{opacity: 0, y: -16}}, {{opacity: 1, y: 0, duration: 0.45, ease: "back.out(1.6)", immediateRender: false}}, {at:.3f});')
        self.js.append(f'tl.to("#{k}", {{opacity: 0, y: -10, duration: 0.4, ease: "power1.in"}}, {hide:.3f});')

    def _media(self, src: str) -> str:
        """Copy (hard-link) a clip into the project, HyperFrames serves files from its own folder."""
        source = (self.root / src).resolve()
        target = self.root / "hf" / "media" / src.replace("/", "_")
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.stat().st_mtime < source.stat().st_mtime:
            target.unlink(missing_ok=True)
            try:
                target.hardlink_to(source)
            except OSError:
                shutil.copy2(source, target)
        return f"media/{target.name}"

    # ------------------------------------------------------------------ segment kinds
    def full(self, seg: dict) -> None:
        src = self.root / seg["src"]
        d = round(seg.get("duration") or duration(src), 3)
        el = self._id("seg")
        self.html.append(f'<div class="full" id="{el}"></div>')
        self.html.append(f'<video id="{el}v" class="fullv" data-start="{self.t:.3f}" data-duration="{d}" '
                         f'data-media-start="0" src="{self._media(seg["src"])}" muted playsinline></video>')
        self._show(f"{el}v", self.t, self.t + d)
        self.t += d - FADE

    def term(self, seg: dict) -> None:
        src = self.root / seg["src"]
        d = round(duration(src), 3)
        vw, vh = size(src)
        th = SH + BAR
        tw = round(SH * vw / vh)
        x = (W - tw) // 2
        el = self._id("seg")
        title = seg.get("title") or prompt_title(src)
        self.html.append(
            f'<div class="window term" id="{el}" style="left:{x}px; top:{WY}px; width:{tw}px; height:{th}px">'
            f'<div class="bar dark"><i></i><i></i><i></i><div class="ttl">{title}</div></div></div>')
        self.html.append(f'<video id="{el}v" class="termv" style="left:{x}px; top:{WY + BAR}px; width:{tw}px; height:{SH}px" '
                         f'data-start="{self.t:.3f}" data-duration="{d}" data-media-start="0" '
                         f'src="{self._media(seg["src"])}" muted playsinline></video>')
        self._show(el, self.t, self.t + d)
        self._show(f"{el}v", self.t, self.t + d)
        self._act(seg.get("act"), self.t)
        self.t += d - FADE

    def browser(self, seg: dict) -> None:
        folder = self.root / seg["dir"]
        take = json.loads((folder / "take.json").read_text())
        video = folder / "take.mp4"
        vw, vh = take["view"]["width"], take["view"]["height"]
        marks = take["marks"]
        off = sync_offset(video, marks["magenta"])
        m0 = marks[seg.get("from", "sync")] - 0.2
        m1 = min(marks.get(seg.get("to", "end"), marks["end"]), duration(video) - off - 0.05)
        cuts = sorted((c["start"] + 1.0, max(c["start"] + 1.0, c["end"] - 0.6), c.get("label", ""))
                      for c in take["cuts"] if "end" in c)

        def at(t: float) -> float:
            """Segment seconds for a take time; times inside a cut land on its start."""
            s = t - m0
            for c0, c1, _ in cuts:
                if t >= c1:
                    s -= c1 - c0
                elif t > c0:
                    s -= t - c0
            return round(s, 3)

        def cut_out(t: float) -> bool:
            return any(c0 < t < c1 for c0, c1, _ in cuts)

        length = round(at(m1), 3)
        base = self.t
        el = self._id("seg")
        camid, curid = f"{el}cam", f"{el}cur"
        # pieces of the take between cuts, each its own <video> (not nested in a timed element)
        pieces, cursor_t, seg_t = [], m0, 0.0
        for c0, c1, _ in cuts + [(m1, m1, "")]:
            d = round(c0 - cursor_t, 3)
            if d > 0.05:
                pieces.append((base + seg_t, d, cursor_t + off))
                seg_t += d
            cursor_t = c1
        videos = "\n".join(
            f'<video id="{el}p{k}" class="clip" data-start="{s:.3f}" data-duration="{d}" data-media-start="{ms:.3f}" '
            f'src="{self._media(seg["dir"] + "/take.mp4")}" muted playsinline style="width:{vw}px;height:{vh}px"></video>'
            for k, (s, d, ms) in enumerate(pieces))

        # camera: "home" is the framing used when no region is in focus (the content column)
        js = self.js
        hw = vw * seg.get("home", 1.0)
        full = (round((vw - hw) / 2, 1), 0, round(hw, 1))
        js.append(f'tl.set("#{camid}", {json.dumps(cam(full, vw))}, 0);')
        for beat in take["beats"]:
            if beat["t"] < m0 - 0.5 or beat["t"] > m1 or cut_out(beat["t"]):
                continue
            box = full if beat["region"] is None else fit(beat["region"], vw, vh, beat.get("pad", 90), beat.get("min_w", 0.5))
            js.append(f'tl.to("#{camid}", {{...{json.dumps(cam(box, vw))}, duration: 1.3, ease: "power3.inOut"}}, {base + max(at(beat["t"]), 0):.3f});')

        # cursor + ripples
        ripples = []
        moves = [e for e in take["events"] if e["type"] == "move"]
        start = moves[0]["from"] if moves else (vw * 0.55, vh * 0.5)
        js.append(f'tl.set("#{curid}", {{x: {start[0]}, y: {start[1]}}}, 0);')
        for e in take["events"]:
            if e["t"] < m0 - 0.05 or e["t"] > m1 or cut_out(e["t"]):
                continue
            c = base + at(e["t"])
            if e["type"] == "move":
                js.append(f'tl.to("#{curid}", {{x: {e["to"][0]}, y: {e["to"][1]}, duration: {e["dur"]}, ease: "power2.inOut"}}, {c:.3f});')
            else:
                k = self._id("rip")
                ripples.append(f'<div class="ripple" id="{k}"></div>')
                cx, cy = e["at"]
                js.append(f'tl.to("#{curid}", {{scale: 0.8, duration: 0.09, yoyo: true, repeat: 1, transformOrigin: "0 0"}}, {c:.3f});')
                js.append(f'tl.fromTo("#{k}", {{x: {cx - 60}, y: {cy - 60}, scale: 0.3, opacity: 0.7}}, '
                          f'{{scale: 1.6, opacity: 0, duration: 0.55, ease: "power1.out", immediateRender: false}}, {c:.3f});')

        # address bar follows the page
        host = seg.get("host", "")
        paths = [(m0, None)]
        for u in take.get("urls", []):
            if u["url"].startswith("http"):
                paths.append((u["t"], "/" + u["url"].split("/", 3)[3] if u["url"].count("/") >= 3 else "/"))
        spans = []
        current = next((p for t, p in reversed(paths) if p and t <= m0), "/")
        spans.append((m0, current))
        for t, p in paths:
            if p and m0 < t < m1 and p != spans[-1][1]:
                spans.append((t, p))
        url_html = []
        for k, (t, p) in enumerate(spans):
            pid = f"{el}u{k}"
            url_html.append(f'<b id="{pid}" style="display:{"inline" if k == 0 else "none"}">{p}</b>')
            if k:
                js.append(f'tl.set("#{el}u{k - 1}", {{display: "none"}}, {base + at(t):.3f});')
                js.append(f'tl.set("#{pid}", {{display: "inline"}}, {base + at(t):.3f});')

        # cut pills and toasts
        for c0, _, label in cuts:
            if label:
                k = self._id("pill")
                self.overlay.append(f'<div class="pill" id="{k}">{label}</div>')
                a = base + at(c0)
                js.append(f'tl.fromTo("#{k}", {{opacity: 0, scale: 0.92}}, {{opacity: 1, scale: 1, duration: 0.35, ease: "back.out(1.6)", immediateRender: false}}, {max(a - 0.2, 0):.3f});')
                js.append(f'tl.to("#{k}", {{opacity: 0, duration: 0.4, ease: "power1.in"}}, {a + 2.2:.3f});')
        for toast in take.get("toasts", []):
            if m0 <= toast["t"] <= m1:
                self._toast(toast["text"], toast.get("kind", "ok"), base + at(toast["t"]) + 0.15, until=base + length)

        scale = SW / vw
        self.html.append(f'''<div class="window" id="{el}" style="left:{WX}px; top:{WY}px; width:{SW}px; height:{SH + BAR}px">
  <div class="bar"><i></i><i></i><i></i><div class="url">{host}{"".join(url_html)}</div></div>
  <div class="screen"><div class="stage" style="width:{vw}px;height:{vh}px;transform:scale({scale})"><div class="cam" id="{camid}" style="width:{vw}px;height:{vh}px" data-layout-allow-overflow>
{videos}
{chr(10).join(ripples)}
<svg class="cur" id="{curid}" viewBox="0 0 24 24" width="66" height="66"><path d="M3 2 L3 19 L7.6 14.8 L10.6 21.4 L13.4 20.2 L10.5 13.7 L16.8 13.7 Z" fill="#111" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/></svg>
  </div></div></div>
</div>''')
        self._show(el, base, base + length)
        self._act(seg.get("act"), base)
        self.t += length - FADE

    def end(self, seg: dict) -> None:
        d = seg.get("duration", 4.0)
        el = self._id("seg")
        self.html.append(f'<section class="endcard" id="{el}"><h1>{seg["title"]}</h1><p>{seg.get("sub", "")}</p></section>')
        self._show(el, self.t, self.t + d + FADE)
        self.t += d

    # ------------------------------------------------------------------ page
    def build(self, segments: list[dict]) -> Path:
        gsap = self.root / "hf" / "gsap.min.js"
        if not gsap.exists():  # not redistributed with the template: taken from the npm package
            dist = self.root / "hf" / "node_modules" / "gsap" / "dist" / "gsap.min.js"
            if not dist.exists():
                raise SystemExit("gsap is missing: run `npm install` in hf/ first")
            shutil.copyfile(dist, gsap)
        for seg in segments:
            getattr(self, seg["kind"])(seg)
        total = round(self.t + FADE, 3)
        hf = self.root / "hf"
        page = PAGE.format(total=total, body="\n".join(self.html), overlay="\n".join(self.overlay),
                           js="\n".join(self.js), W=W, H=H, SW=SW, SH=SH, BAR=BAR, WX=WX, WY=WY,
                           ACT_Y=WY + BAR + SH + 34, PILL_Y=WY + BAR + SH // 2 - 36, TOAST_X=WX + 28, TOAST_Y=WY + BAR + 26)
        (hf / "index.html").write_text(page)
        return hf / "index.html"


PAGE = '''<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width={W}, height={H}" />
<script src="gsap.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #101218; }}
#root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden;
         font-family: Inter, "Helvetica Neue", ui-sans-serif, system-ui, sans-serif; color: #eef0f4;
         background: radial-gradient(1200px 700px at 18% 0%, #2a2f3d 0%, transparent 60%),
                     radial-gradient(1000px 700px at 100% 100%, #16323a 0%, transparent 55%), #101218; }}
.full, .fullv {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; opacity: 0; }}
.window {{ position: absolute; border-radius: 16px; overflow: hidden; background: #fff; opacity: 0;
           box-shadow: 0 0 0 1px rgba(255,255,255,.08), 0 30px 80px rgba(0,0,0,.55), 0 8px 24px rgba(0,0,0,.35); }}
.window.term {{ background: #0d1117; }}
.termv {{ position: absolute; opacity: 0; object-fit: contain; background: #0d1117; }}
.bar {{ position: absolute; left: 0; top: 0; right: 0; height: {BAR}px; background: #eceef2;
        display: flex; align-items: center; padding: 0 16px; gap: 8px; border-bottom: 1px solid #d9dce2; }}
.bar.dark {{ background: #1c2129; border-bottom: 1px solid #2a303a; }}
.bar i {{ width: 12px; height: 12px; border-radius: 50%; background: #c9ccd3; }}
.bar.dark i {{ background: #3a414d; }}
.ttl {{ flex: 1; text-align: center; margin-right: 60px; font: 500 14px/24px "JetBrains Mono", ui-monospace, monospace; color: #9aa1ad; }}
.url {{ margin-left: 18px; flex: 1; max-width: 640px; height: 24px; border-radius: 7px; background: #fff;
        font: 500 13px/24px Inter, ui-sans-serif, system-ui, sans-serif; color: #5b616c; padding: 0 12px; white-space: nowrap; overflow: hidden; }}
.url b {{ color: #1d2129; font-weight: 500; }}
.screen {{ position: absolute; left: 0; top: {BAR}px; width: {SW}px; height: {SH}px; overflow: hidden; }}
.stage {{ position: absolute; left: 0; top: 0; transform-origin: 0 0; }}
.cam {{ position: absolute; left: 0; top: 0; transform-origin: 0 0; }}
.cam video {{ position: absolute; left: 0; top: 0; }}
.cur {{ position: absolute; left: 0; top: 0; filter: drop-shadow(0 4px 6px rgba(0,0,0,.35)); }}
.ripple {{ position: absolute; left: 0; top: 0; width: 120px; height: 120px; border-radius: 50%; border: 6px solid #f28c28; opacity: 0; }}
.act {{ position: absolute; left: 0; right: 0; top: {ACT_Y}px; text-align: center; font-size: 30px; font-weight: 600;
        letter-spacing: -0.01em; color: #f4f5f7; opacity: 0; }}
.toast {{ position: absolute; right: {TOAST_X}px; top: {TOAST_Y}px; display: flex; align-items: center; gap: 12px; padding: 14px 22px;
          border-radius: 12px; background: rgba(18,20,26,.94); color: #eef0f4; font-size: 22px; font-weight: 500;
          box-shadow: 0 12px 30px rgba(0,0,0,.4), 0 0 0 1px rgba(255,255,255,.08); opacity: 0; }}
.toast i {{ width: 12px; height: 12px; border-radius: 50%; background: #34d399; }}
.toast.bad i {{ background: #f87171; }}
.pill {{ position: absolute; left: 0; right: 0; margin: 0 auto; width: fit-content; top: {PILL_Y}px; padding: 16px 30px; border-radius: 999px;
         background: rgba(18,20,26,.92); color: #eef0f4; font-size: 28px; font-weight: 600; opacity: 0;
         box-shadow: 0 16px 40px rgba(0,0,0,.45), 0 0 0 1px rgba(255,255,255,.08); }}
.pill b {{ color: #34d399; font-weight: 600; }}
.endcard {{ position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center;
            gap: 22px; background: #101218; opacity: 0; }}
.endcard h1 {{ font-size: 64px; font-weight: 650; letter-spacing: -0.025em; }}
.endcard p {{ font-size: 28px; color: #9aa1ad; }}
.endcard p b {{ color: #f28c28; font-weight: 600; }}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="{W}" data-height="{H}">
{body}
{overlay}
</div>
<script>
const tl = gsap.timeline({{ paused: true }});
{js}
window.__timelines = window.__timelines || {{}};
window.__timelines["main"] = tl;
tl.seek(0);
</script>
</body>
</html>
'''
