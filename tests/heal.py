#!/usr/bin/env python3
"""Checks pogo.py --heal (heal.py) with no phone and no Claude: a made-up step that stops, and a stand-in `claude`
(POGO_CLAUDE_BIN) that streams a canned answer. The restart (os.execve) is caught, so each case shows what would run.

  python3 tests/heal.py
"""
import json, os, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import heal, pogo

T = tempfile.mkdtemp(prefix="heal-test-")
heal.DIR = os.path.join(T, "out")
heal.WAIT_S = 0
heal.wait_free = lambda phones: True  # (a real script on a real phone mustn't hold up the test)


class Restarted(Exception):
    pass


def fake_restart(new, st, phone_first=None):
    raise Restarted({"chain": heal.flat(new), "state": st, "phone": phone_first})


heal.restart = fake_restart


def script(name, body):
    path = os.path.join(T, name)
    with open(path, "w") as f:
        f.write(body)
    return path


def step(name, msg, code=1):
    """a step in its own folder that prints msg and ends with code"""
    d = os.path.join(T, name)
    os.makedirs(os.path.join(d, "runs"), exist_ok=True)
    p = os.path.join(d, "run.py")
    with open(p, "w") as f:
        f.write(f"import os, sys, time\nr = os.path.join({d!r}, 'runs', str(time.time()))\nos.makedirs(r)\n"
                f"print({msg!r})\nprint('run folder: ' + r)\nsys.exit({code})\n")
    pogo.STEPS[name] = (p, {"fallen"}, set())


CALLS = os.path.join(T, "claude-calls")
os.environ["POGO_CLAUDE_BIN"] = script("claude", f"""#!/usr/bin/env python3
import json, os, sys
open({CALLS!r}, "a").write(sys.argv[2][:40] + "\\n")
print(json.dumps({{"type": "assistant", "message": {{"content": [{{"type": "tool_use", "name": "Bash",
      "input": {{"description": "read the log"}}}}]}}}}))
reply = os.environ["FAKE_REPLY"]
err = reply == "ERROR"
print(json.dumps({{"type": "result", "is_error": err, "result": "quota hit" if err else "looked\\n" + reply}}))
""")
os.chmod(os.environ["POGO_CLAUDE_BIN"], 0o755)


def calls():
    return len(open(CALLS).read().splitlines()) if os.path.exists(CALLS) else 0


def run(argv, reply=None, st=None):
    """pogo.main(--heal argv) -> ('restart', what) or ('exit', code), and how many times Claude was asked"""
    if os.path.exists(CALLS):
        os.remove(CALLS)
    os.environ["FAKE_REPLY"] = "HEAL " + json.dumps(reply) if isinstance(reply, dict) else (reply or "")
    os.environ["POGO_HEAL_STATE"] = json.dumps(st or {})
    os.environ.pop("POGO_PHONE", None)
    try:
        return ("exit", pogo.main(["--heal", *argv])), calls()
    except Restarted as e:
        return ("restart", e.args[0]), calls()
    finally:
        sys.stdout.flush()


fails = 0


def case(what, got, ok):
    global fails
    good = ok(got)
    fails += not good
    print(("ok    " if good else "WRONG ") + what + ("" if good else f"\n      got {got}"))


rerun = {"action": "rerun", "fixed": True, "args": ["--limit", "3"], "phone": None, "pr": "https://x/pr/1",
         "why": "a misread"}
os.environ["POGO_KEEP_OPEN"] = "1"  # (a chain mustn't close a real phone at its end)

step("aa", "12:00:01 STOPPED: lost the screen at /a/b/c 42")
step("bb", "fine", code=0)
step("cc", "12:00:01 STOPPED: Pixel is using the Pixel: run this after it ends")
step("dd", "12:00:01 STOPPED: iPhone Mirroring can't reach the iPhone: lock the iPhone")
step("ee", "12:00:01 interrupted", code=130)

print("signature: " + heal.signature(["x", "12:00 STOPPED: lost tile 7 at /tmp/a/b.png", "run folder: /x"]))
case("signature drops numbers and paths",
     heal.signature(["12:00 STOPPED: lost tile 7 at /tmp/a/b.png"]), lambda s: s == "STOPPED: lost tile # at <path>")

