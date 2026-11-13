#!/usr/bin/env python3
"""Unattended /pvpc: works through the PvpC-tagged list in iPhone Mirroring with no Claude.

  caffeinate -dimsu python3 run.py [--limit N] [--dry-run]       rename every PvpC Pokémon. A renamed one is
                                                                 a keeper: star on, PvpC off. At the end of the
                                                                 list it also runs `fallen` on this run. One that
                                                                 isn't a keeper gets its final tag right there
                                                                 (../shared/door.py), or stays as it is and goes on
                                                                 ../shared/runs/not-sure.json. A Pvp-named one an
                                                                 older run left in PvpC is judged again too
  caffeinate -dimsu python3 run.py fallen <run dir> [--limit N]   which older Pvp Pokémon the new names pushed out,
                                                                 in one pass per line: each line's search typed once,
                                                                 the beaten ones opened from that list and renamed (a
                                                                 trim) or sent to the door for its final tag (name
                                                                 cleared) in the open that appraises them, until the
                                                                 line stops changing. act-fallen: same thing
  caffeinate -dimsu python3 run.py fallen --line <species>       the same pass on one line (plain and shadow) in a new
                                                                 run folder, with no new names: fixes old names a rule
                                                                 change left wrong (a league the form can't play)
  caffeinate -dimsu python3 run.py keepers [--limit N]           star the Pvp-named ones still in the PvpC list
                                                                 (from runs before keepers were starred), PvpC off,
                                                                 without judging them again (the main run does that)
  POGO_PHONE=android caffeinate -dimsu python3 run.py ...   (Android phone over USB, see ../shared/android.py)

Start with Pokémon GO on the inventory, filtered to the PvpC tag. Anything the script isn't sure
about is skipped and written to runs/<time>/log.txt with a capture. Anything unexpected stops the run.

A stop loses nothing: the run that reaches the end takes in earlier runs' new names (at most 12 hours back, carried.json),
so one fallen-out step covers them all. --limit counts renames and tags together; appraisals don't count. Lines that
branch (Eevee aside) are never trimmed or fallen. Only lines a new name landed in get looked at.

By hand, to clear a skip (the same rules, one tool per step):
  python3 ../shared/ui.py read            which screen is up and what's on it; on the appraisal, the VERDICT
  python3 ../shared/ui.py tap <target>    prints x y to click (iPhone): click exactly that spot, never made-up ones
  POGO_PHONE=android python3 ../shared/ui.py press <target>     plans the same safe spot and taps it (Pixel)
  python3 ../shared/ui.py calib <x> <y>   iPhone, once per display resolution: maps screenshot spots to the screen
  python3 ../shared/pvp.py check <species_id> <cp> <hp> <stars|-1> [--near a/d/h]    the ranker
  python3 ../shared/pvp.py update         when a species is missing
  POGO_PHONE=android python3 ../shared/android.py type "<name>"     type into a box on the Pixel
Never tap Transfer, Power Up, Evolve, Mega Evolve or Purify: ui.py refuses them and anything close. Don't work around a
REFUSED. If read says unknown, or shows a popup you didn't expect, stop and look. Don't confirm anything you didn't mean to.
A NOPE by hand: leave it for run.py, whose door gives the final tag.
"""
import functools, json, os, re, sys, time
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "shared"))
import ui, pvp, base, search, fallen, session, door
from base import GYM, Lost, Skip, Stop, appraisal_species, appraise, back_to_list, candy, detail_name, \
    do_rename, exact_ivs, front, go, high_iv, is_shadow, is_tag, keep_capture, load, log, new_run_dir, \
    open_appraisal, open_checked, open_tile, opened_right, recover, same_name, save, set_star, set_tags, slots_of, \
    start, steady_detail, tap, think, to_top, type_line, wait_for

DOOR = None  # door.Door for this run

NAME_OK = re.compile(r"Pvp ?[LGU][A-Za-z0-9 +]*")


