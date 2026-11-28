#!/usr/bin/env python3
"""The game data every script reads: PokeMiners' game master (what the game itself ships), its English names, and
PvPoke's league rankings (the meta list). None of it is in the repo: it lives in ~/.config/pogo/gamedata/.

  gamedata.py update   -> download all three again, then build species.json from them
  gamedata.py build    -> build the species file again from the files already downloaded, and say where it went

The species file (species-<key>.json in the same folder) is in PvPoke's shape ({"pokemon": [...], "moves": [...], "cpms": [...]}) under PvPoke's ids, so pvp.py
and every script read it as they read PvPoke's game master before. pvpoke_ids.json (beside this file) says which
PokeMiners template each PvPoke id is. The regional and unreleased lists are hand lists in rules.py. The key is a
hash of what it's built from (the downloads, the id table, this file, rules.py), so each checkout reads its own
build and a worktree's never changes what the main checkout reads. load() builds it when it's missing (0.2 s).
"""
import glob, hashlib, json, math, os, struct, sys, urllib.request
import jsonfile
import rules

HERE = os.path.dirname(os.path.realpath(__file__))
DIR = os.environ.get("POGO_GAMEDATA") or os.path.expanduser("~/.config/pogo/gamedata")
GM_URL = "https://raw.githubusercontent.com/PokeMiners/game_masters/master/latest/latest.json"
TEXT_URL = "https://raw.githubusercontent.com/PokeMiners/pogo_assets/master/Texts/Latest%20APK/JSON/i18n_english.json"
RANK_URL = "https://raw.githubusercontent.com/pvpoke/pvpoke/master/src/data/rankings/{}.json"
RANK_LISTS = {"L": "little/overall/rankings-500", "G": "all/overall/rankings-1500",
              "U": "all/overall/rankings-2500"}
RAW, TEXT, RANKS = (os.path.join(DIR, f) for f in ("latest.json", "i18n_english.json", "rankings.json"))
KEEP_BUILDS = 6  # species files kept (one per checkout's version of the inputs): the newest
IDS = os.path.join(HERE, "pvpoke_ids.json")
MAX_CPM_LEVEL = 55  # the CP multipliers kept: levels 1 to this, every half level
CLASS_TAG = {"POKEMON_CLASS_LEGENDARY": "legendary", "POKEMON_CLASS_MYTHIC": "mythical",
             "POKEMON_CLASS_ULTRA_BEAST": "ultrabeast"}
REGION_TAG = {"ALOLA": "alolan", "GALARIAN": "galarian", "HISUIAN": "hisuian", "PALDEA": "paldean"}


def missing():
    return f"no game data in {DIR}: run python3 {os.path.join(HERE, 'gamedata.py')} update"


def update():
    os.makedirs(DIR, exist_ok=True)
    for url, path in ((GM_URL, RAW), (TEXT_URL, TEXT)):
        urllib.request.urlretrieve(url, path + ".part")
        json.load(open(path + ".part"))  # (a cut-off download stops here, the old file kept)
        os.replace(path + ".part", path)
    lists = {t: [p["speciesId"] for p in json.load(urllib.request.urlopen(RANK_URL.format(path)))]
             for t, path in RANK_LISTS.items()}
    jsonfile.write(RANKS, lists, indent=0)
    print(f"{len(load()['pokemon'])} species -> {built()}")


def raw():
    """PokeMiners' game master as downloaded: a list of {templateId, data}"""
    if not os.path.exists(RAW):
        sys.exit(missing())
    return json.load(open(RAW))


def built():
    """this checkout's species file: named by a hash of everything it's built from"""
    if not (os.path.exists(RAW) and os.path.exists(TEXT)):
        sys.exit(missing())
    h = hashlib.sha1()
    for f in (RAW, TEXT):
        h.update(f"{os.path.getmtime(f)} {os.path.getsize(f)}".encode())
    for f in (IDS, os.path.realpath(__file__), os.path.join(HERE, "rules.py")):
        h.update(open(f, "rb").read())
    return os.path.join(DIR, f"species-{h.hexdigest()[:12]}.json")


