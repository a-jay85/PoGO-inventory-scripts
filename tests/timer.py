#!/usr/bin/env python3
"""Checks skills/shared/timer.py's tick with no phone: a phone out of reach turns its timers off. A stand-in `adb`
(says the Pixel is there or not) and `osascript` (no real notice) go first on PATH; the jobs are made-up scripts that
print a line. Its own timers.json (POGO_TIMER_CONF), so the real one is never touched.

  python3 tests/timer.py
"""
import json, os, stat, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = tempfile.mkdtemp(prefix="timer-test-")
os.environ["POGO_TIMER_CONF"] = T
BIN = os.path.join(T, "bin")
os.makedirs(BIN)
os.environ["PATH"] = BIN + os.pathsep + os.environ["PATH"]
sys.path.insert(0, os.path.join(ROOT, "skills", "shared"))
import timer

timer.busy = lambda: None  # (a real script on a real phone mustn't hold up the test)


def stub(name, body):
    path = os.path.join(BIN, name)
    with open(path, "w") as f:
        f.write("#!/bin/sh\n" + body + "\n")
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)


stub("osascript", "exit 0")


def pixel(there, idle=60, locked=True):
    """the Pixel on adb or not; idle: minutes since its last touch"""
    if not there:
        return stub("adb", 'echo "error: no devices/emulators found" >&2; exit 1')
    stub("adb", f'if [ "$1" = shell ]; then echo "  lastUserActivityTime=5 ({int(idle * 60000)} ms ago)"; '
                f'echo "  isKeyguardShowing={str(locked).lower()}"; else echo device; fi')


def job(name, phone, line, code=0):
    """a made-up job on phone whose run prints line and ends with code"""
    path = os.path.join(T, f"{name}.py")
    with open(path, "w") as f:
        f.write(f"print({line!r})\nraise SystemExit({code})\n")
    timer.JOBS[name] = (path, lambda: phone, (15, 15))


def fresh(**due):
    for f in (timer.STATE, timer.AWAY, timer.LOG):
        if os.path.exists(f):
            os.remove(f)
    for name, when in due.items():
        timer.at(name, when)


def log():
    return open(timer.LOG).read() if os.path.exists(timer.LOG) else ""


now = time.time()
bad = []


def check(what, ok):
    print(("  ok   " if ok else "  WRONG ") + what)
    if not ok:
        bad.append(what)


REAL = dict(timer.JOBS)
timer.JOBS.clear()
job("pix", "android", "done: 1 thing")
job("pix2", "android", "done: 1 thing")
job("ios", "iphone", "16:21:11 STOPPED: iPhone Mirroring can't reach the iPhone: lock the iPhone, leave it near the Mac",
    1)
job("stops", "android", "15:49:39 STOPPED: no Eggs tab or map in 150s", 1)
job("inuse", "iphone", "12:40:01 STOPPED: you're using the iPhone (iPhone Mirroring says iPhone in Use): run this "
    "after you lock it", 1)
job("crowded", "android", "STOPPED: pid 12 (gift.py) is using the Pixel: run this after it ends", 1)

print("Pixel off adb for a minute: skip, timer stays on")
pixel(False)
fresh(pix=now - 60)
timer.tick()
check("pix still due", "pix" in timer.due())
check("the skip is in the log", "skipped: Pixel not connected over adb" in log())

print("Pixel off adb for 5 min in a row: every Pixel timer off")
fresh(pix=now - 600, pix2=now + 600, ios=now + 600)
json.dump({"android": int(now - 6 * 60)}, open(timer.AWAY, "w"))
timer.tick()
check("pix off", "pix" not in timer.due())
check("pix2 off (same phone, not due yet)", "pix2" not in timer.due())
check("ios still on (other phone)", "ios" in timer.due())
check("the off line says how to turn it back on", "off: the Pixel was off adb" in log() and "timer.py in" in log())
check("the miss count starts again", "android" not in json.load(open(timer.AWAY)))

