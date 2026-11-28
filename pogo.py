#!/usr/bin/env python3
"""One front door for every skill's script. Steps run one after
another; `+` separates them.

  caffeinate -dimsu python3 pogo.py <step> [args] [+ <step> [args]]...
  POGO_PHONE=android caffeinate -dimsu python3 pogo.py \\
      pvpc --limit 5 + ivc --limit 5
  POGO_PHONE=android caffeinate -dimsu python3 pogo.py \\
      ivc --limit 5 + ivc fallen last
  python3 pogo.py list                  every step and what it runs
  python3 pogo.py --no-heal <step> ...  a stop just stops (see below)

A step's args are the same as its own script's (see the top of its
script; `pogo.py list` shows every step). `last` in a step's args is
the run folder that an earlier step of the same skill folder made in
this chain (pvpc, then `pvpc fallen last`).

Every step runs as its own python3 process, so each one starts
clean: its own run folder, its own state. The phone stays unlocked
(iPhone Mirroring stays open) between steps and is closed once at
the end, the same way a single script closes it. POGO_KEEP_OPEN=1
leaves it open at the end too. Under POGO_PHONE=both, a Pixel-only
step (PIXEL: goplus, hatch, evo, account, advsync) runs on the Pixel.

A step that stops or crashes gets healed (heal.py): a headless
Claude finds why and fixes it, then the step runs again with only
what's left. Off with --no-heal or POGO_HEAL=0, and off when a Claude
session starts pogo.py (CLAUDECODE set: that Claude is the one
watching). --heal turns it on there too.

The whole chain is checked before step 1 runs: an unknown step or a
bad first word stops it with nothing done. A step that doesn't end
well (stopped, crashed, usage error, even after healing) doesn't
stop the chain: the steps after it still run, and the chain ends
with the first bad step's exit code and a line naming every bad
step. Ctrl-C (exit 130) or a step killed by a signal stops the chain
there.
"""
import json, os, subprocess, sys, textwrap, time
import heal

HERE = os.path.dirname(os.path.realpath(__file__))  # the repo root
SKILLS = os.path.join(HERE, "skills")
SEP = "+"
FAILED = "POGO_CHAIN_FAILED"  # the bad steps so far, carried over a heal's restart

# step -> (script under skills/, first words it takes (a flag or nothing is always fine), the ones that stay on the Mac)
STEPS = {
    "pvpc":        ("pvpc/run.py", {"fallen", "act-fallen", "keepers"}, set()),
    "ivc":         ("ivc/run.py", {"sort", "names", "fallen", "act-fallen", "resort", "search"}, set()),
    "cleantrades": ("cleanup/cleantrades.py", {"evo", "transfer"}, set()),
    "sizes":       ("cleanup/sizes.py", set(), set()),
    "dbsweep":     ("cleanup/dbsweep.py", set(), set()),
    "dbfill":      ("cleanup/dbfill.py", set(), set()),
    "tradeable":   ("cleanup/tradeable.py", {"refresh", "dynamax", "read", "plan", "tag", "door"}, {"refresh", "plan"}),  # door: the default
    "leftovers":   ("cleanup/leftovers.py", {"again"}, set()),
    "specieswise": ("cleanup/specieswise.py", {"plan", "GIV", "Transfer", "Reroll"}, {"plan"}),
    "dex":         ("dex/dex.py", {"lucky", "100", "xxs", "look", "evolve"}, set()),
    "luckydex":    ("dex/luckydex.py", {"check"}, set()),
    "sizerecords": ("dex/sizerecords.py", {"read", "compare"}, {"compare"}),
    "gift":        ("gift/gift.py", {"run", "look"}, set()),
    "trade":       ("trade/trade.py", {"run", "look", "restart"}, set()),
    "mega":        ("mega/mega.py", set(), set()),
    "evo":         ("evo/evo.py", set(), set()),
    "roster":      ("roster/roster.py", {"count", "report"}, {"report"}),
    "raidteam":    ("roster/raidteam.py", {"count", "report", "keep"}, {"report"}),
    "gymfeed":     ("gymfeed/gymfeed.py", set(), set()),
    "goplus":      ("goplus/goplus.py", set(), set()),
    "hatch":       ("hatch/hatch.py", {"shortest", "longest"}, set()),
    "account":     ("shared/account.py", {"HashTagAJay", "CyrillJan"}, set()),
    "advsync":     ("shared/advsync.py", set(), set()),
}
NEEDS_WORD = {"dex", "raidteam", "roster", "sizerecords", "specieswise"}  # these have no default: the first word is a must
BOTH = {"trade"}  # drives the iPhone and the Pixel, unless POGO_PHONE names one (android, ios): then that one alone
PIXEL = {"goplus", "hatch", "evo", "account", "advsync"}  # Pixel only: under POGO_PHONE=both they run on the Pixel


