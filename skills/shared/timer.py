#!/usr/bin/env python3
"""One local timer for the scripts that run by themselves (gymfeed, hatch, goplus). Each one says when it should run next;
a launchd job runs `timer.py tick` every minute, and tick runs a script whose time has come.

- ~/.config/pogo/timers.json holds {script: when it's due (epoch seconds)}. A script not in it is off.
- A script sets its own next run while it runs: at(name, epoch), later(name, minutes) or off(name).
  One that ended fine and didn't gets its job's AFTER minutes from when it ended.
- A run that stops or crashes (any exit but 0) turns its own timer off, with a log line and a macOS notice, so a
  broken run doesn't come back every 15 min (hatch, 4 times on 2026-11-15). Not when it only found another script
  on the phone: that one tries again. Back on: run the script once by hand, or `timer.py in <name> 0`.
- tick skips a job, and tries again next minute, while another script is running on that job's phone (its lock). A
  script on the other phone doesn't hold it up, and a job that can't run doesn't hold up the next due one
  (the user, 2026-11-23: gymfeed-iphone sat 43 min behind a Pixel run).
- tick skips, and tries again next minute, while you're using the phone (the user, 2026-11-16). The Pixel: touched
  in the last 3 min, or unlocked and touched in the last 10 min (pixel_in_use). Its screen being on says nothing:
  it stays on while plugged in. The iPhone: iPhone Mirroring says "iPhone in Use" (session.connect stops on it at
  once); that run tries again in 5 min, since each try opens Mirroring and takes the Mac's keyboard.
  Mid-run, a run waits for it (base.wait_for_phone, up to 30 min: a call; it clicks Connect) and stops in the same words if it's still
  in use, or if the game came back on another screen.
- A phone out of reach turns its timers off, so a run never starts by itself the moment the phone is back in range
  (coming home with it, 2026-11-15). The Pixel: off once it has been off adb for 5 min in a row while a job is due
  (a shorter miss is a Wi-Fi blip: adbwifi.py reconnects within a minute). The iPhone: off when a run stops on
  "can't reach the iPhone" (no cheap look first: that takes opening iPhone Mirroring). A Pixel run that stops on
  "phone not connected" goes off too. Back on: run the script once by hand, or `timer.py in <name> 0`.
  Each off goes to the log and a macOS notice.
  One script per tick. Its STOPPED / CRASHED / done lines go to ~/.config/pogo/timer.log.
- gymfeed has one timer per phone: gymfeed-pixel and gymfeed-iphone, each with its own 30-32 min and its own off
  (the user, 2026-11-16: both phones feed). A gymfeed run sets the one of the phone it ran on. hatch, goplus: the Pixel.
  An iPhone run goes through iPhone Mirroring, so the Mac must stay awake and unlocked for it.
- goplus runs again 60 min after it connects (or finds it already on). HashTagAJay signed in: its timer goes off,
  till a CyrillJan run connects again. Any other stop (no ball, didn't connect) turns it off, like every stop.
- hatch waits while the Pixel is charging (any power: the Mac's cable or a wall charger): eggs don't move on a
  charger (the user, 2026-11-22). It stays due and runs the first minute the Pixel is off power. The other jobs
  still run in the meantime.
- An account switch (account.py) turns hatch and goplus off first: their times were the old account's. Its egg
  check then sets hatch for the new one, and a switch to CyrillJan (GOPLUS_FOR) sets goplus for the next minute.

Replaces the gymfeed-only timer (gymfeed_cron.sh and gymfeed_timer.sh with their own launchd job, 2026-10-28 to
2026-11-13). Its rule stays: a gymfeed run is due 30-32 min (random) after the last one ended.

  python3 timer.py status               what's due when
  python3 timer.py in <name> <minutes>  run it that many minutes from now (0: next minute)
  python3 timer.py off <name>           no more timed runs of it
  python3 timer.py install              load the launchd job (run from the main checkout: it runs this file)
  python3 timer.py uninstall            unload it
  python3 timer.py tick                 what launchd runs each minute
"""
import fcntl, json, os, random, re, subprocess, sys, time

import jsonfile, locks