print("Pixel back on adb after a short miss: runs, miss count cleared")
pixel(True)
fresh(pix=now - 60)
json.dump({"android": int(now - 2 * 60)}, open(timer.AWAY, "w"))
timer.tick()
check("pix ran", "pix: start" in log())
check("pix due again", "pix" in timer.due())
check("miss count cleared", "android" not in json.load(open(timer.AWAY)))

print("iPhone run stops on can't reach the iPhone: iPhone timers off")
fresh(ios=now - 60, pix=now + 600)
timer.tick()
check("ios off", "ios" not in timer.due())
check("pix still on (other phone)", "pix" in timer.due())
check("the off line", "ios off: a ios run couldn't reach the iPhone" in log())

print("a Pixel run that ends fine: next run as before")
fresh(pix=now - 60)
timer.tick()
check("pix due in 15 min", abs(timer.due().get("pix", 0) - (time.time() + 15 * 60)) < 30)

print("a run that stops: its timer off, the others stay")
fresh(stops=now - 60, pix=now + 600)
timer.tick()
check("stops off", "stops" not in timer.due())
check("pix still on", "pix" in timer.due())
check("the off line says how to turn it back on", "stops off: its run ended with exit 1" in log()
      and "timer.py in stops 0" in log())

print("Pixel touched a minute ago: skip, timer stays on, no away count")
pixel(True, idle=1)
fresh(pix=now - 60)
timer.tick()
check("pix didn't run", "pix: start" not in log())
check("pix still due now", timer.due().get("pix", 0) <= time.time())
check("the skip is in the log", "skipped: you're using the Pixel" in log())
check("no away count", not os.path.exists(timer.AWAY) or "android" not in json.load(open(timer.AWAY)))

print("Pixel unlocked, touched 5 min ago: skip")
pixel(True, idle=5, locked=False)
fresh(pix=now - 60)
timer.tick()
check("pix didn't run", "pix: start" not in log())

print("Pixel locked, touched 5 min ago: runs")
pixel(True, idle=5)
fresh(pix=now - 60)
timer.tick()
check("pix ran", "pix: start" in log())

print("Pixel unlocked, untouched 20 min (a run left it so): runs")
pixel(True, idle=20, locked=False)
fresh(pix=now - 60)
timer.tick()
check("pix ran", "pix: start" in log())

print("an iPhone run that found you using it: tries again in 5 min, other iPhone timers stay")
fresh(inuse=now - 60, ios=now + 600)
timer.tick()
check("inuse due in 5 min", abs(timer.due().get("inuse", 0) - (time.time() + 5 * 60)) < 30)
check("ios still on", "ios" in timer.due())
check("no off notice", " off:" not in log())

print("a run that only found another script on the phone: tries again")
fresh(crowded=now - 60)
timer.tick()
check("crowded due again", "crowded" in timer.due())

print("gymfeed on each phone: each sets its own timer, the other one stays")
timer.JOBS.update(REAL)
fresh(**{"gymfeed-iphone": now + 600})
timer.gymfeed(True, "android")
check("gymfeed-pixel due in 30-32 min", 29 * 60 < timer.due().get("gymfeed-pixel", 0) - time.time() < 33 * 60)
check("gymfeed-iphone as it was", timer.due().get("gymfeed-iphone") == int(now + 600))
timer.gymfeed(False, "iphone")
check("gymfeed-iphone off", "gymfeed-iphone" not in timer.due())
check("gymfeed-pixel still on", "gymfeed-pixel" in timer.due())
check("both jobs known, one per phone", {n: p() for n, (_, p, _) in REAL.items() if n.startswith("gymfeed")}
      == {"gymfeed-pixel": "android", "gymfeed-iphone": "iphone"})

print(f"\n{'all timer cases right' if not bad else f'{len(bad)} WRONG'} ({T})")
sys.exit(1 if bad else 0)
