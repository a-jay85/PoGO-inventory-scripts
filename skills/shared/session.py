#!/usr/bin/env python3
"""A run's phone from start to end. Every script's run goes through main(), and home.start() calls ready().

- iPhone: ready() opens iPhone Mirroring if it isn't open, and waits until it has connected to the iPhone. If it can't
  reach the iPhone, it quits and opens iPhone Mirroring once more. close() goes to its home screen (cmd+1), then quits iPhone Mirroring.
- Android: ready() wakes the phone and unlocks it, and turns its brightness to the lowest (1, which the screen shows as 0) for the run (close() puts it back). With a PIN on the phone, the PIN comes from PIN_FILE (one line,
  digits only, outside the repo so it's never committed). A PIN that fails is never typed again that run: wrong PINs
  lock the phone out for longer each time. It's typed again only if the phone locks itself mid-run after it worked.
  First, once per run: a Pixel on over a day with under 1 GB free for apps is slow (the game drops taps), so it's
  restarted (about a minute). POGO_NO_RESTART=1 only says so; POGO_RESTART=1 restarts it anyway. Every run logs the
  phone's 'on, MB free, load, battery' line at its start and at its end, with the battery used and a row in
  BATTERY_LOG (to see the battery use over time when it's unplugged).
  close() goes to the home screen (the game to the back), then locks the phone.
  Location: once the game is up, home.start() turns the Pixel's location off for the run (gps_off), and close()
  turns it on again. Scripts that need it (NEEDS_GPS: gyms, catching, trades and the distance100- search) keep it
  on, and turn it on again if a killed run left it off. POGO_GPS=1 keeps it on for any script.
- main(body) runs a script's body: STOPPED / interrupted / CRASHED lines and exit codes 1 / 130 / 2, the run folder
  at the end, and close() if the run opened the phone. A run that never touched the phone (a usage error, a plan step)
  leaves it alone. POGO_KEEP_OPEN=1 leaves the phone as it is at the end.

  POGO_PHONE=android python3 session.py open     wake and unlock the Pixel (iPhone: open iPhone Mirroring)
  POGO_PHONE=android python3 session.py close    lock the Pixel (iPhone: quit iPhone Mirroring)
  python3 session.py busy    what's using each phone now, one short line each (touches no phone)
"""
import fcntl, os, re, subprocess, sys, time, traceback

HERE = os.path.dirname(os.path.realpath(__file__))
import ui
import base
import locks
from base import Stop, log, keep_capture

PIN_FILE = os.path.expanduser("~/.config/pogo/android-pin")
MIRRORING = "iPhone Mirroring"
CONNECT_TIMEOUT = 30  # seconds for iPhone Mirroring to show the iPhone
TROUBLE = ("IPHONE IN USE", "IPHONE IS LOCKED", "UNLOCK YOUR IPHONE",  # Mirroring can't reach the iPhone
           "CONNECTION INTERRUPTED",  # (the iPhone went out of reach mid-run, 2026-11-01)
           "IPHONE NOT FOUND",  # (reopened right after that: the iPhone not back yet, 2026-11-02)
           "IPHONE MIRRORING TIMED OUT",  # (used while connecting: read as "up", and its Connect button waits, 2026-11-04)
           "AN ERROR OCCURRED. PLEASE TRY AGAIN")  # Mirroring's own grey "Error" page with a phone icon and Try Again:
#            it lost the iPhone. Opening Mirroring again reconnects (2026-11-11: /trade stopped on it as an unknown screen)

NEEDS_GPS = {"gymfeed.py", "goplus.py", "trade.py",  # gyms, catching, nearby trades
             "phone.py",  # /trade's own process per phone: it runs home.start(), which turned location off
             "tradeable.py", "specieswise.py",  # 'distance100-' measures from where the phone is now
             "account.py"}  # a sign-in: the game may want the map
