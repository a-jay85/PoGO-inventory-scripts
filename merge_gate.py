#!/usr/bin/env python3
"""The merge gate: a PR of this repo merges only when its tests pass, its phone test ran its own code, and its body
says which sibling code was checked. It is a PreToolUse hook (.claude/settings.json) on every Bash call, so it holds
for headless Claude (heal.py) too. Only a `gh pr merge` of this repo gets checked; anything else goes through.

  python3 merge_gate.py <pr>       the same checks by hand: exit 0 = it would merge, 1 = blocked, and why
  python3 merge_gate.py --hook     the hook: reads the tool call on stdin, prints a deny (or notes) on stdout

What it checks, on the PR head as GitHub has it:
- Tests: every tests/ script CLAUDE.md lists (TESTS, plus OPTIONAL ones that exist) runs, all at once, in the PR's
  worktree when that is clean at the head sha, else in a temporary one. Each must exit 0 and print its "all ... the
  same" / "all ... right" line. A PR of .md files only skips them.
- Phone test: a PR that changes a .py under skills/ or one of PHONE_ROOT needs a watch.py run (its
  /tmp/pogo-watch/<stamp>.json) that ended with exit 0 and ran exactly the PR head's copy of each of those files
  (committed then or not). Or a body line `No phone test: <why, 10+ characters>`: it passes, with a warning.
- Siblings: for a .py under skills/, the functions the PR changes (an AST diff from the merge base), who calls each
  one, and phone / account branches where only one side changed. The body needs a line `Siblings: <what was checked,
  what it found>`. Without one it blocks and shows the list; with one the list comes along as notes.
A gate that can't check (gh down, a crash) blocks: a merge never goes through unchecked.
POGO_GH_BIN: a stand-in for `gh` (tests/gate.py).
"""
import ast, json, os, re, shlex, subprocess, sys, tempfile, time, traceback

REPO = "a-jay85/PoGO-inventory-scripts"
ROOT = os.path.dirname(os.path.realpath(__file__))  # any checkout of the repo: they share one git store
WATCH_DIR = "/tmp/pogo-watch"
TESTS = ["readers", "layout", "verdicts", "taggers", "heal"]  # must be there
OPTIONAL = ["lints", "gate"]  # run when there
DONE = re.compile(r"^all\b.*\b(the same|right)\b", re.M)
TEST_S = 480
PHONE_ROOT = {"pogo.py", "heal.py", "watch.py"}  # root scripts a phone run goes through
SIDES = re.compile(r"ANDROID|IOS|IPHONE|\b(ios|android|iphone|pixel)\b|HashTagAJay|CyrillJan", re.I)
TWINS = [("android", "ios"), ("android", "iphone"), ("pixel", "iphone"), ("hashtagajay", "cyrilljan")]
SKIP_DIRS = {".git", "__pycache__", "runs", "tests"}


class Blocked(Exception):
    pass


def git(*args, cwd=None, check=True):
    p = subprocess.run(["git", "-C", cwd or ROOT, *args], capture_output=True, text=True)
    if check and p.returncode:
        raise Blocked(f"git {' '.join(args)} failed: {p.stderr.strip()[:300]}")
    return p.stdout.strip() if p.returncode == 0 else None


def gh(*args, cwd=None):
    cmd = [os.environ.get("POGO_GH_BIN", "gh"), *args, "-R", REPO]
    p = subprocess.run(cmd, cwd=cwd or ROOT, capture_output=True, text=True)
    if p.returncode:
        raise Blocked(f"`gh {' '.join(args)}` failed: {(p.stderr or p.stdout).strip()[:300]}")
    return p.stdout


# ---------- which Bash calls are merges of this repo ----------

VALUE_FLAGS = {"-t", "--subject", "-b", "--body", "-F", "--body-file", "-A", "--author-email", "--match-head-commit"}


def ours(repo):
    r = re.sub(r"^(https?://)?(www\.)?github\.com/", "", repo.strip()).removesuffix(".git").strip("/")
    return r.lower() == REPO.lower()


