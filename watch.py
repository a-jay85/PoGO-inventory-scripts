#!/usr/bin/env python3
"""Run a phone script quietly: no output while it runs, a short summary when it ends.

  POGO_PHONE=android python3 watch.py caffeinate -dimsu python3 pogo.py pvpc --limit 5
  python3 watch.py --wait        wait again for the newest run (after the waiter itself timed out)

Claude starts it with Bash run_in_background, so a run makes one notice: the end. The script runs detached
(its own session), so it keeps going if the waiter is killed. Everything it prints goes to
/tmp/pogo-watch/<stamp>.log; read that file for details. <stamp>.json says where the run came from (the command,
the script's git checkout, its HEAD, its files' state as a tree, POGO_PHONE, start, end, exit code): merge_gate.py
reads it to find a PR's phone test.

The summary is the exit code, the STOPPED / CRASHED / interrupted / error lines, and the last few lines.
"""
import json, os, re, subprocess, sys, tempfile, time

DIR = "/tmp/pogo-watch"
ALARM = re.compile(r"STOPPED|CRASHED|interrupted|Error")
TAIL = 4


def git(top, *args, env=None):
    p = subprocess.run(["git", "-C", top, *args], capture_output=True, text=True, env=env)
    return p.stdout.strip() if p.returncode == 0 else None


def origin(cmd):
    """where cmd's script comes from: its checkout, HEAD, whether it's clean, and the tree of its files as they are
    now (committed or not), so a later commit of the same files still matches"""
    script = next((a for a in cmd if a.endswith(".py")), None)
    out = {"command": cmd, "cwd": os.getcwd(), "phone": os.environ.get("POGO_PHONE"),
           "script": os.path.realpath(script) if script else None}
    top = out["script"] and git(os.path.dirname(out["script"]), "rev-parse", "--show-toplevel")
    if top:
        with tempfile.TemporaryDirectory() as d:  # (a scratch index: the checkout's own index stays as it is)
            env = dict(os.environ, GIT_INDEX_FILE=os.path.join(d, "index"))
            tree = git(top, "read-tree", "HEAD", env=env) is not None and git(top, "add", "-A", env=env) is not None \
                and git(top, "write-tree", env=env)
        out.update(toplevel=top, head=git(top, "rev-parse", "HEAD"), tree=tree or None,
                   clean=git(top, "status", "--porcelain") == "")
    return out


def run(stamp, cmd):
    """the detached half: run cmd, its output to the log, then its exit code to <stamp>.rc (and <stamp>.json)"""
    info = dict(origin(cmd), start=time.strftime("%Y-%m-%dT%H:%M:%S"), end=None, rc=None)
    meta = os.path.join(DIR, stamp + ".json")
    with open(meta, "w") as f:
        json.dump(info, f, indent=1)
    with open(os.path.join(DIR, stamp + ".log"), "ab") as f:
        try:
            rc = subprocess.call(cmd, stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        except OSError as e:
            f.write(f"watch.py: can't start {cmd[0]}: {e}\n".encode())
            rc = 127
    with open(meta, "w") as f:
        json.dump(dict(info, end=time.strftime("%Y-%m-%dT%H:%M:%S"), rc=rc), f, indent=1)
    with open(os.path.join(DIR, stamp + ".rc"), "w") as f:
        f.write(str(rc))


def summary(stamp):
    """the alarm lines (a traceback shows as its exception line only), then the last few lines"""
    with open(os.path.join(DIR, stamp + ".log"), errors="replace") as f:
        lines = [l.rstrip() for l in f if l.strip()]
    alarms = []
    for i, l in enumerate(lines):
        if l.startswith("Traceback"):
            alarms.append(next((m for m in lines[i + 1:] if not m.startswith(" ")), l))
        elif ALARM.search(l) and not l.startswith(" "):
            alarms.append(l)
    shown = list(dict.fromkeys(alarms))[-6:]
    return shown + [l for l in lines[-TAIL:] if l not in shown]


def wait(stamp):
    rc_file = os.path.join(DIR, stamp + ".rc")
    while not os.path.exists(rc_file):
        time.sleep(5)
    rc = open(rc_file).read().strip()
    print(f"run ended, exit {rc} (0 = fine). Log: {os.path.join(DIR, stamp + '.log')}")
    for l in summary(stamp):
        print("  " + l[:200])
    sys.exit(int(rc) if rc.lstrip("-").isdigit() else 1)


def newest():
    logs = sorted(f for f in os.listdir(DIR) if f.endswith(".log")) if os.path.isdir(DIR) else []
    if not logs:
        sys.exit("watch.py: no run to wait for")
    return logs[-1][:-4]


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        sys.exit(__doc__)
    if argv[0] == "--run":
        return run(argv[1], argv[2:])
    if argv[0] == "--wait":
        return wait(argv[1] if len(argv) > 1 else newest())
    os.makedirs(DIR, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    subprocess.Popen([sys.executable, os.path.realpath(__file__), "--run", stamp] + argv,
                     start_new_session=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"started, log: {os.path.join(DIR, stamp + '.log')}")
    wait(stamp)


if __name__ == "__main__":
    main(sys.argv[1:])
