#!/usr/bin/env python3
"""Checks merge_gate.py with no GitHub and no phone: a made-up repo (a skill file, quick stand-in tests), a stand-in
`gh` (POGO_GH_BIN) that answers from a made-up PR, and made-up watch.py run records.

  python3 tests/gate.py
"""
import io, json, os, signal, subprocess, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import merge_gate as g
import watch

T = tempfile.mkdtemp(prefix="gate-test-")
REPO = os.path.join(T, "repo")
WT = os.path.join(T, "wt")
BARE = os.path.join(T, "PoGO-inventory-scripts.git")  # (the origin check wants the repo's name in the url)
PR = os.path.join(T, "pr.json")
g.WATCH_DIR = os.path.join(T, "watch")
g.ROOT = REPO
os.makedirs(g.WATCH_DIR)


def sh(*cmd, cwd=REPO):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


SKILL = '''import ui


def pick(x):
    if ui.ANDROID:
        return x + 1
    else:
        return x - 1


def use():
    return pick(3)
'''
EXTRA = '''

def extra():
    a = 1
    b = 2
    return a + b
'''  # (new at the head: lines 16-18, after pick's line 6)
HEAD_SKILL = SKILL.replace("x + 1", "x + 2") + EXTRA
os.makedirs(REPO)
sh("git", "init", "-q", "-b", "main")
sh("git", "config", "user.email", "t@t")
sh("git", "config", "user.name", "t")
write(os.path.join(REPO, "skills/aa/run.py"), SKILL)
write(os.path.join(REPO, "skills/bb/other.py"), "import run\n\n\ndef go():\n    return run.pick(1)\n\n\ndef extra():\n    return 0\n")
write(os.path.join(REPO, "README.md"), "hi\n")
for t in g.TESTS:
    write(os.path.join(REPO, f"tests/{t}.py"), "import os, sys\nif os.environ.get('GATE_FAIL') == %r:\n"
          "    print('1 WRONG'); sys.exit(1)\nprint('all 3 answers the same')\n" % t)
sh("git", "add", "-A")
sh("git", "commit", "-qm", "base")
sh("git", "init", "-q", "--bare", BARE, cwd=T)
sh("git", "remote", "add", "origin", BARE)
sh("git", "push", "-q", "origin", "main")
sh("git", "worktree", "add", "-q", "-b", "fix/aa", WT, "origin/main")
write(os.path.join(WT, "skills/aa/run.py"), HEAD_SKILL)
write(os.path.join(WT, "README.md"), "hi there\n")
sh("git", "commit", "-qam", "fix", cwd=WT)
HEAD = sh("git", "rev-parse", "HEAD", cwd=WT)
FILES = ["README.md", "skills/aa/run.py"]

os.environ["POGO_GH_BIN"] = os.path.join(T, "gh")
write(os.environ["POGO_GH_BIN"], f"""#!/usr/bin/env python3
import json, sys
pr = json.load(open({PR!r}))
if pr.get("fail"):
    sys.exit("HTTP 502")
if sys.argv[1:3] == ["pr", "view"]:
    print(json.dumps(pr))
elif sys.argv[1:3] == ["pr", "diff"]:
    print("\\n".join(pr["files"]))
""")
os.chmod(os.environ["POGO_GH_BIN"], 0o755)


def pr(body="", files=FILES, **kw):
    write(PR, json.dumps(dict(dict(number=7, url="https://x/pull/7", state="OPEN", headRefName="fix/aa",
                                   headRefOid=HEAD, baseRefName="main"), body=body, files=files, **kw)))


def watch_run(stamp, rc=0, cwd=WT, script="skills/aa/run.py"):
    """a real watch.py record of a run of the skill as the checkout at cwd has it now"""
    cmd = ["python3", os.path.join(cwd, script), "--limit", "1"]
    write(os.path.join(g.WATCH_DIR, stamp + ".json"), json.dumps(dict(watch.origin(cmd), rc=rc)))


