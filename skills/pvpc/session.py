#!/usr/bin/env python3
"""A run's phone from start to end. Every script's run goes through main(), and home.start() calls ready().

- iPhone: ready() opens iPhone Mirroring if it isn't open, and waits until it has connected to the iPhone. If it can't
  reach the iPhone, it quits and opens iPhone Mirroring once more. close() quits iPhone Mirroring.
- Android: ready() wakes the phone and unlocks it. With a PIN on the phone, the PIN comes from PIN_FILE (one line,
  digits only, outside the repo so it's never committed). Tried once a run: wrong PINs lock the phone out for longer
  each time. close() locks the phone.
- main(body) runs a script's body: STOPPED / interrupted / CRASHED lines and exit codes 1 / 130 / 2, the run folder
  at the end, and close() if the run opened the phone. A run that never touched the phone (a usage error, a plan step)
  leaves it alone. POGO_KEEP_OPEN=1 leaves the phone as it is at the end.

  POGO_PHONE=android python3 session.py open     wake and unlock the Pixel (iPhone: open iPhone Mirroring)
  POGO_PHONE=android python3 session.py close    lock the Pixel (iPhone: quit iPhone Mirroring)
"""
import os, re, subprocess, sys, time

import ui
import run as base
from run import Stop, log, keep_capture

PIN_FILE = os.path.expanduser("~/.config/pogo/android-pin")
MIRRORING = "iPhone Mirroring"
CONNECT_TIMEOUT = 30  # seconds for iPhone Mirroring to show the iPhone
TROUBLE = ("IPHONE IN USE", "IPHONE IS LOCKED", "UNLOCK YOUR IPHONE", "UNABLE TO CONNECT", "CAN'T CONNECT",
           "COULDN'T CONNECT", "NOT NEARBY")

opened = False  # this run opened the phone: main() closes it at the end
pin_failed = False  # the PIN didn't work once: never typed again this run


def flag(name):
    return os.environ.get(name, "") not in ("", "0")


# ---------- Android ----------

def adb_ok():
    if ui.android.adb("get-state").strip() != "device":
        raise Stop("phone not connected: plug it in, turn on USB debugging, and tap Allow on the phone")


def awake():
    return "mWakefulness=Awake" in ui.android.shell("dumpsys power | grep -m1 mWakefulness=")


def locked():
    out = ui.android.shell("dumpsys window | grep -E 'isKeyguardShowing=|mIsShowing='")
    return "=true" in out


def read_pin():
    try:
        with open(PIN_FILE) as f:
            pin = f.read().strip()
    except FileNotFoundError:
        return None
    if not re.fullmatch(r"\d{4,16}", pin):
        raise Stop(f"{PIN_FILE} should hold the phone's PIN: digits only, one line")
    return pin


def unlock():
    """phone awake and unlocked. A lock screen with no PIN opens with a swipe; with a PIN, PIN_FILE's PIN goes in"""
    global pin_failed
    a = ui.android
    if not awake():
        a.shell("input keyevent KEYCODE_WAKEUP")
        time.sleep(1.0)
    if not locked():
        return
    log("the phone is locked: unlocking it")
    w, h = a.size()
    a.shell(f"input swipe {w // 2} {int(h * 0.85)} {w // 2} {int(h * 0.3)} 250")  # up off the lock screen
    time.sleep(1.2)
    if not locked():
        return
    pin = read_pin()
    if not pin:
        raise Stop(f"the phone is locked: unlock it, or write its PIN in {PIN_FILE} (digits only) "
                   f"so the scripts can")
    if pin_failed:
        raise Stop("the phone is locked and its PIN didn't work earlier: unlock it by hand")
    a.shell(f"input text {pin}")  # (never logged)
    a.shell("input keyevent KEYCODE_ENTER")
    for _ in range(8):  # the lock screen takes a moment to go
        time.sleep(0.5)
        if not locked():
            log("unlocked the phone")
            return
    pin_failed = True
    raise Stop(f"the PIN in {PIN_FILE} didn't unlock the phone. Not trying again (wrong PINs lock the phone out): "
               f"fix the file, or unlock it by hand")


