#!/usr/bin/env python3
"""git and gh for the repo-root tools (merge_gate.py, wt_cleanup.py, backlog.py): one way to run each, and one reader
of `git worktree list --porcelain`. Standard library only, and nothing runs at import: merge_gate.py is a hook on
every Bash call, and a broken import there lets merges past the gate.

Each caller keeps its own way to fail (merge_gate blocks, wt_cleanup raises, backlog exits), so git() and gh() hand
back the finished process and never raise. watch.py keeps its own git(): it is part of every phone run.
"""
import subprocess


def git(*args, cwd, env=None):
    """-> the finished `git -C cwd args` (text, output captured). Never raises: the caller reads returncode"""
    return subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, env=env)


def gh(*args, bin="gh", repo=None, cwd=None, capture=True):
    """-> the finished `bin args [-R repo]` (text). bin: a stand-in for tests (POGO_GH_BIN, BACKLOG_GH). Never raises"""
    return subprocess.run([bin, *args] + (["-R", repo] if repo else []), cwd=cwd, capture_output=capture, text=True)


def worktrees(porcelain):
    """`git worktree list --porcelain` output -> [(path, HEAD, branch)], the main checkout first (git lists it first).
    branch has no refs/heads/, and is "" for a detached HEAD"""
    out, cur = [], {}
    for line in porcelain.splitlines() + [""]:
        if not line.strip():
            if cur.get("worktree"):
                out.append((cur["worktree"], cur.get("HEAD"), cur.get("branch", "").removeprefix("refs/heads/")))
            cur = {}
        elif " " in line:
            k, v = line.split(" ", 1)
            cur[k] = v
    return out