def merges(command, cwd):
    """the `gh pr merge` calls of this repo in a Bash command -> [(target or None, cwd)]"""
    if "gh" not in command or "merge" not in command:
        return []
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        words = list(lex)
    except ValueError:
        words = command.split()
    out, seg = [], []
    for w in words + [";"]:
        if w and all(c in "();|&<>" for c in w):
            argv = [x for x in seg if not re.match(r"^[A-Za-z_]\w*=", x)] if seg else []
            if argv[:1] == ["cd"] and len(argv) > 1:
                cwd = os.path.join(cwd, os.path.expanduser(argv[1]))
            elif argv[:1] == ["gh"]:
                hit = merge_call(argv, cwd)
                if hit:
                    out.append(hit)
            seg = []
        else:
            seg.append(w)
    return out


def merge_call(argv, cwd):
    rest, repo, i = [], None, 1
    while i < len(argv):
        a = argv[i]
        if a in ("-R", "--repo"):
            repo, i = (argv[i + 1] if i + 1 < len(argv) else ""), i + 2
            continue
        if a.startswith("--repo="):
            repo = a.split("=", 1)[1]
        else:
            rest.append(a)
        i += 1
    if rest[:2] != ["pr", "merge"]:
        return None
    if repo is not None and not ours(repo):
        return None
    target, args = None, rest[2:]
    j = 0
    while j < len(args):
        if args[j] in VALUE_FLAGS:
            j += 2
            continue
        if not args[j].startswith("-"):
            target = args[j]
            break
        j += 1
    if target and "/pull/" in target:
        if not ours(target.split("/pull/")[0]):
            return None
        target = target.split("/pull/")[1].split("/")[0]
    if repo is None:
        url = git("remote", "get-url", "origin", cwd=cwd, check=False) if os.path.isdir(cwd) else None
        if not url or "pogo-inventory-scripts" not in url.lower():
            return None
    return target, cwd


# ---------- the PR ----------

def pr_of(target, cwd):
    if target is None:
        target = git("branch", "--show-current", cwd=cwd, check=False)
        if not target:
            raise Blocked("no PR number in the command and no branch here: write the number, gh pr merge <n> ...")
    pr = json.loads(gh("pr", "view", target, "--json", "number,url,state,headRefName,headRefOid,baseRefName,body",
                       cwd=cwd))
    pr["files"] = [f for f in gh("pr", "diff", str(pr["number"]), "--name-only", cwd=cwd).splitlines() if f.strip()]
    pr["body"] = pr.get("body") or ""
    return pr


def have(sha):
    return git("cat-file", "-e", sha + "^{commit}", check=False) is not None


def get_head(pr):
    if not have(pr["headRefOid"]):
        git("fetch", "-q", "origin", f"pull/{pr['number']}/head", check=False)
    if not have(pr["headRefOid"]):
        raise Blocked(f"can't get the PR head {pr['headRefOid'][:10]}: push the branch, then merge again")
    git("fetch", "-q", "origin", pr["baseRefName"], check=False)
    base = git("merge-base", f"origin/{pr['baseRefName']}", pr["headRefOid"], check=False) \
        or git("merge-base", pr["baseRefName"], pr["headRefOid"])
    return pr["headRefOid"], base


def worktrees():
    """[(path, HEAD, branch)] of every checkout of the repo"""
    out, cur = [], {}
    for l in (git("worktree", "list", "--porcelain") + "\n\n").split("\n"):
        if not l.strip():
            if cur.get("worktree"):
                out.append((cur["worktree"], cur.get("HEAD"), cur.get("branch", "").removeprefix("refs/heads/")))
            cur = {}
        elif " " in l:
            k, v = l.split(" ", 1)
            cur[k] = v
    return out


