"""Shared look for manim intros/explainers that sit next to Screen-Studio-style footage.

    from style import *          # palette, txt(), node(), laptop(), arrow helpers, config.background_color
    class Architecture(Scene): ...

Render with ./render.sh scenes.py Architecture -qh   (Docker image manimcommunity/manim:v0.19.0)
"""

from manim import *

BG = "#101218"      # same as the HyperFrames page background
FG = "#EEF0F4"
DIM = "#9AA1AD"
FAINT = "#2A2F3D"
PANEL = "#151924"
ORANGE = "#F28C28"  # accent (cursor ripple colour in the composition)
BLUE = "#5AA9F0"
TEAL = "#3FBFAA"
GREEN = "#34D399"
RED = "#F87171"
FONT = "Inter"      # mounted read-only into the container by render.sh

config.background_color = BG


def txt(s, size=24, color=FG, weight=NORMAL):
    """Small text is rendered at 4x and scaled down (Pango drops spaces and mis-kerns it otherwise);
    large text is not, or Pango wraps it at the layout width."""
    k = 4 if size < 22 else 1
    return Text(s, font=FONT, font_size=size * k, color=color, weight=weight).scale(1 / k)


def label(s, size=17, color=DIM):
    return txt(s, size, color)


def node(title, sub=None, w=2.9, h=1.15, color=BLUE, title_size=26):
    """A rounded box with a title and an optional dim subtitle (a component in a diagram)."""
    box = RoundedRectangle(width=w, height=h, corner_radius=.14, stroke_color=color, stroke_width=3,
                           fill_color=color, fill_opacity=.10)
    group = VGroup(txt(title, title_size, FG, weight=SEMIBOLD))
    if sub:
        group.add(txt(sub, 17, DIM))
    group.arrange(DOWN, buff=.1).move_to(box)
    return VGroup(box, group)


def laptop(color=FG):
    screen = RoundedRectangle(width=1.5, height=.95, corner_radius=.07, stroke_color=color, stroke_width=3)
    inner = Rectangle(width=1.28, height=.74, stroke_width=0, fill_color=FAINT, fill_opacity=1).move_to(screen)
    prompt = txt("$ ssh", 16, GREEN).move_to(inner).align_to(inner, LEFT).shift(RIGHT * .1)
    base = Polygon([-.95, 0, 0], [.95, 0, 0], [.8, .14, 0], [-.8, .14, 0], stroke_color=color, stroke_width=3)
    base.next_to(screen, DOWN, buff=0)
    return VGroup(screen, inner, prompt, base)


def arrow(a, b, color=DIM, ratio=.1):
    return Arrow(a, b, buff=.1, stroke_width=3, color=color, max_tip_length_to_length_ratio=ratio)


def lines(*rows, size=16, color=DIM, align=ORIGIN):
    """A multi-line edge label (short lines read better than one long one)."""
    return VGroup(*[label(r, size, color) for r in rows]).arrange(DOWN, buff=.06, aligned_edge=align)


def midpoint(line, t=.5):
    """Point along a line; DashedLine has no points of its own, so point_from_proportion fails on it."""
    return interpolate(line.get_start(), line.get_end(), t)