def decide(species, cp, hp, ivs, raws):
    out = ui.check_rows(species, cp, hp, ivs, own=species in pvp.OWN_ONLY)
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
        slots, form = slots_of(sp, cp, hp, exact_ivs(sp, cp, hp, ivs, raws))
        first = pvp.root(form)  # the form CP and HP fit, not sp[0]: Pumpkaboo's sizes all come in sp
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
        info, _, _ = open_checked(i, n, c)  # (a row's names run together '... •...': one of them is fine)
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
    info, texts, _ = open_checked(i, tile_name, tile_cp)
    cp = info["cp"] or tile_cp  # (after that check: it can read a covered digit again)
    if not any(is_tag(t, "PvpC") for t in info["tags"]):
        raise Skip(f"no PvpC tag on detail: {info['tags']}")
    sp = ui.species_for(info["name"], info["texts"])
    shadow = is_shadow(texts)
    open_appraisal()
    if not sp:  # a name the user gave it ('L35'): the appraisal names the species
        sp = appraisal_species(info["texts"])
    ivs, raws = appraise()
    # a costume one that can't evolve (its plain form can): ranked as its own species only (the user, 2026-11-02)
    dead = door.dead_end(DOOR.has("costume", door.key(tile_name, tile_cp)), sp, texts)
    if dead is None:
        go("dialog", "detail")  # (the appraisal hides the close button: the skip's close stopped the run, 2026-11-02)
        raise Skip("costume or not / its Evolve button didn't read: can't tell what it can rank as")
    pvp.OWN_ONLY = set(sp) if dead else set()
    try:
        name = decide_forms(sp, cp, info["hp"], ivs, raws)
        slots = new_slots(sp, cp, info["hp"], ivs, raws, name)
    finally:
        pvp.OWN_ONLY = set()
    if dead:
        log(f"  costume, can't evolve: ranked as {'/'.join(sp)} only")
    think()
    go("dialog", "detail")
    if name == "NOPE" and high_iv(ivs, raws)[0]:  # bad for PvP but 98%+: /ivc names it instead
        set_tags(on=["IVC"], off=["PvpC"])
        name = "->IVC"
    elif name == "NOPE":
        name = DOOR.judge(info, texts, sp, ivs, (tile_name, tile_cp), size=base.extras(texts)[2], raws=raws)
        name = door.UNSURE if name == door.UNSURE else "NOPE"
    elif (who := beaten(info, sp, shadow, slots, cp, ivs, raws, tile_name, tile_cp)):
        log(f"  {name} is beaten everywhere: {who}. Not renamed")
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


def line_searches(line, pool):
    """a line's searches for the fallen-out step, Pvp names only (`&pvp`: a nickname starting with it). Only a Pvp
    name holds a slot, so the rest of the line's tiles never need reading (user, 2026-11-02)"""
    return [q + "&pvp" for q in pvp.line_searches(line, pool)]


def line_of(sp, shadow):
    """(pool key, first stage, the line's searches) as pools_of makes them, or None (a branching line, two lines)"""
    firsts = list(dict.fromkeys(pvp.root(s) for s in sp if s in pvp.PLAIN))
    if len(firsts) != 1 or pvp.letters(firsts[0]) is None:
        return None
    first = firsts[0]
    return first + ("+shadow" if shadow else ""), first, line_searches(pvp.tree(first), "shadow" if shadow else "plain")


def holders(key, first, qs, cp, name=None):
    """[(who, slots)] Pvp ones already in this line: this run's new names (appraised), and the names the newest
    earlier run on this account read off the line's searches. A slot only ever passes to a better one (a trim or a
    fallen tag happens because someone beats it), so an older read can miss a holder but never shows a wrong one.
    Same CP as this one: left out (it could be this one). So is one read with no CP (0) and this one's name."""
    out = [(f"{r['name']!r} CP{r['cp']} (this run)", to_slots(r["slots"])) for r in load("renamed.json", [])
           if r.get("slots") and r["cp"] != cp and (line_of(r["species"], r["shadow"]) or [None])[0] == key]
    runs, me = os.path.split(base.RUN_DIR)
    account = DOOR.account if DOOR else None
    for d in sorted((d for d in os.listdir(runs) if RUN_NAME.fullmatch(d) and d != me), reverse=True):
        path = os.path.join(runs, d)
        try:
            reads = json.load(open(os.path.join(path, "pools.json")))
            wants = json.load(open(os.path.join(path, "counts.json")))
        except (OSError, ValueError):
            continue
        if not all(q in reads for q in qs) or not account or signed_in(path) != account:
            continue
        if any(wants.get(q) is not None and len(reads[q]) > wants[q] for q in qs):
            break  # extra tiles could be misread copies that look better than they are: as plan() does
        out += [(f"{n!r} CP{c or '?'} (read {d})", sl) for q in qs for n, c in reads[q]  # CP 0: CP not read
                if c != cp and not (c == 0 and name and same_name(n, name)) and (sl := pvp.name_slots(n, first))]
        break
    return out


