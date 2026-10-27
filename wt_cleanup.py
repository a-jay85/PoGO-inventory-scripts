#!/usr/bin/env python3
"""Remove every worktree whose PR has merged. Same idea as IBL5's bin/cleanup, cut down.

  python3 ~/PoGO-inventory-scripts/wt_cleanup.py [--dry-run]

A worktree goes only when all of these hold:
  - its PR on GitHub is MERGED (found by branch name, or by tip commit for a detached HEAD),
    and its tip is the PR's head or an ancestor of it (nothing was committed after the merge);
    a detached HEAD whose tip is already on origin/main needs no PR,
  - `git status` shows nothing changed or untracked,
  - no process has its working directory inside it (a live Claude session or a phone run).
Anything else is skipped with the reason. Its run folders (skills/*/runs/, ignored by git) are copied to
~/claude-plans/_backups/worktree-runs/<slug>/ first, then the worktree and its local branch are removed.
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


def in_use(path):
    """True if any process's working directory is inside path. Unsure (lsof missing) counts as in use."""
    try:
        r = subprocess.run(["lsof", "-a", "-d", "cwd", "-Fn"], capture_output=True, text=True)
    except FileNotFoundError:
        return True
    real = os.path.realpath(path)
    for line in r.stdout.splitlines():
        if line.startswith("n"):
            cwd = os.path.realpath(line[1:])
            if cwd == real or cwd.startswith(real + os.sep):
                return True
    return False


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
        if in_use(path):
            skip("a process is running inside it")
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