HERE = os.path.dirname(os.path.realpath(__file__))
SKILLS = os.path.dirname(HERE)
CONF = os.path.expanduser(os.environ.get("POGO_TIMER_CONF", "~/.config/pogo"))  # (the env: a test's own folder)
STATE = os.path.join(CONF, "timers.json")
AWAY = os.path.join(CONF, "timer_away.json")  # {phone: when it was first missed}. Not in timers.json: status lists that
GRACE = 5  # minutes off adb in a row before the Pixel's timers go off
UNREACHED = re.compile(r"can't reach the iPhone|phone not connected")  # a run's stop that means the phone is away
IN_USE = re.compile(r"you're using the iPhone")  # a stop that means: you have the iPhone in your hand, later
IN_USE_WAIT = 5  # minutes till an iPhone run that found you using it tries again
TOUCHED = 3  # minutes since the last touch on the Pixel that count as you using it
TOUCHED_UNLOCKED = 10  # the same, while it's unlocked (a page you read without touching)
BUSY = re.compile(r"is using the (Pixel|iPhone): run this after it ends")  # a stop that only means: try again later
LOG = os.path.join(CONF, "timer.log")
LABEL = "pogo.timer"
PLIST = os.path.expanduser(f"~/Library/LaunchAgents/{LABEL}.plist")
PATH = "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
RAID_WAIT = 45  # minutes: a raid's length, till a gym with one on gives its Pokémon back
CHARGING_WAITS = {"hatch"}  # jobs that wait while the Pixel charges
GOPLUS_FOR = "CyrillJan"  # the one account the GO Plus+ is paired with (goplus.py, account.py)
KEEP = os.path.join(CONF, "gymfeed_keep_on_until")  # (epoch seconds) till then gymfeed's "off" keeps it on (both phones)


# name -> (script under skills/, its phone, minutes after a run that set no next run: (lo, hi))
JOBS = {
    "gymfeed-pixel": ("gymfeed/gymfeed.py", lambda: "android", (30, 32)),
    "gymfeed-iphone": ("gymfeed/gymfeed.py", lambda: "iphone", (30, 32)),
    "hatch": ("hatch/hatch.py", lambda: "android", (15, 15)),
    "goplus": ("goplus/goplus.py", lambda: "android", (60, 60)),
}
LOG_LINES = re.compile(r"STOPPED|CRASHED|Traceback|NotReady|Refused|done:|fed |taps in|gyms to feed|raid:|hatch|"
                       r"incubat|next run|connect|GO Plus")