def clean(path):
    """nothing changed or new, apart from runs/ links (a worktree needs them to test)"""
    st = git("status", "--porcelain", cwd=path, check=False)
    if st is None:
        return False
    return all(l.startswith("??") and re.search(r"(^|/)runs/?$", l[3:].strip()) for l in st.splitlines() if l)


def pr_worktree(pr):
    return next((p for p, _, b in worktrees() if b == pr["headRefName"]), None)


# ---------- tests ----------

def run_tests(path):
    """-> [what failed, with its last lines]"""
    have_ = [t for t in TESTS + OPTIONAL if os.path.exists(os.path.join(path, "tests", t + ".py"))]
    bad = [f"tests/{t}.py is missing" for t in TESTS if t not in have_]
    env = {k: v for k, v in os.environ.items() if k not in ("POGO_PHONE", "POGO_HEAL_STATE", "POGO_HEAL_PHONE")}
    runs = []
    for t in have_:
        f = tempfile.TemporaryFile("w+")
        runs.append((t, f, subprocess.Popen([sys.executable, os.path.join("tests", t + ".py")], cwd=path, env=env,
                                            stdout=f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)))
    end = time.time() + TEST_S
    for t, f, p in runs:
        try:
            rc = p.wait(timeout=max(1, end - time.time()))
        except subprocess.TimeoutExpired:
            p.kill()
            rc = "killed after %d s" % TEST_S
        f.seek(0)
        out = f.read()
        if rc != 0 or not (DONE if t in TESTS else re.compile(r"^all ", re.M)).search(out):
            tail = "\n".join("    " + l for l in out.rstrip().splitlines()[-12:])
            bad.append(f"tests/{t}.py ended with exit {rc}" + ("" if rc != 0 else ", but no 'all ... the same' line")
                       + f". Its last lines:\n{tail}")
    return bad


def tests_for(pr, head):
    """-> [what failed]. In the PR's own clean worktree at the head sha, else a temporary one of the head"""
    path = next((p for p, h, _ in worktrees() if h == head and clean(p)), None)
    if path:
        return run_tests(path)
    with tempfile.TemporaryDirectory(prefix="gate-") as d:
        wt = os.path.join(d, "wt")
        git("worktree", "add", "-q", "--detach", wt, head)
        try:
            return run_tests(wt)
        finally:
            git("worktree", "remove", "--force", wt, check=False)


# ---------- the phone test ----------

def phone_files(files):
    return [f for f in files if f.endswith(".py") and (f.startswith("skills/") or f in PHONE_ROOT)]


def blob(rev, path):
    return git("rev-parse", "-q", "--verify", f"{rev}:{path}", check=False)


def phone_script(script, top):
    rel = os.path.relpath(script, top) if script and top else ""
    return rel.startswith("skills/") or rel == "pogo.py"


def phone_runs():
    """watch.py's run records, newest first"""
    names = sorted((f for f in os.listdir(WATCH_DIR) if f.endswith(".json")), reverse=True) \
        if os.path.isdir(WATCH_DIR) else []
    for n in names:
        try:
            with open(os.path.join(WATCH_DIR, n)) as f:
                r = json.load(f)
        except (OSError, ValueError):
            continue
        if not isinstance(r, dict) or not phone_script(r.get("script"), r.get("toplevel")):
            continue  # (a run of a test or a tool never touched a phone)
        if r.get("tree") and git("cat-file", "-e", r["tree"], check=False) is not None:
            yield n[:-5], r


def phone_test(files, head, wt):
    """-> (the run that tested these files, why the near ones (from wt, or partly the same) don't count)"""
    want = {f: blob(head, f) for f in files}
    near = []
    for stamp, r in phone_runs():
        diff = [f for f in files if blob(r["tree"], f) != want[f]]
        cmd = " ".join(r.get("command") or [])[:120]
        if not diff and r.get("rc") == 0:
            return (stamp, r), near
        if len(near) < 3 and (len(diff) < len(files) or r.get("toplevel") == wt):
            if not diff:
                why = f"ended with exit {r.get('rc')}" if r.get("rc") is not None else "has not ended"
            else:
                why = "ran other contents of " + ", ".join(diff) + " (changed since: run it again)"
            near.append(f"run {stamp} ({cmd}) {why}")
    return None, near


