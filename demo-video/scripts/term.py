"""Record a terminal clip where commands are typed out, then turn it into an MP4.

    clip = Clip(cwd=work_dir, prompt_path="~/demo")
    clip.say("# the bundle alice downloaded")             # a dim comment line, typed
    clip.run("./show_bundle.sh alice.zip")                 # typed at the prompt, then executed
    clip.session("ssh -F alice/ssh_config router",         # interactive: wait for each prompt
                 [(r"# $", 'show system information', {"clear": True}),   # clear: hide a login banner
                  (r"# $", "logout")])
    clip.record(out_dir / "t2")                            # → t2.cast, t2.mp4, t2.json

asciinema records a child process (this module, re-run with --play) inside a pty of the
requested size; agg renders the cast and ffmpeg encodes it. Keystrokes in interactive
sessions are sent one at a time, so the remote end's echo is what looks like typing.
take.json-like telemetry: start time of each step, so the compositor can place labels.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
import time
from pathlib import Path

COLS, ROWS = 104, 28
FONT_SIZE = 34
THEME = "github-dark"
IDLE_LIMIT = 4


class Clip:
    def __init__(self, cwd: Path, prompt_path: str = "~", user: str = "alice", host: str = "laptop") -> None:
        self.cwd = Path(cwd)
        self.prompt = f"\x1b[1;32m{user}@{host}\x1b[0m:\x1b[1;34m{prompt_path}\x1b[0m$ "
        self.steps: list[dict] = []

    def say(self, text: str) -> None:
        self.steps.append({"kind": "say", "text": text})

    def run(self, cmd: str, hold: float = 1.6, timeout: int = 120, display: str | None = None) -> None:
        self.steps.append({"kind": "run", "cmd": cmd, "display": display or cmd, "hold": hold, "timeout": timeout})

    def session(self, cmd: str, dialogue: list[tuple[str, str]], hold: float = 1.6, timeout: int = 90,
                display: str | None = None) -> None:
        self.steps.append({"kind": "session", "cmd": cmd, "display": display or cmd, "dialogue": dialogue,
                           "hold": hold, "timeout": timeout})

    def pause(self, seconds: float) -> None:
        self.steps.append({"kind": "pause", "seconds": seconds})

    def record(self, out: Path) -> Path:
        out.parent.mkdir(parents=True, exist_ok=True)
        spec = out.with_suffix(".spec.json")
        spec.write_text(json.dumps({"cwd": str(self.cwd), "prompt": self.prompt, "steps": self.steps}))
        cast = out.with_suffix(".cast")
        subprocess.run(["asciinema", "rec", "--overwrite", "-q", "--cols", str(COLS), "--rows", str(ROWS),
                        "-c", f"{sys.executable} {Path(__file__).resolve()} --play {spec}", str(cast)], check=True)
        gif = out.with_suffix(".gif")
        subprocess.run(["agg", "--theme", THEME, "--font-size", str(FONT_SIZE), "--idle-time-limit", str(IDLE_LIMIT),
                        "--fps-cap", "30", "--no-loop", "--text-font-family", "JetBrainsMono Nerd Font Mono,JetBrains Mono",
                        str(cast), str(gif)], check=True, capture_output=True)
        mp4 = out.with_suffix(".mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(gif), "-movflags", "faststart",
                        "-vf", "fps=30,pad=ceil(iw/2)*2:ceil(ih/2)*2", "-c:v", "libx264", "-crf", "16",
                        "-g", "30", "-keyint_min", "30",  # HyperFrames can't seek clips with sparse keyframes
                        "-pix_fmt", "yuv420p", str(mp4)], check=True)
        gif.unlink()
        return mp4


# ---------------------------------------------------------------------- player (inside asciinema)
def _type(text: str, cps: float = 18) -> None:
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(random.uniform(0.6, 1.4) / cps)


def _pump(child, until: float) -> str:
    import pexpect

    seen = ""
    while time.time() < until:
        try:
            chunk = child.read_nonblocking(4096, timeout=0.2)
        except pexpect.TIMEOUT:
            if not child.isalive():
                break
            continue
        except pexpect.EOF:
            break
        sys.stdout.write(chunk)
        sys.stdout.flush()
        seen += chunk
    return seen


def play(spec_path: str) -> None:
    import re

    import pexpect

    spec = json.loads(Path(spec_path).read_text())
    cwd, prompt = spec["cwd"], spec["prompt"]
    marks = []
    t0 = time.time()
    time.sleep(0.8)
    for step in spec["steps"]:
        marks.append({"t": round(time.time() - t0, 2), **{k: v for k, v in step.items() if k in ("kind", "cmd", "text")}})
        if step["kind"] == "pause":
            time.sleep(step["seconds"])
            continue
        sys.stdout.write(prompt)
        sys.stdout.flush()
        time.sleep(0.6)
        if step["kind"] == "say":
            sys.stdout.write("\x1b[2;37m")
            _type(step["text"])
            sys.stdout.write("\x1b[0m\r\n")
            time.sleep(0.9)
            continue
        _type(step["display"])
        time.sleep(0.45)
        sys.stdout.write("\r\n")
        sys.stdout.flush()
        child = pexpect.spawn("bash", ["-c", step["cmd"]], cwd=cwd, dimensions=(ROWS, COLS),
                              encoding="utf-8", codec_errors="replace")
        deadline = time.time() + step["timeout"]
        if step["kind"] == "session":
            buffer = ""
            for entry in step["dialogue"]:
                pattern, send, opts = entry[0], entry[1], (entry[2] if len(entry) > 2 else {})
                while not re.search(pattern, buffer) and time.time() < deadline and child.isalive():
                    buffer += _pump(child, time.time() + 0.3)
                if opts.get("clear"):
                    # drop a long login banner: clear, then reprint the command line and the remote prompt
                    tail = "\r\n".join(buffer.replace("\r\n", "\n").split("\n")[-opts.get("keep", 2):])
                    sys.stdout.write("\x1b[2J\x1b[H" + prompt + step["display"] + "\r\n" + tail)
                    sys.stdout.flush()
                time.sleep(0.7)
                buffer = ""
                for ch in send:
                    child.send(ch)
                    buffer += _pump(child, time.time() + random.uniform(0.04, 0.09))
                time.sleep(0.3)
                child.send("\r")
        _pump(child, deadline)
        child.close()
        time.sleep(step["hold"])
    sys.stdout.write(prompt)
    sys.stdout.flush()
    time.sleep(1.5)
    Path(spec_path).with_name(Path(spec_path).name.replace(".spec.json", ".json")).write_text(json.dumps(marks, indent=1))


if __name__ == "__main__" and sys.argv[1:2] == ["--play"]:
    play(sys.argv[2])