def usage(msg=None):
    head = textwrap.fill(f"pogo.py: {msg}", 70, subsequent_indent="  ") + "\n\n" if msg else ""
    sys.exit(head + __doc__)


def split(argv):
    """['pvpc', '--limit', '5', '+', 'ivc'] -> [['pvpc', '--limit', '5'], ['ivc']]"""
    steps, cur = [], []
    for a in argv:
        if a == SEP:
            steps.append(cur)
            cur = []
        else:
            cur.append(a)
    steps.append(cur)
    return steps


def check(steps):
    """every step known, its first word one it takes, --limit a number, `last` after a step that makes one.
    Stops before anything runs"""
    made = set()
    for i, s in enumerate(steps, 1):
        if not s:
            usage(f"step {i} is empty (two `+` in a row, or one at an end)")
        name, args = s[0], s[1:]
        if name not in STEPS:
            usage(f"step {i}: no step {name!r}. Steps: {', '.join(STEPS)}")
        script, words, _ = STEPS[name]
        first = args[0] if args else None
        if first and not first.startswith("--") and first not in words:
            usage(f"step {i} ({name}): {first!r} isn't one of {', '.join(sorted(words)) or 'its flags'}")
        if name in NEEDS_WORD and (not first or first.startswith("--")):
            usage(f"step {i} ({name}) needs one of {', '.join(sorted(words))} first")
        for j, a in enumerate(args):
            if a == "--limit" and (j + 1 >= len(args) or not args[j + 1].isdigit()):
                usage(f"step {i} ({name}): --limit needs a number")
        folder = os.path.dirname(script)
        if "last" in args and folder not in made:
            usage(f"step {i} ({name}): `last` needs an earlier step in {folder}/ that makes a run folder")
        made.add(folder)


def runs_in(folder):
    d = os.path.join(SKILLS, folder, "runs")
    return {e.path for e in os.scandir(d) if e.is_dir()} if os.path.isdir(d) else set()


def phones(steps):
    """the phones the chain uses: POGO_PHONE's, and both for a two-phone step"""
    env = os.environ.get("POGO_PHONE", "").lower()
    out = {"android"} if env == "android" else {"ios", "android"} if env == "both" else {"ios"}
    if any(s[0] in BOTH for s in steps) and env not in ("android", "ios", "iphone"):  # (one named: /trade on it alone)
        out = {"ios", "android"}
    return out


def on_phone(step):
    name, args = step[0], step[1:]
    first = args[0] if args else None
    return first not in STEPS[name][2]


def say(msg):
    print(time.strftime("%H:%M:%S ") + "pogo: " + msg, flush=True)


def run_one(cmd, env):
    """run cmd to its end -> exit code. Ctrl-C reaches the child too (same terminal): wait for it to log its own
    end and come back, instead of killing it mid-tap"""
    p = subprocess.Popen(cmd, env=env)
    interrupted = False
    while True:
        try:
            code = p.wait()
            break
        except KeyboardInterrupt:
            interrupted = True
    return 130 if interrupted and code == 0 else code