# ---------- siblings ----------

def defs(tree):
    """qualified name -> the function's node; '<module>' -> the code outside any def"""
    out, top = {}, []

    def walk(body, prefix):
        for n in body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                out[prefix + n.name] = n
                walk(n.body, prefix + n.name + ".")
            elif isinstance(n, ast.ClassDef):
                walk(n.body, prefix + n.name + ".")
            elif not prefix:
                top.append(n)

    walk(tree.body, "")
    out["<module>"] = ast.Module(body=top, type_ignores=[])
    return out


def same(a, b):
    if a is None or b is None:
        return a is b
    if isinstance(a, ast.Module):
        return ast.dump(a) == ast.dump(b)
    strip = lambda n: ast.dump(ast.Module(body=[s for s in n.body if not isinstance(s, (ast.FunctionDef,
                                         ast.AsyncFunctionDef, ast.ClassDef))], type_ignores=[]))
    return ast.dump(a.args) == ast.dump(b.args) and strip(a) == strip(b) \
        and [ast.dump(d) for d in a.decorator_list] == [ast.dump(d) for d in b.decorator_list]


def parse(src):
    try:
        return ast.parse(src or "")
    except SyntaxError:
        return None


def branches(fn):
    return [n for n in ast.walk(fn) if isinstance(n, (ast.If, ast.IfExp)) and SIDES.search(ast.unparse(n.test))]


def one_sided(old, new):
    """phone / account branches in a changed function where one side changed and the other didn't"""
    out, olds = [], {}
    for n in branches(old) if old is not None and not isinstance(old, ast.Module) else []:
        olds.setdefault(ast.dump(n.test), []).append(n)
    if isinstance(new, ast.Module):
        return out
    dump = lambda x: ast.dump(x) if isinstance(x, ast.AST) else str([ast.dump(s) for s in x])
    for n in branches(new):
        test = ast.unparse(n.test)[:60]
        twins = olds.get(ast.dump(n.test))
        o = twins.pop(0) if twins else None
        if o is None:
            out.append(f"line {n.lineno}: new branch `if {test}`: does the other side need the same?")
            continue
        yes, no = dump(n.body) != dump(o.body), dump(n.orelse) != dump(o.orelse)
        empty = not n.orelse if isinstance(n, ast.If) else False
        if yes and not no:
            out.append(f"line {n.lineno}: `if {test}`: only the if side changed"
                       + (" (it has no else: is the other side somewhere else?)" if empty else ", else unchanged"))
        elif no and not yes:
            out.append(f"line {n.lineno}: `if {test}`: only the else side changed, the if side unchanged")
    return out


def code_files(rev):
    """the .py files a caller can be in: skills/ and the root scripts"""
    names = git("ls-tree", "-r", "--name-only", rev).splitlines()
    return [f for f in names if f.endswith(".py") and ("/" not in f or f.startswith("skills/"))
            and not SKIP_DIRS & set(f.split("/")[:-1])]


def callers(trees, name):
    """-> ['file:line in fn'] of every call to a function of this name (by name: a same-named one shows too)"""
    out = []
    for f, t in trees.items():
        stack = []

        def visit(node):
            is_def = isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            if is_def:
                stack.append(node.name)
            if isinstance(node, ast.Call):
                fn = node.func
                if (fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)) == name:
                    out.append(f"{f}:{node.lineno}" + (f" in {'.'.join(stack)}" if stack else ""))
            for c in ast.iter_child_nodes(node):
                visit(c)
            if is_def:
                stack.pop()

        if t is not None:
            visit(t)
    return out


