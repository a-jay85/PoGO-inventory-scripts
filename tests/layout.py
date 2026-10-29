#!/usr/bin/env python3
"""Pins how the scripts find each other and their files: imports, the one shared tapper, run folders, paths.
No phone: every script is imported (not run) in a process of its own, the way its own command line would.
A refactor that moves shared code must keep all of it the same.

  python3 tests/layout.py            check against tests/layout.json
  python3 tests/layout.py --record   write layout.json from today's code (after a change you meant)

What it pins, per script:
  names   its own top-level names (functions, classes, constants): what other scripts import from it
  copies  how many copies of each skill file got loaded (pvpc/run.py, the shared tapper, must be 1)
  runs    every run folder it can build (os.path.join(..., "runs", ...)): a moved one loses its history
What must hold, every time (not recorded):
  every `module.name` the code uses exists, every path the code builds to a repo file exists,
  every function that reads the tapper's run state (RUN_DIR, ...) reads the one copy, and log() writes there.
"""
import ast, importlib.util, json, os, re, subprocess, sys, tempfile, types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
GOLD = os.path.join(ROOT, "tests", "layout.json")
TOOLKIT_NAMES = ("run", "base")  # what the scripts call the shared tapper


def rel(p):
    return os.path.relpath(os.path.realpath(p), os.path.realpath(ROOT))


def scripts():
    out = ["pogo.py"]
    for d in sorted(os.listdir(SKILLS)):
        if os.path.isdir(os.path.join(SKILLS, d)):
            out += sorted(f"skills/{d}/{f}" for f in os.listdir(os.path.join(SKILLS, d)) if f.endswith(".py"))
    return out


# ---------- inside one script's process ----------

def mine(m):
    f = getattr(m, "__file__", None)
    return isinstance(m, types.ModuleType) and f and os.path.realpath(f).startswith(os.path.realpath(ROOT) + os.sep) \
        and "/tests/" not in f


def load(path):
    """import the script the way `python3 path` would, minus its __main__ block"""
    full = os.path.join(ROOT, path)
    sys.path.insert(0, os.path.dirname(full))
    sys.argv = [full] + (["ios"] if path == "skills/trade/phone.py" else [])  # (phone.py reads its phone at import)
    name = "run" if path == "skills/pvpc/run.py" else "__probe__"  # (pvpc's run.py names itself `run` as __main__)
    spec = importlib.util.spec_from_file_location(name, full)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def tree(m):
    return ast.parse(open(m.__file__).read())


def joins(t):
    """every os.path.join(...) call in the file"""
    for n in ast.walk(t):
        if isinstance(n, ast.Call) and ast.unparse(n.func) == "os.path.join":
            yield n


def is_tapper(x):
    """the module that owns the run state: its own new_run_dir sets RUN_DIR"""
    f = vars(x).get("new_run_dir")
    return isinstance(f, types.FunctionType) and f.__module__ == x.__name__ and "RUN_DIR" in f.__code__.co_names


def state_names(mods):
    """the tapper's run state: what it declares global, and what other files set on it (base.RUN_DIR = ...)"""
    names = set()
    for m in mods:
        for n in ast.walk(tree(m)):
            if isinstance(n, ast.Global) and is_tapper(m):
                names |= set(n.names)
            if isinstance(n, (ast.Assign, ast.AugAssign)):
                for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                    if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id in TOOLKIT_NAMES:
                        names.add(t.attr)
    return names


def code_names(co):
    out = set(co.co_names)
    for c in co.co_consts:
        if isinstance(c, types.CodeType):
            out |= code_names(c)
    return out


def functions(m):
    for v in list(vars(m).values()):
        if isinstance(v, types.FunctionType) and v.__module__ == m.__name__:
            yield v
        elif isinstance(v, type) and v.__module__ == m.__name__:
            yield from (f for f in vars(v).values() if isinstance(f, types.FunctionType))


