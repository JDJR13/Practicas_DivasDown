import sys, time, json, urllib.request
from playwright.sync_api import sync_playwright
OUT, URL = sys.argv[1], "http://127.0.0.1:8123"
def api(): return json.load(urllib.request.urlopen(URL + "/api/state"))
def sim(**k):
    urllib.request.urlopen(urllib.request.Request(URL + "/api/sim", json.dumps(k).encode(), {"Content-Type": "application/json"}))
def wait(pred, t=40):
    t0 = time.time()
    while time.time() - t0 < t:
        s = api()
        if pred(s): return s
        time.sleep(0.05)
    raise TimeoutError(api()["state"])
with sync_playwright() as p:
    b = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    pg = b.new_page(viewport={"width": 1920, "height": 1080})
    logs = []; pg.on("console", lambda m: logs.append(m.text)); pg.on("pageerror", lambda e: logs.append("ERR " + str(e)))
    pg.goto(URL); time.sleep(1.5)
    pg.screenshot(path=f"{OUT}/1_attract.png")
    sim(pot=450); sim(button=True); wait(lambda s: s["state"] == "READY"); time.sleep(1.4)
    pg.screenshot(path=f"{OUT}/2_ready.png")
    sim(button=True); wait(lambda s: s["state"] == "COUNTDOWN"); time.sleep(0.45)
    pg.screenshot(path=f"{OUT}/3_countdown3.png")
    wait(lambda s: s["state"] == "COUNTDOWN" and s["count"] == 1); time.sleep(0.4)
    pg.screenshot(path=f"{OUT}/3b_countdown1.png")
    wait(lambda s: s["state"] == "CAPTURE"); time.sleep(0.12)
    pg.screenshot(path=f"{OUT}/4_flash.png"); time.sleep(0.8)
    pg.screenshot(path=f"{OUT}/4b_capture.png")
    wait(lambda s: s["state"] == "COUNTDOWN" and s["shot"] == 3); time.sleep(0.5)
    pg.screenshot(path=f"{OUT}/4c_shot3.png")
    wait(lambda s: s["state"] == "PROCESSING"); time.sleep(1.2)
    pg.screenshot(path=f"{OUT}/5_processing.png")
    wait(lambda s: s["state"] == "RESULT"); time.sleep(2.2)
    pg.screenshot(path=f"{OUT}/6_result.png")
    pg.evaluate("document.body.dataset.state='SLEEP'"); time.sleep(1.6)
    pg.screenshot(path=f"{OUT}/7_sleep.png")
    print("consola:", logs[:10])
    b.close()