def ran_lines(stamp, *hits, name="1-1", blob=None):
    """a made-up line file of a run: the lines of skills/aa/run.py it ran (blob: the copy it says it ran)"""
    d = {"skills/aa/run.py": sorted(hits)}
    if blob:
        d["__blobs__"] = {"skills/aa/run.py": blob}
    write(os.path.join(g.WATCH_DIR, f"{stamp}.lines.{name}"), json.dumps(d))


def notes(o):
    return o["hookSpecificOutput"].get("additionalContext", "") if o else ""


def clear_runs():
    for f in os.listdir(g.WATCH_DIR):
        os.remove(os.path.join(g.WATCH_DIR, f))


def gate(command="gh pr merge 7 --squash --delete-branch", cwd=WT, tool="Bash"):
    """the hook, as Claude Code calls it -> its JSON answer or None"""
    stdin, stdout = sys.stdin, sys.stdout
    sys.stdin, sys.stdout = io.StringIO(json.dumps({"tool_name": tool, "cwd": cwd,
                                                    "tool_input": {"command": command}})), io.StringIO()
    try:
        g.main(["--hook"])
        text = sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout = stdin, stdout
    return json.loads(text) if text.strip() else None


def denied(o, *words):
    r = o and o["hookSpecificOutput"].get("permissionDecision") == "deny" and o["hookSpecificOutput"].get(
        "permissionDecisionReason", "")
    return bool(r) and all(w in r for w in words)


def passed(o):
    return o is not None and "permissionDecision" not in o["hookSpecificOutput"]


fails = 0


def case(what, got, ok):
    global fails
    good = ok(got)
    fails += not good
    print(("ok    " if good else "WRONG ") + what + ("" if good else f"\n      got {json.dumps(got)[:1500]}"))


SIB = "Siblings: other.py go checked, the iPhone side wants +2 too, done"

pr()
case("not a merge: nothing", gate("git status"), lambda o: o is None)
case("a merge only in text: nothing", gate("echo 'gh pr merge 7' && grep -r 'gh pr merge' ."), lambda o: o is None)
case("another repo's merge: nothing", gate("gh pr merge 7 -R someone/else --squash"), lambda o: o is None)
case("another repo's PR url: nothing", gate("gh pr merge https://github.com/someone/else/pull/7"),
     lambda o: o is None)
case("not a Bash call: nothing", gate(tool="Read"), lambda o: o is None)
case("a merge outside the repo with no -R: nothing", gate(cwd=T), lambda o: o is None)

o = gate()
case("phone code, no phone run, no Siblings: blocked, both said", o,
     lambda o: denied(o, "1. No phone test", WT + "/watch.py", "--limit 1", "2. No `Siblings:` line", "gh pr edit 7"))
case("the siblings list: the change, its caller in another skill, the one-sided phone branch", o,
     lambda o: denied(o, "skills/aa/run.py pick: changed", "skills/bb/other.py:5 in go", "skills/aa/run.py:12 in use",
                      "`if ui.ANDROID`: only the if side changed")
     and "skills/aa/run.py use:" not in o["hookSpecificOutput"]["permissionDecisionReason"])

o = gate("cd " + WT + " && gh pr merge --squash", cwd=T)
case("no number: the branch's PR, after a cd", o, lambda o: denied(o, "PR #7") or denied(o, "No phone test"))

watch_run("20260101-000001")
pr(body="Fixes it.\n" + SIB)
o = gate()
case("a phone run of the head code + Siblings: passes, the list comes as notes", o,
     lambda o: passed(o) and "phone test: run 20260101-000001" in o["hookSpecificOutput"]["additionalContext"]
     and "only the if side changed" in o["hookSpecificOutput"]["additionalContext"]
     and "tests: all passed" in o["hookSpecificOutput"]["additionalContext"])
case("a run with no line files: a note, not a block", o,
     lambda o: passed(o) and "changed lines: not checked" in notes(o) and "20260101-000001" in notes(o))

ran_lines("20260101-000001", 1, 4, 5, 6, 11, 15, 16, 17, 18)
o = gate()
case("every changed line ran: says so", o, lambda o: passed(o) and "all 4 changed code lines ran" in notes(o))