def load():
    """the species file: {"pokemon": [...], "moves": [...], "cpms": [...]}, built first if this checkout has none"""
    path = built()
    if os.path.exists(path):
        return json.load(open(path))
    data = build()
    jsonfile.write(path, data, indent=0)
    for old in sorted(glob.glob(os.path.join(DIR, "species-*.json")), key=os.path.getmtime)[:-KEEP_BUILDS]:
        os.remove(old)
    return data


def rankings():
    """PvPoke's overall ranking per league (L G U): speciesIds, best first"""
    if not os.path.exists(RANKS):
        sys.exit(missing())
    return json.load(open(RANKS))


def f32(x):
    """the game's numbers are 32-bit floats: the same value PvPoke writes (0.094 -> 0.0939999967813491)"""
    return struct.unpack("f", struct.pack("f", x))[0]


def cpms(gm):
    """the CP multiplier of every level from 1 to MAX_CPM_LEVEL, half levels too (the mean of the squares)"""
    full = [f32(x) for x in next(t for t in gm if t["templateId"] == "PLAYER_LEVEL_SETTINGS")
            ["data"]["playerLevel"]["cpMultiplier"]][:MAX_CPM_LEVEL]
    out = []
    for i, m in enumerate(full):
        out.append(m)
        if i + 1 < len(full):
            out.append(math.sqrt((m * m + full[i + 1] ** 2) / 2))
    return out


def move_numbers(gm):
    """move number -> its name in the templates (COMBAT_V0482_MOVE_DYNAMAX_CANNON: 482 -> DYNAMAX_CANNON). A few new
    moves are named only by number elsewhere"""
    return {int(t["templateId"][8:12]): t["templateId"].split("_MOVE_", 1)[1] for t in gm
            if t["templateId"].startswith("COMBAT_V") and t["templateId"][8:12].isdigit()}


def move_id(m, numbers):
    """PvPoke's move id: no _FAST on the end"""
    return (numbers.get(m, str(m)) if isinstance(m, int) else m).removesuffix("_FAST")


