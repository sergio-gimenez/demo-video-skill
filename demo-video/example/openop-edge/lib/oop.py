"""OEG calls through the local GUI's /api/ proxy with the saved session (setup and cleanup only)."""
import json, os, time, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
GUI = os.environ.get("OPENOP_GUI", "http://127.0.0.1:3100")
API = GUI + "/api/oeg/edge-application-management/v0.1alpha1"
STATE = HERE / ".state-dev.json"


def call(method, path, body=None):
    cookies = "; ".join(f"{c['name']}={c['value']}" for c in json.loads(STATE.read_text())["cookies"])
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Cookie": cookies, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        return json.loads(data) if data else None


def cleanup(names=("podinfo",)):
    """Remove our instances, then our profiles (only ones named in `names`)."""
    apps = {a["appId"]: a for a in call("GET", "/apps") if a["name"] in names}
    for i in call("GET", "/appinstances"):
        if i["appId"] in apps:
            call("DELETE", f"/appinstances/{i['appInstanceId']}")
    for _ in range(60):
        if not [i for i in call("GET", "/appinstances") if i["appId"] in apps]:
            break
        time.sleep(3)
    for app_id in apps:
        call("DELETE", f"/apps/{app_id}")
    return len(apps)


if __name__ == "__main__":
    print("removed profiles:", cleanup(), "| left:", [a["name"] for a in call("GET", "/apps")],
          [i["name"] for i in call("GET", "/appinstances")])
