#!/usr/bin/env python3
"""One phone for /trade, run as its own process: trade.py starts one for the iPhone and one for the Android phone.
ui.py and android.py keep one phone's state in module globals, so each phone gets a process of its own.

  POGO_PHONE=android python3 phone.py <name>     (or no POGO_PHONE for the iPhone)

Reads one JSON request a line on stdin, answers one JSON line on stdout:
  {"op": "look"}                    -> {"path", "bounds", "texts": [[x, y, w, h, text], ...]}
  {"op": "tap", "fx", "fy"}         a tap at window fractions (iPhone: iPhone Mirroring brought forward first)
  {"op": "type", "text"}            {"op": "key", "name"}
Errors come back as {"error": "..."}.
"""
import json, os, random, sys, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
import ui
import run as base

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
    bounds = last or ui.capture()[1]
    x, y = base.to_points(fx, fy, bounds)
    ui.sh(ui.HELPER, "click", f"{x:.1f}", f"{y:.1f}", str(random.randint(50, 100)))


def main():
    proto = sys.stdout
    sys.stdout = sys.stderr  # run.log() prints: keep it off the answer line
    ui.ensure_helper()
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
            else:
                out = {"error": f"unknown op {op}"}
        except (ui.Refused, base.Stop) as e:
            out = {"error": str(e)}
        except Exception:
            out = {"error": traceback.format_exc()}
        print(json.dumps(out), file=proto, flush=True)


if __name__ == "__main__":
    main()
