#!/usr/bin/env python3
"""Unattended /pvpc: works through the PvpC-tagged list in iPhone Mirroring with no Claude.

  caffeinate -dimsu python3 run.py [--limit N] [--dry-run]       rename every PvpC Pokémon. A renamed one is
                                                                 a keeper: star on, PvpC off. At the end of the
                                                                 list it also runs `fallen` on this run. One that
                                                                 isn't a keeper gets its final tag right there
                                                                 (../shared/door.py), or stays as it is and goes on
                                                                 ../shared/runs/not-sure.json
  caffeinate -dimsu python3 run.py fallen <run dir>              which older Pvp Pokémon the new names pushed out,
                                                                 and which to trim (reads only) -> <run dir>/fallen.txt
  caffeinate -dimsu python3 run.py act-fallen <run dir> [--limit N]  appraise the beaten ones; in that same open,
                                                                 rename a trim to the leagues it's still best in or
                                                                 tag a fallen one GuaranteedLucky / Old / door (name
                                                                 cleared) once that can't change, until nothing changes
  caffeinate -dimsu python3 run.py keepers [--limit N]           star the Pvp-named ones still in the PvpC list
                                                                 (from runs before keepers were starred), PvpC off
  POGO_PHONE=android caffeinate -dimsu python3 run.py ...   (Android phone over USB, see ../shared/android.py)

Start with Pokémon GO on the inventory, filtered to the PvpC tag. Anything the script isn't sure
about is skipped and written to runs/<time>/log.txt with a capture. Anything unexpected stops the run.
"""
import json, os, re, sys, time
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "shared"))
import ui, pvp, base, search, fallen, session, door
from base import GYM, Lost, Skip, Stop, appraisal_species, appraise, back_to_list, candy, detail_name, \
    do_rename, exact_ivs, front, go, high_iv, is_shadow, is_tag, keep_capture, load, log, new_run_dir, \
    open_appraisal, open_tile, opened_right, recover, same_name, save, scroll_for_new, set_star, set_tags, slots_of, \
    start, steady_detail, tap, think, to_top, type_line, wait_for

MAX_SKIPS_IN_A_ROW = 5
DOOR = None  # door.Door for this run
END_AFTER_STALE = 3  # scrolls in a row that show no new tiles

NAME_OK = re.compile(r"Pvp ?[LGU][A-Za-z0-9 +]*")


def decide(species, cp, hp, ivs, raws):
    out = ui.check_rows(species, cp, hp, ivs)
    verdict = next((l for l in out.splitlines() if l.startswith("VERDICT:")), "")
    m = re.match(r"VERDICT: (.+?) \((.*)\)$", verdict)
    if not m:
        raise Skip(f"no verdict: {out[-200:]}")
    name, why = m.groups()
    if name in ("NEED BARS", "NO MATCH"):
        raise Skip(f"{verdict} | bars={ivs} raw={raws}")
    if "confirm with user" in out:
        raise Skip(f"branching family, letter needs a human: {verdict}")
    if why.startswith("bar reading") and any(abs(r - round(r)) > 0.3 for r in raws):
        raise Skip(f"bar reading picks it but raw={raws} is borderline: {verdict}")
    if not (why.startswith("every candidate agrees") or why.startswith("bar reading")):
        raise Skip(f"odd verdict: {verdict}")
    if name != "NOPE" and not (NAME_OK.fullmatch(name) and len(name) <= 12):
        raise Skip(f"odd name {name!r}")
    return name


def decide_forms(sp, cp, hp, ivs, raws):
    """several forms left (Pumpkaboo sizes have different stats): keep the ones CP and HP fit.
    Go ahead only if they all give the same name."""
    if len(sp) == 1:
        return decide(sp[0], cp, hp, ivs, raws)
    names, why = {}, []
    for s in sp:
        try:
            names[s] = decide(s, cp, hp, ivs, raws)
        except Skip as e:
            if "NO MATCH" not in str(e):
                why.append(f"{s}: {e}")
    if len(set(names.values())) == 1 and not why:
        return next(iter(names.values()))
    raise Skip(f"species unclear: {names or sp} {'; '.join(why)}")