def beaten(info, sp, shadow, slots, cp, ivs, raws, tile_name, tile_cp):
    """the new name would be beaten in every slot by a Pvp one already in its line (the fallen-out step would only
    take it off again) -> who beats it, or None: rename. Never for what that step would leave named: 98%+, or
    anything it can't tell. (A costume one goes on to the door, which names and stars one at 93%+. So does a shiny one)"""
    line = slots and line_of(sp, shadow)
    if not line or high_iv(ivs, raws)[0]:
        return None
    mine = to_slots(slots)
    others = holders(*line, cp, tile_name)
    if not others or pvp.kept(mine, others):
        return None
    if door.tile_icons(info).get("shiny") is None:
        return None
    return "; ".join(f"{pvp.slot_text(sl, r, line[1])} by {min((o[sl], w) for w, o in others if sl in o)[1]}"
                     for sl, r in mine.items())


# ---------- the list ----------

# ---------- fallen out and trims ----------
# New names can push older Pvp Pokémon out of the top. Per league and form only the best one owned keeps its place
# (ties keep). One that's still best somewhere gets renamed to show just those leagues: a trim. One that's best
# nowhere has fallen out, and its final tag comes from the door (verdict.py, shared with /ivc).
# A trim can make room for a league the old name had to leave out, and that league can beat someone else. So
# act-fallen goes round until nothing changes. What a Pokémon really has comes from appraising it (truths.json);
# until then, from what its name shows. The pool: every Pvp name in the line, read off in-game searches by dex number.

MAX_ROUNDS = 8
LAST_BARS = None  # (bars, raws, info, texts) of the appraisal appraise_slots just did: fall_here needn't do it again


def pools_of(renamed):
    """{key: [first stage, shadow, [searches]]} for every line a new name landed in"""
    out = {}
    for r in renamed:
        for first in dict.fromkeys(pvp.root(s) for s in r["species"] if s in pvp.PLAIN):
            if pvp.letters(first) is None:
                log(f"  {r['name']!r}: the {pvp.display(first)} line branches, its names can't be read back: skipped")
                continue
            key = first + ("+shadow" if r["shadow"] else "")
            out[key] = [first, r["shadow"], line_searches(pvp.tree(first), "shadow" if r["shadow"] else "plain")]
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
                key = pvp.root(r["slots"][0][1]) + ("+shadow" if r["shadow"] else "")  # the form the slots are for
                t.setdefault(key, []).append({"name": r["name"], "cp": r["cp"], "slots": r["slots"]})
    return t


def add_truth(pool, n, c, slots):
    t = load_truths()
    lst = [x for x in t.get(pool, []) if not (x["cp"] == c and same_name(x["name"], n))]
    t[pool] = lst + [{"name": n, "cp": c, "slots": [[a, f, r] for (a, f), r in slots.items()]}]
    save("truths.json", t)


def members(results, qs, first, truths):
    """[(name, cp, search, slots, known)] for every clean Pvp name the pool's searches showed. Appraised ones come
    with their real slots. Appraised ones no search showed (a misread tile) still count, with no search.
    A tile read with no CP (CP 0: a chip row under the search bar hid the top row's CPs) still holds what its name
    shows, so it beats others, but it can't be found again to open: it comes last, CP 0, and plan() never acts on it.
    One with the name of an appraised one no search showed is that one (Skrelp U2 under the chips, 2026-11-09)."""
    left, out, blind = list(truths), [], []
    for q in qs:
        for n, c in results.get(q, []):
            if not c:
                blind.append((n, q))
                continue
            t = next((t for t in left if t["cp"] == c and same_name(n, t["name"])), None)
            if t:
                left.remove(t)
                out.append((n, c, q, to_slots(t["slots"]), True))
            else:
                sl = pvp.name_slots(n, first)
                if sl:
                    out.append((n, c, q, sl, False))
    out += [(t["name"], t["cp"], None, to_slots(t["slots"]), True) for t in left]
    for n, q in blind:
        sl = pvp.name_slots(n, first)
        if sl and not any(same_name(n, m[0]) for m in out if not m[1] or m[2] is None):
            out.append((n, 0, q, sl, False))
    return out