def siblings(base, head, files):
    """-> the lines of the siblings list (empty: no .py under skills/ changed)"""
    py = [f for f in files if f.startswith("skills/") and f.endswith(".py")]
    if not py:
        return []
    trees = {f: parse(git("show", f"{head}:{f}")) for f in code_files(head)}
    lines = []
    for f in py:
        old = parse(git("show", f"{base}:{f}", check=False)) or ast.Module(body=[], type_ignores=[])
        new = trees.get(f) or parse(git("show", f"{head}:{f}", check=False))
        if new is None and blob(head, f):
            lines.append(f"{f}: doesn't parse at the head")
            continue
        new = new or ast.Module(body=[], type_ignores=[])
        o, n = defs(old), defs(new)
        for name in [k for k in n if k in o and not same(o[k], n[k])] + [k for k in n if k not in o] \
                + [k for k in o if k not in n]:
            kind = "changed" if name in o and name in n else "new" if name in n else "removed"
            lines.append(f"{f} {name}: {kind}")
            if name != "<module>":
                short = name.split(".")[-1]
                cs = callers(trees, short)
                lines.append(f"    callers ({len(cs)}): " + (", ".join(cs[:10]) + (" ..." if len(cs) > 10 else "")
                                                          if cs else "none found"))
                for s in one_sided(o.get(name), n.get(name)) if name in n else []:
                    lines.append("    " + s)
                low = short.lower()
                for a, b in TWINS:
                    for x, y in ((a, b), (b, a)):
                        twin = name[:len(name) - len(short)] + re.sub(x, y, short, flags=re.I)
                        if x in low and twin in n and twin != name and same(o.get(twin), n.get(twin)):
                            lines.append(f"    its twin {twin} didn't change: does it need the same?")
    return lines


# ---------- the verdict ----------

def line(body, key):
    m = re.search(rf"^[ \t>*-]*{key}:[ \t]*(.*)$", body, re.M | re.I)
    return m.group(1).strip() if m else None


def check(target, cwd):
    """-> (blocks, notes, warnings) for one merge"""
    pr = pr_of(target, cwd)
    n = pr["number"]
    if pr.get("state") not in (None, "OPEN"):
        return [], [f"PR #{n} is {pr['state']}: not checked"], []
    head, base = get_head(pr)
    files, body = pr["files"], pr["body"]
    blocks, notes, warns = [], [f"merge_gate: PR #{n}, head {head[:10]}, {len(files)} files"], []
    edit = (f"Edit the body: gh pr view {n} -R {REPO} --json body -q .body > /tmp/pr{n}.md, add the line, then "
            f"gh pr edit {n} -R {REPO} --body-file /tmp/pr{n}.md")
    wt = pr_worktree(pr) or "<the PR's worktree>"

    phone = phone_files(files)
    if phone:
        why = line(body, "No phone test")
        ran, near = phone_test(phone, head, wt)
        if ran:
            notes.append(f"phone test: run {ran[0]} ({' '.join(ran[1].get('command') or [])[:150]}), exit 0, "
                         f"ran the head's copy of {', '.join(phone)}")
            cmd = " ".join(ran[1].get("command") or [])
            own = {f.split("/")[1] for f in phone if f.count("/") >= 2 and not f.startswith("skills/shared/")}
            if own and not any(f"/{k}/" in cmd or f" {k}" in cmd for k in own):
                warns.append(f"PR #{n}'s phone test ({cmd[:100]}) isn't a run of {', '.join(sorted(own))}: "
                             "was that the right script?")
        elif why is not None and len(why) >= 10:
            warns.append(f"PR #{n} merged with no phone test: {why}")
        else:
            script = next((f for f in phone if f.startswith("skills/")), "skills/<skill>/<script>.py")
            blocks.append(
                f"No phone test of this code. It changes phone code ({', '.join(phone)}), and no watch.py run that "
                f"ended with exit 0 ran these files as they are at the PR head {head[:10]}.\n"
                + "".join(f"  {x}\n" for x in near)
                + f"  Do: commit and push every change first, then from the PR's worktree, in the foreground:\n"
                  f"  POGO_PHONE=android python3 {wt}/watch.py caffeinate -dimsu python3 {wt}/{script} --limit 1\n"
                  f"  (the script the change touches, the smallest run that reaches it; `ps aux | grep -E "
                  f"'skills/|pogo.py'` first: nothing else may run on the phone). If it can't be tested on the phone, "
                  f"add a body line `No phone test: <why, 10+ characters>`"
                + (f" (the one there is too short: {why!r})" if why is not None else "") + f". {edit}")

    sib = siblings(base, head, files)
    if sib:
        listing = "\n".join("  " + s for s in sib)
        if line(body, "Siblings"):
            notes.append("siblings (the PR says: " + line(body, "Siblings")[:200] + "):\n" + listing)
        else:
            blocks.append(
                "No `Siblings:` line in the PR body. These functions changed; check each caller and each "
                "one-sided phone / account branch (does the other phone, the other account, the other caller need "
                f"the same fix?):\n{listing}\n  Then add a body line `Siblings: <what you checked, what you found>`, "
                f"e.g. `Siblings: gift.py read_card's 3 callers checked, the iPhone side has the same bug, fixed "
                f"too`. {edit}")

    if all(f.endswith(".md") for f in files):
        notes.append("tests: skipped (only .md files)")
    else:
        t0 = time.time()
        bad = tests_for(pr, head)
        if bad:
            blocks.append("Tests failed at the PR head:\n" + "\n".join("  " + b for b in bad)
                          + f"\n  Do: fix it in {wt}, run the test there till it passes, commit, push.")
        else:
            notes.append(f"tests: all passed ({time.time() - t0:.0f} s)")
    return blocks, notes, warns


