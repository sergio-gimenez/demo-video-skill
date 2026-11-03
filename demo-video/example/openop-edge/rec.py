"""Record every shot of the OpenOP edge-deployment video, in story order.

The GUI is the upstream ETSI OpenOP portal (labs.etsi.org/rep/oop/code/portal), unmodified, served by vite
on 127.0.0.1:3100 with VITE_PORTAL_BACKEND_URL pointing at a deployed OpenOP backend. Session:
.state-dev.json from login.py (a person signs in; no password is handled here).

    export OPENOP_BACKEND=http://<portal>:31082 KUBE_CONTEXT=<edge cluster context>
    python3 rec.py                  # all shots
    python3 rec.py a2 t3            # single shots
    python3 rec.py cleanup          # remove our profile and instance (not recorded)

Side effects (on that backend): registers profile "podinfo" (provider demo_provider), deploys instance
"podinfo_bcn" in the first edge zone, deletes the instance in a4; cleanup removes the profile.
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "lib"))
from playwright.sync_api import expect  # noqa: E402
import oop  # noqa: E402
from take import Take  # noqa: E402
from term import Clip  # noqa: E402

GUI = oop.GUI
EAM = f"{GUI}/apis/edge-application-management/explore"
SHOTS = HERE / "shots"
WORK = HERE / "work"
STATE = str(HERE / ".state-dev.json")
KUBE = ["kubectl", "--context", os.environ.get("KUBE_CONTEXT", "edge-barcelona")]
PODS = "get pods -A --no-headers -o custom-columns=POD:.metadata.name,STATUS:.status.phase"
CHART = "https://stefanprodan.github.io/podinfo/podinfo-6.7.1.tgz"
RESOURCES = json.dumps({"infraKind": "kubernetes", "applicationResources": {"cpuPool": {
    "numCPU": 1, "memory": 1024, "topology": {"minNumberOfNodes": 1, "minNodeCpu": 1, "minNodeMemory": 1024}}},
    "isStandalone": False}, indent=2)


def clip() -> Clip:
    return Clip(cwd=WORK, prompt_path="~/demo", user="dev", host="laptop")


def podinfo_pods() -> list[tuple[str, str]]:
    """(namespace, pod) of every podinfo pod; the chart names them after the release (podinfo-bcn-…)."""
    out = subprocess.run(KUBE + ["get", "pods", "-A", "--no-headers", "-o",
                                 "custom-columns=NS:.metadata.namespace,POD:.metadata.name"],
                         capture_output=True, text=True, check=True).stdout
    return [tuple(line.split()) for line in out.splitlines() if " podinfo" in line]


def pod_ns() -> str:
    pods = podinfo_pods()
    if not pods:
        raise SystemExit("no podinfo pod found")
    return pods[0][0]


# ---------------------------------------------------------------------- shots
def a1_register() -> None:
    """Home → register an application profile (podinfo Helm chart)."""
    with Take.open(SHOTS / "a1", storage_state=STATE) as take:
        page = take.page
        take.goto(f"{GUI}/")
        take.mark("home")
        take.focus(None)
        take.hold(2500)
        steps = page.get_by_text("Register an application profile")
        take.focus(page.get_by_text("Get started", exact=True), min_w=0.6,
                   union=[page.get_by_text("Check instance status", exact=True)])
        take.hold(1200)
        take.click(steps, settle=1500)
        page.wait_for_url(re.compile(r"/explore/profiles"))
        take.focus(None)
        take.hold(1200)
        take.mark("form")
        take.click(page.get_by_role("button", name="Register application").first, settle=1000)
        dialog = page.get_by_role("dialog")
        take.focus(page.locator("#app-name"), min_w=0.6, union=[page.locator("#app-provider"), page.locator("#app-package-type")])
        take.type(page.locator("#app-name"), "podinfo")
        take.type(page.locator("#app-version"), "6.7.1")
        take.type(page.locator("#app-provider"), "demo_provider")
        take.focus(page.locator("#image-path"), min_w=0.6)
        take.type(page.locator("#image-path"), CHART, delay=25)
        take.hold(600)
        take.focus(page.locator("#app-component-0"), min_w=0.6, union=[page.get_by_label("Component 1, interface 1 ID")])
        take.type(page.locator("#app-component-0"), "podinfo")
        take.type(page.get_by_label("Component 1, interface 1 ID"), "http")
        take.hold(500)
        res = page.locator("#app-resources")
        res.scroll_into_view_if_needed()
        take.focus(res, min_w=0.6)
        take.click(res, settle=300)
        res.fill(RESOURCES)  # pasted: CPU only, no GPU pool
        take.hold(1800)
        submit = dialog.get_by_role("button", name="Register application")
        take.focus(submit, min_w=0.6, union=[dialog.get_by_role("button", name="Cancel")])
        take.click(submit, settle=2000)
        expect(page.get_by_role("dialog")).to_have_count(0, timeout=20_000)
        take.toast("Application profile registered")
        take.mark("registered")
        row = page.get_by_role("row", name=re.compile("podinfo"))
        expect(row).to_be_visible(timeout=20_000)
        take.focus(page.locator("table"), min_w=0.6)
        take.hold(3500)


def a2_deploy() -> None:
    """Instances → create podinfo_bcn in Barcelona → ready → details."""
    for i in oop.call("GET", "/appinstances"):  # a retake starts from no instance
        if i["name"] == "podinfo_bcn":
            oop.call("DELETE", f"/appinstances/{i['appInstanceId']}")
            for _ in range(60):
                if not any(x["name"] == "podinfo_bcn" for x in oop.call("GET", "/appinstances")):
                    break
                time.sleep(3)
    with Take.open(SHOTS / "a2", storage_state=STATE) as take:
        page = take.page
        take.goto(f"{EAM}/instances")
        take.mark("instances")
        take.focus(None)
        take.hold(1500)
        take.click(page.get_by_role("button", name="Create instance").first, settle=1000)
        dialog = page.get_by_role("dialog")
        take.focus(dialog, min_w=0.55)
        take.type(dialog.get_by_placeholder(re.compile("video_")), "podinfo_bcn")
        take.move(dialog.locator("#instance-app"), dur=0.8)
        take.hold(900)
        zone = dialog.get_by_text("Barcelona")
        take.click(zone, settle=900)
        dialog.locator("input[type=radio]").first.check(force=True)
        take.hold(800)
        take.click(dialog.locator("button[type=submit]"), settle=1500)
        expect(page.get_by_role("dialog")).to_have_count(0, timeout=20_000)
        take.mark("created")
        row = page.get_by_role("row", name=re.compile("podinfo_bcn"))
        expect(row).to_be_visible(timeout=20_000)
        take.focus(page.locator("table"), min_w=0.6)
        take.hold(2500)
        t0 = take.t()
        for _ in range(60):
            if "ready" in row.inner_text():
                break
            take.click(page.get_by_role("button", name="Refresh"), settle=4000)
            row = page.get_by_role("row", name=re.compile("podinfo_bcn"))
        else:
            raise SystemExit("podinfo_bcn never became ready")
        take.focus(page.locator("table"), min_w=0.6)
        take.toast(f"Ready in Barcelona · {take.t() - t0:.0f} s")
        take.hold(2500)
        take.mark("details")
        take.click(page.get_by_role("button", name="Actions for podinfo_bcn"), settle=900)
        take.click(page.get_by_role("menuitem", name="Details"), settle=1200)
        take.focus(page.get_by_role("dialog"), min_w=0.5)
        take.hold(4000)
        take.click(page.get_by_role("dialog").get_by_role("button", name="Close").last, settle=800)
        take.focus(None)
        take.hold(800)


def t3_check() -> None:
    ns = pod_ns()
    c = clip()
    c.say("# the instance is a pod on the Barcelona edge cluster")
    c.run(f"{' '.join(KUBE)} {PODS} | grep podinfo", display=f"kubectl {PODS} | grep podinfo", hold=3)
    c.say("# and the app answers (port forwarded from the cluster)")
    c.run(f"{' '.join(KUBE)} -n {ns} port-forward $({' '.join(KUBE)} -n {ns} get svc -o name | grep podinfo | head -1) "
          f"9898:9898 >/dev/null 2>&1 & PF=$!; sleep 2; curl -s localhost:9898 | jq '{{hostname, version, message}}'; kill $PF",
          display="curl -s localhost:9898 | jq '{hostname, version, message}'", hold=4)
    c.record(SHOTS / "t3")


def ensure_instance() -> None:
    """For a retake of a4: deploy podinfo_bcn off-camera if it is not there."""
    if any(i["name"] == "podinfo_bcn" for i in oop.call("GET", "/appinstances")):
        return
    app = next(a for a in oop.call("GET", "/apps") if a["name"] == "podinfo")
    zone = oop.call("GET", "/edge-cloud-zones")[0]
    oop.call("POST", "/appinstances", {"name": "podinfo_bcn", "appId": app["appId"],
                                       "edgeCloudZoneId": zone["edgeCloudZoneId"]})
    for _ in range(60):
        if any(i["name"] == "podinfo_bcn" and i["status"] == "ready" for i in oop.call("GET", "/appinstances")):
            break
        time.sleep(3)
    for _ in range(40):
        if podinfo_pods():
            break
        time.sleep(3)


def a4_remove() -> None:
    """Delete podinfo_bcn: the row goes at once; the pod follows on the cluster (t5)."""
    ensure_instance()
    with Take.open(SHOTS / "a4", storage_state=STATE) as take:
        page = take.page
        take.goto(f"{EAM}/instances")
        take.mark("instances")
        row = page.get_by_role("row", name=re.compile("podinfo_bcn"))
        expect(row).to_be_visible(timeout=20_000)
        take.focus(page.locator("table"), min_w=0.6)
        take.hold(1500)
        take.click(page.get_by_role("button", name="Actions for podinfo_bcn"), settle=900)
        take.click(page.get_by_role("menuitem", name="Delete"), settle=1000)
        alert = page.get_by_role("alertdialog")
        take.focus(alert, min_w=0.5)
        take.hold(1800)
        take.click(alert.get_by_role("button", name="Delete"), settle=1500)
        take.mark("deleted")
        expect(page.get_by_role("row", name=re.compile("podinfo_bcn"))).to_have_count(0, timeout=60_000)
        take.toast("Instance removed")
        take.focus(None)
        take.hold(3000)


def t5_gone() -> None:
    for _ in range(40):  # the pod terminates shortly after the instance is gone
        if not podinfo_pods():
            break
        time.sleep(3)
    c = clip()
    c.say("# and on the edge cluster")
    c.run(f"{' '.join(KUBE)} {PODS} | grep podinfo || echo 'no podinfo pods'",
          display=f"kubectl {PODS} | grep podinfo || echo 'no podinfo pods'", hold=3.5)
    c.record(SHOTS / "t5")


def cleanup() -> None:
    print("removed profiles:", oop.cleanup(("podinfo",)))


SHOT_LIST = {"a1": a1_register, "a2": a2_deploy, "t3": t3_check, "a4": a4_remove, "t5": t5_gone, "cleanup": cleanup}

if __name__ == "__main__":
    WORK.mkdir(exist_ok=True)
    names = sys.argv[1:] or ["a1", "a2", "t3", "a4", "t5", "cleanup"]
    for name in names:
        print(f"== {name}", flush=True)
        SHOT_LIST[name]()