@functools.cache
def sister_forms(first, shadow):
    """other lines whose searches are this line's (Pumpkaboo's sizes, Giratina's forms): the game can't tell them apart"""
    kind = "shadow" if shadow else "plain"
    qs = line_searches(pvp.tree(first), kind)
    return tuple(r for r in dict.fromkeys(pvp.root(s) for s in pvp.PLAIN) if r != first
                 and pvp.letters(r) is not None and line_searches(pvp.tree(r), kind) == qs)


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
        sis = sister_forms(first, shadow)
        if sis:  # forms one search can't tell apart (Pumpkaboo's sizes): a Pvp name
            elsewhere = [t for r in sis for t in truths.get(r + ("+shadow" if shadow else ""), [])]  # appraised as
            # another form: not this pool's
            ms = [m for m in ms if m[4] or not any(t["cp"] == m[1] and same_name(m[0], t["name"]) for t in elsewhere)]
            acts = pvp.plan_pool([(n, sl, k) for n, _, _, sl, k in ms], first, same_name, twins)
            kn = [i for i, m in enumerate(ms) if m[4]]  # doesn't say the form, so a name alone can't beat anyone.
            for i, a in zip(kn, pvp.plan_pool([(ms[i][0], ms[i][3], True) for i in kn], first, same_name,  # only
                                              lambda x, y: twins(kn[x], kn[y]))):  # appraised ones decide a fall
                acts[i] = a
        for (n, c, q, sl, k), a in zip(ms, acts):
            if a[0] != "keep" and c:  # (CP 0: only there to beat others, see members())
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


CARRY_HOURS = 12  # one sitting of stops and restarts. Older stopped runs are left to `run.py fallen <run dir>`
RUN_NAME = re.compile(r"\d{8}-\d{6}")


signed_in = base.trainer_of  # a run folder -> its account


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


def appraise_slots(pool, n, c, known=None, gate=None):
    """on its detail screen: species, shadow or not, then every top-100 slot it really has (appraised, unless
    known). A costume one that can't evolve: its own species' slots only. gate: the door, for costume or not.
    -> (slots or None if it's the other kind, what to log). Leaves the detail screen open."""
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
    dead = door.dead_end(gate.has("costume", door.key(n, c)) if gate else None, sp, texts)
    if dead is None:
        raise Skip("costume or not / its Evolve button didn't read: can't tell what it ranks as")
    pvp.OWN_ONLY = set(sp) if dead else set()
    try:
        slots, s = slots_of(sp, cp, info["hp"], ivs)
    finally:
        pvp.OWN_ONLY = set()
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
    """{(pool, name, cp)} the walk already tagged (or left on purpose): the plan still has them under their old name"""
    return {tuple(x) for x in load("tagged.json", [])}


def mark(pool, n, c):
    save("tagged.json", load("tagged.json", []) + [[pool, n, c]])


def fall_here(pool, n, c, gate):
    """on its detail screen, appraised, beaten everywhere: its final tag from the door, in this same open
    -> (tagged?, what to log)"""
    info, texts = LAST_BARS[2:] if LAST_BARS else steady_detail()[:2]
    if gate.listed()[door.key(n, c)]:
        mark(pool, n, c)
        return False, "beaten everywhere, on the door's not-sure list: left as it is"
    keep, ivs, raws, iv = high_iv(*(LAST_BARS[:2] if LAST_BARS else (None, None)))
    if keep:
        mark(pool, n, c)
        return False, f"beaten everywhere, but {iv}: 98%+ never goes, left as it is"
    got = gate.judge(info, texts, species_here(pool, texts), ivs, (n, c), size=base.extras(texts)[2], raws=raws,
                     clear=True, unstar=True)
    mark(pool, n, c)  # (a not-sure one is on the door's list now)
    return got == "tag", f"beaten everywhere: door {got}"


