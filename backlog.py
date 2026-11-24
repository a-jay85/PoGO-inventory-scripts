#!/usr/bin/env python3
"""The phone backlog: things to check, verify or fix on a phone that can't be done now (the phone is busy, or the
user is using it). They live as GitHub Issues in the private repo a-jay85/PoGO-inventory-scripts-backlog, because
this repo is public and an issue names trainers, species, CPs and IVs (the user, 2026-11-22, after IBL5's backlog).

  python3 backlog.py search <term>                       open and closed issues that match
  python3 backlog.py open [<label>]                      open issues (a label: pixel, iphone, both, verify, fix, by-hand)
  python3 backlog.py new <phone> <kind> <title> <body>   file one (phone: pixel|iphone|both, kind: verify|fix|by-hand)
  python3 backlog.py comment <n> <text>                  add to an issue (a repeat sighting, what a look found)
  python3 backlog.py close <n> <what closed it>          close with the run or PR that settled it
  python3 backlog.py ready                               are both phones free? Then the open issues, oldest first

A new issue's body: the first line is where it came from (a run folder, a /tmp/pogo-watch log, or a PR URL of this
repo), it cites a file:line (the rule or reader involved), and it says what to look at on the phone and what goes
wrong if nobody does: over 100 characters. A title that's already open isn't filed again: its issue is printed.
Kinds: verify (look at the phone and confirm what a script read or did), fix (a script bug seen on the phone: fix it,
phone-test, merge), by-hand (the user's own call, like a special trade: Claude reads and reports, never tags).

ready: a phone is free when no run holds its lock (skills/shared/locks.py) and
no skills/ script is running; the Pixel must also show in adb devices. The iPhone's Mirroring isn't opened to check
(it connects when a run starts). Exit 0 when both are free, 1 when not (and what's using each).
Scripts never call this: Claude files issues after reading a run, so a phone run never waits on the network.
"""
import json, os, re, subprocess, sys
import repotools  # (stdlib only)

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), "skills", "shared"))
import locks  # (stdlib only)

REPO = "a-jay85/PoGO-inventory-scripts-backlog"
GH = os.environ.get("BACKLOG_GH", "gh")
PHONES = ("pixel", "iphone", "both")
KINDS = ("verify", "fix", "by-hand")
LOCKS = {"pixel": "android", "iphone": "iphone"}  # backlog phone name -> locks.py phone name
ORIGIN = re.compile(r"^(https://github\.com/a-jay85/PoGO-inventory-scripts/pull/\d+|\S*(/runs/|/tmp/pogo-watch/)\S+)")
FILE_LINE = re.compile(r"[\w./-]+\.\w+:\d+")
BODY_MIN = 101


def gh(*args, capture=True):
    """-> gh's stdout; a failed gh stops with its error"""
    p = repotools.gh(*args, bin=GH, repo=REPO, capture=capture)
    if p.returncode:
        sys.exit(f"gh {' '.join(args[:2])}: {(p.stderr or '').strip() or 'failed'}")
    return p.stdout or ""


def body_problem(body):
    """-> the first rule a new issue's body breaks, or None"""
    first = body.strip().splitlines()[0] if body.strip() else ""
    if not ORIGIN.match(first):
        return "the first line must be where it came from: a run folder, a /tmp/pogo-watch log, or a PR URL"
    if not FILE_LINE.search(body):
        return "cite a file:line (the rule or reader involved, e.g. skills/shared/verdict.py:256)"
    if len(body) < BODY_MIN:
        return f"too short ({len(body)} characters): say what to look at on the phone and what goes wrong if not"
    return None


def issues(state="open", label=None, search=None):
    args = ["issue", "list", "--state", state, "--limit", "200", "--json", "number,title,labels,createdAt"]
    if label:
        args += ["--label", label]
    if search:
        args += ["--search", search]
    return sorted(json.loads(gh(*args)), key=lambda i: i["createdAt"])


def show(found):
    for i in found:
        print(f"#{i['number']} [{','.join(l['name'] for l in i['labels'])}] {i['title']}")
    if not found:
        print("none")


def phone_busy():
    """-> {phone: why it's busy, or None}"""
    ps = subprocess.run(["pgrep", "-fl", r"skills/.*\.py"], capture_output=True, text=True).stdout
    running = [l for l in ps.splitlines() if "tests/" not in l]
    busy = {p: locks.holder(lp) for p, lp in LOCKS.items()}
    if not busy["pixel"]:
        adb = subprocess.run(["adb", "devices"], capture_output=True, text=True).stdout if _has("adb") else ""
        if not re.search(r"\tdevice$", adb, re.M):
            busy["pixel"] = "not in adb devices (USB, or USB debugging off)"
    for p in busy:
        if not busy[p] and running:
            busy[p] = f"a script is running: {running[0]}"
    return busy


def _has(cmd):
    return subprocess.run(["which", cmd], capture_output=True).returncode == 0


def main(a):
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = a[0], a[1:]
    if cmd == "search" and rest:
        show(issues("all", search=" ".join(rest)))
    elif cmd == "open":
        show(issues(label=rest[0] if rest else None))
    elif cmd == "new" and len(rest) == 4:
        phone, kind, title, body = rest
        if phone not in PHONES or kind not in KINDS:
            sys.exit(f"new: phone is one of {', '.join(PHONES)}; kind one of {', '.join(KINDS)}")
        if why := body_problem(body):
            print(f"new: {why}", file=sys.stderr)
            return 2
        same = [i for i in issues(search=f'"{title}" in:title') if i["title"].strip() == title.strip()]
        if same:
            print(f"already open: #{same[0]['number']} {same[0]['title']} (add to it: backlog.py comment)")
            return 0
        print(gh("issue", "create", "--title", title, "--body", body, "--label", phone, "--label", kind).strip())
    elif cmd == "comment" and len(rest) == 2:
        gh("issue", "comment", rest[0], "--body", rest[1])
        print(f"commented on #{rest[0]}")
    elif cmd == "close" and len(rest) == 2:
        gh("issue", "close", rest[0], "--comment", rest[1])
        print(f"closed #{rest[0]}")
    elif cmd == "ready":
        busy = phone_busy()
        for p, why in busy.items():
            print(f"{p}: {'busy: ' + why if why else 'free'}")
        if any(busy.values()):
            print("not both free: the backlog waits")
            return 1
        show(issues())
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
