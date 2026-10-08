# PoGO-inventory-scripts

Small helpers for sorting a Pokémon GO storage by PvP IV rank.

## Scripts

### `pvp.py`

A command-line tool for PvP stat-product ranks. It reads Pokémon base stats from `gamemaster.json` and the CP multiplier table from `Pokemon.js`.

It has three commands.

**`match`** lists every level and IV combo that gives a CP and HP you saw in the game.

```
python3 pvp.py match <species> <cp> <hp> [stars]
```

`stars` is the appraisal star count (0–4). It is optional and narrows the IV total range.

```
$ python3 pvp.py match meditite 300 60
L15.5  14/14/13
L15.5  15/12/13
L16.0  12/13/12
...
```

**`rank`** shows the stat-product rank of an IV spread in Little, Great and Ultra League. It covers the species and every evolution after it. It also shows the level where each one hits the league cap.

```
python3 pvp.py rank <species> <atk> <def> <hp>
```

```
$ python3 pvp.py rank meditite 0 15 15
meditite: L6 (lv30.0), G1251 (lv50.0), U1251 (lv50.0)
  medicham: G613 (lv50.0), U1229 (lv50.0)
```

**`check`** does the same thing as `match`. For each match it also shows the best rank in each league across the whole family, and it marks any top-100 rank with `<== TOP100`.

```
python3 pvp.py check <species> <cp> <hp> <stars>
```

```
$ python3 pvp.py check meditite 300 60 2
L16.0  13/10/12  L2671(meditite) G247(meditite) U230(medicham)
...
```

#### Rules it uses

- League caps: Little 500, Great 1500, Ultra 2500.
- Max level is 50. Best buddy levels are not counted.
- Little Cup is only checked for base forms that can evolve.
- When two IV spreads tie, they share the better rank.
- Species names use PvPoke IDs, such as `medicham` or `stunfisk_galarian`.

#### Requirements

Python 3, standard library only.

## Data files

`gamemaster.json` and `Pokemon.js` come from [PvPoke](https://github.com/pvpoke/pvpoke) (MIT license). To update them, download fresh copies:

```
curl -O https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/gamemaster.json
curl -O https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/js/pokemon/Pokemon.js
```