def lock():
    """screen off and locked. KEYCODE_SLEEP only turns the screen off: it locks right away with the phone's
    'Power button instantly locks' on, else after its 'Lock after screen timeout' time"""
    a = ui.android
    if awake():
        a.shell("input keyevent KEYCODE_SLEEP")
    return True


# ---------- iPhone ----------

def mirroring_running():
    return subprocess.run(["pgrep", "-x", MIRRORING], capture_output=True).returncode == 0


def quit_mirroring():
    try:
        ok = subprocess.run(["osascript", "-e", f'quit app "{MIRRORING}"'], timeout=10,
                            capture_output=True).returncode == 0
    except subprocess.TimeoutExpired:
        ok = False
    if not ok:
        ok = subprocess.run(["pkill", "-x", MIRRORING]).returncode == 0
    return ok


def mirroring_screen():
    """'none' (no window), 'connecting', 'trouble' (can't reach the iPhone) or 'up', and the screen's text"""
    try:
        path = ui.capture()[0]
    except ui.Refused:
        return "none", ""
    j = " ".join(t[4].upper() for t in ui.ocr(path))
    if "CONNECTING" in j:
        return "connecting", j
    if any(w in j for w in TROUBLE):
        return "trouble", j
    return "up", j


def connect():
    """iPhone Mirroring open and showing the iPhone. Opened once more if it can't reach it"""
    for attempt in range(2):
        if not mirroring_running():
            log("opening iPhone Mirroring")
        base.front()  # opens it (after you've left the Mac alone a moment: it takes the keyboard)
        end = time.time() + CONNECT_TIMEOUT
        while time.time() < end:
            state, j = mirroring_screen()
            if state == "up":
                return
            if state == "trouble":
                break
            time.sleep(1.0)
        keep_capture("mirroring")
        if attempt == 0:
            log(f"iPhone Mirroring can't reach the iPhone ({state}: {j[:80]}): opening it again")
            quit_mirroring()
            time.sleep(2.0)
    raise Stop("iPhone Mirroring can't reach the iPhone: lock the iPhone, leave it near the Mac, and run again")


# ---------- a run ----------

def ready():
    """the phone ready to be seen and tapped. Cheap after the first time: home.start() calls it every time
    (a Mirroring that loses the iPhone later shows as home.where()'s 'mirroring' screen)"""
    global opened
    if ui.ANDROID:
        adb_ok()
        unlock()
    elif not opened or not mirroring_running():
        connect()
    opened = True


def close():
    """the end of a run: lock the Pixel, or quit iPhone Mirroring"""
    if flag("POGO_KEEP_OPEN"):
        return
    if ui.ANDROID:
        if ui.android.adb("get-state").strip() == "device":
            lock()
            log("locked the phone")
        if not ui.android.NO_WINDOW:
            ui.android.close()
    elif mirroring_running():
        log("quit iPhone Mirroring" if quit_mirroring() else "couldn't quit iPhone Mirroring")


def limit(a, default=10 ** 9):
    """--limit N from a script's arguments"""
    return int(a[a.index("--limit") + 1]) if "--limit" in a else default


def main(body, *args):
    """run a script's body(*args), then close the phone if the run opened it. Exits with 0, 1 (stopped),
    130 (interrupted) or 2 (crashed). A sys.exit() in the body keeps its own code"""
    code = 0
    try:
        body(*args)
    except SystemExit as e:
        code = e.code
    except Stop as e:
        keep_capture("stop")
        log(f"STOPPED: {e}")
        code = 1
    except KeyboardInterrupt:
        log("interrupted")
        code = 130
    except Exception as e:
        keep_capture("crash")
        log(f"CRASHED: {type(e).__name__}: {e}")
        code = 2
    finally:
        if opened:
            try:
                close()
            except Exception as e:  # never hide the run's own end
                log(f"couldn't close the phone: {type(e).__name__}: {e}")
        if base.RUN_DIR and os.path.isdir(base.RUN_DIR):
            print(f"run folder: {base.RUN_DIR}", flush=True)
    sys.exit(code)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a not in (["open"], ["close"]):
        sys.exit(__doc__)
    base.RUN_DIR = "/tmp/pogo_session"
    try:
        ready() if a == ["open"] else close()
    except Stop as e:
        sys.exit(f"STOPPED: {e}")