(r, n) = run(["aa", "--limit", "5", "+", "bb"], rerun)
case("a fix reruns the step with Claude's args, then the rest", (r, n),
     lambda g: g[0][0] == "restart" and g[0][1]["chain"] == ["aa", "--limit", "3", "+", "bb"] and g[1] == 1
     and g[0][1]["state"]["fixes"] == 1 and len(g[0][1]["state"]["fixed"]) == 1)

(r, n) = run(["bb", "+", "aa", "+", "bb", "fallen", "last"], dict(rerun, args=[]))
case("a later `last` whose folder isn't run again becomes the path", r,
     lambda g: g[0] == "restart" and g[1]["chain"][:2] == ["aa", "+"] and g[1]["chain"][-1].startswith(T))

(r, n) = run(["aa", "--limit", "5"], dict(rerun, args=["--limit", "9"]))
case("a --limit that goes up is refused", r, lambda g: g == ("exit", 1))

(r, n) = run(["aa"], dict(rerun, args=["sort", "x"]))
case("args the step doesn't take are refused (pogo's own check)", r, lambda g: g == ("exit", 1))

(r, n) = run(["aa"], "I fixed it but forgot the line")
case("no HEAL line: stop", r, lambda g: g == ("exit", 1))

(r, n) = run(["aa"], "ERROR")
case("Claude failing (quota): stop", r, lambda g: g == ("exit", 1))

(r, n) = run(["aa"], {"action": "stop", "fixed": False, "why": "a rule for Ajay"})
case("Claude says stop: stop", r, lambda g: g == ("exit", 1))

(r, n) = run(["aa", "+", "bb"], {"action": "next", "fixed": False})
case("nothing left: on to the next step", r, lambda g: g[0] == "restart" and g[1]["chain"] == ["bb"])

(r, n) = run(["aa"], {"action": "next", "fixed": False})
case("nothing left in the last step: the run ends fine", r, lambda g: g == ("exit", 0))

sig = heal.signature(["STOPPED: lost the screen at /a 42"])
(r, n) = run(["aa"], rerun, st={"fixed": [sig], "fixes": 1, "rounds": 1})
case("the stop that was fixed comes back: stop, Claude not asked", (r, n), lambda g: g == (("exit", 1), 0))

(r, n) = run(["aa"], rerun, st={"rounds": heal.ROUNDS})
case("too many heals: stop, Claude not asked", (r, n), lambda g: g == (("exit", 1), 0))

(r, n) = run(["aa"], rerun, st={"fixes": heal.FIXES, "fixed": ["other"], "rounds": 1})
case("a fix over FIXES: stop after it", r, lambda g: g == ("exit", 1))

(r, n) = run(["cc"], rerun)
case("a stop for you: stop, Claude not asked", (r, n), lambda g: g == (("exit", 1), 0))

(r, n) = run(["dd", "--limit", "4"], rerun)
case("can't reach the iPhone, early: same args again after a wait, no Claude", (r, n),
     lambda g: g[0][0] == "restart" and g[0][1]["chain"] == ["dd", "--limit", "4"] and g[1] == 0
     and g[0][1]["state"]["waits"] == 1)

(r, n) = run(["dd"], rerun, st={"waits": heal.WAITS})
case("can't reach the iPhone too many times: stop", (r, n), lambda g: g == (("exit", 1), 0))

(r, n) = run(["ee"], rerun)
case("Ctrl-C: never healed", (r, n), lambda g: g == (("exit", 130), 0))

os.environ["POGO_PHONE"] = "both"
try:
    os.environ["FAKE_REPLY"] = "HEAL " + json.dumps(dict(rerun, phone="ios"))
    os.environ["POGO_HEAL_STATE"] = "{}"
    pogo.main(["--heal", "aa", "--limit", "5"])
    r = None
except Restarted as e:
    r = e.args[0]
finally:
    os.environ.pop("POGO_PHONE")
case("POGO_PHONE=both: the rerun goes to the phone that failed", r, lambda g: g and g["phone"] == "ios")

os.environ["POGO_HEAL_PHONE"] = "android"
os.environ["FAKE_REPLY"] = ""
seen = []
real_tee = heal.tee
heal.tee = lambda cmd, env, out: (seen.append(env.get("POGO_PHONE")), (0, []))[1]
try:
    pogo.main(["--heal", "bb", "+", "bb"])
finally:
    heal.tee = real_tee
case("POGO_HEAL_PHONE goes to the first step only", seen, lambda g: g[0] == "android" and g[1] != "android")

print(f"\n{'all heal cases right' if not fails else f'{fails} WRONG'}")
sys.exit(1 if fails else 0)
