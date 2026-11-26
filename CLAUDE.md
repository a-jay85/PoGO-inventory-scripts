# PoGO-inventory-scripts

Scripts that sort a Pokémon GO storage: `pvpc`, `ivc`, `cleanup`, `trade`, `gift`, `mega`, `evo`, `dex`, `roster`, `gymfeed` and `goplus`. Each one lives in `skills/<name>/`. The scripts are the source of truth: each script's top comment says how to run it, and the code says the rules. The skills under `skills/` have no `SKILL.md` files (the one Claude skill is `.claude/skills/backlog/`). `/pvpc` or `/ivc` in chat means run that step through `pogo.py`.

## The live scripts run from the main checkout

Whatever is on the main checkout's `main` branch is what runs on the phone.

- Never edit the main checkout (`~/PoGO-inventory-scripts`) directly. That covers code, docs and config, however small the change.
- After a PR merges, update the main checkout or the live scripts never see the change:
  `git -C ~/PoGO-inventory-scripts pull --ff-only`
- Pull right after the merge, even while a script is running on the phone. Don't wait for the run, don't set up a job to wait for it, and don't mention the pull in the reply unless it fails.

The skills import each other by relative path (`HERE/../shared`), so they must stay siblings under `skills/`.

`pogo.py` (at the repo root) is the one front door: it runs any skill's script by step name, and chains steps with `+` (`pogo.py pvpc --limit 5 + ivc`). Each step is its own process. A new script gets a line in its `STEPS` table. Every `pogo.py` run heals a step that stops or crashes: a headless Claude fixes it (worktree, tests, phone test, PR, merge, pull), then the step runs again with only what's left (`heal.py`, at the repo root, says how). Off with `--no-heal`, and off when Claude starts `pogo.py` (the Claude watching fixes it). Scripts run on their own never heal. Code two skills both need goes in `skills/shared/` (the shared library), never copied. The tapper (taps, timing, run folders, logging) is `skills/shared/base.py`; scripts `import base`. Also in `skills/shared/`: `taps.py` (one tap, the swipe to the next Pokémon, SELECT ALL, purify), `tagsheet.py` (exact search, detail page reads, the tag sheet), `savedsearch.py` (saved searches, tag a whole search), `powerup.py` (level reads, power-ups), `rules.py` (tag names and rule constants), `popups.py` (boxes over any screen and the one safe tap that closes each: `base.wait_for` and `home.unstick` use it, so a new box goes there and every script knows it), `pages.py` (whole screens one script owns, like the trade lobby, the gift list or a gym, and the tap its owner leaves each by: `home.unstick` uses it, and each owner's classify calls its readers, so there is one copy).

What every file can do is mapped from the code by `codemap.py` (repo root): `.claude/rules/codemap.md` has one line per file and loads by itself when a script is read, and `skills/MAP.md` has every function with its arguments and comment. Before writing a helper (a level, a CP, a candy count, a search), grep `skills/MAP.md` for it: it is likely already in `skills/shared/`. After adding, renaming or removing a function, or changing a file's top comment, run `python3 codemap.py` and commit both maps.

Facts many scripts share (the two accounts, the tags, what a trade pays, where the Pokémon database and the game master are) are in `.claude/rules/facts.md`, which always loads. A new fact that two or more skills need goes there. A fact only one skill needs goes in that skill's `.claude/rules/<skill>.md`. A lasting game fact or user rule goes in the repo, not in Claude's memory: memory is tied to the folder a session starts in, so worktree sessions never see it.

A speed win found in one script goes to every script that does the same step, in the same PR or the next one, without the user asking. Before opening the PR, grep `skills/` for the same wait, read, search or loop. Best: move that step into `skills/shared/`, so one change reaches every script. If another script can't take the win, the PR body says why.

A read that says something isn't there (no name, a grey icon, no X, 0 results, no date) may be a screen still loading. Look again with `base.settle(read, ok, timeout)` or `base.wait_for` before acting on it. Never tap or type to make it show up: the blank-search nudge did that and turned a real 0 into 1182 (#293).

## The phone backlog

Something that needs a look on a phone but can't be done now (the phone is busy, the user is using it, a run left a Pokémon unsure) goes in the phone backlog: GitHub Issues in the private repo `a-jay85/PoGO-inventory-scripts-backlog`, through `backlog.py` (repo root). Search before filing. When both phones are free, `python3 backlog.py ready` says so and lists what's waiting. `.claude/skills/backlog/SKILL.md` has how to file and work it.

A fix that needs a phone test, with the phone busy, never waits for the phone. Open the PR, write `No phone test: phone busy, filed in backlog #<n>` in its body, and file a `fix`-kind backlog issue (the PR URL, the exact `watch.py` command to run, what to look for). The night backlog run tests it and closes the issue. Don't merge until that test passes.

## Running the scripts

- `POGO_PHONE=android`: the Pixel, over USB. Nothing set: the iPhone, through iPhone Mirroring. `POGO_PHONE=both`: `/gift` and `/mega` run both at once.
- iPhone runs pause when the Mac's keyboard or mouse is touched, and go on after 5 seconds idle. The pointer goes back after each tap. Pixel taps go through adb, so the Mac stays free.
- Every script starts from any screen (`home.start()`). At the end it quits iPhone Mirroring or locks the Pixel. `POGO_KEEP_OPEN=1` leaves it open. `python3 skills/shared/session.py open|close` does just that part.
- Pixel setup, once: USB debugging on, tap Allow on the phone, and put the PIN in `~/.config/pogo/android-pin` (digits only, `chmod 600`). `POGO_PHONE=android python3 skills/shared/android.py check` checks it.
- One script per phone. `session.ready()` takes a lock for the whole run (`/tmp/pogo-android.lock`, `/tmp/pogo-iphone.lock`). A second script stops and says what's using the phone. A test script must go through `session.ready()` too. `python3 skills/shared/session.py busy` says what's using each phone now, without touching one (a hook blocks the old `ps | grep` check).
- `~/.config/pogo/accounts.json` says which Google account is which trainer (`skills/shared/account.py`).

## Every change goes in a worktree, a PR and a squash-merge

1. Make a worktree outside the repo:
   `git -C ~/PoGO-inventory-scripts worktree add ~/PoGO-inventory-scripts-worktrees/<slug> -b <type>/<slug> origin/main`
2. Enter it with `EnterWorktree(path=...)`. Don't `cd` into it.
3. Commit, then push in a separate command. Never chain `git commit && git push`.
4. Open a PR with `gh pr create`. Squash-merge only: `gh pr merge --squash --delete-branch`.
   `merge_gate.py` (repo root, a hook in `.claude/settings.json`) checks every `gh pr merge` of this repo first, and blocks it with what to do. It runs the tests on the PR head. A PR that changes a `.py` under `skills/`, or `pogo.py`, `heal.py` or `watch.py`, needs a `watch.py` phone run of the PR head, ended with exit 0, or a body line `No phone test: <why>`. It may also ask for body lines (`Siblings:`, `Unreached:`, `Speed elsewhere:`, `Shared checked:`). When each one is needed: `.claude/rules/testing.md`. `python3 merge_gate.py <n>` runs the same checks by hand.
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

Any job that touches more than one Pokémon starts with the search that finds them all. Write that search first, before any plan that opens tiles one by one. Then tag the whole result at once with `savedsearch.tag_pile` (long press, SELECT ALL, tag). Open tiles only for what no search term can tell (exact IVs, a read pokedb doesn't have yet), and only the tiles that search found. Prefer a tighter search over scanning more tiles.

Every search term, how `&` `,` `!` combine, and the known bugs are in `skills/shared/SEARCH.md`. It loads into every session from the line below:

@skills/shared/SEARCH.md

## Seeing the phone

Scripts see the Android phone with its own screenshots (`adb exec-out screencap`, via `ui.capture()` / `android.capture()` in `skills/shared/android.py`). Never use scrcpy or a Mac window grab (`screencapture`) for it: scrcpy's picture froze at random while the Mac was in use, and its code is gone. New scripts reuse `ui.capture()` and don't add their own capture path.

When Claude needs to see the screen (a live look or a run's saved png), use `skills/shared/peek.py`. A picture costs about width × height / 750 tokens, and it stays in context for the rest of the session.

1. Read the text first: `POGO_PHONE=android python3 ~/PoGO-inventory-scripts/skills/shared/peek.py --text` (or `peek.py <png> --text`). That's often enough.
2. If the text isn't enough, crop to the part you need: `peek.py [png] --crop top|mid|bottom|x0,y0,x1,y1`. Then Read `/tmp/peek.png`. A crop of a live Android capture comes from the full-size screenshot, so small text stays sharp.
3. Don't Read the same picture twice. Don't Read the 3× `/tmp/pvpc_android_sharp.png` or `/tmp/pvpc_iphone_sharp.png` whole: the model shrinks anything over 1568 px anyway.

## Never commit

The repo is public. These stay local and are in `.gitignore`:

- `skills/*/runs/`: run logs and screen captures (trainer names, inventory)
- `skills/shared/.state.json`, `skills/shared/.calib.json`, `skills/trade/.state.json`: per-machine state
- `skills/shared/helper`: built from `helper.swift` on first use
- `skills/shared/pokedb.sqlite`: every Pokémon read (IVs, CP, nicknames)

## Testing

Which test to run after which change, and what the merge gate asks for in a PR body: `.claude/rules/testing.md` (it loads when a `.py` is read).

Nothing tests taps and timing off the phone. A change to how a skill reads or taps the phone isn't done until it has run on the phone, from its worktree, through `watch.py` (the merge gate looks for that run):
`POGO_PHONE=android python3 <worktree>/watch.py caffeinate -dimsu python3 <worktree>/skills/pvpc/run.py --limit 1`. Claude starts it and watches it itself; no need to ask the user to watch.

Claude watches a phone run quietly, through `watch.py` (repo root) started with Bash `run_in_background: true, timeout: 7200000`:
`POGO_PHONE=android python3 ~/PoGO-inventory-scripts/watch.py caffeinate -dimsu python3 <script> [args]`.
It prints nothing while the script runs, then one short summary at the end (exit code, STOPPED / CRASHED / error lines, last lines). The full output is in `/tmp/pogo-watch/<stamp>.log`, and where the run came from (checkout, HEAD, file contents, exit code) in `<stamp>.json`. Every python3 the run starts writes which lines of its checkout ran to `<stamp>.lines.*` (`linetrace/sitecustomize.py`; on a phone run it costs nothing you can see). The script runs detached, so if the waiter times out, `watch.py --wait` waits again. No `Monitor` on a run: a user hook blocks it.
A worktree has no `runs/` folders, and the species lists and saved reads (`runs/reads-<trainer>.json`, `checked-*.json`) live there (`skills/cleanup/runs/`). `watch.py` links the main checkout's dex, roster and cleanup `runs` folders into the worktree for the run and takes them off after. A run started without `watch.py` needs them linked by hand, and taken off before `merge_gate.py` or `wt_cleanup.py`, because they break `tests/layout.py`. Never `tests/layout.py --record` with them in place.

`--dry-run` still taps for real, so it isn't a safe first test. If you couldn't run it, say so in the PR body.