# ---------- one Pokémon ----------

def new_slots(sp, cp, hp, ivs, raws, name):
    """[[league, form, rank]] for every top-100 slot, so the fallen-out step knows the ones its name has no room for.
    None if the exact IVs or the form are unsure (then its name is all the fallen-out step goes on)"""
    sp = [s for s in sp if s in pvp.PLAIN]
    if name == "NOPE" or not sp:
        return None
    try:
        slots, _ = slots_of(sp, cp, hp, exact_ivs(sp, cp, hp, ivs, raws))
        first = pvp.root(sp[0])
        if pvp.letters(first) is None or pvp.slots_name(first, slots) != name:
            return None
    except Exception as e:  # extra data: never let it stop a rename
        log(f"  no slots saved for {name!r}: {type(e).__name__}: {e}")
        return None
    return [[a, f, r] for (a, f), r in slots.items()]


def keep():
    """a PvP keeper, done: star on, PvpC off (like /ivc's Keep). PvpC is only the to-do pile"""
    set_star(True)
    set_tags(off=["PvpC"])


def finish_keepers(limit):
    """the PvpC list's Pvp-named ones (kept by runs from before keep()): star on, PvpC off. -> how many"""
    done = Counter()

    def visit(i, n, c):
        if not (n.lower().startswith("pvp") or re.match(r"P\S{0,2}p(?=[ LGU+]|$)", n)):
            return False  # still to do: /pvpc's main walk names it
        open_tile(i)
        info, _, _ = steady_detail()
        # OCR can run a row's names together ('Pvp Gm38 Um9 •Pvp Gn50U26+ •...'): one of them, same CP, is fine
        if not any(opened_right(info, part.strip(), c) for part in n.split("•")):
            raise Skip(f"opened {info['name']!r} but tile said {n!r}")
        if not re.match(r"P\S?p ?[LGU]", info["name"] or ""):
            raise Skip(f"not a Pvp name on detail: {info['name']!r}")
        if not any(is_tag(t, "PvpC") for t in info["tags"]):
            raise Skip(f"no PvpC tag on detail: {info['tags']}")
        keep()
        log(f"DONE kept {info['name']!r} CP{c}: star on, PvpC off")
        done["kept"] += 1
        go("close", "list")
        return True

    to_top()
    search.walk_list(visit, stop=lambda n: done["kept"] >= limit)  # (walk_list's limit counts passed ones too)
    return done["kept"]


def process(i, tile_name, tile_cp):
    open_tile(i)
    info, texts, _ = steady_detail()
    cp = info["cp"] or tile_cp
    if not opened_right(info, tile_name, tile_cp):
        raise Skip(f"opened {info['name']!r} but tile said {tile_name!r}")
    if not any(is_tag(t, "PvpC") for t in info["tags"]):
        raise Skip(f"no PvpC tag on detail: {info['tags']}")
    sp = ui.species_for(info["name"], info["texts"])
    shadow = is_shadow(texts)
    open_appraisal()
    if not sp:  # a name the user gave it ('L35'): the appraisal names the species
        sp = appraisal_species(info["texts"])
    ivs, raws = appraise()
    name = decide_forms(sp, cp, info["hp"], ivs, raws)
    slots = new_slots(sp, cp, info["hp"], ivs, raws, name)
    think()
    go("dialog", "detail")
    if name == "NOPE" and high_iv(ivs, raws)[0]:  # bad for PvP but 98%+: /ivc names it instead
        set_tags(on=["IVC"], off=["PvpC"])
        name = "->IVC"
    elif name == "NOPE":
        name = DOOR.judge(info, texts, sp, ivs, (tile_name, tile_cp), size=base.extras(texts)[2], raws=raws)
        name = door.UNSURE if name == door.UNSURE else "NOPE"
    else:
        do_rename(name)
        # for the fallen-out step at the end
        save("renamed.json", load("renamed.json", []) + [{"name": name, "cp": cp, "species": sp, "shadow": shadow,
                                                           "slots": slots}])
        keep()
    log(f"DONE {tile_name} CP{cp} {'/'.join(map(str, ivs))}{' shadow' if shadow else ''} -> {name}")
    go("close", "list")
    return name


