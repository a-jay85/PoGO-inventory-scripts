#!/usr/bin/env python3
"""Signature moves not in GO yet (the user, 2026-11-19: future-proofing counts mainline moves too): a damaging move
(not Z, not Max) that only one family learns in the main games, by Pokémon Showdown's data, and that GO's game master
(../shared/gamemaster.json) doesn't have. Smeargle's Sketch is left out. Writes sigmoves.json beside this file: one
row per Pokémon (dex number and Showdown form) that learns one, with the move's type.

  python3 sigmoves.py          fetch Showdown's moves, learnsets and Pokédex, write sigmoves.json (a few seconds)

pull.mjs reads sigmoves.json for its third pull (dialgadex-counters-sig-[pp2-]<date>.json): each learner gets every
charged move of that type some Pokémon has in GO, as if the move came out as strong as the best of its type. Run this
again when GO adds moves or a new game comes out, then node pull.mjs.
"""
import json, os, re, sys, tempfile, urllib.request

HERE = os.path.dirname(os.path.realpath(__file__))
SRC = "https://play.pokemonshowdown.com/data/"
OUT = os.path.join(HERE, "sigmoves.json")
sys.path.insert(0, os.path.join(HERE, "..", "shared"))


def key(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def fetch(name, into):
    p = os.path.join(into, name)
    req = urllib.request.Request(SRC + name, headers={"User-Agent": "Mozilla/5.0"})  # (the default one gets a 403)
    with urllib.request.urlopen(req, timeout=60) as r, open(p, "wb") as f:
        f.write(r.read())
    return json.load(open(p))


def build(moves, learnsets, dex, gm):
    """-> [{num, forme, type, move}]: every learner of every signature move GO doesn't have"""
    go = {key(m["moveId"].replace("_", "")) for m in gm["moves"]} | {key(m.get("name", "")) for m in gm["moves"]}

    def base(k):
        p = dex.get(k, {})
        return base(key(p["baseSpecies"])) if p.get("baseSpecies") and key(p["baseSpecies"]) != k else k

    def root(k):
        k, seen = base(k), set()
        while dex.get(k, {}).get("prevo") and k not in seen:
            seen.add(k)
            k = base(key(dex[k]["prevo"]))
        return k
    learn = {}
    for mon, d in learnsets.items():
        if mon not in dex or dex[mon].get("num", 0) <= 0 or mon == "smeargle":
            continue
        for mv in d.get("learnset") or {}:
            learn.setdefault(mv, set()).add(mon)
    out = []
    for mk, m in sorted(moves.items()):
        if m.get("category") == "Status" or not m.get("basePower") or m.get("isZ") or m.get("isMax") \
                or m.get("num", 0) <= 0 or m.get("isNonstandard") in ("CAP", "LGPE", "Custom", "Unobtainable"):
            continue
        who = learn.get(mk, set())
        if len({root(w) for w in who}) != 1 or mk in go:
            continue
        out += [{"num": dex[w]["num"], "forme": key(dex[w].get("forme", "")), "type": m["type"], "move": m["name"]}
                for w in sorted(who)]
    return out


def main():
    if sys.argv[1:]:
        sys.exit(__doc__)
    import pvp  # (after the argv check: pvp.py's own 'update' runs on import when argv[1] is 'update')
    with tempfile.TemporaryDirectory() as t:
        rows = build(fetch("moves.json", t), fetch("learnsets.json", t), fetch("pokedex.json", t), pvp.GM)
    json.dump(rows, open(OUT, "w"), indent=0)
    print(f"{len({r['move'] for r in rows})} signature moves not in GO, {len(rows)} learners -> {OUT}")


if __name__ == "__main__":
    main()
