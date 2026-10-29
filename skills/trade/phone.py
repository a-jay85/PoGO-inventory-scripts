#!/usr/bin/env python3
"""One phone for /trade, run as its own process: trade.py starts one for the iPhone and one for the Android phone.
ui.py and android.py keep one phone's state in module globals, so each phone gets a process of its own.

  POGO_PHONE=android python3 phone.py <name>     (or no POGO_PHONE for the iPhone)

Reads one JSON request a line on stdin, answers one JSON line on stdout:
  {"op": "look"}                    -> {"path", "bounds", "texts": [[x, y, w, h, text], ...]}
  {"op": "tap", "fx", "fy"}         a tap at window fractions (iPhone: iPhone Mirroring brought forward first)
  {"op": "type", "text"}            {"op": "key", "name"}
  {"op": "search", "q"}             type q into the open search panel's bar -> {"ok"}: the bar reads q
  {"op": "restart"}                 force-close Pokémon GO and open it again (doesn't wait for it to load)
  {"op": "start", "run_dir"}        open Pokémon GO if it isn't, and wait until it's loaded -> {"screen"}
  {"op": "unstick", "texts", "backs"}  one step out of a screen nobody knows (Android: Back; iPhone: reopen the game)
  {"op": "ready"}                   wake and unlock the Pixel, or open iPhone Mirroring (trade.py look: a run's end
                                    closed them). "close" undoes it only if the phone wasn't up before
  {"op": "close"}                   the run's end: lock the Pixel, or quit iPhone Mirroring (if "start"/"ready" opened it)
Errors come back as {"error": "..."}.
"""
import json, os, random, sys, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
import ui
import run as base
import home, search, session

NAME = sys.argv[1]
ui.CAP = f"/tmp/trade_{NAME}.png"  # each phone its own capture: with one shared file a phone could read the other's
last = None  # the latest look's bounds: taps are placed in it


def look():
    global last
    path, bounds = ui.capture()
    last = bounds
    return {"path": path, "bounds": bounds, "texts": [list(t) for t in ui.ocr(path)]}


def tap(fx, fy):
    base.front()  # iPhone: a click while another app is in front only brings the window forward, and is lost
    # (front() before the capture below, as before. trade.py spaces its own taps: no tap gap here, and none counted)
    base.click(fx, fy, last or ui.capture()[1], bring_front=False, spaced=False, counted=False)


def ready():
    """the phone ready to be seen. One that was up already is left up at the end"""
    if ui.ANDROID:
        session.adb_ok()
        was_up = session.awake() and not session.locked()
    else:
        was_up = session.mirroring_running()
    session.ready()
    if was_up:
        session.opened = False  # close() leaves it alone


def restart():
    if ui.ANDROID:
        pkg = ui.android.PKG
        ui.android.shell(f"am force-stop {pkg}; monkey -p {pkg} -c android.intent.category.LAUNCHER 1")
        return
    # iPhone, through iPhone Mirroring's own shortcuts: cmd+2 the App Switcher, cmd+1 the home screen
    base.key("2", cmd=True)
    time.sleep(2)
    bounds = ui.capture()[1]
    x1, y1 = base.to_points(0.5, 0.6, bounds)  # Pokémon GO's card, in the middle: swipe it off the top
    x2, y2 = base.to_points(0.5, 0.05, bounds)
    base.front()
    ui.sh(ui.HELPER, "drag", f"{x1:.1f}", f"{y1:.1f}", f"{x2:.1f}", f"{y2:.1f}", "250")
    time.sleep(1.5)
    home.iphone_open()


def main():
    proto = sys.stdout
    sys.stdout = sys.stderr  # run.log() prints: keep it off the answer line
    ui.ensure_helper()
    # iPhone: type the searches key by key (about 2 s). The paste never landed in the trade picker (2026-10-24), and
    # finding that out cost two lost pastes, 15-20 s, every run
    search.PASTE["ok"] = False
    for line in sys.stdin:
        req = json.loads(line)
        out = {}
        try:
            op = req["op"]
            if op == "look":
                out = look()
            elif op == "tap":
                tap(req["fx"], req["fy"])
            elif op == "type":
                base.type_text(req["text"])
            elif op == "key":
                base.key(req["name"])
            elif op == "search":  # (iPhone: typed key by key; Android: adb types it)
                out = {"ok": search.type_into_panel(req["q"], last or ui.capture()[1])}
            elif op == "ready":
                ready()
            elif op == "restart":
                restart()
            elif op == "start":
                base.new_run_dir(None, req["run_dir"])  # its log lines and captures go with trade.py's
                out = {"screen": home.start(storage=False)}
            elif op == "unstick":
                home.backs = req["backs"]  # each trip to the friend page gets its own allowance
                home.reopened = req["backs"] > 0  # iPhone: one reopen a trip too
                home.unstick(req["texts"])
            elif op == "close":
                if session.opened:
                    session.close()
            else:
                out = {"error": f"unknown op {op}"}
        except (ui.Refused, base.Stop) as e:
            out = {"error": str(e)}
        except Exception:
            out = {"error": traceback.format_exc()}
        print(json.dumps(out), file=proto, flush=True)


if __name__ == "__main__":
    main()
