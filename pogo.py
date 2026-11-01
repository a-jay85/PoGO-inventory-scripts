#!/usr/bin/env python3
"""One front door for every skill's script. Steps run one after another; `+` separates them.

  caffeinate -dimsu python3 pogo.py <step> [args] [+ <step> [args]]...
  POGO_PHONE=android caffeinate -dimsu python3 pogo.py pvpc --limit 5 + ivc --limit 5
  POGO_PHONE=android caffeinate -dimsu python3 pogo.py ivc --limit 5 + ivc fallen last
  python3 pogo.py list                       every step and what it runs

A step's args are the same as its own script's (see its SKILL.md). `last` in a step's args is the run folder that
an earlier step of the same skill folder made in this chain (pvpc, then `pvpc fallen last`).

Every step runs as its own python3 process, so each one starts clean: its own run folder, its own state. The phone
stays unlocked (iPhone Mirroring stays open) between steps and is closed once at the end, the same way a single
script closes it. POGO_KEEP_OPEN=1 leaves it open at the end too.

The whole chain is checked before step 1 runs: an unknown step or a bad first word stops it with nothing done. The
chain stops at the first step that doesn't end well (stopped, crashed, interrupted, usage error), with its exit code.
"""
import os, subprocess, sys, time

HERE = os.path.dirname(os.path.realpath(__file__))  # the repo root
SKILLS = os.path.join(HERE, "skills")
SEP = "+"

# step -> (script under skills/, first words it takes (a flag or nothing is always fine), the ones that stay on the Mac)
STEPS = {
    "pvpc":        ("pvpc/run.py", {"fallen", "act-fallen", "keepers"}, set()),
    "ivc":         ("ivc/run.py", {"sort", "names", "fallen", "act-fallen", "search"}, set()),
    "cleantrades": ("cleanup/cleantrades.py", {"evo", "fix", "transfer"}, set()),
    "sizes":       ("cleanup/sizes.py", set(), set()),
    "tradeable":   ("cleanup/tradeable.py", {"refresh", "dynamax", "read", "plan", "tag", "door"}, {"refresh", "plan"}),  # door: the default
    "dex":         ("dex/dex.py", {"lucky", "100", "look", "evolve"}, set()),
    "luckydex":    ("dex/luckydex.py", {"check"}, set()),
    "gift":        ("gift/gift.py", {"run", "look"}, set()),
    "trade":       ("trade/trade.py", {"run", "look", "restart"}, set()),
    "mega":        ("mega/mega.py", set(), set()),
    "roster":      ("roster/roster.py", {"count", "report"}, {"report"}),
    "gymfeed":     ("gymfeed/gymfeed.py", set(), set()),
    "account":     ("shared/account.py", {"HashTagAJay", "CyrillJan"}, set()),
}
NEEDS_WORD = {"dex", "roster"}  # these have no default: the first word is a must
BOTH = {"trade"}  # drives the iPhone and the Pixel, whatever POGO_PHONE says


def usage(msg=None):
    sys.exit((f"pogo.py: {msg}\n\n" if msg else "") + __doc__)


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
    if any(s[0] in BOTH for s in steps):
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
            print(f"  {name:12} {script}{extra}" + (f"   (Mac only: {', '.join(sorted(mac))})" if mac else ""))
        return 0
    steps = split(argv)
    check(steps)
    keep_open = os.environ.get("POGO_KEEP_OPEN", "") not in ("", "0")
    chain = len(steps) > 1
    env = dict(os.environ, POGO_KEEP_OPEN="1") if chain else dict(os.environ)  # each step leaves the phone up
    last, code, touched = {}, 0, False
    try:
        for i, s in enumerate(steps, 1):
            name = s[0]
            script = STEPS[name][0]
            folder = os.path.dirname(script)
            if "last" in s[1:] and folder not in last:
                say(f"step {i} ({name}): no earlier step made a run folder in {folder}/ for `last`: stopping")
                code = 2
                break
            args = [last[folder] if a == "last" else a for a in s[1:]]
            if chain:
                say(f"step {i}/{len(steps)}: {name} {' '.join(args)}".rstrip())
            before = runs_in(folder)
            touched |= on_phone(s)
            code = run_one([sys.executable, os.path.join(SKILLS, script), *args], env)
            new = sorted(runs_in(folder) - before)
            if new:
                last[folder] = new[-1]
            if code:
                if chain:
                    say(f"step {i} ({name}) ended with exit code {code}: the chain stops here")
                break
    finally:
        if chain and touched and not keep_open:
            close(phones(steps))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