BOX_WAIT = 3  # seconds the 'No location access' box gets to come up after location goes off (later: android.ready)
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
    # only these two sections: plain 'dumpsys window' starts with the last ANR's snapshot, which can hold an old
    # isKeyguardShowing=true for as long as no other app hangs (2026-10-27)
    out = ui.android.shell("dumpsys window displays | grep isKeyguardShowing=; "
                           "dumpsys window policy | grep mIsShowing=")
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
    try:
        a.shell(f"input text {pin}", timeout=15)
        a.shell("input keyevent KEYCODE_ENTER", timeout=15)
    except subprocess.TimeoutExpired:  # its message holds the command, PIN and all: never let it reach a log
        raise Stop("typing the PIN timed out: unlock the phone by hand") from None
    for _ in range(8):  # the lock screen takes a moment to go
        time.sleep(0.5)
        if not locked():
            log("unlocked the phone")
            return
    pin_failed = True
    raise Stop(f"the PIN in {PIN_FILE} didn't unlock the phone. Not trying again (wrong PINs lock the phone out): "
               f"fix the file, or unlock it by hand")


WORN_UP = 24 * 3600  # s on: a Pixel on this long with WORN_MB or less free gets restarted at a run's start
WORN_MB = 1024  # MB the phone can still give apps (MemAvailable). 2026-11-19: 1d15h up, 690 MB, and the game
#                 dropped taps for 7-33 s each time it came back. A fresh restart: 3.1 GB. Down to 0.8 GB 24 min later
#                 with the game open, so memory alone says little: the day on is what counts
BOOT_TIMEOUT = 180  # s for a restarted phone to say it's up


def health():
    """-> (seconds on, MB free for apps, 1-minute load, battery %, plugged in). MemFree says little: Android keeps
    it low on purpose"""
    text = ui.android.shell("cat /proc/uptime /proc/loadavg; grep MemAvailable /proc/meminfo; "
                            "dumpsys battery | grep -E -m4 ' level:|powered:'")
    out = text.split()
    return (float(out[0]), int(out[out.index("MemAvailable:") + 1]) // 1024, float(out[2]),
            int(out[out.index("level:") + 1]), "powered: true" in text)


def say_health(up, mb, load, battery, plugged):
    return (f"on {int(up // 3600)}h{int(up % 3600 // 60):02d}m, {mb} MB free, load {load:.1f}, "
            f"battery {battery}% {'plugged in' if plugged else 'on battery'}")


BATTERY_LOG = os.path.expanduser("~/.config/pogo/phone-battery.csv")  # one row per Pixel run: its battery over time
started = None  # (time, battery %) at this run's start, for the end line


def end_health():
    """the end of a Pixel run: the same line as at its start, with the battery it used, and a row in BATTERY_LOG
    (when, script, minutes, battery at the start and end, plugged in) to see the battery use over time unplugged"""
    reading = health()
    battery, plugged = reading[3], reading[4]
    used = ""
    if started:
        mins = (time.time() - started[0]) / 60
        used = f" ({battery - started[1]:+d}% in {mins:.0f} min)"
        new = not os.path.exists(BATTERY_LOG)
        os.makedirs(os.path.dirname(BATTERY_LOG), exist_ok=True)
        with open(BATTERY_LOG, "a") as f:
            if new:
                f.write("end,script,minutes,start %,end %,plugged in\n")
            f.write(f"{time.strftime('%Y-%m-%d %H:%M')},{os.path.basename(sys.argv[0])},{mins:.1f},"
                    f"{started[1]},{battery},{'yes' if plugged else 'no'}\n")
    log(f"phone at the end: {say_health(*reading)}{used}")