def close(used):
    """the chain's end: lock the Pixel / quit iPhone Mirroring, once, as a single script does"""
    for phone in sorted(used):
        env = dict(os.environ, POGO_PHONE=phone)
        env.pop("POGO_KEEP_OPEN", None)
        subprocess.run([sys.executable, os.path.join(SKILLS, "shared", "session.py"), "close"], env=env)


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        usage()
    if argv == ["list"]:
        for name, (script, words, mac) in STEPS.items():
            extra = f"  [{' | '.join(sorted(words))}]" if words else ""
            line = f"  {name:12} {script}{extra}" + (f"  (Mac only: {', '.join(sorted(mac))})" if mac else "")
            print(textwrap.fill(line, 70, subsequent_indent=" " * 15, break_on_hyphens=False))
        return 0
    healing = heal.wanted(argv[0])
    if argv[0] in ("--heal", "--no-heal"):
        argv = argv[1:]
        if not argv:
            usage("--heal / --no-heal needs a step")
    steps = split(argv)
    check(steps)
    phone_first = os.environ.pop("POGO_HEAL_PHONE", None)  # heal.py: the first step on the one phone that failed
    keep_open = os.environ.get("POGO_KEEP_OPEN", "") not in ("", "0")
    chain = len(steps) > 1
    env = dict(os.environ, POGO_KEEP_OPEN="1") if chain else dict(os.environ)  # each step leaves the phone up
    last, code, touched = {}, 0, False
    try:
        failed = json.loads(os.environ.pop(FAILED, "") or "[]")  # [name, code] of bad steps before a heal's restart
    except ValueError:
        failed = []
    try:
        for i, s in enumerate(steps, 1):
            name = s[0]
            script = STEPS[name][0]
            folder = os.path.dirname(script)
            if "last" in s[1:] and folder not in last:
                say(f"step {i} ({name}): no earlier step made a run folder in {folder}/ for `last`: skipping it")
                failed.append([name, 2])
                continue
            args = [last[folder] if a == "last" else a for a in s[1:]]
            if chain:
                say(f"step {i}/{len(steps)}: {name} {' '.join(args)}".rstrip())
            before = runs_in(folder)
            touched |= on_phone(s)
            cmd = [sys.executable, os.path.join(SKILLS, script), *args]
            step_env = dict(env, POGO_PHONE=phone_first) if phone_first and i == 1 else env
            if name in PIXEL and step_env.get("POGO_PHONE", "").lower() == "both":  # (ui reads both as the iPhone)
                step_env = dict(step_env, POGO_PHONE="android")
            if healing:
                last_before, started, out = dict(last), time.time(), heal.out_file()
                code, lines = heal.tee(cmd, step_env, out)
            else:
                code = run_one(cmd, step_env)
            new = sorted(runs_in(folder) - before)
            if new:
                last[folder] = new[-1]
            if code and healing:
                os.environ[FAILED] = json.dumps(failed)  # (a restart starts pogo.py over: it keeps these)
                phone = (step_env.get("POGO_PHONE") or "ios").lower()
                phone = phone if phone in ("android", "both") else "ios"
                code = heal.handle(steps, i - 1, args, code, lines, out, started,
                                   lambda n: os.path.dirname(STEPS[n][0]), last_before, check, phone)
                os.environ.pop(FAILED, None)  # (no restart: this run keeps them itself)
                if code == 0:
                    break  # (Claude found nothing left to do in the last step)
            if code:
                failed.append([name, code])
                if code == 130 or code < 0 or not chain:
                    if chain:
                        say(f"step {i} ({name}) ended with exit code {code}: the chain stops here")
                    break
                if i < len(steps):
                    say(f"step {i} ({name}) ended with exit code {code}: going on with the rest")
    finally:
        if chain and touched and not keep_open:
            close(phones(steps))
    if failed and chain:
        say("didn't end well: " + ", ".join(f"{n} (exit {c})" for n, c in failed))
    return failed[0][1] if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