clear_runs()
watch_run("20260101-000001")
ran_lines("20260101-000001", 1, 4, 5, 6, 15, name="1-1")
ran_lines("20260101-000001", 16, 17, name="2-1")
write(os.path.join(g.WATCH_DIR, "20260101-000001.lines.3-1.tmp"), json.dumps({"skills/aa/run.py": [18]}))
o = gate()
case("one changed line never ran: passes, a note with it by function (two pid files merged, a .tmp left out)", o,
     lambda o: passed(o) and "1 of 4 changed code lines never ran" in notes(o)
     and "skills/aa/run.py extra: line 18" in notes(o) and "either reach them with a run that does" in notes(o))

clear_runs()
watch_run("20260101-000001")
ran_lines("20260101-000001", 1, 4, 5, 6, 15, name="1-1", blob=g.blob(HEAD, "skills/aa/run.py"))
ran_lines("20260101-000001", 16, 17, 18, name="2-1", blob="0" * 40)
o = gate()
case("lines from a process that ran another copy of the file (a heal pulled new code mid-run) don't count", o,
     lambda o: denied(o, "3 of 4 changed code lines never ran"))

clear_runs()
watch_run("20260101-000001")
ran_lines("20260101-000001", 1, 4, 5, 6, 15)
o = gate()
case("most changed lines never ran, no Unreached: line: blocked, lists them, asks for the line", o,
     lambda o: denied(o, "3 of 4 changed code lines never ran", "skills/aa/run.py extra: lines 16, 17, 18",
                      "`Unreached: <why"))
pr(body="Fixes it.\n" + SIB + "\nUnreached: extra() runs only on a full moon")
o = gate()
case("most never ran, with an Unreached: line: passes, the reason and the list in the notes", o,
     lambda o: passed(o) and "3 of 4" in notes(o) and "full moon" in notes(o))
watch_run("20260101-000006")
ran_lines("20260101-000006", 16, 17, 18)
pr(body="Fixes it.\n" + SIB)
case("two runs of the head code: their lines add up", gate(),
     lambda o: passed(o) and "all 4 changed code lines ran" in notes(o) and "runs 2026" in notes(o))
clear_runs()
watch_run("20260101-000001")

case("-R this repo and a url of this repo count too",
     [gate("gh pr merge -R a-jay85/PoGO-inventory-scripts 7"),
      gate("gh pr merge https://github.com/a-jay85/PoGO-inventory-scripts/pull/7 --squash")],
     lambda os_: all(passed(o) for o in os_))

clear_runs()
write(os.path.join(WT, "skills/aa/run.py"), SKILL.replace("x + 1", "x + 3"))
watch_run("20260101-000002")  # (run with an edit, then the edit went away: the run tested other code)
sh("git", "checkout", "--", "skills/aa/run.py", cwd=WT)
case("a run of other contents: blocked, says run it again", gate(),
     lambda o: denied(o, "20260101-000002", "ran other contents of skills/aa/run.py", "run it again"))

clear_runs()
sh("git", "checkout", "-q", "--detach", "origin/main", cwd=WT)
write(os.path.join(WT, "skills/aa/run.py"), HEAD_SKILL)
watch_run("20260101-000003")  # (tested before the commit: HEAD was the base, the file the PR's)
sh("git", "checkout", "-q", "--", ".", cwd=WT)
sh("git", "checkout", "-q", "fix/aa", cwd=WT)
case("a run before the commit, of the same file contents: passes", gate(), passed)

clear_runs()
watch_run("20260101-000005", script="tests/readers.py")
case("a run of a test, not a phone script: doesn't count", gate(), lambda o: denied(o, "No phone test"))

clear_runs()
watch_run("20260101-000004", rc=1)
case("a run of the head code that stopped: blocked, says its exit", gate(),
     lambda o: denied(o, "20260101-000004", "ended with exit 1"))

clear_runs()
pr(body="No phone test: short\n" + SIB)
case("No phone test: with a short reason: blocked", gate(), lambda o: denied(o, "too short"))
pr(body="No phone test: the screen it handles shows once a year\n" + SIB)
o = gate()
case("No phone test: with a reason: passes, with a warning", o,
     lambda o: passed(o) and "no phone test: the screen it handles" in o.get("systemMessage", ""))