def restart_if_worn():
    """a Pixel on a long time with little memory free is slow: the game drops taps and reads come late. Then it's
    restarted (about a minute) before the run uses it. Once per run, at its start, never mid-run.
    POGO_NO_RESTART=1: only says it would. POGO_RESTART=1: restarts it whatever its numbers"""
    global started
    up, mb, load, battery, plugged = health()
    started = (time.time(), battery)
    log(f"phone: {say_health(up, mb, load, battery, plugged)}")
    if not flag("POGO_RESTART") and (up < WORN_UP or mb > WORN_MB):  # (a chain's next step finds it fresh)
        return
    if flag("POGO_NO_RESTART"):
        log("  the phone is worn (long on, little memory free): a restart would speed it up (POGO_NO_RESTART set)")
        return
    log("  the phone is worn (long on, little memory free): restarting it first (about a minute)")
    t0 = time.time()
    ui.android.adb("reboot", timeout=60)
    end = t0 + BOOT_TIMEOUT
    while time.time() < end:  # adb drops, then comes back before the phone is done starting
        time.sleep(3)
        try:
            # boot done, and settings answering: right after the boot says done, 'settings get' printed nothing and
            # dim() crashed (2026-11-19)
            out = ui.android.shell("getprop sys.boot_completed; settings get system screen_brightness",
                                   timeout=10).split()
            if out[:1] == ["1"] and len(out) == 2 and out[1].isdigit():
                break
        except subprocess.TimeoutExpired:
            pass
    else:
        raise Stop(f"restarted the phone, but it didn't come back in {BOOT_TIMEOUT}s: check it's on and plugged in")
    time.sleep(5)  # the lock screen and the window manager settle
    unlock()
    # the first unlock after a restart blanks 'settings get' for a moment: dim() read nothing and crashed (2026-11-19)
    brightness = lambda: ui.android.shell("settings get system screen_brightness", timeout=10).strip()
    if not base.settle(brightness, str.isdigit, 30).isdigit():
        raise Stop("restarted the phone, but its settings never answered: check it, then run again")
    log(f"  restarted in {time.time() - t0:.0f}s: {say_health(*health())}")


def lock():
    """the home screen, then screen off and locked (the Pixel 4 XL shows its lock screen at once: checked
    2026-10-23). The game goes to the back first, so the next unlock opens on the home screen: a game that comes back
    from there checks its eggs and hatches a ready one (the user, 2026-11-14)"""
    if awake():
        ui.android.shell("input keyevent KEYCODE_HOME")
        time.sleep(0.8)
        ui.android.shell("input keyevent KEYCODE_SLEEP")


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
    except ui.Refused as e:
        return "none", str(e)
    j = ui.joined(ui.ocr(path))
    if "CONNECTING" in j:
        return "connecting", j
    if any(w in j for w in TROUBLE):
        return "trouble", j
    return "up", j


def fit():
    """the iPhone Mirroring window at the size the scripts read (ui.SIZE): macOS 27 opens it smaller"""
    try:
        ui.window()
    except ui.Refused:
        return  # no window yet: connect() fits it once it's up
    try:
        was = ui.fit_window()
    except ui.Refused as e:
        raise Stop(f"{e}. Allow this terminal in System Settings > Privacy & Security > Accessibility")
    if was:
        time.sleep(0.5)  # the window redraws at the new size
        now = ui.window()[3:]
        if (round(now[0]), round(now[1])) != ui.SIZE:
            raise Stop(f"set the iPhone Mirroring window to {ui.SIZE[0]} x {ui.SIZE[1]}, but it's "
                       f"{now[0]:.0f} x {now[1]:.0f}")
        log(f"iPhone Mirroring window {was[0]} x {was[1]} -> {ui.SIZE[0]} x {ui.SIZE[1]}")


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
                fit()
                return
            if state == "trouble":
                if "IPHONE IN USE" in j:  # opening it again won't help while it's in your hand. The words must not
                    quit_mirroring()  # say "can't reach": timer.py turns the iPhone's timers off on those
                    raise Stop("you're using the iPhone (iPhone Mirroring says iPhone in Use): run this after you "
                               "lock it")
                break
            time.sleep(1.0)
        if ui.CANT_CAPTURE in j:  # 30 s of this isn't a window still opening. Opening it again won't help (2026-11-04)
            raise Stop("macOS won't let this terminal take pictures of the iPhone Mirroring window. Run from one with "
                       "Screen Recording allowed (System Settings > Privacy & Security). tmux counts as its own app")
        keep_capture("mirroring")
        if attempt == 0:
            log(f"iPhone Mirroring can't reach the iPhone ({state}: {j[:80]}): opening it again")
            quit_mirroring()
            time.sleep(2.0)
    raise Stop("iPhone Mirroring can't reach the iPhone: lock the iPhone, leave it near the Mac, and run again")


