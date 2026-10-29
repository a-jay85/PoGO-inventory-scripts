# PoGO-inventory-scripts

Claude Code skills that sort a Pokémon GO storage: `/pvpc`, `/ivc`, `/ivcsort`, `/cleanup`, `/trade`, `/gift`, `/mega`, `/dex`, `/roster` and `/gymfeed`. Each one lives in `skills/<name>/`.

## The live skills run from the main checkout

`~/.claude/skills/<name>` is a symlink to `~/PoGO-inventory-scripts/skills/<name>`. Whatever is on the main checkout's `main` branch is what runs on the phone.

- Never edit the main checkout (`~/PoGO-inventory-scripts`) directly. That covers code, SKILL.md files, docs and config, however small the change.
- After a PR merges, update the main checkout or the skills never see the change:
  `git -C ~/PoGO-inventory-scripts pull --ff-only`
- Don't pull while a script is running on the phone. Python has already loaded the old files, but a skill that imports another one mid-run gets a mix.

The skills import each other by relative path (`HERE/../shared`), so they must stay siblings under `skills/`.

`pogo.py` (at the repo root) is the one front door: it runs any skill's script by step name, and chains steps with `+` (`pogo.py pvpc --limit 5 + ivc`). Each step is its own process. A new script gets a line in its `STEPS` table. Code two skills both need goes in `skills/shared/` (the shared library), never copied. The tapper (taps, timing, run folders, logging) is `skills/shared/base.py`; scripts `import base`.

## Every change goes in a worktree, a PR and a squash-merge

1. Make a worktree outside the repo:
   `git -C ~/PoGO-inventory-scripts worktree add ~/PoGO-inventory-scripts-worktrees/<slug> -b <type>/<slug> origin/main`
2. Enter it with `EnterWorktree(path=...)`. Don't `cd` into it.
3. Commit, then push in a separate command. Never chain `git commit && git push`.
4. Open a PR with `gh pr create`. Squash-merge only: `gh pr merge --squash --delete-branch`.
5. Claude does this step itself and never hands it to the user. Leave the worktree (`ExitWorktree` with `keep`), pull the main checkout (above), then remove every merged worktree:
   `python3 ~/PoGO-inventory-scripts/wt_cleanup.py`
   It removes only worktrees whose PR merged, with nothing uncommitted and no process inside, and it saves their `runs/` folders to `~/claude-plans/_backups/worktree-runs/` first. It also sweeps leftovers from other sessions. `--dry-run` shows what it would do.

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

## In-game searches

Before typing or building a storage search, read `skills/shared/SEARCH.md` (live at `~/PoGO-inventory-scripts/skills/shared/SEARCH.md`). It lists every search term, how `&` `,` `!` combine, and the known bugs. Prefer a tighter search over scanning more tiles.

## Seeing the phone

Scripts see the Android phone with its own screenshots (`adb exec-out screencap`, via `ui.capture()` / `android.capture()` in `skills/shared/android.py`). Never use scrcpy or a Mac window grab (`screencapture`) for it: scrcpy's picture freezes at random while the Mac is in use. New scripts reuse `ui.capture()` and don't add their own capture path. `POGO_SCRCPY=1` brings the old scrcpy window back, only if the user asks for it.

When Claude needs to see the screen (a live look or a run's saved png), use `skills/shared/peek.py`. A picture costs about width × height / 750 tokens, and it stays in context for the rest of the session.

1. Read the text first: `POGO_PHONE=android python3 ~/PoGO-inventory-scripts/skills/shared/peek.py --text` (or `peek.py <png> --text`). That's often enough.
2. If the text isn't enough, crop to the part you need: `peek.py [png] --crop top|mid|bottom|x0,y0,x1,y1`. Then Read `/tmp/peek.png`. A crop of a live Android capture comes from the full-size screenshot, so small text stays sharp.
3. Don't Read the same picture twice. Don't Read the 3× `/tmp/pvpc_sharp.png` whole: the model shrinks anything over 1568 px anyway.

## Never commit

The repo is public. These stay local and are in `.gitignore`:

- `skills/*/runs/`: run logs and screen captures (trainer names, inventory)
- `skills/shared/.state.json`, `skills/shared/.calib.json`, `skills/shared/.paste.json`, `skills/trade/.state.json`: per-machine state
- `skills/shared/helper`: built from `helper.swift` on first use

## Testing

`python3 tests/readers.py` pins what every text reader says today (search-bar checks, result counts, name matchers), from OCR text alone. Run it after any change to one. It must say "all ... the same". If an answer changed on purpose, run `--record` and say which answers changed in the PR body.

`python3 tests/layout.py` pins how the scripts find each other and their files: each script's names, the one shared copy of `run.py` (its run folder), where every run folder goes, and that every path and `module.name` the code uses exists. Run it after moving or renaming a file, or moving code between files. It must say "all ... the same". Same `--record` rule.

Nothing tests taps and timing off the phone. A change to how a skill reads or taps the phone isn't done until it has run on the phone:
`POGO_PHONE=android caffeinate -dimsu python3 ~/.claude/skills/pvpc/run.py --limit 1`. Claude starts it and watches it itself; no need to ask the user to watch.
`--dry-run` still taps for real, so it isn't a safe first test. If you couldn't run it, say so in the PR body.
