---
paths:
  - "**/*.py"
  - "*.py"
  - "tests/**"
---
# Tests and the merge gate

## What the merge gate asks for

`merge_gate.py` (repo root, a hook in `.claude/settings.json`) checks every `gh pr merge` of this repo first, and blocks it with what to do. It runs every test below on the PR head. A PR that changes a `.py` under `skills/`, or `pogo.py`, `heal.py` or `watch.py`, needs a `watch.py` phone run, ended with exit 0, of the files as they are at the PR head. If one can't be done, a body line `No phone test: <why>`. Such a PR also needs a body line `Siblings: <what was checked, what it found>`. The gate lists the changed functions, their callers, and phone or account branches where only one side changed. It also lists the PR's changed lines that the phone run never reached. If most of them never ran, it blocks until the body has a line `Unreached: <why they can't be reached>`. A PR that changes a `.py` under `skills/` and talks about speed in its title or body ("faster", "fewer", "2.0 s -> 1.2 s") needs a body line `Speed elsewhere: <which other scripts got the same win, or why none can>`. The gate lists functions of the same name in other skills, which are likely copies. A PR that adds a function to a `.py` under `skills/` (outside `skills/shared/`) that looks like one `skills/shared/` already has (a name word in common, like `trainer_tabs` and `ui.banner_tabs`, or rare words in both comments, like "GPS banner") needs a body line `Shared checked: <for each new function: the look-alike and why it isn't a fit, or that it moved to shared>`. The gate lists each new function and its look-alikes. One that calls its look-alike passes. With no look-alikes, no line is needed. `python3 merge_gate.py <n>` runs the same checks by hand.

## Which test after which change

`python3 tests/readers.py` pins what every text reader says today (search-bar checks, result counts, name matchers), from OCR text alone. Run it after any change to one. It must say "all ... the same". If an answer changed on purpose, run `--record` and say which answers changed in the PR body.

`python3 tests/layout.py` pins how the scripts find each other and their files: each script's names, the one shared copy of `run.py` (its run folder), where every run folder goes, and that every path and `module.name` the code uses exists. Run it after moving or renaming a file, or moving code between files. It must say "all ... the same". Same `--record` rule.

`python3 tests/lints.py` pins four bad patterns that came back after fixes, from the code alone: a typed search that ends in a thin letter (`#IVC&xxl` reads back as `#IVC&xx`), a label lookup used with no None check (`tap_text(label(...))`), hand-rolled wait loops per function (use `base.settle` or `base.wait_for`), and hand-rolled "two reads in a row agree" loops (use `base.steady`). A new one fails with its file:line and what to do instead. Run it after any change under `skills/`. It must say "all ... the same". Same `--record` rule.

`python3 tests/heal.py` checks `pogo.py`'s healing with a made-up failing step and a stand-in Claude. Run it after any change to `heal.py` or `pogo.py`.

`python3 tests/timer.py` checks `skills/shared/timer.py`'s tick with a stand-in `adb` and made-up jobs: a phone out of reach turns its timers off. Run it after any change to `timer.py`. It must say "all timer cases right".

`python3 tests/gate.py` checks `merge_gate.py` with a made-up repo and PR, a stand-in `gh` and made-up phone runs. Run it after any change to `merge_gate.py`, `watch.py` or `linetrace/sitecustomize.py`. It must say "all gate cases right".

`python3 tests/verdicts.py` pins the final tag `verdict.py` gives made-up Pokémon. `python3 tests/taggers.py` runs the bulk taggers' searches (`tradeable.py tag`, `cleantrades.py`) over made-up Pokémon and checks they tag what `verdict.py` says. Run both after any change to a rule or a tag search.

`python3 tests/codemap.py` checks both code maps match the code. Run it after any change to a `.py` under `skills/` or the repo root. It must say "all code maps the same". Out of date: `python3 codemap.py`, then commit both maps.

`python3 tests/hundred.py` checks `dex.hundred_useful` (which forms a new 100% copy would help) on a made-up evolution tree. Run it after any change to it. It must say "all hundred cases right".

`skills/cleanup/savedsearches.py` reads the saved searches off the Pixel and checks they hold the terms in `rules.SAVED`. Run it after changing one on the phone.