# ---------- one script per phone ----------

held = None  # this process's lock file, open for as long as it runs. The system lets go when the process ends


def claim():
    """this phone for this process. -> None once it's ours, or what's using it. Two at once tap over each other: a
    test typing gift searches pulled /cleantrades onto the Friends tab, and it stopped on a screen it didn't know
    (2026-11-05). The lock goes with the process, however it ends"""
    global held
    if held:
        return None
    f = open(locks.path("android" if ui.ANDROID else "iphone"), "a+")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.seek(0)
        who = f.read().strip() or "another script"
        f.close()
        return who
    f.truncate(0)
    f.write(f"pid {os.getpid()} ({' '.join(sys.argv)})\n")
    f.flush()
    held = f
    locks.awake()  # the Mac awake for the whole run
    return None


def busy():
    """what's using each phone now, one short line each, and any other skill script running. Reads the locks claim()
    takes (a held flock means a live run; the pid in a free one is stale), so it touches no phone. For Claude's check
    before a phone test: `ps | grep` matched every Claude process and printed 10-15 KB (2026-11-22)"""
    lines = []
    for phone, name in (("android", "Pixel"), ("iphone", "iPhone")):
        who = locks.holder(phone)
        lines.append(f"{name}: busy, {who[:150]}" if who else f"{name}: free")
    out = subprocess.run(["pgrep", "-fl", r"(skills/[a-z]+/[a-z_]+|pogo)\.py"], capture_output=True, text=True).stdout
    other = [l.split()[0] + " " + (m.group(0)[:120] if (m := re.search(r"\S*(skills/|pogo\.py).*", l)) else l.split(None, 1)[-1][:120])
             for l in out.splitlines() if l[:1].isdigit()
             and not re.match(r"\d+ (\S*/)?(zsh|bash|sh) ", l)  # a shell running a command line that names a script
             and l.split()[0] != str(os.getpid()) and "session.py busy" not in l and "pgrep" not in l]
    lines.append("other skill scripts: " + ("none" if not other else f"{len(other)}\n  " + "\n  ".join(other[:5])))
    return "\n".join(lines)


# ---------- a run ----------

def ready():
    """the phone ready to be seen and tapped. Cheap after the first time: home.start() calls it every time
    (a Mirroring that loses the iPhone later shows as home.where()'s 'mirroring' screen)"""
    global opened
    if who := claim():  # (before opened: main() must not close the phone on the script using it)
        raise Stop(f"{who} is using the {'Pixel' if ui.ANDROID else 'iPhone'}: run this after it ends")
    if ui.ANDROID:
        adb_ok()
        if not opened:
            in_use_check()
            restart_if_worn()
        unlock()
        ui.android.dim()  # USB or Wi-Fi
        if not opened and needs_gps() and ui.android.gps_back():
            log("turned the phone's location on again (an earlier run left it off)")
    elif not opened or not mirroring_running():
        connect()
    opened = True


IN_USE = 60  # seconds: a Claude-started run won't take a Pixel a person touched this recently


def in_use_check():
    """a run Claude starts (CLAUDECODE set) stops before its first tap while you're using the Pixel: unlocked and
    touched by hand in the last minute. The user said the Pixel was free, then saw a raid that couldn't wait; the
    test started 3 min later pressed Back through it (2026-11-27). A run you start yourself isn't held up"""
    if not os.environ.get("CLAUDECODE") or locked():
        return
    ago = ui.android.by_hand()
    if ago is not None and ago < IN_USE:
        raise Stop(f"you're using the Pixel (touched {ago:.0f}s ago): run this once you're done with it")


def needs_gps():
    return flag("POGO_GPS") or os.path.basename(sys.argv[0]) in NEEDS_GPS