def verdict(command, cwd):
    """-> None (not a merge of this repo), or (block message or None, notes, warnings)"""
    calls = merges(command, cwd)
    if not calls:
        return None
    blocks, notes, warns = [], [], []
    for target, where in calls:
        try:
            b, n, w = check(target, where)
        except Blocked as e:
            b, n, w = [f"The gate couldn't check this merge: {e}"], [], []
        blocks += b
        notes += n
        warns += w
    if not blocks:
        return None, "\n".join(notes), warns
    msg = ("merge_gate.py blocked this merge. Do each numbered step, then run the same gh pr merge again (the gate "
           "checks again):\n" + "\n".join(f"{i}. {b}" for i, b in enumerate(blocks, 1)))
    return msg, "\n".join(notes), warns


def hook(text):
    """the hook: the PreToolUse JSON in -> the JSON to print, or None"""
    try:
        ev = json.loads(text)
    except ValueError:
        return None
    command = (ev.get("tool_input") or {}).get("command") or ""
    if ev.get("tool_name") not in (None, "Bash") or "merge" not in command:
        return None
    try:
        v = verdict(command, ev.get("cwd") or os.getcwd())
    except Exception:
        tail = "".join(traceback.format_exc().splitlines(True)[-6:])
        v = ("merge_gate.py crashed, so the merge is blocked. Fix merge_gate.py in its own PR (tests/gate.py), or "
             "ask Ajay to merge this one on github.com. The crash:\n" + tail, "", [])
    if v is None:
        return None
    msg, notes, warns = v
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
    if msg:
        out["hookSpecificOutput"].update(permissionDecision="deny", permissionDecisionReason=msg)
    elif notes:
        out["hookSpecificOutput"]["additionalContext"] = notes
    if warns:
        out["systemMessage"] = "merge_gate: " + "; ".join(warns)
    return out


def main(argv):
    if argv[:1] == ["--hook"]:
        out = hook(sys.stdin.read())
        if out:
            print(json.dumps(out))
        return 0
    if not argv or argv[0].startswith("-"):
        sys.exit(__doc__)
    try:
        msg, notes, warns = verdict(f"gh pr merge {argv[0]} -R {REPO}", os.getcwd())
    except Blocked as e:
        msg, notes, warns = str(e), "", []
    for t in (notes, msg, *warns):
        if t:
            print(t)
    return 1 if msg else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
