"""pogo.py --heal: a step that stops or crashes gets fixed, then runs again with only what's left.

  POGO_PHONE=android caffeinate -dimsu python3 ~/PoGO-inventory-scripts/pogo.py --heal pvpc --limit 50 + ivc
  python3 ~/PoGO-inventory-scripts/pogo.py --heal ...     the iPhone (POGO_PHONE unset), from a tmux pane too

When a step ends STOPPED (exit 1) or CRASHED (exit 2):
- A stop only you can clear (phone in use, not plugged in, locked, PIN, Screen Recording) ends the run with a note.
- iPhone Mirroring can't reach the iPhone, early in a step: wait WAIT_S, run the step again, WAITS times at most.
- Anything else: a headless Claude (`claude -p`, CLAUDE_HEADLESS=1) reads the output and the run folder. It fixes the
  code the usual way (worktree, tests, a phone test, PR, squash-merge, pull of the main checkout), or decides there
  is nothing to fix (a flaky lost tap), and answers with the step's args for only what's left. Its actions show here
  as one short line each; its report goes to ~/claude-plans/_reports/.
- pogo.py then starts over as a fresh process (os.execv, so a pulled fix to any file counts): the step again with
  those args, then the steps after it, every `last` written out as its folder.
At most FIXES fixes and ROUNDS heals per run. A stop that comes back after its fix ends the run. Ctrl-C never heals.

The step's output goes to the pane and to /tmp/pogo-heal/<stamp>.out. Ctrl-C while Claude works stops it and the run.
POGO_CLAUDE_BIN: a stand-in for `claude` (tests/heal.py). The gymfeed timer skips itself while pogo.py runs.
"""
import collections, fcntl, json, os, re, subprocess, sys, threading, time

HERE = os.path.dirname(os.path.realpath(__file__))  # the repo root: the main checkout when run live
DIR = "/tmp/pogo-heal"
REPORTS = os.path.expanduser("~/claude-plans/_reports")
FIXES = 2  # code fixes per run
ROUNDS = 4  # heals of any kind per run (fixes, reruns with no fix, waits)
WAITS = 3  # "can't reach the iPhone" waits per run
WAIT_S = 300
EARLY_S = 180  # a can't-reach stop this soon after the step started did nothing yet: same args again
CLAUDE_S = 2 * 3600  # Claude's time for one heal
FREE_S = 15 * 60  # wait at most this long for the phone to be free before the rerun
TAIL = 80  # lines of output Claude gets in its prompt (the whole file is there to read)

END = re.compile(r"\b(STOPPED|CRASHED): (.*)")
HUMAN = ("is using the Pixel", "is using the iPhone", "phone not connected", "PIN", "the phone is locked",
         "unlock it by hand", "won't let this terminal take pictures")
CANT_REACH = "iPhone Mirroring can't reach the iPhone"


def say(msg):
    print(time.strftime("%H:%M:%S ") + "heal: " + msg, flush=True)


# ---------- the state that rides along through each os.execv ----------

def state():
    try:
        s = json.loads(os.environ.get("POGO_HEAL_STATE", ""))
    except ValueError:
        s = {}
    for k in ("fixes", "rounds", "waits"):
        s.setdefault(k, 0)
    s.setdefault("fixed", [])  # signatures of the stops a fix was made for
    s.setdefault("prs", [])
    return s


# ---------- running a step ----------

def out_file():
    os.makedirs(DIR, exist_ok=True)
    return os.path.join(DIR, time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}.out")


def tee(cmd, env, path):
    """run cmd, its output to the pane and to path -> (exit code, its last lines). Ctrl-C reaches the child too
    (same terminal): wait for it to log its own end, as pogo.run_one does"""
    lines = collections.deque(maxlen=400)
    env = dict(env, PYTHONUNBUFFERED="1")
    interrupted = False
    with open(path, "a") as f:
        p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             errors="replace", bufsize=1)
        while True:
            try:
                for line in p.stdout:
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    f.write(line)
                    lines.append(line.rstrip("\n"))
                code = p.wait()
                break
            except KeyboardInterrupt:
                interrupted = True
    return (130 if interrupted and code == 0 else code), list(lines)