# ---------- the list ----------

def pick(ts, skipped):
    """first tile not already named Pvp..., passing over ones skipped earlier this run"""
    seen = Counter()
    for i, (n, c, _, _) in enumerate(ts, 1):
        # OCR misreads or drops the v in small tile text (Pyp G13, Pp+): Piplup and Pupitar still get picked
        if n.lower().startswith("pvp") or re.match(r"P\S{0,2}p(?=[ LGU+]|$)", n):
            continue
        seen[(n, c)] += 1
        if seen[(n, c)] > skipped[(n, c)]:
            return i, n, c
    return None


# ---------- fallen out and trims ----------
# New names can push older Pvp Pokémon out of the top. Per league and form only the best one owned keeps its place
# (ties keep). One that's still best somewhere gets renamed to show just those leagues: a trim. One that's best
# nowhere has fallen out, and fallen.py tags it GuaranteedLucky / Old / Nope (shared with /ivc).
# A trim can make room for a league the old name had to leave out, and that league can beat someone else. So
# act-fallen goes round until nothing changes. What a Pokémon really has comes from appraising it (truths.json);
# until then, from what its name shows. The pool: every Pvp name in the line, read off in-game searches by dex number.

MAX_ROUNDS = 8
LAST_BARS = None  # (bars, raws, info, texts) of the appraisal appraise_slots just did: tag_here needn't do it again


def pools_of(renamed):
    """{key: [first stage, shadow, [searches]]} for every line a new name landed in"""
    out = {}
    for r in renamed:
        for first in dict.fromkeys(pvp.root(s) for s in r["species"] if s in pvp.PLAIN):
            if pvp.letters(first) is None:
                log(f"  {r['name']!r}: the {pvp.display(first)} line branches, its names can't be read back: skipped")
                continue
            key = first + ("+shadow" if r["shadow"] else "")
            out[key] = [first, r["shadow"], pvp.line_searches(pvp.tree(first), "shadow" if r["shadow"] else "plain")]
    return out


def to_slots(lst):
    return {(t, f): r for t, f, r in lst}


def load_truths():
    """{pool key: [{name, cp, slots}]}: what appraised Pokémon really have. Starts with this run's new names."""
    t = load("truths.json", {})
    if not t:
        for r in load("renamed.json", []):
            sp = [s for s in r["species"] if s in pvp.PLAIN]
            if r.get("slots") and sp:
                key = pvp.root(sp[0]) + ("+shadow" if r["shadow"] else "")
                t.setdefault(key, []).append({"name": r["name"], "cp": r["cp"], "slots": r["slots"]})
    return t


def add_truth(pool, n, c, slots):
    t = load_truths()
    lst = [x for x in t.get(pool, []) if not (x["cp"] == c and same_name(x["name"], n))]
    t[pool] = lst + [{"name": n, "cp": c, "slots": [[a, f, r] for (a, f), r in slots.items()]}]
    save("truths.json", t)


def members(results, qs, first, truths):
    """[(name, cp, search, slots, known)] for every clean Pvp name the pool's searches showed. Appraised ones come
    with their real slots. Appraised ones no search showed (a misread tile) still count, with no search."""
    left, out = list(truths), []
    for q in qs:
        for n, c in results.get(q, []):
            if not c:
                continue
            t = next((t for t in left if t["cp"] == c and same_name(n, t["name"])), None)
            if t:
                left.remove(t)
                out.append((n, c, q, to_slots(t["slots"]), True))
            else:
                sl = pvp.name_slots(n, first)
                if sl:
                    out.append((n, c, q, sl, False))
    return out + [(t["name"], t["cp"], None, to_slots(t["slots"]), True) for t in left]


