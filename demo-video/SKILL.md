---
name: demo-video
description: >
  Record a shareable product/demo video of a real web app + terminal, Screen Studio style:
  Playwright drives the real UI at 4K with a visible pointer and logs telemetry, terminal
  steps are typed out (asciinema → agg), an optional manim intro explains the architecture,
  and HyperFrames composes it all (framed window, eased zooms into what matters, redrawn
  cursor with click ripples, cut-out waits with a pill, result toasts, act labels, end card)
  and renders locally in 4K. Use when the user asks to "record a video/demo/walkthrough",
  "make it like we normally do", "Screen Studio / zooming video", "HyperFrames video",
  "manim intro/diagram animation", or wants a video to share after a demo.
---

# Demo video (Playwright + terminal + manim → HyperFrames)

Worked example: `example/openop-edge/` (the ETSI OpenOP portal: register an app, deploy it to an edge zone,
check the pod with kubectl, remove it; a two-scene manim intro). Read its `rec.py` and `build.py` before writing
a new project: they show every API below in use.

## Requirements

Python 3.11+ with `playwright` and `pexpect`; a Playwright Chromium headless shell (`playwright install
chromium-headless-shell`, or point `DEMO_VIDEO_CHROME` at one); `asciinema` (2.x) and `agg`; `ffmpeg`; Node 20+
(HyperFrames via `npx`, GSAP via `npm install` in `hf/`); Docker for manim; the Inter and JetBrains Mono fonts.

## House style (the defaults; follow them unless the user asks otherwise)

- **4K, slow, pointer visible.** Real 4K takes (viewport 3840×2160 + CSS zoom 2), slow pacing (typed text,
  holds of 1.5–3.5 s after each result), render with `--resolution 4k`.
- **Sparse overlays.** A few short act labels (≈5 s, no numbers, no subtitles), toasts only for real results,
  one pill per cut-out wait. **No "made with AI / Playwright / HyperFrames" credit**, no tooling mentions.
- **Real infrastructure, real results.** Never fake a success; if a step fails, fix and re-record it.
- **Store everything outside /tmp** (a reboot wiped a whole pipeline once): `<project>/video/`.
- `DO_NOT_TRACK=1` for every HyperFrames command (demos often run against internal hosts).
- Ask before side effects outside the demo environment; note every change the recording makes.

## Layout of a video project

```
video/
  lib/        take.py term.py compose.py      ← copy from this skill's scripts/
  tools/      contact_sheet.sh
  intro/      scenes.py style.py render.sh     ← manim (copy manim/*)
  rec.py      one function per shot, in story order; `python3 rec.py a1 t2 …` re-records single shots
  build.py    SEGMENTS list (the storyboard) → hf/index.html
  hf/         HyperFrames project (copy hf-template/*, set PROJECT/DATE), media/ is filled by compose
  shots/      <name>/take.{mp4,json} (browser), <name>.{cast,mp4,json} (terminal)
  out/        final renders
  logs/  state.json (ids created while recording, for later shots and cleanup)
```

## Workflow

1. **Storyboard first** (acts → shots). Mix browser shots (what users click) and terminal shots (what they
   run). Plan side effects and cleanup (things a take creates must be deletable for a retake).
2. **Explore the real pages** headless once (dump form fields, screenshot) before writing selectors.
3. **Record** with `rec.py` (see APIs below). Run long shots in the background; record independent shots
   while waiting; never run two shots that restart/modify the same service concurrently.
4. **QA every shot**: `tools/contact_sheet.sh shots/x/take.mp4 sheet.png 9` and the last frame of each
   terminal clip (`ffmpeg -sseof -1.2 …`). Look at them. Re-record what is wrong.
5. **manim intro** (optional): `intro/render.sh scenes.py Scene -ql -s` for a last-frame check, then `-qh`.
6. **Compose**: `python3 build.py` → `cd hf && DO_NOT_TRACK=1 npx --yes hyperframes@0.8.134 lint`
   (0 errors, 0 warnings).
7. **Draft render** + contact sheet of 24 frames: `render --quality draft -o renders/draft.mp4`. Review.
8. **Final** (frame cache on disk, never the RAM-backed /tmp: a 5 min 4K render needs ~6 GB of PNG frames):
   ```bash
   C=<project>/video/.frames-cache; mkdir -p $C
   DO_NOT_TRACK=1 npx --yes hyperframes@0.8.134 render --quality delivery --resolution 4k \
     --video-frame-format png --frames-cache-dir $C -o ../out/<name>-4k.mp4; rm -rf $C
   ```

## Browser shots: `lib/take.py`

```python
with Take.open(SHOTS / "a2", storage_state=".state-dev.json", ignore_https_errors=True) as take:
    page = take.page
    take.goto(url); take.mark("page")              # marks: segment start ("from") and anchors
    take.focus(locator, min_w=0.55, union=[other])  # camera beat: ease into region(s); focus(None) = home
    take.type(page.locator("#id_name"), "lab-1")     # clears pre-filled fields first
    take.click(locator, settle=1200)                 # pointer move + ripple logged
    take.download(button, WORK / "bundle.zip")
    take.toast("Bundle downloaded")                  # result chip (kind "bad" = red dot)
    take.cut_start(); wait(); take.cut_end("3 min later · <b>Ready</b>")   # removed from the video
```
- Log in once per user (`storage_state`), don't show logins unless they matter.
- After a reload, **wait for async UI** (badges, statuses) with `expect(...).to_contain_text(...)` before the
  final hold, and call `focus()` again (regions change after reloads/scrolls).
