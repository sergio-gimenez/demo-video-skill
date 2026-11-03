"""Sign in once as the demo developer and save the session for the OpenOP-branded local GUI.

    python3 login.py            # opens a browser window on the test portal; sign in there

The GUI under test runs locally (vite on 127.0.0.1:3100, OpenOP brand) and proxies /api/
to the test backend, but Keycloak only redirects back to the backend's own address. So the
login happens on the backend's address and its session cookies are copied to 127.0.0.1.
The password is typed by a person in the window; nothing here reads or stores it.
"""

import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

BACKEND = os.environ["OPENOP_BACKEND"]  # the deployed portal, e.g. http://portal.example:31082
OUT = Path(__file__).parent / ".state-dev.json"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, executable_path="/usr/bin/chromium")
    context = browser.new_context(viewport={"width": 1280, "height": 860})
    page = context.new_page()
    page.goto(BACKEND + "/")
    print("Sign in in the browser window; this waits until the portal answers /api/auth/me.")
    page.wait_for_url(BACKEND + "/**", timeout=0)
    while page.request.get(BACKEND + "/api/auth/me").status != 200:
        page.wait_for_timeout(1000)
    state = context.storage_state()
    host = BACKEND.split("//")[1].split(":")[0]
    state["cookies"] = [{**c, "domain": "127.0.0.1"} for c in state["cookies"] if c["domain"].lstrip(".") == host]
    state["origins"] = []
    OUT.write_text(json.dumps(state))
    OUT.chmod(0o600)
    print(f"saved {len(state['cookies'])} cookie(s) for 127.0.0.1 → {OUT.name}")
    browser.close()