def probe(path):
    m = load(path)
    mods = {id(x): x for x in list(sys.modules.values()) if mine(x)}
    for x in list(mods.values()):  # (and any loaded by path and kept only in a global)
        mods.update((id(v), v) for v in vars(x).values() if mine(v))
    mods = list(mods.values())
    errors, out = [], {}

    out["names"] = sorted(k for k, v in vars(m).items()
                          if not k.startswith("__") and not isinstance(v, types.ModuleType))

    files = {}
    for x in mods:
        files.setdefault(rel(x.__file__), set()).add(id(x))
    out["copies"] = {f: len(ids) for f, ids in sorted(files.items()) if len(ids) > 1}

    runs = set()
    for x in mods:
        t = tree(x)
        for n in ast.walk(t):  # every module.name the code uses
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name):
                v = vars(x).get(n.value.id)
                if mine(v) and not hasattr(v, n.attr):
                    errors.append(f"{rel(x.__file__)}:{n.lineno}: {n.value.id}.{n.attr} doesn't exist")
        for n in joins(t):  # every path it builds that it can work out without running
            try:
                p = eval(compile(ast.Expression(n), x.__file__, "eval"), dict(vars(x)))
            except Exception:
                continue
            if not isinstance(p, str) or not os.path.realpath(p).startswith(os.path.realpath(ROOT)):
                continue
            r = rel(p)
            if "/runs" in "/" + r or r.endswith("/runs"):
                if x is m:  # (the run folder made at import is named by the time: pin where, not when)
                    runs.add(re.sub(r"\d{8}-\d{6}", "<time>", r))
            elif "." in os.path.basename(r) and not os.path.basename(r).startswith(".") \
                    and not re.search(r"\*|\d{8}", r) and not os.path.exists(p):  # (not local state, globs or dated)
                errors.append(f"{rel(x.__file__)}:{n.lineno}: {r} doesn't exist")
    out["runs"] = sorted(runs)

    tapper = [x for x in mods if is_tapper(x)]
    if len(tapper) > 1:  # (none: this script never loads the tapper)
        errors.append(f"{len(tapper)} copies of the tapper: {[rel(x.__file__) for x in tapper]}")
    if tapper:
        tk, names = tapper[0], state_names(mods)
        for x in mods:  # whoever reads the run state must read the tapper's own copy
            for f in functions(x):
                for name in sorted(code_names(f.__code__) & names):
                    if name in f.__globals__ and f.__globals__ is not vars(tk):
                        errors.append(f"{rel(x.__file__)}: {f.__qualname__} reads its own {name}, not the tapper's")
        with tempfile.TemporaryDirectory() as d:  # and every log() writes where the tapper says
            tk.new_run_dir(None, d=d)
            logs = {id(v): (rel(x.__file__), v) for x in mods for k, v in vars(x).items()
                    if k == "log" and isinstance(v, types.FunctionType)}
            for i, (where, f) in enumerate(logs.values()):
                sys.stdout = open(os.devnull, "w")
                try:
                    f(f"layout check {i}")
                finally:
                    sys.stdout = sys.__stdout__
                if f"layout check {i}" not in open(os.path.join(d, "log.txt")).read():
                    errors.append(f"{where}: log() didn't write to the tapper's run folder")

    if path == "pogo.py":
        out["steps"] = {k: v[0] for k, v in sorted(m.STEPS.items())}
        for k, v in m.STEPS.items():
            if not os.path.exists(os.path.join(SKILLS, v[0])):
                errors.append(f"pogo.py: step {k}: skills/{v[0]} doesn't exist")
    out["errors"] = errors
    return out


# ---------- the check ----------

def run_all(phone):
    env = {k: v for k, v in os.environ.items() if k != "POGO_PHONE"} | ({"POGO_PHONE": phone} if phone else {})
    out, crashed = {}, {}
    for s in scripts():
        p = subprocess.run([sys.executable, os.path.abspath(__file__), "--probe", s], env=env, cwd=ROOT,
                           capture_output=True, text=True, timeout=120)
        if p.returncode:
            crashed[s] = (p.stderr.strip().splitlines() or ["(no output)"])[-1]
        else:
            out[s] = json.loads(p.stdout.strip().splitlines()[-1])
    return out, crashed


def now():
    """the pins from the iPhone path; the problems from both phones (ui.android is there on Android only)"""
    found, crashed = run_all(None)
    android, crashed2 = run_all("android")  # (importing android.py starts nothing: no adb at import)
    for s, e in crashed2.items():
        crashed.setdefault(s, f"(Android) {e}")
    for s, r in found.items():
        theirs = set(android.get(s, {}).get("errors", []))
        r["errors"] = [e for e in r["errors"] if "doesn't exist" not in e or e in theirs or s not in android]
        r["errors"] += [f"(Android) {e}" for e in theirs - set(r["errors"]) if "doesn't exist" not in e]
    return found, crashed


def main(a):
    if a[:1] == ["--probe"]:
        r = probe(a[1])
        print(json.dumps(r))
        return 0
    if a not in ([], ["--record"]):
        sys.exit(__doc__)
    found, crashed = now()
    errors = [e for r in found.values() for e in r.pop("errors")]
    errors = list(dict.fromkeys(errors)) + [f"{s}: won't import: {e}" for s, e in crashed.items()]
    for e in errors:
        print(e)
    if a == ["--record"]:
        if errors:
            print(f"{len(errors)} problems: fix them first, nothing recorded")
            return 1
        with open(GOLD, "w") as f:
            json.dump(found, f, indent=1, sort_keys=True)
            f.write("\n")
        print(f"recorded {len(found)} scripts -> {GOLD}")
        return 0
    gold = json.load(open(GOLD))
    bad = len(errors)
    for s in sorted(set(gold) | set(found)):
        if s not in found or s not in gold:
            if s not in crashed:
                print(f"{s}: {'gone' if s not in found else 'new'} (run --record if that's meant)")
                bad += 1
            continue
        for k in sorted(set(gold[s]) | set(found[s])):
            g, n = gold[s].get(k), found[s].get(k)
            if g == n:
                continue
            bad += 1
            if isinstance(g, list) and isinstance(n, list):
                print(f"{s} {k}: lost {sorted(set(g) - set(n))}, gained {sorted(set(n) - set(g))}")
            else:
                print(f"{s} {k}: was {g!r}, now {n!r}")
    print(f"{bad} changed or broken" if bad else f"all {len(gold)} scripts the same")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