pr(body="", files=["README.md"])
o = gate()
case("only docs: passes, no phone test, no Siblings, no tests", o,
     lambda o: passed(o) and "tests: skipped" in o["hookSpecificOutput"]["additionalContext"])

pr(body="No phone test: the screen it handles shows once a year\n" + SIB)
os.environ["GATE_FAIL"] = "verdicts"
o = gate()
os.environ.pop("GATE_FAIL")
case("a failing test: blocked, with its last lines", o,
     lambda o: denied(o, "tests/verdicts.py ended with exit 1", "1 WRONG") and "readers.py" not in
     o["hookSpecificOutput"]["permissionDecisionReason"])

write(os.path.join(REPO, "tests/lints.py"), "print('all 9 files clean')\n")
case("an optional test passes on exit 0 and any 'all ...' line", g.run_tests(REPO), lambda b: b == [])
write(os.path.join(REPO, "tests/lints.py"), "print('3 new')\n")
case("an optional test with no 'all ...' line fails", g.run_tests(REPO), lambda b: len(b) == 1 and "lints" in b[0])
os.remove(os.path.join(REPO, "tests/lints.py"))

write(os.path.join(WT, "stray.py"), "x = 1\n")
os.environ["GATE_FAIL"] = "layout"
o = gate()
os.environ.pop("GATE_FAIL")
os.remove(os.path.join(WT, "stray.py"))
case("a dirty worktree: tests run in a temporary checkout of the head, which is removed",
     [o, sh("git", "worktree", "list")], lambda g_: denied(g_[0], "tests/layout.py") and g_[1].count("\n") == 1)

pr(body=SIB, fail=True)
case("gh failing: blocked, never let through", gate(), lambda o: denied(o, "couldn't check", "HTTP 502"))

NPT = "No phone test: the screen it handles shows once a year\n"
pr(title="fix(aa): faster pick", body=NPT + SIB)
case("a speed PR with no Speed elsewhere: line: blocked, lists the same-named function in another skill", gate(),
     lambda o: denied(o, "is about speed (it says 'faster')", "`Speed elsewhere:",
                      "skills/aa/run.py extra: also in skills/bb/other.py:8"))
pr(title="fix(aa): pick", body=NPT + SIB + "\nTaps went 2.0 s -> 1.2 s")
case("a speed PR found by the body's timings: blocked too", gate(), lambda o: denied(o, "`Speed elsewhere:"))
pr(title="fix(aa): faster pick", body=NPT + SIB + "\nSpeed elsewhere: bb's extra is another thing, nothing to do")
case("a speed PR with a Speed elsewhere: line: passes, the line and the list in the notes", gate(),
     lambda o: passed(o) and "another thing" in notes(o) and "skills/bb/other.py:8" in notes(o))
pr(title="docs: faster", body="", files=["README.md"])
case("a speed PR of docs only: no Speed elsewhere: needed", gate(), passed)

pr(body=SIB, state="MERGED")
case("a PR already merged: let through (gh says so itself)", gate(), passed)

real = g.check
g.check = lambda *a: 1 / 0
try:
    o = gate()
finally:
    g.check = real
case("the gate crashing: blocked, with the crash", o, lambda o: denied(o, "crashed", "ZeroDivisionError"))

# ---------- what counts as a changed code line ----------

SRC = """\"\"\"doc\"\"\"
import os


@property
def f(a,
      b):
    \"\"\"doc
    more\"\"\"
    # note
    try:
        y = call(a,
                 b)
    except KeyError:
        pass
    else:
        y = 2
    if a:
        return 1
    elif b:
        return 2
"""
got = {u[0]: sorted(u[1]) for u in g.units(SRC, "x.py")}
case("code lines: no docstring, decorator, def, comment, try:, else:; a call over two lines is one", got,
     lambda d: d == {2: [2], 12: [12, 13], 14: [14], 15: [15], 17: [17], 18: [18], 19: [19], 20: [20], 21: [21]})

