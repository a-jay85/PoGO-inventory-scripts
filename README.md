# PoGO-inventory-scripts

Scripts that run Pokémon GO on a phone from a Mac. They sort the storage (PvP and IV keepers, trades, transfers), and do the daily chores (gifts, Mega Evolutions, gym berries, eggs).

They drive a Pixel over adb (USB or Wi-Fi), or an iPhone through iPhone Mirroring. They read the screen with OCR (text reading from a screenshot) and tap like a person would.

Each script's top comment says what it does and how to run it. The code is the rule book. This page is the map.

## Running a script

`pogo.py` runs any script by its step name. `+` chains steps. Each step runs as its own process.

```
POGO_PHONE=android python3 pogo.py pvpc --limit 5 + ivc
python3 pogo.py list          every step and the words it takes
```

- `POGO_PHONE=android` is the Pixel. Unset is the iPhone. `POGO_PHONE=both` runs `gift` and `mega` on both phones at once.
- Every script starts from any screen, and closes the phone at the end. `POGO_KEEP_OPEN=1` leaves it open.
- One script per phone at a time. A second one stops and says what's using the phone.
- iPhone runs pause while you touch the Mac's keyboard or mouse. Pixel runs leave the Mac free.

### Healing

When a step stops or crashes, `pogo.py` starts a headless Claude to fix it (`heal.py`). Claude fixes the code in a worktree, tests it, merges it, and pulls it. Then the step runs again with only what's left. `--no-heal` turns this off. Scripts started on their own never heal.

### Watching a run

`watch.py` runs a script quietly and prints one short summary at the end. The full log goes to `/tmp/pogo-watch/`.

```
POGO_PHONE=android python3 watch.py python3 skills/pvpc/run.py --limit 1
```

## The steps

| Step | What it does |
|---|---|
| `pvpc` | Works through the PvpC-tagged list: keeps top PvP IVs and names them |
| `ivc` | Works through the IVC-tagged list: keeps the best IVs, names them by IV% |
| `cleantrades` | After trading: tags the saved searches, powers up for Candy XL, tags Transfer |
| `tradeable` | Tags CyrillJan's Tradeable search by what a trade to HashTagAJay is worth |
| `leftovers` | Tags HashTagAJay's Leftovers search by what a trade to another account is worth |
| `specieswise` | Re-judges the #GIV or #Transfer pile by species alone, opening nothing |
| `sizes` | Keeps every XXL Pokémon |
| `dbfill` | Opens one search's Pokémon the database doesn't know yet, and saves their IVs |
| `dbsweep` | Drops bulk-transferred Pokémon from the database |
| `dex` | Reads a Pokédex page and prints a search of what's missing, for the other account |
| `luckydex` | Puts HashTagAJay's missing luckies into CyrillJan's Luckydex search |
| `sizerecords` | Reads each species' size records and says which account would beat the other |
| `roster` | HashTagAJay's best 6 raid attackers per boss, and which species a new copy would help |
| `raidteam` | The signed-in account's best 6 raid attackers per 4★+ boss, at today's levels |
| `trade` | Local trades between the two accounts, iPhone and Pixel at once |
| `gift` | Sends gifts to every friend who can take one, most useful first |
| `mega` | Mega Evolves every Pokémon tagged TODO, once a day each |
| `evo` | Evolves every free trade evolution tagged Evo |
| `gymfeed` | Feeds berries to the Pokémon defending your gyms |
| `hatch` | Hatches ready eggs, fills the free ∞ incubator, sets the next timer |
| `goplus` | Connects the GO Plus+ |
| `account` | Switches the Pixel to the other Google account |
| `advsync` | Turns Adventure Sync on |

## Where things live

- `skills/<name>/`: one folder per job.
- `skills/shared/`: code two or more scripts need. `base.py` is the tapper (taps, timing, run folders, logging). The rest covers searches, popups, power-ups, tags, the rules, and the phone session.
- `skills/shared/SEARCH.md`: every in-game search term, and its known bugs.
- `skills/shared/pokedb.py`: a SQLite memory of every Pokémon the scripts have read (IVs, CP, nickname, candy). The file is `~/.config/pogo/pokemon.db`, outside the repo.
- `skills/shared/timer.py`: one launchd timer that runs `gymfeed`, `hatch` and `goplus` on their own. `python3 skills/shared/timer.py install` turns it on.
- `skills/shared/adbwifi.py`: keeps the Pixel reachable over Wi-Fi when it's unplugged. `python3 skills/shared/adbwifi.py install` turns it on.
- `skills/MAP.md` and `.claude/rules/codemap.md`: maps of every file and function, written by `python3 codemap.py`.
- `merge_gate.py`: checks a PR before it merges (tests, phone run, notes in the body).
- `wt_cleanup.py`: removes worktrees whose PR merged.
- `tests/`: off-phone tests. `CLAUDE.md` says which to run after which change.

## Setup

- macOS with Python 3 and Pillow (`pip3 install pillow`).
- The Pixel: USB debugging on, Allow tapped on the phone, and the PIN in `~/.config/pogo/android-pin` (digits only, `chmod 600`). Check it with `POGO_PHONE=android python3 skills/shared/android.py check`.
- The iPhone: iPhone Mirroring, and Screen Recording allowed for the terminal. `skills/shared/helper` builds itself from `helper.swift` on first use.
- `~/.config/pogo/accounts.json` says which Google account is which trainer.

## `pvp.py`, the PvP rank tool

`skills/shared/pvp.py` ranks IV spreads by stat product in Little, Great and Ultra League. The scripts use it, and it runs on its own too:

```
python3 skills/shared/pvp.py check <species> <cp> <hp> <stars>   IV/level combos for a CP and HP, with best ranks
python3 skills/shared/pvp.py rank <species> <atk> <def> <hp>     ranks for the species and each evolution
python3 skills/shared/pvp.py name <species> <atk> <def> <hp>     the nickname a script would give it
python3 skills/shared/pvp.py update                              download the game master and PvPoke ranks again
```

```
$ python3 skills/shared/pvp.py rank meditite 0 15 15
Meditite [('L', 6)]
Medicham [('G', 613)]
```

League caps are 500, 1500 and 2500. Max level is 50, with no best buddy. Tied spreads share the better rank. Species names use PvPoke IDs, like `medicham` or `stunfisk_galarian`.

The older `pvp.py` at the repo root does `match`, `rank` and `check` with the root copies of the data files.

## Data files

The scripts read [PokeMiners' game master](https://github.com/PokeMiners/game_masters) and PvPoke's league rankings. Neither is in the repo: `python3 skills/shared/gamedata.py update` downloads them into `~/.config/pogo/gamedata/`. The root copies of `gamemaster.json` and `Pokemon.js` (for the root `pvp.py`) come from [PvPoke](https://github.com/pvpoke/pvpoke) (MIT license). Their license is in `LICENSE-pvpoke`.

## Contributing

Every change goes in a worktree, a PR and a squash-merge. The main checkout's `main` is what runs on the phone, so pull it after each merge. `CLAUDE.md` has the full rules.
