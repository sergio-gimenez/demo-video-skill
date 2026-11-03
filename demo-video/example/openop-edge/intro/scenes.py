"""Manim intro for the OpenOP edge-deployment video: the architecture, then the demo flow.

Render: ./render.sh scenes.py Architecture -qh   (last-frame check: -ql -s)
Grounded in oop/architecture (develop): oeg/app-registration-flow.md, oeg/app-instance-flow.md,
srm/architecture.md (OEG publishes command.srm.service.deploy on the DataBus, SRM fulfils it
through a TF-SDK adapter and answers with event.srm.operation.completed).
"""

from style import *  # noqa: F401,F403


class Architecture(Scene):
    def construct(self):
        title = txt("Deploy an app at the edge with OpenOP", 40, FG, weight=SEMIBOLD).to_edge(UP, buff=.4)
        self.play(FadeIn(title, shift=DOWN * .2), run_time=1.0)
        self.wait(.3)

        y = .35
        dev = laptop().scale(.85).move_to([-6.0, y, 0])
        dev[2].become(txt("$ curl", 16, GREEN).move_to(dev[1]).align_to(dev[1], LEFT).shift(RIGHT * .1))
        dev_l = label("app developer", 18, FG).next_to(dev, DOWN, buff=.18)
        portal = node("Portal", "web UI", w=2.0, h=1.0, color=BLUE, title_size=23).move_to([-3.35, 1.55, 0])
        oeg = node("OEG", "exposure gateway", w=2.35, h=1.1, color=BLUE).move_to([-1.0, y, 0])
        bus = node("DataBus", "NATS", w=1.9, h=1.0, color=FAINT, title_size=22).move_to([1.85, y, 0])
        srm = node("SRM", "resource manager", w=2.35, h=1.1, color=BLUE).move_to([4.75, y, 0])

        zone = RoundedRectangle(width=4.6, height=2.0, corner_radius=.2, stroke_color=TEAL, stroke_width=3,
                                fill_color=PANEL, fill_opacity=1).move_to([4.2, -2.55, 0])
        zone_l = label("edge cloud zone · Barcelona · Kubernetes", 16, TEAL).next_to(zone.get_top(), DOWN, buff=.16)
        pod = node("podinfo", "your app", w=1.9, h=.85, color=FG, title_size=20).move_to(zone).shift(DOWN * .2)

        fm = node("FM", "federation", w=2.0, h=.9, color=FAINT, title_size=22).move_to([-1.0, -2.55, 0])
        fm_l = lines("partner operators' zones", "(not in this video)", size=15).next_to(fm, DOWN, buff=.14)

        self.play(FadeIn(oeg, shift=UP * .2), FadeIn(portal, shift=UP * .2), run_time=.7)
        self.play(FadeIn(bus), FadeIn(srm), run_time=.7)
        self.play(FadeIn(zone), FadeIn(zone_l), run_time=.6)
        self.play(FadeIn(fm), FadeIn(fm_l), run_time=.5)
        self.play(FadeIn(dev), FadeIn(dev_l), run_time=.5)
        self.wait(.3)

        # --- northbound: the same CAMARA API from the portal or from code
        a_dev = arrow(dev.get_right(), oeg[0].get_left(), color=ORANGE, ratio=.12)
        t_dev = lines("CAMARA Edge App", "Management API", size=15, color=ORANGE).next_to(a_dev, DOWN, buff=.16)
        a_por = arrow(portal[0].get_bottom(), oeg[0].get_top() + LEFT * .5, color=ORANGE, ratio=.15)
        t_por = label("same API", 15, ORANGE).next_to(oeg, UP, buff=.1).shift(RIGHT * .45)
        self.play(GrowArrow(a_dev), FadeIn(t_dev), run_time=.9)
        self.play(GrowArrow(a_por), FadeIn(t_por), run_time=.7)
        calls = lines("POST /apps", "POST /appinstances", size=16, color=FG, align=LEFT)
        calls.next_to(t_dev, DOWN, buff=.3)
        self.play(FadeIn(calls, shift=UP * .1), run_time=.6)
        self.wait(.4)

        # --- inside the platform: a command out, an event back
        a_cmd = arrow(oeg[0].get_right(), bus[0].get_left(), color=BLUE, ratio=.2)
        a_cmd2 = arrow(bus[0].get_right(), srm[0].get_left(), color=BLUE, ratio=.2)
        t_cmd = label("command.srm.service.deploy", 15, BLUE).next_to(bus, UP, buff=.3)
        self.play(GrowArrow(a_cmd), GrowArrow(a_cmd2), FadeIn(t_cmd), run_time=1.0)
        a_dep = arrow(srm[0].get_bottom(), zone.get_top() + RIGHT * .55, color=TEAL, ratio=.2)
        t_dep = lines("TF-SDK", "adapter", size=15, color=TEAL).next_to(a_dep, RIGHT, buff=.12)
        self.play(GrowArrow(a_dep), FadeIn(t_dep), run_time=.8)
        self.play(FadeIn(pod, scale=.9), run_time=.6)
        self.play(Flash(pod[0], color=GREEN, line_length=.22, flash_radius=.95), run_time=.6)

        yb = y - 1.0
        xs, xo = srm[0].get_left()[0] + .45, oeg[0].get_right()[0] - .45
        back = VGroup(DashedLine([xs, y - .55, 0], [xs, yb, 0], stroke_width=3, color=GREEN),
                      DashedLine([xs, yb, 0], [xo, yb, 0], stroke_width=3, color=GREEN),
                      Arrow([xo, yb, 0], [xo, y - .55, 0], buff=0, stroke_width=3, color=GREEN,
                            max_tip_length_to_length_ratio=.4))
        t_back = label("event.srm.operation.completed → ready", 15, GREEN).next_to(back[1], DOWN, buff=.14)
        self.play(Create(back), FadeIn(t_back), run_time=1.0)
        self.wait(2.6)


class Flow(Scene):
    def construct(self):
        title = txt("In this video", 40, FG, weight=SEMIBOLD).to_edge(UP, buff=.5)
        self.play(FadeIn(title, shift=DOWN * .2), run_time=.8)
        steps = [("Register", "an app profile", BLUE),
                 ("Deploy", "to an edge zone", BLUE),
                 ("Check", "pod and app", TEAL),
                 ("Remove", "and it is gone", RED)]
        cards = VGroup(*[node(a, b, w=2.9, h=1.35, color=c, title_size=26) for a, b, c in steps])
        cards.arrange(RIGHT, buff=.42).move_to(UP * .2)
        nums = VGroup(*[txt(str(i + 1), 20, DIM).next_to(c, UP, buff=.18) for i, c in enumerate(cards)])
        arrows = VGroup(*[arrow(cards[i][0].get_right(), cards[i + 1][0].get_left(), ratio=.35) for i in range(3)])
        for i, c in enumerate(cards):
            anims = [FadeIn(c, shift=UP * .15), FadeIn(nums[i])]
            if i:
                anims.append(GrowArrow(arrows[i - 1]))
            self.play(*anims, run_time=.7)
            self.wait(.35)
        foot = lines("upstream ETSI OpenOP portal and Edge Application Management API",
                     "on a test deployment", size=19, color=DIM).to_edge(DOWN, buff=.8)
        self.play(FadeIn(foot, shift=UP * .1), run_time=.7)
        self.wait(2.4)
