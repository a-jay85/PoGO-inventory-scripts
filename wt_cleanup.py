#!/usr/bin/env python3
"""Remove every worktree whose PR has merged. Same idea as IBL5's bin/cleanup, cut down.

  python3 ~/PoGO-inventory-scripts/wt_cleanup.py [--dry-run]

A worktree goes only when all of these hold:
  - its PR on GitHub is MERGED (found by branch name, or by tip commit for a detached HEAD),
    and its tip is the PR's head or an ancestor of it (nothing was committed after the merge);
    a detached HEAD whose tip is already on origin/main needs no PR,
  - `git status` shows nothing changed or untracked,
  - nothing is using it: no process inside it or naming it, no live Claude session in it or on its branch.
Anything else is skipped with the reason. Its run folders (skills/*/runs/, ignored by git) are copied to
~/claude-plans/_backups/worktree-runs/<slug>/ first, then the worktree and its local branch are removed.
Other ignored files in it (.state.json, .calib.json, .claude/) go with it; the main checkout has its own.
The main checkout is never touched.
"""
import glob, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.realpath(__file__))
BACKUPS = os.path.expanduser("~/claude-plans/_backups/worktree-runs")


def git(*args, cwd=HERE, check=True):
    r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r


def worktrees():
    """[(path, branch or None, tip)] for every worktree but the main one."""
    out, cur = [], {}
    for line in git("worktree", "list", "--porcelain").stdout.splitlines() + [""]:
        if not line:
            if cur:
                out.append(cur)
            cur = {}
            continue
        key, _, val = line.partition(" ")
        cur[key] = val
    main = os.path.realpath(out[0]["worktree"])  # git always lists the main worktree first
    return [(w["worktree"], w.get("branch", "").removeprefix("refs/heads/") or None, w.get("HEAD"))
            for w in out if os.path.realpath(w["worktree"]) != main]


def merged_pr(branch, tip):
    """The merged PR {number, headRefOid} for this branch (or this tip, if detached), else None."""
    args = ["--head", branch] if branch else ["--search", tip]
    r = subprocess.run(["gh", "pr", "list", "--state", "merged", *args, "--json", "number,headRefOid"],
                       capture_output=True, text=True, cwd=HERE)
    if r.returncode:
        raise RuntimeError(f"gh pr list: {r.stderr.strip()}")
    prs = json.loads(r.stdout or "[]")
    return prs[0] if prs else None


def tip_in_pr(tip, pr):
    head = pr["headRefOid"]
    if tip == head:
        return True
    if git("cat-file", "-e", head + "^{commit}", check=False).returncode:
        git("fetch", "-q", "origin", f"pull/{pr['number']}/head", check=False)
    return git("merge-base", "--is-ancestor", tip, head, check=False).returncode == 0


def _inside(p, real):
    p = os.path.realpath(p)
    return p == real or p.startswith(real + os.sep)


def _alive(pid):
    try:
        os.kill(int(pid), 0)
    except (OSError, TypeError, ValueError):
        return False
    return True


def in_use(path, branch):
    """Why path looks in use, or None. Unsure (a check that can't run) counts as in use.

    Three looks: a process's working directory inside it; a process whose command line names it (a phone
    run started from elsewhere); a live Claude session in the session registry that sits in it or on its
    branch (an EnterWorktree session's own process cwd stays where it launched)."""
    real = os.path.realpath(path)
    try:
        lsof = subprocess.run(["lsof", "-a", "-d", "cwd", "-Fn"], capture_output=True, text=True).stdout
        ps = subprocess.run(["ps", "-axo", "command="], capture_output=True, text=True).stdout
    except FileNotFoundError as e:
        return f"can't check ({e.filename} missing)"
    if any(line.startswith("n") and _inside(line[1:], real) for line in lsof.splitlines()):
        return "a process is running inside it"
    if any(path in cmd or real in cmd for cmd in ps.splitlines()):
        return "a running command names it"
    reg = os.path.expanduser("~/.claude/session-registry/active.json")
    try:
        sessions = json.load(open(reg)).values() if os.path.exists(reg) else []
    except (OSError, ValueError):
        return "can't read the session registry"
    gitdir = os.path.realpath(os.path.join(git("rev-parse", "--path-format=absolute", "--git-common-dir").stdout.strip()))
    for s in sessions:
        if not _alive(s.get("pid")):
            continue
        if any(s.get(k) and _inside(s[k], real) for k in ("cwd", "repo")):
            return f"Claude session {s.get('name', s.get('id'))} is in it"
        if branch and s.get("branch") == branch and os.path.realpath(s.get("gitdir") or "") == gitdir:
            return f"Claude session {s.get('name', s.get('id'))} is on its branch"
    return None


def backup_runs(path):
    runs = [d for d in glob.glob(os.path.join(path, "skills", "*", "runs")) if os.listdir(d)]
    for d in runs:
        skill = os.path.basename(os.path.dirname(d))
        shutil.copytree(d, os.path.join(BACKUPS, os.path.basename(path), skill), dirs_exist_ok=True)
    return len(runs)


def main():
    dry = "--dry-run" in sys.argv[1:]
    removed = skipped = 0
    for path, branch, tip in worktrees():
        name = os.path.basename(path)

        def skip(why):
            nonlocal skipped
            skipped += 1
            print(f"skip   {name}: {why}")

        if not branch and git("merge-base", "--is-ancestor", tip, "origin/main", check=False).returncode == 0:
            why = f"detached at {tip[:7]}, already on main"  # nothing in it that main doesn't have
        else:
            try:
                pr = merged_pr(branch, tip)
            except RuntimeError as e:
                skip(str(e))
                continue
            if not pr:
                skip(f"no merged PR for {branch or 'detached ' + tip[:7]}")
                continue
            if not tip_in_pr(tip, pr):
                skip(f"has commits after PR #{pr['number']} merged")
                continue
            why = f"PR #{pr['number']} merged"
        if git("status", "--porcelain", cwd=path).stdout.strip():
            skip("uncommitted or untracked files")
            continue
        busy = in_use(path, branch)
        if busy:
            skip(busy)
            continue
        if dry:
            print(f"would  {name}: {why}")
            continue
        n = backup_runs(path)
        r = git("worktree", "remove", path, check=False)
        if r.returncode:
            skip(f"git worktree remove: {r.stderr.strip()}")
            continue
        if branch:
            git("branch", "-D", branch, check=False)
        removed += 1
        saved = f", {n} run folder(s) saved to {BACKUPS}/{name}" if n else ""
        print(f"remove {name}: {why}{saved}")
    git("worktree", "prune", check=False)
    print(f"{removed} removed, {skipped} skipped" + (" (dry run)" if dry else ""))


if __name__ == "__main__":
    main()
