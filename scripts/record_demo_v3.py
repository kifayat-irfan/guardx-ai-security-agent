"""GuardX demo V3 screen recorder — real SenseNova AI story.

Captures the REAL dashboard via headless Chromium + CDP screenshots,
driving the actual UI. The incident shown is a genuine SenseNova-analyzed
incident (created live before recording); nothing is fabricated.

Frames -> /tmp/guardx_frames_v3/frame_%05d.jpg (6 fps)
Events -> /tmp/guardx_v3_events.jsonl
"""
import base64
import json
import os
import sys
import threading
import time
import urllib.request

import websocket

CDP_URL = "http://127.0.0.1:9222"
DASHBOARD = "http://127.0.0.1:3000/"
BACKEND = "http://127.0.0.1:8000"
FRAMES = "/tmp/guardx_frames_v3"
EVENTS_LOG = "/tmp/guardx_v3_events.jsonl"
FPS = 6

# the real SenseNova-analyzed incident (created live pre-recording)
INFO = json.load(open("/tmp/guardx_v3_incident.json"))
INCIDENT_ID = INFO["incident_id"]
ID_PREFIX = INCIDENT_ID[:8]

t0 = time.time()
events = []


def log_event(kind: str, payload: dict):
    events.append({"t": round(time.time() - t0, 2), "kind": kind,
                   "payload": payload})


def sse_listener(stop):
    req = urllib.request.Request(BACKEND + "/api/v1/events/stream",
                                 headers={"Accept": "text/event-stream"})
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            buf = ""
            while not stop.is_set():
                chunk = resp.read(1024).decode("utf-8", "replace")
                if not chunk:
                    break
                buf += chunk
                while "\n\n" in buf:
                    raw, buf = buf.split("\n\n", 1)
                    name, data = "message", ""
                    for line in raw.splitlines():
                        if line.startswith("event:"):
                            name = line[6:].strip()
                        elif line.startswith("data:"):
                            data = line[5:].strip()
                    if name in ("zone_event", "incident"):
                        try:
                            payload = json.loads(data) if data else {}
                        except Exception:
                            payload = {"raw": data[:200]}
                        kind = payload.get("event_type", name) \
                            if name == "zone_event" else name
                        log_event(kind, payload)
    except Exception as e:
        log_event("sse_error", {"error": str(e)[:200]})


class CDP:
    def __init__(self, ws_url: str):
        self.ws = websocket.create_connection(ws_url, timeout=60)
        self._id = 0

    def send(self, method: str, params: dict | None = None, timeout: float = 60):
        self._id += 1
        self.ws.send(json.dumps({"id": self._id, "method": method,
                                 "params": params or {}}))
        end = time.time() + timeout
        while time.time() < end:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result")
        raise TimeoutError(method)

    def evaluate(self, expr: str):
        r = self.send("Runtime.evaluate",
                      {"expression": expr, "returnByValue": True})
        return (r.get("result") or {}).get("value")

    def screenshot(self, path: str):
        r = self.send("Page.captureScreenshot", {"format": "jpeg",
                                                 "quality": 84})
        with open(path, "wb") as f:
            f.write(base64.b64decode(r["data"]))