def stamp():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def note(line):
    os.makedirs(CONF, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(f"{stamp()} {line}\n")


# ---------- the due times ----------

def _edit(change):
    """read timers.json, change(dict) it, write it back, under a lock (a script and tick can write at once)"""
    os.makedirs(CONF, exist_ok=True)
    with open(STATE + ".lock", "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = jsonfile.read(STATE, {})
        change(state)
        jsonfile.write(STATE, state, indent=1, sort_keys=True)
        return dict(state)


def due():
    return _edit(lambda s: None)


def at(name, when):
    """run name at when (epoch seconds)"""
    _edit(lambda s: s.__setitem__(name, int(when)))


def later(name, minutes):
    at(name, time.time() + minutes * 60)
    return time.strftime("%H:%M", time.localtime(time.time() + minutes * 60))


def off(name):
    _edit(lambda s: s.pop(name, None))


def gymfeed(feedable, phone, raid=False):
    """a gymfeed run's last word, on its phone's timer (phone: "android" or "iphone"). feedable True: a gym is left
    to feed (next one in 30-32 min); False, none (off, unless gymfeed_keep_on_until is still ahead: then it keeps
    looking every 30-32 min). raid: a gym had a raid on, its Pokémon are out of it till the raid ends, so the next
    run is RAID_WAIT min away (the user, 2026-11-23)"""
    name = "gymfeed-pixel" if phone == "android" else "gymfeed-iphone"
    lo, hi = JOBS[name][2]
    try:
        keep = int(open(KEEP).read().strip())
    except (OSError, ValueError):
        keep = 0
    if raid and feedable:
        when = later(name, RAID_WAIT)
        note(f"{name}: a raid is on at a gym, next after {when}")
    elif feedable or keep > time.time():
        when = later(name, random.uniform(lo, hi))
        note(f"{name}: {'gyms to feed' if feedable else 'no gym to feed, kept on'}, next after {when}")
    else:
        off(name)
        note(f"{name}: no gym to feed, timer off")


# ---------- the minute tick ----------

def busy(phone):
    """-> what's using this phone ('android' or 'iphone'), or None. Its lock (session.claim): every phone script
    holds it, a test script too. The other phone doesn't count: a Pixel run and an iPhone run go side by side
    (POGO_PHONE=both does it)"""
    return locks.holder(phone)


def pixel_in_use():
    """-> True while you look to be using the Pixel. Its last touch from PowerManager's own "(N ms ago)": its clock
    leaves out deep sleep, so /proc/uptime can't be set against it. adb taps count as touches too, so the minutes
    right after a run count as in use: that only puts the next run off a little. A read it can't make: not in use"""
    out = subprocess.run(["adb", "shell", "dumpsys power | grep -m1 ' lastUserActivityTime='; "
                          "dumpsys window displays | grep isKeyguardShowing=; dumpsys window policy | grep mIsShowing="],
                         capture_output=True, text=True).stdout
    m = re.search(r"lastUserActivityTime=\d+ \((\d+) ms ago\)", out)
    if not m:
        return False
    idle = int(m.group(1)) / 60000
    return idle < TOUCHED or ("=true" not in out and idle < TOUCHED_UNLOCKED)


def pixel_charging():
    """-> True while the Pixel is on power (AC, USB or wireless). A read it can't make: not charging"""
    out = subprocess.run(["adb", "shell", "dumpsys battery"], capture_output=True, text=True).stdout
    return bool(re.search(r"(AC|USB|Wireless) powered: true", out))


def skip(why):
    """a skip line once, not every minute while it waits"""
    try:
        last = open(LOG).read().splitlines()[-1].split(" ", 2)[2]
    except (OSError, IndexError):
        last = ""
    if last != f"skipped: {why}":
        note(f"skipped: {why}")


# ---------- a phone out of reach ----------

def missed(phone, gone):
    """gone: this tick didn't reach the phone. -> minutes it has been out of reach in a row (0 when reached)"""
    away = jsonfile.read(AWAY, {})
    if not gone:
        if away.pop(phone, None) is not None:
            jsonfile.write(AWAY, away)
        return 0
    if phone not in away:
        away[phone] = int(time.time())
        jsonfile.write(AWAY, away)
    return (time.time() - away[phone]) / 60


def notify(text):
    subprocess.run(["osascript", "-e", f'display notification {json.dumps(text)} with title "pogo timer"'],
                   capture_output=True)


def away_off(phone, why):
    """every timer on this phone off, with one log line and a notice that say how to turn them back on"""
    names = [n for n in due() if n in JOBS and JOBS[n][1]() == phone]
    for n in names:
        off(n)
    missed(phone, False)  # the next miss counts from 0 again
    if names:
        text = f"{', '.join(names)} off: {why}. Back on: run it once, or timer.py in <name> 0"
        note(text)
        notify(text)


def blocked(phone):
    """-> why a job on this phone can't run this minute, or None. A Pixel out of reach for GRACE min turns its
    timers off (away_off), and the reason says so"""
    if who := busy(phone):
        return f"another phone script is running ({who[:80]})"
    if phone == "android":
        state = subprocess.run(["adb", "get-state"], capture_output=True, text=True).stdout.strip()
        if (gone := missed(phone, state != "device")) >= GRACE:
            away_off(phone, f"the Pixel was off adb for {gone:.0f} min")
            return "the Pixel was off adb: its timers are off"
        if state != "device":
            return "Pixel not connected over adb"
        if pixel_in_use():
            return "you're using the Pixel"
    return None


def tick():
    now = time.time()
    ready = sorted((t, n) for n, t in due().items() if n in JOBS and t <= now)
    if any(n in CHARGING_WAITS for _, n in ready) and pixel_charging():
        missed("android", False)  # (adb answered: an old away count would turn every Pixel timer off at the next blip)
        skip(f"the Pixel is charging: {', '.join(n for _, n in ready if n in CHARGING_WAITS)} waits")
        ready = [r for r in ready if r[1] not in CHARGING_WAITS]  # (left in, it would hold every other job up)
    waits = []
    for _, name in ready:  # a job that can't run doesn't hold up one on the other phone (the user, 2026-11-23:
        script, phone, after = JOBS[name]  # gymfeed-iphone sat 43 min behind a Pixel run)
        phone = phone()
        if why := blocked(phone):
            if why not in waits:
                waits.append(why)
            continue
        break
    else:
        if waits:
            skip("; ".join(waits))
        return
    env = dict(os.environ, PATH=PATH)
    env.pop("POGO_PHONE", None)
    if phone == "android":
        env["POGO_PHONE"] = "android"
    note(f"{name}: start ({phone})")
    started = time.time()
    run = subprocess.run(["caffeinate", "-imsu", sys.executable, os.path.join(SKILLS, script)], env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in run.stdout.splitlines():
        if LOG_LINES.search(line):
            note(f"  {line.strip()[:200]}")
    if run.returncode != 0 and IN_USE.search(run.stdout):
        when = later(name, IN_USE_WAIT)
        return note(f"{name}: end (exit {run.returncode}), you're using the iPhone: next after {when}")
    if any(UNREACHED.search(line) for line in run.stdout.splitlines()):
        note(f"{name}: end (exit {run.returncode})")
        return away_off(phone, f"a {name} run couldn't reach the {'Pixel' if phone == 'android' else 'iPhone'}")
    if run.returncode != 0 and not BUSY.search(run.stdout):
        off(name)
        stop = next((line.strip() for line in run.stdout.splitlines() if re.search(r"STOPPED|CRASHED", line)), "")
        text = f"{name} off: its run ended with exit {run.returncode}. Back on: run it once, or timer.py in {name} 0"
        note(f"{name}: end (exit {run.returncode}), timer off")
        note(text)
        notify(f"{text}\n{stop[:120]}" if stop else text)
        return
    left = due()
    if name in left and left[name] <= started:  # it set no next run itself
        when = later(name, random.uniform(*after))
        note(f"{name}: end (exit {run.returncode}), next after {when}")
    else:
        note(f"{name}: end (exit {run.returncode}), " +
             (f"next after {time.strftime('%H:%M', time.localtime(left[name]))}" if name in left else "timer off"))


# ---------- launchd ----------

def install():
    os.makedirs(os.path.dirname(PLIST), exist_ok=True)
    out = os.path.join(CONF, "timer.out")
    open(PLIST, "w").write(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>{LABEL}</string>
	<key>ProgramArguments</key>
	<array>
		<string>{sys.executable}</string>
		<string>{os.path.realpath(__file__)}</string>
		<string>tick</string>
	</array>
	<key>EnvironmentVariables</key>
	<dict>
		<key>PATH</key>
		<string>{PATH}</string>
	</dict>
	<key>StandardOutPath</key>
	<string>{out}</string>
	<key>StandardErrorPath</key>
	<string>{out}</string>
	<key>StartInterval</key>
	<integer>60</integer>
</dict>
</plist>
""")
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{LABEL}"], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", PLIST], check=True)
    print(f"loaded {LABEL}: runs {os.path.realpath(__file__)} tick every minute")


def uninstall():
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"])
    print(f"unloaded {LABEL}")


def main(a):
    if not a or a[0] in ("-h", "--help"):
        sys.exit(__doc__)
    if a[0] == "tick":
        tick()
    elif a[0] == "status":
        for n, t in sorted(due().items(), key=lambda x: x[1]):
            print(f"{n}: due {time.strftime('%Y-%m-%d %H:%M', time.localtime(t))}")
        for n in JOBS:
            if n not in due():
                print(f"{n}: off")
    elif a[0] == "in" and len(a) == 3:
        print(f"{a[1]}: due {later(a[1], float(a[2]))}")
    elif a[0] == "off" and len(a) == 2:
        off(a[1])
        print(f"{a[1]}: off")
    elif a[0] == "install":
        install()
    elif a[0] == "uninstall":
        uninstall()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