- JS `confirm()` dialogs: `page.once("dialog", lambda d: d.accept())` before the click.
- Options of custom selects can be unclickable under zoom: draw the move/click, pick with keyboard.

## Terminal shots: `lib/term.py`

```python
c = Clip(cwd=WORK, prompt_path="~/demo", user="dev")
c.say("# a dim comment line, typed")             # tells the viewer what comes next
c.run("cmd", display="shorter cmd shown", hold=3)
c.session("cd b && ssh -o LogLevel=ERROR -F ssh_config r1",
          [(r"#\s*$", "show version", {"clear": True}), (r"#\s*$", "logout")])
c.record(SHOTS / "t3")                           # → t3.mp4 (≈2160 px wide, github-dark, JetBrains Mono)
```
- `display=` hides noisy flags (`-o BatchMode=yes`, `LogLevel`) and long ids from what is typed.
- `-o LogLevel=ERROR` hides SSH pre-login banners and "Permanently added" warnings but keeps errors.
- `{"clear": True}` on the first prompt hides a post-login banner (MOTD/EULA).
- Tools with relative paths (e.g. `ssh -F ssh_config` bundles) must run **from inside** their folder.
- agg idle limit is 4 s: long waits shrink automatically; use `c.pause(n)` for "30 s later" moments.

## Composition: `lib/compose.py`

`SEGMENTS` kinds: `full` (manim/title clip), `browser` (`dir`, `from` mark, `host`, `home` framing ≈0.76
for centred web apps, `act`), `term` (`src`, `title`, `act`), `end` (`title`, `sub`, `duration`).
Segments crossfade (0.45 s). Toasts are clamped to their segment. Window 1536×864 on a 1920×1080 stage;
the stage keeps take pixels so camera boxes and pointer positions are in take px.

## manim intros

- Render through Docker, nothing installed on the host: `manim/render.sh` (image
  `manimcommunity/manim:v0.19.0`, Inter mounted from `/usr/share/fonts/opentype/inter`). There are no Linux
  wheels for `manimpango`; a host install needs `libcairo2-dev libpango1.0-dev` (sudo).
- `manim/style.py`: palette matching the composition, `txt()` (render 4× then scale: fixes lost spaces and
  kerning), `node()`, `laptop()`, `arrow()`, `lines()` for multi-line edge labels, `midpoint()`.
- Label every edge (what crosses it). Keep scenes 20–30 s; 2 scenes ≈ 50 s is enough before the footage.
- Check overlaps on the last frame (`-ql -s`) before `-qh`.
- **Narration** (voice + subtitles) is not part of this skill. If asked: write the script per beat, synthesise it
  with a TTS that returns word timestamps, time the manim animations against those timestamps, then mix, loudnorm
  and emit an SRT. Keep API keys in the environment and never print them. Only add narration when asked.

## HyperFrames gotchas

- Pin the CLI (`hyperframes@0.8.134` in hf-template/package.json) so re-renders match.
- A `<video data-start>` must not sit inside another timed element; containers are plain divs whose opacity
  is tweened.
- Hide elements initially with CSS (`opacity: 0`), not `tl.set(…, 0)` (lint warns; frame 0 shows them).
- `fromTo` renders its start state at t=0 unless `immediateRender: false`.
- Playwright's screencast ignores `device_scale_factor`: use the 3840×2160 viewport + zoom 2 trick.
  Its side effects, now handled in `take.py`'s init script (verified on a React + Radix UI app):
  `vh`/`vw` ignore the zoom, so shadcn dialogs (`max-h-[90vh]`, centred with `top-1/2`) opened twice too tall and
  off-screen (the click hit the backdrop, the dialog closed, typed keys hit page shortcuts: `d` = dark mode); Radix
  poppers (menus, selects) placed themselves at twice their coordinates. The script rescales `[role=dialog][data-state]`
  and counter-zooms `[data-radix-popper-content-wrapper]`. A new UI kit: check one dialog and one menu first.
- SSO apps whose IdP only redirects back to the deployed host: run the GUI locally (vite proxy for `/api/`), let the
  person sign in once on the deployed host in a headed browser, copy its cookies to `127.0.0.1` (`example/openop-edge/login.py`).
- Never `pkill -f '<pattern>'` inside a recorded command: the pattern is also in the calling shell's command line and
  kills it (exit 144). Background a helper with `& PF=$!` and `kill $PF`.
- Sync: the magenta frame at take start aligns video time with telemetry time (`sync_offset`).
- Every source clip needs dense keyframes (`-g 30` at 30 fps): agg-rendered GIF→MP4 clips had 8 s gaps and the
  4K render failed with `VIDEO_SOURCE_UNRENDERABLE` (term.py now encodes with `-g 30 -keyint_min 30`).
- The default frame cache is `<tmpdir>/hyperframes-extract-cache-<uid>`; on many Linux setups /tmp is a small RAM-backed tmpfs
  and filling it breaks every shell, the coding agent's own included. Always pass `--frames-cache-dir`.
- `ffmpeg -y` rewrites files in place: copy a take before re-recording if a render still uses it (compose
  hard-links media into `hf/media/`).