def gps_off():
    """the Pixel's location off for the rest of the run, unless this script needs it. home.start() calls it once
    the game is up: the game wants a fix while it loads"""
    if not ui.ANDROID or needs_gps():
        return
    try:
        if ui.android.gps_off():
            log("turned the phone's location off for the run")
            close_location_box()
    except Exception as e:  # (never in the way of the run)
        log(f"couldn't turn the phone's location off: {type(e).__name__}: {e}")


def game_in_front():
    return ui.android.game_in_front()


GPS_BLIP_WAIT = 10  # seconds the game gets to drop its 'Failed to detect location' banner once location is on


def gps_blip():
    """the game's solid 'Failed to detect location. (12)' banner (ui.gps_banner_solid) comes after some minutes with
    location off, stays, and hides what's under it. Location on takes it off in ~4 s, and with location off again
    it stayed gone (Pixel, 2026-11-26). Only when this run turned location off (gps_off). -> True if it went"""
    if not ui.ANDROID or not os.path.exists(ui.android.GPS_FILE):
        return False
    t0 = time.time()
    ui.android.shell("cmd location set-location-enabled true")
    up = base.settle(lambda: (ui.ocr(ui.capture()[0]), ui.gps_banner())[1], lambda up: not up,
                     timeout=GPS_BLIP_WAIT, gap=0.5)
    ui.android.shell("cmd location set-location-enabled false")
    close_location_box()
    log(f"  the 'Failed to detect location' banner {'stayed' if up else 'went'} with location on for a moment "
        f"({time.time() - t0:.1f}s)")
    return not up


def close_location_box():
    """Android's own 'No location access' box (Close / Turn on location) comes up over the game right after location
    goes off, and taps meant for the game stop on it ('Pokémon GO isn't on the phone screen', Pixel 2026-11-22).
    Back closes it, the same as its Close"""
    t0 = time.time()
    if base.settle(game_in_front, lambda up: not up, timeout=BOX_WAIT):
        return  # it never came: the game stayed in front
    texts = ui.ocr(ui.capture()[0])
    if "NO LOCATION ACCESS" not in ui.joined(texts):
        log(f"something else is over the game after location went off: {ui.summary(texts, 80)}")
        return  # (no Back: it might be the game's own screen. home.start's checks deal with what it is)
    ui.android.key("back")
    if base.settle(game_in_front, bool, timeout=3):
        log(f"  closed Android's 'No location access' box ({time.time() - t0:.1f}s)")
    else:
        log("  Android's 'No location access' box didn't close with Back")


def close():
    """the end of a run: the Pixel's brightness and location back (every run dims it), then lock it; or quit iPhone Mirroring"""
    if ui.ANDROID and held and ui.android.restore():
        log("put the phone's brightness back")
    if ui.ANDROID and held and ui.android.gps_back():
        log("turned the phone's location on again")
    if ui.ANDROID and held and started:
        try:  # (never in the way of the lock)
            end_health()
        except Exception as e:
            log(f"couldn't read the phone's battery at the end: {type(e).__name__}: {e}")
    if flag("POGO_KEEP_OPEN"):
        return
    if who := claim():
        log(f"not closing the phone: {who} is using it")
        return
    if ui.ANDROID:
        if ui.android.adb("get-state").strip() == "device":
            lock()
            log("locked the phone")
    elif mirroring_running():
        try:  # the iPhone's home screen first (Mirroring's cmd+1), so the game goes to the back, as on the Pixel
            base.key("1", cmd=True)
            time.sleep(0.8)
        except Exception as e:
            log(f"couldn't go to the iPhone's home screen: {e}")
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
        log(f"CRASHED: {type(e).__name__}: {e}\n{traceback.format_exc()}")
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
    if a == ["busy"]:
        sys.exit(print(busy()))
    if a not in (["open"], ["close"]):
        sys.exit(__doc__)
    base.RUN_DIR = "/tmp/pogo_session"
    try:
        ready() if a == ["open"] else close()
    except Stop as e:
        sys.exit(f"STOPPED: {e}")