def settle_here(pool, n, c, known, rename, gate):
    """on its detail screen: appraise it if need be, then rename or tag it if that can't change any more (rename: the
    rest are appraised, so it may rename anyway). -> (how many renamed or tagged, what to log)"""
    slots, what = appraise_slots(pool, n, c, known, gate)
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
        done, why = fall_here(pool, n, c, gate)
        return int(done), f"{what}: {why}"
    return 0, f"{what}: name stays"


def show(q):
    """the results of q, at the top: typed only if they aren't on screen already (the walk's own last search)"""
    if search.LAST.get("q") == q:
        _, bounds = ui.capture()
        search.to_top(bounds)
    else:
        search.start_search(q)


def walk_line(q, todo, tried, limit, gate, record):
    """walk one search's list, handle the to-do ones in it. -> how many got renamed or tagged"""
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
        done, what = settle_here(t["pool"], name, c, known, t["act"] == "rename", gate)
        count[0] += done
        line = f"{'DONE' if done else '  checked'} {n!r} CP{c}: {what}"
        log(line)
        record.append(f"  {n!r:16} CP{c:<5} {t['what']}: {what}")
        go("close", "list")
        return False

    show(q)
    search.walk_list(visit, stop=lambda n: not pending or count[0] >= limit)
    for t in pending:
        tried.add((t["pool"], t["name"], t["cp"], t["act"], t["new"]))
        if count[0] < limit:
            log(f"  {t['name']!r} CP{t['cp']}: not found in {q}, left as it is")
    return count[0]


def line_pools(species):
    """fallen-pools.json for one line, plain and shadow (`fallen --line`)"""
    if species not in pvp.PLAIN:
        sys.exit(f"no species {species!r} (a PvPoke species id, e.g. amaura)")
    first = pvp.root(species)
    if pvp.letters(first) is None:
        sys.exit(f"the {pvp.display(first)} line branches, its names can't be read back")
    return {first + ("+shadow" if sh else ""): [first, sh, line_searches(pvp.tree(first), "shadow" if sh else "plain")]
            for sh in (False, True)}


def one_walk(limit):
    """fallen out and trims in one pass: each line's search is typed once, its tiles read, and the beaten ones opened
    from that same list. Each one's rename or tag happens in the open that appraises it, round after round on the same
    list until the line stops changing. -> how many renamed or tagged"""
    renamed = load("renamed.json", [])
    pools = load("fallen-pools.json", {}) or pools_of(renamed)
    save("fallen-pools.json", pools)
    results, wants = load("pools.json", {}), load("counts.json", {})
    log(f"fallen out: {len(renamed)} new names, {len(pools)} lines")
    if not pools:
        return 0
    front()
    search.to_search_list()
    dexes = sorted({pvp.PLAIN[s]["dex"] for first, _, _ in pools.values() for s in pvp.tree(first)})
    gate = None  # the door (its costume search), typed only once a line has someone to open (2026-11-02)
    done, tried, record = 0, set(), []
    for key, (first, shadow, qs) in pools.items():
        if done >= limit:
            break
        for q in qs:
            if q not in results:
                path, texts, bounds = search.start_search(q)
                results[q], wants[q] = search.read_results(q, path, texts, bounds)
                save("pools.json", results)
                save("counts.json", wants)
                log(f"  {q}: {len(results[q])} tiles (game says {wants[q]})")
        for rnd in range(1, MAX_ROUNDS + 1):
            gone = tagged()
            todo = [t for t in plan(*state(), only=key) if t["q"]
                    and (t["pool"], t["name"], t["cp"]) not in gone
                    and (t["pool"], t["name"], t["cp"], t["act"], t["new"]) not in tried]
            checks = any(t["act"] == "check" for t in todo)  # a rename in a line still being appraised could be
            todo = [t for t in todo if t["act"] != "rename" or not checks]  # undone: it waits for the next round
            if not todo or done >= limit:
                break
            log(f"{key} round {rnd}: {len(todo)} to look at")
            if gate is None:
                gate = door.Door("PvpC", scope=",".join(map(str, dexes)) + "&pvp",
                                 account=DOOR.account if DOOR else None, rank_gym=True)
            for q in sorted(dict.fromkeys(t["q"] for t in todo), key=lambda q: q != search.LAST.get("q")):
                if done < limit:  # (the search on screen first: no typing)
                    done += walk_line(q, [t for t in todo if t["q"] == q], tried, limit - done, gate, record)
        else:
            log(f"{key}: STILL CHANGING after {MAX_ROUNDS} rounds. Look at the log for names that keep flipping")
    left = [t for t in plan(*state()) if t["act"] == "fallen" and (t["pool"], t["name"], t["cp"]) not in tagged()]
    save("fallen.json", left)
    with open(os.path.join(base.RUN_DIR, "fallen.txt"), "w") as f:
        f.write("\n".join([f"FALLEN OUT AND TRIMS: {done} renamed or tagged"] + record +
                          ([f"", f"STILL BEATEN, NOT TAGGED: {len(left)}"] +
                           [f"  {t['name']!r:16} CP{t['cp']:<5} {t['what']}" for t in left] if left else [])) + "\n")
    log(f"fallen out done: {done} renamed or tagged, {len(left)} beaten and left. See {base.RUN_DIR}/fallen.txt")
    return done


