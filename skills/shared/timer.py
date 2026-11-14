#!/usr/bin/env python3
"""One local timer for the scripts that run by themselves (gymfeed, hatch, goplus). Each one says when it should run next;
a launchd job runs `timer.py tick` every minute, and tick runs a script whose time has come.

- ~/.config/pogo/timers.json holds {script: when it's due (epoch seconds)}. A script not in it is off.
- A script sets its own next run while it runs: at(name, epoch), later(name, minutes) or off(name).
  One that didn't (it stopped, or had nothing to say) gets its job's AFTER minutes from when it ended.
- tick skips, and tries again next minute, while any other phone script is running or the Pixel isn't on adb.
  One script per tick. Its STOPPED / CRASHED / done lines go to ~/.config/pogo/timer.log.
- gymfeed's phone: ~/.config/pogo/gymfeed_phone ("iphone" or "android"; no file: android). hatch, goplus: the Pixel.
  An iPhone run goes through iPhone Mirroring, so the Mac must stay awake and unlocked for it.
- goplus runs again 60 min after it connects (or finds it already on). HashTagAJay signed in: its timer goes off,
  till a CyrillJan run connects again. Any other stop (no ball, didn't connect) tries again 60 min after it ended.

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

HERE = os.path.dirname(os.path.realpath(__file__))
SKILLS = os.path.dirname(HERE)
CONF = os.path.expanduser("~/.config/pogo")
STATE = os.path.join(CONF, "timers.json")
LOG = os.path.join(CONF, "timer.log")
LABEL = "pogo.timer"
PLIST = os.path.expanduser(f"~/Library/LaunchAgents/{LABEL}.plist")
PATH = "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
KEEP = os.path.join(CONF, "gymfeed_keep_on_until")  # (epoch seconds) till then gymfeed's "off" keeps it on


def gymfeed_phone():
    try:
        return "iphone" if open(os.path.join(CONF, "gymfeed_phone")).read().strip() == "iphone" else "android"
    except OSError:
        return "android"


# name -> (script under skills/, its phone, minutes after a run that set no next run: (lo, hi))
JOBS = {
    "gymfeed": ("gymfeed/gymfeed.py", gymfeed_phone, (30, 32)),
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
        try:
            state = json.load(open(STATE))
        except (OSError, ValueError):
            state = {}
        change(state)
        tmp = STATE + ".tmp"
        json.dump(state, open(tmp, "w"), indent=1, sort_keys=True)
        os.replace(tmp, STATE)
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


def gymfeed(feedable):
    """a gymfeed run's last word: True, a gym is left to feed (next one in 30-32 min); False, none (off, unless
    gymfeed_keep_on_until is still ahead: then it keeps looking every 30-32 min)"""
    lo, hi = JOBS["gymfeed"][2]
    try:
        keep = int(open(KEEP).read().strip())
    except (OSError, ValueError):
        keep = 0
    if feedable or keep > time.time():
        when = later("gymfeed", random.uniform(lo, hi))
        note(f"gymfeed: {'gyms to feed' if feedable else 'no gym to feed, kept on'}, next after {when}")
    else:
        off("gymfeed")
        note("gymfeed: no gym to feed, timer off")


# ---------- the minute tick ----------

def busy():
    """-> what's using a phone, or None. The phone locks (session.claim), then any python running a script of
    this repo (by its command line, or the folder it runs in: `cd skills/gift && python3 gift.py`)"""
    import fcntl as f
    for phone in ("android", "iphone"):
        try:
            with open(f"/tmp/pogo-{phone}.lock", "a+") as fh:
                try:
                    f.flock(fh, f.LOCK_EX | f.LOCK_NB)
                except OSError:
                    fh.seek(0)
                    return fh.read().strip() or f"a script on the {phone}"
        except OSError:
            pass
    me = {os.getpid(), os.getppid()}
    out = subprocess.run(["pgrep", "-fl", r"PoGO-inventory-scripts.*\.py"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        pid, _, cmd = line.partition(" ")
        if int(pid) not in me and "timer.py" not in cmd:
            return cmd
    pids = subprocess.run(["pgrep", "-i", "python"], capture_output=True, text=True).stdout.split()
    for pid in pids:
        if int(pid) in me:
            continue
        cwd = subprocess.run(["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"], capture_output=True, text=True).stdout
        if "PoGO-inventory-scripts" in cwd:
            return f"python in {cwd.split('n', 1)[-1].strip()}"
    return None


def skip(why):
    """a skip line once, not every minute while it waits"""
    try:
        last = open(LOG).read().splitlines()[-1].split(" ", 2)[2]
    except (OSError, IndexError):
        last = ""
    if last != f"skipped: {why}":
        note(f"skipped: {why}")


def tick():
    now = time.time()
    ready = sorted((t, n) for n, t in due().items() if n in JOBS and t <= now)
    if not ready:
        return
    name = ready[0][1]
    script, phone, after = JOBS[name]
    phone = phone()
    if who := busy():
        return skip(f"another phone script is running ({who[:80]})")
    if phone == "android":
        state = subprocess.run(["adb", "get-state"], capture_output=True, text=True).stdout.strip()
        if state != "device":
            return skip("Pixel not connected over adb")
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