def signature(lines):
    """the step's last STOPPED / CRASHED line, numbers and paths taken out: the same stop again reads the same"""
    for l in reversed(lines):
        m = END.search(l)
        if m:
            s = re.sub(r"/\S+", "<path>", m.group(0))
            return re.sub(r"\d+", "#", s)[:200]
    return next((l for l in reversed(lines) if l.strip()), "no output")[:200]


def end_line(lines):
    return next((l for l in reversed(lines) if END.search(l)), "")


def needs_you(line):
    return next((h for h in HUMAN if h in line), None)


# ---------- the phone free again ----------

def lock_free(phone):
    try:
        with open(f"/tmp/pogo-{phone}.lock", "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)
        return True
    except OSError:
        return False


def wait_free(phones):
    end = time.time() + FREE_S
    said = False
    while True:
        busy = [p for p in phones if not lock_free(p)]
        if not busy:
            return True
        if time.time() > end:
            return False
        if not said:
            say(f"waiting for the {', '.join(busy)} to be free")
            said = True
        time.sleep(10)


def phones_of(phone):
    return {"android": ["android"], "both": ["iphone", "android"]}.get(phone, ["iphone"])


# ---------- asking Claude ----------

PROMPT = """You are healing a Pokémon GO storage script that stopped early. Nobody is watching: never ask a question,
decide. The repo's rules are in {repo}/CLAUDE.md and your memory; follow them (worktree, PR, squash-merge, pull,
wt_cleanup.py, never edit the main checkout).

The run: {cmd}
POGO_PHONE: {phone}
Step {n} of {total} failed: {step}
Exit code: {code} (1 = STOPPED, 2 = CRASHED)
Its end: {end}
Its whole output: {out}
Its run folder (log.txt, stop/crash captures): {folder}
Earlier heals this run: {history}

The last lines of its output:
{tail}

Do this:
1. Find why it stopped. Read the run folder's log.txt and the code. For a picture use skills/shared/peek.py (--text
   first). Saved iPhone shots and the Pixel come first, as the testing rules say.
2. Decide which kind of stop it is:
   - A bug in the code: fix it.
   - Not a bug, no code change helps (the phone went out of reach, a lost tap or lost screen seen once, the game
     itself acting up): no fix, just run it again.
   - Something only Ajay can decide (a rule change, a new screen whose right answer is a judgment call) or do: stop.
   A lost tap or lost screen on the iPhone has no known cause. Don't guess a fix for one seen once: run it again.
   Earlier heals list the stops already fixed this run. The same one again means the fix didn't work: stop.
3. To fix: a worktree from origin/main, the fix, the tests CLAUDE.md lists for what you changed, then a phone test of
   the fix on the phone that failed, with a small --limit. Run the phone test in the foreground (watch.py, no
   run_in_background: nothing would wake you), and use watch.py --wait if it outlasts the Bash timeout. Before the
   phone test and before pulling the main checkout, check with ps that no phone script runs other than
   pogo.py pid {pid} (this run, waiting for you). Then commit, push, PR, squash-merge, ExitWorktree keep, pull the
   main checkout, wt_cleanup.py. If the test fails and you can't make it pass, close the PR and stop.
4. Work out the step's args to run again with only what's left. Read the step's script top comment for how it
   carries on (ivc `sort <run dir>`, trade --done N, a --limit less what got done, a run folder in place of `last`).
   The old args: {args}. A --limit, if any, may only go down. Args for this one step only: the steps after it run
   on their own. Nothing left: action "next". With POGO_PHONE=both and one phone fine, give the phone that failed.
5. Write a short report to {reports}/{date}-heal-{name}-{hhmm}.md: what stopped, why, what you did, the PR.
6. Your last line, exactly one line of JSON after the word HEAL:
HEAL {{"action": "rerun" | "next" | "stop", "fixed": true | false, "args": ["..."], "phone": "ios" | "android" | null, "pr": "<url>" | null, "why": "<one short sentence>"}}
"""


def show(ev):
    """one short pane line per tool Claude uses"""
    if ev.get("type") != "assistant":
        return
    for c in ev.get("message", {}).get("content", []) or []:
        if c.get("type") != "tool_use":
            continue
        i = c.get("input") or {}
        what = i.get("description") or i.get("file_path") or i.get("pattern") or i.get("command") or ""
        say(f"  claude {c.get('name')}: {str(what).splitlines()[0][:100] if what else ''}")


def ask_claude(prompt):
    """-> (Claude's last text, None) or (None, why it failed)"""
    cmd = [os.environ.get("POGO_CLAUDE_BIN", "claude"), "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--dangerously-skip-permissions"]
    env = dict(os.environ, CLAUDE_HEADLESS="1")
    env.pop("POGO_HEAL_STATE", None)
    try:
        p = subprocess.Popen(cmd, cwd=HERE, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             errors="replace", stdin=subprocess.DEVNULL)
    except OSError as e:
        return None, f"can't start claude: {e}"
    try:
        return read_claude(p)
    except KeyboardInterrupt:
        p.kill()
        return None, "Ctrl-C: stopped Claude (a worktree or PR it made may be left: wt_cleanup.py --dry-run shows)"


def read_claude(p):
    late = threading.Timer(CLAUDE_S, p.kill)  # (a long Bash call prints nothing for a while: no check per line)
    late.daemon = True
    late.start()
    result, last_text, other = None, "", collections.deque(maxlen=5)
    for line in p.stdout:
        try:
            ev = json.loads(line)
        except ValueError:
            other.append(line.strip())
            continue
        show(ev)
        if ev.get("type") == "assistant":
            texts = [c.get("text", "") for c in ev.get("message", {}).get("content", []) or [] if c.get("type") == "text"]
            last_text = texts[-1] if texts else last_text
        elif ev.get("type") == "result":
            result = ev
    code = p.wait()
    if not late.is_alive():
        return None, f"Claude took over {CLAUDE_S // 60} minutes: stopped it"
    late.cancel()
    if result is None:
        return None, f"claude ended (exit {code}) with no result: {' | '.join(other)[:300]}"
    if result.get("is_error"):
        return None, f"claude failed: {str(result.get('result') or result.get('subtype'))[:300]}"
    return (result.get("result") or last_text), None


def answer(text):
    """the HEAL {...} line -> dict, or None"""
    for l in reversed((text or "").splitlines()):
        l = l.strip().strip("`")
        if l.startswith("HEAL"):
            try:
                a = json.loads(l[4:].strip())
            except ValueError:
                return None
            return a if isinstance(a, dict) else None
    return None


# ---------- the next chain ----------

def limit_of(args):
    return int(args[args.index("--limit") + 1]) if "--limit" in args and args.index("--limit") + 1 < len(args) \
        and str(args[args.index("--limit") + 1]).isdigit() else None


def check_answer(a, old_args, phone):
    """-> why it can't be used, or None"""
    if a.get("action") not in ("rerun", "next", "stop"):
        return f"no action rerun/next/stop: {a.get('action')!r}"
    if a["action"] != "rerun":
        return None
    args = a.get("args")
    if not isinstance(args, list) or not all(isinstance(x, str) for x in args):
        return "args isn't a list of words"
    old, new = limit_of(old_args), limit_of(args)
    if "--limit" in args and new is None:
        return "--limit with no number"
    if old is not None and (new is None or new > old):
        return f"--limit went from {old} to {new}"
    p = a.get("phone")
    if p not in (None, "ios", "android"):
        return f"phone {p!r}"
    if p and phone != "both" and p != phone:
        return f"phone {p} on a {phone} run"
    return None


def chain(steps, i, args, folder_of, last):
    """the run from step i on: step i with args, then the ones after it. A `last` whose folder no earlier step of the
    new chain makes becomes that folder's path"""
    out, made = [], set()
    for j, s in enumerate(steps[i:]):
        a = list(args) if j == 0 else list(s[1:])
        f = folder_of(s[0])
        a = [last[f] if x == "last" and f not in made and f in last else x for x in a]
        out.append([s[0]] + a)
        made.add(f)
    return out


def flat(steps):
    out = []
    for k, s in enumerate(steps):
        out += (["+"] if k else []) + s
    return out


def restart(new, st, phone_first=None):
    """pogo.py again, a fresh process: new code counts"""
    env = dict(os.environ, POGO_HEAL_STATE=json.dumps(st))
    env.pop("POGO_HEAL_PHONE", None)
    if phone_first:
        env["POGO_HEAL_PHONE"] = phone_first
    say("running again: " + " ".join(flat(new)))
    sys.stdout.flush()
    os.execve(sys.executable, [sys.executable, os.path.join(HERE, "pogo.py"), "--heal", *flat(new)], env)


# ---------- one heal ----------

def handle(steps, i, args, code, lines, out, started, folder_of, last, check, phone):
    """step i (0-based) ended with code. Starts the run over (never returns) or -> the run's exit code.
    last: the run folders made before step i (a `last` in the new chain becomes one of them)"""
    if code not in (1, 2):
        return code
    st = state()
    end = end_line(lines) or (lines[-1] if lines else "")
    sig = signature(lines)
    name = steps[i][0]
    if (h := needs_you(end)) and CANT_REACH not in end:
        say(f"stopped for you ({h}): {end.strip()[:160]}")
        return code
    if st["rounds"] >= ROUNDS:
        say(f"{ROUNDS} heals this run already: stopping here")
        return code
    st["rounds"] += 1
    if CANT_REACH in end and time.time() - started < EARLY_S:
        if st["waits"] >= WAITS:
            say(f"the iPhone was out of reach {WAITS + 1} times: stopping. Lock it, leave it near the Mac, run again")
            return code
        st["waits"] += 1
        say(f"the iPhone is out of reach: trying again in {WAIT_S // 60} minutes ({st['waits']}/{WAITS})")
        time.sleep(WAIT_S)
        restart(chain(steps, i, args, folder_of, last), st)
    if sig in st["fixed"]:
        say(f"the stop that was fixed came back: stopping. {end.strip()[:160]}")
        return code
    hist = "; ".join(f"fixed {x}" for x in st["fixed"]) or "none"
    now = time.localtime()
    folder = next((l.split("run folder: ", 1)[1].strip() for l in reversed(lines) if "run folder: " in l), "unknown")
    prompt = PROMPT.format(repo=HERE, cmd=" ".join(flat(steps)), phone=phone, n=i + 1, total=len(steps),
                           step=" ".join([name] + args), code=code, end=end.strip(), out=out, folder=folder,
                           history=hist, tail="\n".join(lines[-TAIL:]), pid=os.getpid(), args=json.dumps(args),
                           reports=REPORTS, date=time.strftime("%Y-%m-%d", now), name=name,
                           hhmm=time.strftime("%H%M", now))
    say(f"step {i + 1} ({name}) ended: {end.strip()[:160]}")
    say("asking Claude to find why and fix it (Ctrl-C stops it)")
    text, err = ask_claude(prompt)
    if err:
        say(err)
        return code
    a = answer(text)
    if a is None:
        say("Claude's answer had no HEAL line: stopping. Its last words: " + (text or "")[-300:].replace("\n", " "))
        return code
    if (bad := check_answer(a, args, phone)):
        say(f"can't use Claude's answer ({bad}): stopping. {json.dumps(a)[:300]}")
        return code
    say(f"Claude: {a['action']}{' (fixed, ' + str(a.get('pr')) + ')' if a.get('fixed') else ''}: {a.get('why', '')}")
    if a.get("fixed"):
        st["fixes"] += 1
        st["fixed"].append(sig)
        if a.get("pr"):
            st["prs"].append(a["pr"])
    if a["action"] == "stop":
        return code
    if a.get("fixed") and st["fixes"] > FIXES:
        say(f"that was fix {st['fixes']}, over {FIXES}: stopping here")
        return code
    if a["action"] == "next":
        if i + 1 >= len(steps):
            return 0
        new = chain(steps, i + 1, steps[i + 1][1:], folder_of, last)
        phone_first = None
    else:
        new = chain(steps, i, a["args"], folder_of, last)
        phone_first = a.get("phone") if phone == "both" else None
    try:
        check(new)
    except SystemExit as e:
        say(f"the next run doesn't check out: {str(e.code).splitlines()[0][:200]}")
        return code
    if not wait_free(phones_of(phone_first or phone)):
        say(f"the phone is still in use after {FREE_S // 60} minutes: stopping")
        return code
    restart(new, st, phone_first)