def build():
    """the species data from PokeMiners' game master, the English names and the id table"""
    gm = raw()
    text = json.load(open(TEXT))["data"]
    text = dict(zip(text[::2], text[1::2]))
    ids = json.load(open(IDS))
    numbers = move_numbers(gm)
    by_t, by_pf, dex_of = {}, {}, {}  # template -> settings, (pokemonId, form or None) -> template, pokemonId -> dex
    for t in gm:
        p = t["data"].get("pokemonSettings")
        if p and t["templateId"].startswith("V"):
            by_t[t["templateId"]] = p
            by_pf.setdefault((p["pokemonId"], p.get("form")), t["templateId"])
            dex_of[p["pokemonId"]] = int(t["templateId"][1:5])
    # the PvPoke ids of each template: plain ones (no shadow, no mega), the shortest first (the main one)
    plain_of = {}
    for sid, v in ids.items():
        if not v.get("shadow") and not v.get("mega"):
            plain_of.setdefault(v["t"], []).append(sid)
    for v in plain_of.values():
        v.sort(key=lambda s: (len(s), s))

    def template(pid, form, like=None):
        """a pokemonId (and form) -> its template. No form: the one with like's form ending (Wormadam's Sandy cloak ->
        BURMY_SANDY, an Alolan one -> PIKACHU_ALOLA) if there is one, else _NORMAL"""
        if form:
            return by_pf.get((pid, form))
        if like and "_" in like:
            for i in range(1, len(like.split("_"))):
                end = "_".join(like.split("_")[i:])
                if (pid, f"{pid}_{end}") in by_pf:
                    return by_pf[(pid, f"{pid}_{end}")]
            for r in REGION_TAG:  # (Galarian Zen Darmanitan -> DARUMAKA_GALARIAN)
                if r in like.split("_")[1:] and (pid, f"{pid}_{r}") in by_pf:
                    return by_pf[(pid, f"{pid}_{r}")]
        got = by_pf.get((pid, f"{pid}_NORMAL"))
        if not got:  # (Nidoran♀ is NIDORAN_FEMALE with the form NIDORAN_NORMAL)
            mine = sorted(t for (q, f), t in by_pf.items() if q == pid and f and main_id(t))
            got = next((t for t in mine if t.endswith("_NORMAL")), mine[0] if mine else None)
        return got or by_pf.get((pid, None))

    def main_id(tid):
        return (plain_of.get(tid) or [None])[0]

    def types(p):
        ty = [x.replace("POKEMON_TYPE_", "").lower() for x in (p.get("type"), p.get("type2")) if x]
        return ty + ["none"] * (2 - len(ty))

    def moves(p):
        """fast, charged and elite moves. A non-TM move (Rayquaza's Dragon Ascent) counts as elite: no normal TM
        teaches it"""
        odd = lambda k: p.get(k) or []
        fast = [move_id(m, numbers) for m in odd("quickMoves") + odd("eliteQuickMove") + odd("nonTmQuickMoves")]
        charged = [move_id(m, numbers) for m in
                   odd("cinematicMoves") + odd("eliteCinematicMove") + odd("nonTmCinematicMoves")]
        elite = [move_id(m, numbers) for m in odd("eliteQuickMove") + odd("eliteCinematicMove")
                 + odd("nonTmQuickMoves") + odd("nonTmCinematicMoves")]
        return list(dict.fromkeys(fast)), list(dict.fromkeys(charged)), list(dict.fromkeys(elite))

    # the plain families first: what each template evolves into, then its parent. The parent is the one whose
    # evolutions list it (what GO lets you evolve), else the game's parentPokemonId (a form no evolution reaches:
    # Alolan Raichu -> Pikachu)
    def mapped(t, pid):  # (a form PvPoke has no id for, like Dusk Rockruff or a costume: its species' plain one)
        return t if main_id(t) else template(pid, None)

    kids_of, parent_of = {}, {}
    for tid, p in by_t.items():
        if not main_id(tid) and not p.get("form"):  # (the formless copy of a species with forms)
            continue
        if not (home := mapped(tid, p["pokemonId"])) or not main_id(home):
            continue
        kids = kids_of.setdefault(home, [])
        for b in p.get("evolutionBranch") or []:
            if "evolution" in b and not b.get("temporaryEvolution"):
                kt = mapped(template(b["evolution"], b.get("form")), b["evolution"])
                if kt and main_id(kt) and main_id(kt) not in kids:
                    kids.append(main_id(kt))
    for tid, kids in kids_of.items():
        for k in kids:
            parent_of.setdefault(k, main_id(tid))
    # (no evolution reaches it, like Wyrdeer or Alolan Raichu: the game's parentPokemonId. That gives the candy
    # family only: the parent's evolutions stay what GO lets you evolve, so pvp.kin_parent reads it)
    for tid in plain_of:
        p = by_t[tid]
        par = p.get("parentPokemonId")
        fam_of = (p.get("familyId") or "").removeprefix("FAMILY_")
        if not par and fam_of != p["pokemonId"] and fam_of in dex_of:  # (no parent, another's candy: Archaludon)
            par = fam_of
        if main_id(tid) not in parent_of and par:
            pt = mapped(template(par, None, p.get("form")), par)
            up, seen = main_id(pt) if pt else None, set()
            while up and up not in seen:  # (never under its own evolution: Azurill's candy is Marill's)
                seen.add(up)
                up = parent_of.get(up)
            if pt and main_id(pt) and main_id(tid) not in seen:
                parent_of[main_id(tid)] = main_id(pt)
    sh = lambda x: f"{x}_shadow" if f"{x}_shadow" in ids else None

    def candy_name(p):
        """the Candy's name on the detail page ('MARILL' for Azurill): its family's first Pokémon, in English"""
        fam = (p.get("familyId") or "").removeprefix("FAMILY_")
        dex = dex_of.get(fam) or dex_of.get(p["pokemonId"])
        return text.get(f"pokemon_name_{dex:04d}", fam.replace("_", " ").title()).upper() if dex else None

    out = []
    for sid, v in ids.items():
        tid = v["t"]
        p = by_t[tid]
        form = p.get("form") or ""
        s = p["stats"]
        fast, charged, elite = moves(p)
        e = {"dex": int(tid[1:5]), "speciesName": v["name"], "speciesId": sid,
             "baseStats": {"atk": s["baseAttack"], "def": s["baseDefense"], "hp": s["baseStamina"]},
             "types": types(p), "fastMoves": fast, "chargedMoves": charged, "eliteMoves": elite,
             "template": tid, "form": form, "familyId": p.get("familyId"), "candy": candy_name(p)}
        tags = []
        if p.get("pokemonClass") in CLASS_TAG:
            tags.append(CLASS_TAG[p["pokemonClass"]])
        tags += [tag for r, tag in REGION_TAG.items() if r in form.split("_")[1:]]
        base = sid.removesuffix("_shadow")
        if base in rules.REGIONAL:
            tags.append("regional")
        if v.get("dup"):
            tags.append("duplicate")
        if not p.get("isTradable", True):
            tags.append("untradeable")
        main = main_id(tid)
        if v.get("mega"):
            o = next(o for o in p["tempEvoOverrides"] if o.get("tempEvoId") == v["mega"])
            e["baseStats"] = {"atk": o["stats"]["baseAttack"], "def": o["stats"]["baseDefense"],
                              "hp": o["stats"]["baseStamina"]}
            e["types"] = types({"type": o.get("typeOverride1"), "type2": o.get("typeOverride2")})
            e["size"] = {"h": o.get("averageHeightM"), "w": o.get("averageWeightKg")}
            tags.append("mega")
            fam = {"parent": parent_of.get(main)}  # (as PvPoke: a mega's parent is its base form's parent)
        else:
            e["size"] = {"h": p.get("pokedexHeightM"), "w": p.get("pokedexWeightKg"),
                         "hsd": p.get("heightStdDev"), "wsd": p.get("weightStdDev")}
            if p.get("shadow"):
                tags.append("shadow" if v.get("shadow") else "shadoweligible")
            # (another PvPoke id of the same template, like lanturnw or a costume Pikachu, has the main one's parent.
            # It evolves into nothing: a costume one can't evolve)
            fam = {"parent": parent_of.get(main), "evolutions": kids_of.get(tid) if sid == main else None}
            if v.get("shadow"):  # (a shadow's family is shadows. No shadow of the parent: the parent, as PvPoke)
                fam = {"parent": fam["parent"] and (sh(fam["parent"]) or fam["parent"]),
                       "evolutions": [k for k in map(sh, fam["evolutions"] or []) if k]}
        fam = {k: x for k, x in fam.items() if x}
        if fam:  # (as PvPoke: no family when nothing links)
            e["family"] = {"id": e["familyId"], **fam}
        e["tags"] = tags
        e["released"] = base not in rules.UNRELEASED
        out.append(e)
    moves_out = []
    for t in gm:
        c = t["data"].get("combatMove")
        n = t["templateId"][8:12]
        if c and t["templateId"].startswith("COMBAT_V") and n.isdigit():  # (not COMBAT_VM_: a mega's own move)
            mid = move_id(t["templateId"].split("_MOVE_", 1)[1], numbers)
            moves_out.append({"moveId": mid, "name": text.get(f"move_name_{n}", mid.replace("_", " ").title()),
                              "type": c.get("type", "").replace("POKEMON_TYPE_", "").lower()})
    return {"pokemon": out, "moves": moves_out, "cpms": cpms(gm)}


if __name__ == "__main__":
    if sys.argv[1:] == ["update"]:
        update()
    elif sys.argv[1:] == ["build"]:
        if os.path.exists(built()):
            os.remove(built())
        data = load()
        print(f"{len(data['pokemon'])} species, {len(data['moves'])} moves -> {built()}")
    else:
        sys.exit(__doc__)