def plan(pools, results, wants, truths, only=None):
    """what every member of every pool needs: [{name, cp, pool, q, act, new, why, all, ...}], keeps left out.
    act: check (appraise it), rename, fallen. all: a check whose name shows nothing still best (likely fallen)"""
    out = []
    for key, (first, shadow, qs) in pools.items():
        if only and key != only:
            continue
        over = [q for q in qs if wants.get(q) is not None and len(results.get(q, [])) > wants[q]]
        if over:  # extra tiles could be misread copies that look better than they are
            log(f"  {key}: read more tiles than the game counts in {over}: no fallen check for this line")
            continue
        ms = members(results, qs, first, truths.get(key, []))
        twins = lambda i, j: ms[i][1] == ms[j][1] and search.looks_same(ms[i][0], ms[j][0])
        acts = pvp.plan_pool([(n, sl, k) for n, _, _, sl, k in ms], first, same_name, twins)
        for (n, c, q, sl, k), a in zip(ms, acts):
            if a[0] != "keep":
                out.append({"name": n, "cp": c, "pool": key, "q": q, "shadow": shadow, "act": a[0],
                            "new": a[1] if a[0] == "rename" else None, "why": [] if a[0] == "rename" else a[1],
                            "all": a[0] == "fallen" or (a[0] == "check" and a[2]),
                            "dex": sorted({pvp.PLAIN[s]["dex"] for s in pvp.tree(first)}),
                            "what": f"{'shadow ' if shadow else ''}{pvp.display(first)} line"})
    return out


def state():
    pools = load("fallen-pools.json")
    results = {q: [tuple(x) for x in v] for q, v in load("pools.json", {}).items()}
    return pools, results, load("counts.json", {}), load_truths()


def plan_lines(todo):
    """the trims, for fallen.txt"""
    trims = [t for t in todo if not t["all"]]
    if not trims:
        return []
    return ["", f"TRIMS: {len(trims)} still best in some leagues, beaten in others. act-fallen appraises each one and "
            "renames it to just the leagues it's still best in. The final name comes after the appraisal: a league "
            "the old name had no room for can show up, and push out someone else (act-fallen goes round until nothing "
            "changes)."] + \
        [f"  {t['name']!r:16} CP{t['cp']:<5} {t['what']}: " + (f"-> {t['new']!r}" if t["new"] else "; ".join(t["why"]))
         for t in trims]


CARRY_HOURS = 12  # one sitting of stops and restarts. Older stopped runs are left to `run.py fallen <run dir>`
RUN_NAME = re.compile(r"\d{8}-\d{6}")


def signed_in(path):
    """the account a run's log says it ran on, or None"""
    try:
        with open(os.path.join(path, "log.txt")) as f:
            return next((m[1] for m in re.finditer(r"signed in: (\S+)", f.read())), None)
    except OSError:
        return None


def carry_over():
    """new names from earlier runs that stopped before their fallen-out step, added to this run's renamed.json.
    Looks back from this run to the last one with a fallen.json, at most CARRY_HOURS. Only pvpc's main run calls it."""
    runs, me = os.path.split(base.RUN_DIR)
    if not RUN_NAME.fullmatch(me):
        return []
    start = time.mktime(time.strptime(me, "%Y%m%d-%H%M%S"))
    found = []
    for d in sorted((d for d in os.listdir(runs) if RUN_NAME.fullmatch(d) and d < me), reverse=True):
        path = os.path.join(runs, d)
        if os.path.exists(os.path.join(path, "fallen.json")) or \
                start - time.mktime(time.strptime(d, "%Y%m%d-%H%M%S")) > CARRY_HOURS * 3600 or \
                signed_in(path) not in (None, signed_in(base.RUN_DIR)):  # the other account's names
            break
        if os.path.exists(os.path.join(path, "renamed.json")):
            with open(os.path.join(path, "renamed.json")) as f:
                found.append((d, json.load(f)))
    renamed = load("renamed.json", [])
    key = lambda r: (r["name"], r["cp"], tuple(r["species"]), r["shadow"])
    have, carried, added = {key(r) for r in renamed}, [], []
    for d, rs in reversed(found):  # oldest first
        new = [r for r in rs if key(r) not in have]
        have.update(map(key, new))
        added += new
        carried.append([d, len(new)])
        log(f"carried over from {d} (stopped before its fallen-out step): {len(new)} new names of {len(rs)}")
    if added:
        save("renamed.json", added + renamed)
        save("carried.json", load("carried.json", []) + carried)
    return added