# ---------- the tracer, as watch.py starts it ----------

TR = os.path.join(T, "traced")
os.makedirs(TR)
write(os.path.join(TR, "a.py"), """import os, subprocess, sys


def f(x):
    if x:
        return 1
    return 2


f(True)
subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "b.py")])
""")
write(os.path.join(TR, "b.py"), "import json\ny = json.dumps(3)\nif y == 4:\n    print('no')\n")
write(os.path.join(TR, "c.py"), "import sys, time\nopen(sys.argv[1], 'w').close()\ntime.sleep(30)\n")
sh("git", "init", "-q", cwd=TR)
watch.DIR = os.path.join(T, "trwatch")
os.makedirs(watch.DIR)
watch.run("20260101-000100", ["python3", os.path.join(TR, "a.py")])


BLOBS = {}


def lines_of(stamp):
    out, n = {}, 0
    for f in os.listdir(watch.DIR):
        if f.startswith(stamp + ".lines."):
            n += 1
            d = json.load(open(os.path.join(watch.DIR, f)))
            BLOBS.update(d.pop("__blobs__", {}))
            for k, v in d.items():
                out.setdefault(k, set()).update(v)
    return n, {k: sorted(v) for k, v in out.items()}


n, got = lines_of("20260101-000100")
case("tracer: a run's lines, its child process's too, one file each, the untaken branch not in it", (n, got),
     lambda x: x == (2, {"a.py": [1, 4, 5, 6, 10, 11], "b.py": [1, 2, 3]}))
case("tracer: each file's git blob, as it was when the process ran it", BLOBS,
     lambda b: b == {f: subprocess.run(["git", "hash-object", os.path.join(TR, f)], capture_output=True, text=True)
                     .stdout.strip() for f in ("a.py", "b.py")})
case("tracer: the run record says where its lines go",
     json.load(open(os.path.join(watch.DIR, "20260101-000100.json"))),
     lambda r: r.get("lines") == os.path.join(watch.DIR, "20260101-000100.lines") and r.get("rc") == 0)

env = watch.trace_env("20260101-000101", TR, dict(os.environ, PYTHONPATH="/somewhere"))
case("tracer: watch.py's env keeps a PYTHONPATH there was, after the tracer's", env["PYTHONPATH"],
     lambda p: p == watch.TRACER + os.pathsep + "/somewhere")
ready = os.path.join(T, "ready")
p = subprocess.Popen([sys.executable, os.path.join(TR, "c.py"), ready], env=env)
end = time.time() + 20
while not os.path.exists(ready) and time.time() < end:
    time.sleep(0.05)
p.send_signal(signal.SIGTERM)
p.wait(timeout=20)
case("tracer: a run stopped by SIGTERM still writes its lines, and still dies of SIGTERM",
     (p.returncode, lines_of("20260101-000101")[1]), lambda x: x == (-signal.SIGTERM, {"c.py": [1, 2, 3]}))

env = dict(os.environ, PYTHONPATH=watch.TRACER)
quiet = subprocess.run([sys.executable, os.path.join(TR, "b.py")], env=env, capture_output=True, text=True)
case("tracer: off with no POGO_TRACE, and Homebrew's sitecustomize still runs", [quiet.returncode, quiet.stderr,
     subprocess.run([sys.executable, "-c", "import sys; print(sys.executable)"], env=env, capture_output=True,
                    text=True).stdout.strip() == subprocess.run([sys.executable, "-c", "import sys; print(sys.executable)"],
                                                                capture_output=True, text=True).stdout.strip()],
     lambda x: x == [0, "", True])
if os.path.exists("/usr/bin/python3"):
    old = subprocess.run(["/usr/bin/python3", os.path.join(TR, "b.py")],
                         env=watch.trace_env("20260101-000102", TR), capture_output=True, text=True)
    case("tracer: an old python3 (no sys.monitoring) runs fine, untraced", [old.returncode, old.stderr],
         lambda x: x == [0, ""])

print(f"\n{'all gate cases right' if not fails else f'{fails} WRONG'}")
sys.exit(1 if fails else 0)
