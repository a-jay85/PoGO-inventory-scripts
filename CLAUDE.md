# PoGO-inventory-scripts

Claude Code skills that sort a Pokémon GO storage: `/pvpc`, `/ivc`, `/ivcsort` and `/cleanup`. Each one lives in `skills/<name>/`.

## The live skills run from the main checkout

`~/.claude/skills/<name>` is a symlink to `~/PoGO-inventory-scripts/skills/<name>`. Whatever is on the main checkout's `main` branch is what runs on the phone.

- Never edit the main checkout (`~/PoGO-inventory-scripts`) directly. That covers code, SKILL.md files, docs and config, however small the change.
- After a PR merges, update the main checkout or the skills never see the change:
  `git -C ~/PoGO-inventory-scripts pull --ff-only`
- Don't pull while a script is running on the phone. Python has already loaded the old files, but a skill that imports another one mid-run gets a mix.

The skills import each other by relative path (`HERE/../pvpc`), so they must stay siblings under `skills/`.

## Every change goes in a worktree, a PR and a squash-merge

1. Make a worktree outside the repo:
   `git -C ~/PoGO-inventory-scripts worktree add ~/PoGO-inventory-scripts-worktrees/<slug> -b <type>/<slug> origin/main`
2. Enter it with `EnterWorktree(path=...)`. Don't `cd` into it.
3. Commit, then push in a separate command. Never chain `git commit && git push`.
4. Open a PR with `gh pr create`. Squash-merge only: `gh pr merge --squash --delete-branch`.
5. Pull the main checkout (above), then remove the worktree:
   `git -C ~/PoGO-inventory-scripts worktree remove ~/PoGO-inventory-scripts-worktrees/<slug>`

`main` is linear. A merged branch's SHAs never land on `main`, because the squash makes a new commit. Confirm a merge by content, not by SHA. Start the next branch fresh from `origin/main`. Stacking on a branch that later squash-merges means rebasing with `git rebase --onto origin/main <old-parent-tip> <branch>`.

Force-pushes use `--force-with-lease` only. No `git stash` in a worktree: the stash is shared across all of them.

## Commit and PR titles

Conventional commits. Decision test: *"Can a skill now do something on the phone it couldn't before?"*

- Yes: `feat:`
- A bug fixed, the same intended behaviour back: `fix:`
- Same behaviour, cleaner code: `refactor:`
- Docs only: `docs:`
- Repo housekeeping, tooling, data refresh: `chore:`

Classify by what the diff is. Scope is the skill when there is one, e.g. `fix(pvpc): ...`.

Amend only when fixing the commit just made in this conversation and it isn't pushed yet. Otherwise make a new commit.

## Seeing the phone

Scripts see the Android phone with its own screenshots (`adb exec-out screencap`, via `ui.capture()` / `android.capture()` in `skills/pvpc/android.py`). Never use scrcpy or a Mac window grab (`screencapture`) for it: scrcpy's picture freezes at random while the Mac is in use. New scripts reuse `ui.capture()` and don't add their own capture path. `POGO_SCRCPY=1` brings the old scrcpy window back, only if the user asks for it.

## Never commit

The repo is public. These stay local and are in `.gitignore`:

- `skills/*/runs/`: run logs and screen captures (trainer names, inventory)
- `skills/pvpc/.state.json`, `skills/pvpc/.calib.json`: per-machine state
- `skills/pvpc/helper`: built from `helper.swift` on first use

## Testing

There are no automated tests. A change to how a skill reads or taps the phone isn't done until it has run on the phone:
`POGO_PHONE=android caffeinate -dimsu python3 ~/.claude/skills/pvpc/run.py --limit 1`, with the user watching.
`--dry-run` still taps for real, so it isn't a safe first test. If you couldn't run it, say so in the PR body.