def fallen_step():
    """reads only: pool searches -> pools.json + counts.json, the fallen-out ones -> fallen.json, the plan (fallen
    and trims) -> fallen.txt, their groups -> fallen-groups.json. Stops and starts again where it left off."""
    renamed = load("renamed.json", [])
    pools = pools_of(renamed)
    save("fallen-pools.json", pools)
    results, wants = load("pools.json", {}), load("counts.json", {})
    qs = list(dict.fromkeys(q for _, _, qq in pools.values() for q in qq))
    log(f"fallen out: {len(renamed)} new names, {len(pools)} lines, {len(qs)} searches ({sum(q in results for q in qs)} done)")
    if qs:
        front()
        search.to_search_list()
    for q in qs:
        if q in results:
            continue
        got, want = search.run_search(q)
        results[q], wants[q] = got, want
        save("pools.json", results)
        save("counts.json", wants)
        log(f"  {q}: {len(got)} tiles (game says {want})")
    todo = plan(*state())
    found = [t for t in todo if t["all"]]
    save("fallen.json", found)
    grouped = fallen.groups(iv_only=False) if found else {}
    if not found:
        save("fallen-groups.json", grouped)
    lines = fallen.summary(found, grouped) + plan_lines(todo)
    with open(os.path.join(base.RUN_DIR, "fallen.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")
    log(f"{len(found)} fallen out, {len(todo) - len(found)} to trim, see {os.path.join(base.RUN_DIR, 'fallen.txt')}")
    return found


def species_here(pool, texts=None):
    """the open detail screen's species ids, from its candy and types, within the pool's line"""
    first = load("fallen-pools.json")[pool][0]
    if texts is None:
        texts = steady_detail()[1]
    got = candy(texts)  # a line with a baby takes the next one's candy (Azurill: MARILL CANDY)
    if ui.norm(got or "") not in {ui.norm(pvp.base_name(s)) for s in pvp.tree(first)}:
        raise Skip(f"candy reads {got!r}, not the {pvp.display(first)} line's")
    seen = type_line(texts)
    sp = [s for s in pvp.tree(first) if {t.upper() for t in pvp.PLAIN[s]["types"] if t != "none"} == seen]
    if not sp:
        raise Skip(f"no form in the {pvp.display(first)} line has types {sorted(seen)}")
    return sp


def appraise_slots(pool, n, c, known=None):
    """on its detail screen: species, shadow or not, then every top-100 slot it really has (appraised, unless
    known). -> (slots or None if it's the other kind, what to log). Leaves the detail screen open."""
    first, shadow, _ = load("fallen-pools.json")[pool]
    info, texts, _ = steady_detail()
    if not opened_right(info, n, c):
        raise Skip(f"opened {info['name']!r} but tile said {n!r}")
    if is_shadow(texts) != shadow:
        return None, f"{'shadow' if is_shadow(texts) else 'not shadow'}, the pool was the other kind"
    global LAST_BARS
    LAST_BARS = None
    if known:
        return known, "appraised earlier"
    sp = species_here(pool, texts)
    cp = info["cp"] or c
    open_appraisal()
    bars, raws = appraise()
    go("dialog", "detail")
    LAST_BARS = bars, raws, info, texts  # (the detail screen read before the appraisal: it fades out slowly)
    ivs = exact_ivs(sp, cp, info["hp"], bars, raws)
    slots, s = slots_of(sp, cp, info["hp"], ivs)
    add_truth(pool, n, c, slots)
    return slots, f"{pvp.display(s)} {'/'.join(map(str, ivs))}"


def renamed_to(pool, old, c, new):
    """the rename is done: the pool and the truths know it by its new name now"""
    results = load("pools.json", {})
    for q in load("fallen-pools.json")[pool][2]:
        i = next((i for i, (n, cc) in enumerate(results.get(q, [])) if cc == c and same_name(n, old)), None)
        if i is not None:
            results[q][i] = [new, c]
            break
    save("pools.json", results)
    t = load_truths()
    for x in t.get(pool, []):
        if x["cp"] == c and same_name(x["name"], old):
            x["name"] = new
    save("truths.json", t)


def settle_one(pool, n, c):
    """with all that's known now, what this one needs: (act, new name, does another one in the line still wait for
    its appraisal?)"""
    todo, me = plan(*state(), only=pool), None
    for t in todo:
        if t["cp"] == c and same_name(t["name"], n):
            me = t
    waiting = any(t["act"] == "check" for t in todo if t is not me)
    return (me["act"], me["new"], waiting) if me else ("keep", None, waiting)


def tagged():
    """{(pool, name, cp)} that act-fallen already handled in the open that appraised them (tag_here)"""
    return {tuple(x) for x in load("tagged.json", [])}


def tag_here(pool, n, c, gates):
    """on its detail screen, just appraised and beaten everywhere: tag it now, as fallen.act would later, if
    fallen-groups.json has its group (and, for the door, gates has a Door for its search). -> (done?, what to log)"""
    grouped = load("fallen-groups.json", {})
    g, q = next(((g, q) for g, qs in grouped.items() for q, lst in qs.items()
                 if any(cc == c and same_name(nn, n) for nn, cc in lst)), (None, None))
    if g is None or g == "Nope" and q not in gates:
        return False, "beaten everywhere, tagged later"
    mark = lambda: save("tagged.json", load("tagged.json", []) + [[pool, n, c]])
    if g != "Nope":
        set_tags(on=[g], off=["PvpC"])
        base.clear_name()
        mark()
        return True, f"beaten everywhere: tagged {g}, name cleared"
    gate = gates[q]
    if gate.listed()[door.key(n, c)]:
        mark()
        return False, "beaten everywhere, on the door's not-sure list: left as it is"
    keep, ivs, raws, iv = high_iv(*(LAST_BARS[:2] if LAST_BARS else (None, None)))
    if keep:
        mark()
        return False, f"beaten everywhere, but {iv}: 98%+ never goes, left as it is"
    info, texts = LAST_BARS[2:] if LAST_BARS else steady_detail()[:2]
    got = gate.judge(info, texts, species_here(pool, texts), ivs, (n, c), size=base.extras(texts)[2], raws=raws,
                     clear=True, unstar=True)
    mark()
    return got == "tag", f"beaten everywhere: door {got}"


def trim_here(pool, n, c, known, rename, gates):
    """on its detail screen: appraise it if need be, then rename or tag it if that can't change any more (rename: the
    rest are appraised, so it may rename anyway). -> (how many renamed or tagged, what to log)"""
    slots, what = appraise_slots(pool, n, c, known)
    if slots is None:
        return 0, what
    act, new, waiting = settle_one(pool, n, c)
    if act == "rename" and waiting and not rename:  # a line still waiting for an appraisal can beat it some more
        return 0, f"{what}: to rename to {new!r} once the rest are appraised"
    if act == "rename":
        if not same_name(detail_name(), new):  # a run cut off after the rename already did it
            do_rename(new)
        renamed_to(pool, n, c, new)
        return 1, f"{what}: renamed {n!r} -> {new!r}"
    if act == "fallen":  # a slot lost to an appraised one stays lost: this can't change
        done, why = tag_here(pool, n, c, gates)
        return int(done), f"{what}: {why}"
    return 0, f"{what}: name stays"


def trim_walk(q, todo, tried, limit, gates):
    """walk one search's list, handle the to-do ones in it. -> how many got renamed"""
    pending, count = list(todo), [0]

    def visit(i, n, c):
        t = next((t for t in pending if t["cp"] == c and
                  (same_name(n, t["name"]) or (t["new"] and same_name(n, t["new"])))), None)
        if not t or count[0] >= limit:
            return False
        pending.remove(t)
        tried.add((t["pool"], t["name"], t["cp"], t["act"], t["new"]))
        open_tile(i)
        name = t["name"]
        if not same_name(n, name):  # a run cut off after this rename already did it
            renamed_to(t["pool"], name, c, n)
            name = n
        known = next((to_slots(x["slots"]) for x in load_truths().get(t["pool"], [])
                      if x["cp"] == c and same_name(x["name"], name)), None)
        done, what = trim_here(t["pool"], name, c, known, t["act"] == "rename", gates)
        count[0] += done
        log(f"{'DONE trim' if done else '  checked'} {n!r} CP{c}: {what}")
        go("close", "list")
        return False

    search.start_search(q)
    search.walk_list(visit, stop=lambda n: not pending or count[0] >= limit)
    for t in pending:
        tried.add((t["pool"], t["name"], t["cp"], t["act"], t["new"]))
        if count[0] < limit:
            log(f"  {t['name']!r} CP{t['cp']}: not found in {q}, left as it is")
    return count[0]


def recheck_fallen(n, c):
    """on its detail screen: still fallen only if each of its real slots has someone better. If it turns out to be
    best somewhere after all, it gets renamed to show that. Leaves the detail screen open."""
    f = next(f for f in load("fallen.json") if (f["name"], f["cp"]) == (n, c))
    known = next((to_slots(x["slots"]) for x in load_truths().get(f["pool"], [])
                  if x["cp"] == c and same_name(x["name"], n)), None)
    slots, what = appraise_slots(f["pool"], n, c, known)
    if slots is None:
        return False, what
    act, new = settle_one(f["pool"], n, c)
    if act == "fallen":
        return True, f"{what}: {'; '.join(f['why'])}"
    if act == "rename":
        do_rename(new)
        renamed_to(f["pool"], n, c, new)
        return False, f"{what}: still best somewhere, renamed {new!r}"
    return False, f"{what}: still best somewhere"


def door_gates(todo):
    """{door group search: Door} for the likely fallen ones still to appraise, so tag_here can send one to the door in
    the same open"""
    gates, account = {}, None
    for q, lst in load("fallen-groups.json", {}).get("Nope", {}).items():
        if any(t["act"] == "check" and any(cc == t["cp"] and same_name(nn, t["name"]) for nn, cc in lst)
               for t in todo):
            gates[q] = door.Door("PvpC", scope=q, account=account)
            account = gates[q].account
    return gates


def act_fallen(limit):
    """appraise the ones something beats. Each one's rename or tag happens in that same open once it can't change,
    round after round until nothing changes. Then tag whatever is beaten everywhere and still left"""
    front()
    search.to_search_list()
    done, tried = 0, set()
    gates = door_gates(plan(*state()))
    for rnd in range(1, MAX_ROUNDS + 1):
        todo = [t for t in plan(*state()) if t["act"] in ("check", "rename") and t["q"]
                and (t["pool"], t["name"], t["cp"], t["act"], t["new"]) not in tried]
        if not todo or done >= limit:
            break
        checks = {t["pool"] for t in todo if t["act"] == "check"}  # a rename in a line still being appraised
        todo = [t for t in todo if t["act"] == "check" or t["pool"] not in checks]  # could be undone: those wait
        log(f"round {rnd}: {len(todo)} to look at")
        for q in dict.fromkeys(t["q"] for t in todo):
            if done < limit:
                done += trim_walk(q, [t for t in todo if t["q"] == q], tried, limit - done, gates)
    else:
        log(f"STILL CHANGING after {MAX_ROUNDS} rounds: stopped going round. Look at the log for names that keep flipping")
    gone = tagged()
    found = [t for t in plan(*state()) if t["act"] == "fallen" and (t["pool"], t["name"], t["cp"]) not in gone]
    save("fallen.json", found)
    log(f"trims done: {done} renamed or tagged. {len(found)} beaten everywhere, still to tag")
    if found and done < limit:
        fallen.groups(iv_only=False)
        pool = lambda n, c: next(f["pool"] for f in load("fallen.json") if (f["name"], f["cp"]) == (n, c))
        done += sum(fallen.act(limit - done, recheck_fallen, "PvpC", lambda n, c: species_here(pool(n, c)),
                               off=("PvpC",)).values())
    return done


def main(limit, dry):
    global DOOR
    front()
    skipped, counts = Counter(), Counter()
    if not dry:
        DOOR = door.Door("PvpC")
        skipped.update(DOOR.listed())  # not sure last time, under the same rules: pass them
        log(f"door: {sum(skipped.values())} on the not-sure list, passed over")
    to_top()
    skips_in_a_row = 0
    scroll_how = "drag"  # Mirroring ignores the scroll wheel here
    seen = set()  # CPs of every tile read so far: a scroll that shows none we haven't seen got nowhere
    stale = 0
    log(f"start, log in {base.RUN_DIR}")
    while counts["done"] + counts["skip"] < limit:
        _, texts, _, bounds = wait_for("list")
        ts = [(ui.tile_name(n), c, x, y) for n, c, x, y in ui.tiles(texts)]  # without the tag icon ('$96 AD')
        seen.update(t[1] for t in ts)
        p = pick(ts, skipped)
        if not p:
            if dry:
                log("DRY nothing to do on this screen, would scroll")
                return counts
            fresh, scroll_how = scroll_for_new(ts, seen, bounds, scroll_how)
            stale = 0 if fresh else stale + 1
            if stale >= END_AFTER_STALE:
                log("no new Pokémon after scrolling: end of list")
                counts["end"] = 1
                break
            continue
        i, n, c = p
        if dry:
            log(f"DRY next is tile {i}: {n} CP{c}")
            tap(f"tile {i}", dry=True)
            return counts
        log(f"tile {i}: {n} CP{c}")
        try:
            result = process(i, n, c)
            counts["door" if result == "NOPE" else result if result == door.UNSURE else "renamed"] += 1
            counts["done"] += 1
            if result == door.UNSURE:  # (one left as it is is still in the list, unnamed)
                skipped[(n, c)] += 1
            skips_in_a_row = 0
            stale = 0
        except (Skip, Lost) as e:
            if isinstance(e, Lost):
                recover(e, f"{n} CP{c}")
            else:
                keep_capture(f"skip-{n}")
                log(f"SKIP {n} CP{c}: {e}")
            skipped[(n, c)] += 1
            counts["skip"] += 1
            skips_in_a_row += str(e) != GYM  # a row of gym defenders is nothing wrong
            if skips_in_a_row >= MAX_SKIPS_IN_A_ROW:
                raise Stop(f"{skips_in_a_row} skips in a row, something's off")
            back_to_list()
    return counts


def script(cmd, limit, dry):
    start()
    if cmd == "fallen":
        return fallen_step()
    if cmd == "act-fallen":
        return log(f"finished: {act_fallen(limit)} renamed or tagged")
    if cmd == "keepers":
        return log(f"finished: {finish_keepers(limit)} keepers starred, PvpC off")
    counts = main(limit, dry)
    at_end = counts.pop("end", 0)
    log(f"finished: {dict(counts)}")
    if at_end:  # and what earlier runs that stopped early renamed
        try:
            carry_over()
        except Exception as e:  # never let it stop this run's own fallen-out step
            log(f"no carry-over from earlier runs: {type(e).__name__}: {e}")
    if at_end and load("renamed.json", []):  # still on the phone: check what the new names pushed out
        try:
            fallen_step()
        except (Stop, Skip) as e:
            keep_capture("fallen")
            log(f"fallen out step STOPPED: {e} (run `run.py fallen {base.RUN_DIR}` to go on)")


if __name__ == "__main__":
    a = sys.argv[1:]
    limit = session.limit(a)
    dry = "--dry-run" in a
    cmd = a[0] if a and a[0] in ("fallen", "act-fallen", "keepers") else None
    if cmd in ("fallen", "act-fallen"):
        if len(a) < 2 or not os.path.isdir(a[1]):
            sys.exit(f"usage: run.py {cmd} <run dir>")
        new_run_dir(None, os.path.abspath(a[1]))
    if cmd == "act-fallen" and not os.path.exists(os.path.join(base.RUN_DIR, "fallen-groups.json")):
        sys.exit("run fallen first, and read fallen.txt")
    session.main(script, cmd, limit, dry)