def main(limit, dry):
    global DOOR
    front()
    skipped, counts = Counter(), Counter()
    if not dry:
        DOOR = door.Door("PvpC", rank_gym=True)
        skipped.update(DOOR.listed())  # not sure last time, under the same rules: pass them
        log(f"door: {sum(skipped.values())} on the not-sure list, passed over")
    to_top()
    log(f"start, log in {base.RUN_DIR}")
    if dry:
        ts = ui.tiles(wait_for("list")[1])
        if ts:
            log(f"DRY next is tile 1: {ui.tile_name(ts[0][0])} CP{ts[0][1]}")
            tap("tile 1", dry=True)
        return counts

    def visit(i, n, c):
        """a Pvp-named one still here (an older run named it and left PvpC on) is judged again like the rest: kept
        (star, PvpC off) or the door (user, 2026-11-02)"""
        log(f"tile {i}: {n} CP{c}")
        try:
            result = process(i, n, c)
        except (Skip, Lost):
            counts["skip"] += 1
            raise
        counts["door" if result == "NOPE" else result if result == door.UNSURE else "renamed"] += 1
        counts["done"] += 1
        return result != door.UNSURE  # (one left as it is is still in the list, unnamed)

    # (walk_list's limit counts passed ones too)
    if search.walk_list(visit, stop=lambda n: counts["done"] + counts["skip"] >= limit, passed=skipped):
        counts["end"] = 1
    return counts


def script(cmd, limit, dry):
    start()
    if cmd in ("fallen", "act-fallen"):  # (act-fallen: the old name of the second half)
        return log(f"finished: {one_walk(limit)} renamed or tagged")
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
    if at_end and load("renamed.json", []):  # still on the phone: rename or tag what the new names pushed out
        try:
            one_walk(limit)  # (its own --limit: the end of a run writes too now)
        except (Stop, Skip) as e:
            keep_capture("fallen")
            # exit 1, not 0: pogo.py heals only a step that ends STOPPED or CRASHED
            raise Stop(f"fallen out step: {e} (run `run.py fallen {base.RUN_DIR}` to go on)") from e


if __name__ == "__main__":
    a = sys.argv[1:]
    limit = session.limit(a)
    dry = "--dry-run" in a
    cmd = a[0] if a and a[0] in ("fallen", "act-fallen", "keepers") else None
    if cmd in ("fallen", "act-fallen") and "--line" in a:
        pools = line_pools(a[a.index("--line") + 1])
        new_run_dir(None, base.RUN_DIR)
        save("fallen-pools.json", pools)
    elif cmd in ("fallen", "act-fallen"):
        if len(a) < 2 or not os.path.isdir(a[1]):
            sys.exit(f"usage: run.py {cmd} <run dir> | --line <species>")
        new_run_dir(None, os.path.abspath(a[1]))
    session.main(script, cmd, limit, dry)