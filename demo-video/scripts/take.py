"""Record a 4K browser take with Playwright, plus the telemetry the compositor needs.

A take is one continuous browser session. The page is laid out at 1920x1080 and drawn
at 2x (viewport 3840x2160 + CSS zoom 2), because Playwright's screencast ignores
device_scale_factor. Everything is logged in viewport pixels and in seconds from the
first frame; a magenta frame at t=0 lets the compositor line the video up with the log.

    with Take.open(out_dir / "a2", storage_state="dev.json", ignore_https_errors=True) as take:
        take.goto(url)
        take.focus(page.locator("#box"))         # camera beat: ease into this region
        take.click(page.get_by_role("button", name="Save"))
        take.toast("Saved", "ok")                 # a result chip in the corner
        take.cut_start(); wait_for_something(); take.cut_end("3 min later · Ready")
        take.focus(None)                          # back to the full page

Writes <dir>/take.mp4 (H.264, crf 14) and <dir>/take.json.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

VIEW = {"width": 3840, "height": 2160}
ZOOM = 2


def _find_chrome() -> str | None:
    """$DEMO_VIDEO_CHROME, else the newest headless shell Playwright has downloaded, else Playwright's own choice
    (None). The fallback matters when the pip package and the browser cache are at different Playwright versions."""
    if os.environ.get("DEMO_VIDEO_CHROME"):
        return os.environ["DEMO_VIDEO_CHROME"]
    shells = sorted(Path.home().glob(".cache/ms-playwright/chromium_headless_shell-*/*/chrome-headless-shell"),
                    key=lambda p: int(p.parts[-3].rsplit("-", 1)[1]))
    return str(shells[-1]) if shells else None


CHROME = _find_chrome()


class Take:
    def __init__(self, page, out: Path) -> None:
        self.page = page
        self.out = out
        self.t0 = time.monotonic()
        self.pos = (VIEW["width"] * 0.55, VIEW["height"] * 0.5)
        self.events: list[dict] = []
        self.marks: dict[str, float] = {}
        self.beats: list[dict] = []
        self.cuts: list[dict] = []
        self.toasts: list[dict] = []
        self.urls: list[dict] = []

    # ------------------------------------------------------------------ clock & log
    def t(self) -> float:
        return round(time.monotonic() - self.t0, 3)

    def mark(self, name: str) -> None:
        self.marks[name] = self.t()

    def toast(self, text: str, kind: str = "ok") -> None:
        self.toasts.append({"t": self.t(), "text": text, "kind": kind})

    def focus(self, locator=None, pad: float = 90, min_w: float = 0.5, union=None) -> None:
        """Camera beat at this moment: a region (viewport px) to frame, or None for the full page."""
        if locator is None:
            self.beats.append({"t": self.t(), "region": None})
            return
        boxes = [self.box(l) for l in ([locator] + list(union or []))]
        x0 = min(b["x"] for b in boxes)
        y0 = min(b["y"] for b in boxes)
        x1 = max(b["x"] + b["width"] for b in boxes)
        y1 = max(b["y"] + b["height"] for b in boxes)
        self.beats.append({"t": self.t(), "region": {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0},
                           "pad": pad, "min_w": min_w})

    def cut_start(self) -> None:
        self.cuts.append({"start": self.t()})

    def cut_end(self, label: str) -> None:
        self.cuts[-1].update({"end": self.t(), "label": label})

    # ------------------------------------------------------------------ pointer
    def box(self, locator) -> dict:
        locator.scroll_into_view_if_needed()
        b = locator.bounding_box()
        assert b is not None, locator
        return b

    def move(self, locator, dur: float = 0.9, dx: float = 0.5, dy: float = 0.5) -> None:
        b = self.box(locator)
        to = (round(b["x"] + b["width"] * dx, 1), round(b["y"] + b["height"] * dy, 1))
        self.events.append({"type": "move", "t": self.t(), "dur": dur, "from": self.pos, "to": to})
        self.pos = to
        self.page.mouse.move(*to, steps=8)
        self.page.wait_for_timeout(int(dur * 1000) + 200)

    def click(self, locator, settle: int = 1200, **kw) -> None:
        self.move(locator, **kw)
        self.events.append({"type": "click", "t": self.t(), "at": self.pos})
        self.page.mouse.click(*self.pos)
        self.page.wait_for_timeout(settle)

    def type(self, locator, text: str, delay: int = 60) -> None:
        self.click(locator, settle=300)
        if locator.input_value():
            locator.fill("")
            self.page.wait_for_timeout(250)
        locator.press_sequentially(text, delay=delay)
        self.page.wait_for_timeout(500)

    def hold(self, ms: int) -> None:
        self.page.wait_for_timeout(ms)

    def goto(self, url: str, settle: int = 900) -> None:
        self.page.goto(url, wait_until="networkidle")
        self.page.wait_for_timeout(settle)

    def download(self, locator, save_as: Path, settle: int = 1500) -> Path:
        with self.page.expect_download() as info:
            self.click(locator, settle=200)
        info.value.save_as(save_as)
        self.page.wait_for_timeout(settle)
        return save_as

    # ------------------------------------------------------------------ session
    @classmethod
    @contextmanager
    def open(cls, out: Path, storage_state: str | None = None, **context_kw):
        from playwright.sync_api import sync_playwright

        out.mkdir(parents=True, exist_ok=True)
        raw = out / "raw"
        shutil.rmtree(raw, ignore_errors=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROME)
            context = browser.new_context(viewport=VIEW, storage_state=storage_state, accept_downloads=True,
                                          record_video_dir=str(raw), record_video_size=VIEW, **context_kw)
            # the init script runs before <html> exists: zoom once the document is there.
            # Under CSS zoom, vh/vw still count unzoomed pixels, so fixed dialogs sized or centred
            # with them (max-h-[90vh], top-1/2) end up twice too tall and off-screen: rescale them (Radix/shadcn
            # dialogs only, marked by data-state; Bootstrap modals are full-screen wrappers and must not move).
            half = 100 / ZOOM
            fix = (f"[role=dialog][data-state],[role=alertdialog][data-state]{{max-height:{0.9 * half:.0f}vh !important;"
                   f"top:{half / 2:.0f}vh !important;left:{half / 2:.0f}vw !important}}"
                   # Radix poppers (menus, selects) place themselves with translate() in device pixels, which
                   # the zoom doubles: undo the zoom on the wrapper, restore it on the content.
                   f"[data-radix-popper-content-wrapper]{{zoom:{1 / ZOOM}}}"
                   f"[data-radix-popper-content-wrapper]>*{{zoom:{ZOOM}}}")
            context.add_init_script(
                f"document.addEventListener('DOMContentLoaded', () => "
                f"{{ document.documentElement.style.zoom = '{ZOOM}'; const s = document.createElement('style'); "
                f"s.textContent = '{fix}'; document.head.appendChild(s); }});")
            page = context.new_page()
            take = cls(page, out)
            page.on("framenavigated", lambda f: f == page.main_frame and take.urls.append({"t": take.t(), "url": f.url}))
            page.set_content("<body style='margin:0;background:#ff00ff'></body>")
            take.mark("magenta")
            page.wait_for_timeout(800)
            take.mark("sync")
            try:
                yield take
            finally:
                take.mark("end")
                video = page.video.path()
                context.close()
                browser.close()
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-c:v", "libx264",
                                "-preset", "slow", "-crf", "14", "-g", "15", "-pix_fmt", "yuv420p",
                                str(out / "take.mp4")], check=True)
                shutil.rmtree(raw, ignore_errors=True)
                (out / "take.json").write_text(json.dumps(
                    {"view": VIEW, "zoom": ZOOM, "events": take.events, "marks": take.marks, "beats": take.beats,
                     "cuts": take.cuts, "toasts": take.toasts, "urls": take.urls}, indent=1))