def main() -> int:
    os.makedirs(FRAMES, exist_ok=True)
    if os.path.exists(EVENTS_LOG):
        os.remove(EVENTS_LOG)
    stop = threading.Event()
    t = threading.Thread(target=sse_listener, args=(stop,), daemon=True)
    t.start()

    tabs = json.loads(urllib.request.urlopen(
        CDP_URL + "/json/list", timeout=10).read())
    page = next(t for t in tabs if t["type"] == "page")
    cdp = CDP(page["webSocketDebuggerUrl"])
    cdp.send("Page.enable")
    cdp.send("Runtime.enable")
    cdp.send("Page.navigate", {"url": DASHBOARD})

    frame = 0

    def hold(seconds: float, label: str = ""):
        nonlocal frame
        n = int(seconds * FPS)
        for _ in range(n):
            s = time.time()
            frame += 1
            cdp.screenshot(f"{FRAMES}/frame_{frame:05d}.jpg")
            dt = time.time() - s
            time.sleep(max(0, 1.0 / FPS - dt))
        print(f"  [{label}] held {seconds:.0f}s -> frame {frame} "
              f"(t={time.time() - t0:.1f}s)", flush=True)

    def scroll_to(sel: str, smooth_s: float = 2.0):
        cdp.evaluate(
            f"document.querySelector('{sel}').scrollIntoView"
            f"({{behavior:'smooth', block:'start'}})")
        hold(smooth_s, f"scroll {sel}")

    def click_text(tag: str, text: str):
        js = ("[...document.querySelectorAll('" + tag + "')]"
              ".find(e => e.textContent.trim().startsWith('" + text + "'))"
              ".click()")
        cdp.evaluate(js)

    def click_incident_row():
        # click the row of the real SenseNova incident (latest first)
        js = (
            "[...document.querySelectorAll('#incidents tbody tr')]"
            f".find(tr => tr.innerText.includes('{ID_PREFIX}'))"
            ".click()"
        )
        cdp.evaluate(js)

    for _ in range(30):
        if cdp.evaluate("document.body.innerText.includes('backend connected')"):
            break
        time.sleep(1)
    print("dashboard ready", flush=True)
    log_event("recording_start", {"incident_id": INCIDENT_ID})

    # --- Beat 1: command center (rec 0-12) ---
    print("beat 1: command center", flush=True)
    cdp.evaluate("window.scrollTo({top:0, behavior:'smooth'})")
    hold(5, "overview")
    scroll_to("#live")
    hold(5, "live feed")

    # --- Beat 2: vision (rec 12-30) ---
    print("beat 2: vision", flush=True)
    scroll_to("#cameras")
    hold(16, "vision (real YOLO)")

    # --- Beat 3: security event + incident (rec 30-48) ---
    print("beat 3: incident detected", flush=True)
    scroll_to("#incidents")
    hold(4, "incident list")
    click_incident_row()
    hold(12, "incident detail (real AI analysis)")
    log_event("incident_beat_end", {})

    # --- Beat 4: RAG / policies (rec 48-62) ---
    print("beat 4: policies / RAG", flush=True)
    scroll_to("#policies")
    hold(12, "policies")

    # --- Beat 5: LangGraph workflow (rec 62-78) ---
    print("beat 5: workflow", flush=True)
    scroll_to("#workflow")
    hold(4, "workflow idle")
    click_text("button", "Run workflow")
    print("  workflow running...", flush=True)
    hold(10, "workflow result (real SenseNova)")
    log_event("workflow_end", {})

    # --- Beat 6: persistence (rec 78-90) ---
    print("beat 6: persistence", flush=True)
    scroll_to("#incidents")
    hold(5, "history")
    scroll_to("#live")
    hold(5, "live stream")

    # --- Beat 7: reprocess (rec 90-104) ---
    print("beat 7: reprocess", flush=True)
    scroll_to("#incidents")
    hold(2, "history 2")
    click_incident_row()
    hold(3, "detail 2")
    click_text("button", "Reprocess")
    print("  reprocessing (real)...", flush=True)
    hold(7, "reprocess result")

    # --- Beat 8: health / n8n (rec 104-112) ---
    print("beat 8: health / n8n", flush=True)
    scroll_to("#system")
    hold(6, "health")

    # --- Beat 9: hero (rec 112-120) ---
    print("beat 9: hero", flush=True)
    cdp.evaluate("window.scrollTo({top:0, behavior:'smooth'})")
    hold(2, "scroll top")
    hold(6, "hero")

    stop.set()
    with open(EVENTS_LOG, "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    zones = [e for e in events if e["kind"] == "zone_enter"]
    print(f"DONE: {frame} frames, {len(zones)} zone_enter events logged",
          flush=True)
    for z in zones[:8]:
        print(f"  zone_enter at t={z['t']}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
