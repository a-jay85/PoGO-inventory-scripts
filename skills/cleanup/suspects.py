#!/usr/bin/env python3
"""Suspects: an untraded Nope that may still belong in its species' top IV or PvP spots. tradeable.py tag --nope
checks every one before it tags anything (the user's rule: no tag until it's cleared).

A suspect is in the untraded Nope pile and either
  - still has an /ivc name ('96 HD') or a Pvp name: it was named once, so it may still be a keeper, or
  - 93%+ (an IV sum of 42+) whatever its name. Every stat 11+ and 3* finds those; the appraisal tells, or
  - a gym defender (GYM_DEFENDERS), whatever its name or IVs, traded ones too: it may be top 20 CP or top 20 IV of
    its species (/ivcsort's gym rule). Each run judges them again: their rank moves as the pool changes.
Steps, in the tag run's dir (find does the first four in one walk, opening each suspect once):
  list   walk the pile with no taps: the named ones, and the unnamed 82%+ ones to appraise
  pools  the searches /ivcsort and /pvpc compare with (everything owned in the line, minus Nope) -> pools.json.
         Typed first for the ones read in an earlier run (runs/reads-<trainer>.json), so they're judged on the spot.
  read   open it. IVs: the earlier read (same HP), else its /ivc name when that settles it (by_name: the 4attack,
         4defense, 4hp searches agree with its capitals, the species is pinned, no PvP slot that counts), else
         an appraisal.
  judge  IV: /ivcsort's judge() on its /ivc name (or the name /ivc would give it). PvP: pvp.fallen() on its top-100
         slots against every Pvp name in the line. CyrillJan (no PvP there) counts only giver_slots(): top 20 in
         a league the form is viable in. -> verdicts.json
  apply  still open: KEEP (either side keeps): star on, Nope off. A PvP keeper too, like /pvpc's keepers
         (star, no PvpC). One with neither kind of name gets the one /ivc (or /pvpc) would give it.
         CLEARED: nickname blanked, so the game shows the species name. Nope stays: tag --nope tags it next.
         LEAVE: unsure (a misread search, a branching line, XXL/xxs): nothing changes.
One whose pool searches weren't typed yet is judged after the walk (later.json), then act finds it again.
run() -> the ones still unresolved. tag --nope tags nothing while there are any.
runs/checked-<trainer>.json remembers the species-named ones already appraised (name, CP), so a rerun doesn't
appraise them again.

  POGO_PHONE=android caffeinate -dimsu python3 suspects.py [--dry-run]   --dry-run reads and judges, changes nothing
"""
import importlib.util, itertools, json, os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
sys.path.append(os.path.join(HERE, "..", "ivcsort"))
sys.path.append(os.path.join(HERE, "..", "ivc"))
import ui
import run as base
from run import Stop, Skip, log, go
import search, session, home
import pvp
import ivc
import sort

spec = importlib.util.spec_from_file_location("ivcsort_run", os.path.join(HERE, "..", "ivcsort", "run.py"))
isr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(isr)
import cleantrades as ct

HIGH = 42  # IV sum of 93%
HIGH_TERMS = "&3*&3-4attack&3-4defense&3-4hp"  # every stat 11+ and 82%+: holds for every 93%+ one
GYM_DEX = ",".join(str(d) for d in sorted({sort.SPECIES[s]["dex"] for s in ivc.GYM_DEFENDERS}))
GYM_TERMS = "&" + GYM_DEX


def load(name, default=None):
    return base.load(name, default) if os.path.exists(os.path.join(base.RUN_DIR, name)) else default


def pvp_name(n):
    """a Pvp name, the v misread or not (Pyp G13, PvP U9)"""
    return bool(re.match(r"P\S{0,2}p(?=[ LGU+]|$)", n or "", re.I))


def named(n):
    return isr.ivc_name(n) or pvp_name(n)


GIVER_PVP_TOP = 20  # CyrillJan doesn't play PvP: it keeps a Nope for PvP only if it's this good (the user, 2026-10-27)


def checked_file(who):
    return os.path.join(HERE, "runs", f"checked-{who}.json")


def load_checked(who):
    return json.load(open(checked_file(who))) if os.path.exists(checked_file(who)) else []


def add_checked(who, row):
    """read the file again first: a cleared one is added mid-walk too, and an older copy would drop it"""
    checked = load_checked(who)
    checked.append(row)
    json.dump(checked, open(checked_file(who), "w"))


def is_gym(m):
    return any(s in ivc.GYM_DEFENDERS for s in m["species_options"] or [])


def pool_kind(m):
    return "shadow" if m["shadow"] else "plain"


# ---------- find ----------

def read_nope(n, c):
    """on its detail screen: read_member's read, with every form it could be. Stops at one with no Nope tag"""
    m = isr.read_member(n, c, ivc=False)
    if not any(base.is_tag(t, "Nope") for t in m["tags"]):
        raise Skip(f"no Nope tag on detail: {m['tags']}")
    _, texts, _, _ = base.wait_for("detail")
    m["species_options"] = m["species_options"] or base.species_from_candy(texts, m["cp"], m["hp"])
    return m


def read_one(n, c):
    """on its detail screen: species, flags and exact IVs. Comes back to the detail screen"""
    return appraise_one(read_nope(n, c))


def appraise_one(m):
    """read_nope's read -> exact IVs and the one species they fit (an appraisal)"""
    opts = m["species_options"]
    base.open_appraisal()
    try:
        bars, raws = base.appraise()
    finally:
        go("dialog", "detail")
    ivs = base.exact_ivs(opts, m["cp"], m["hp"], bars, raws)
    fit = [s for s in opts if any(pvp.cp(pvp.SPECIES[s]["baseStats"], ivs, lv) == m["cp"] and
                                  pvp.hp(pvp.SPECIES[s]["baseStats"], ivs, lv) == m["hp"] for lv in pvp.LEVELS)]
    if len({(sort.SPECIES[s]["dex"], sort.region(s)) for s in fit if s in sort.SPECIES}) != 1:
        raise Skip(f"species unclear: {opts} -> {fit}")
    m["species_options"], m["species"] = fit, sort.pick_species(fit)
    m["ivs"] = list(ivs)
    m["moves"] = []
    if not isr.ivc_name(m["name"]) and any(ivc.elite_moves(s) for s in fit):  # /ivc would put an Elite TM in the name
        m["moves"] = isr.ivcrun.elite_on(fit, isr.ivcrun.read_moves())
    return m


def reads_file(who):
    return os.path.join(HERE, "runs", f"reads-{who}.json")


def load_reads(who):
    """{'tile|cp': read} the suspects read in earlier runs (species, exact IVs), so a rerun can type their pool
    searches first and needn't appraise them again. The HP must match when it's opened."""
    return json.load(open(reads_file(who))) if os.path.exists(reads_file(who)) else {}


def save_read(reads, who, m):
    reads[f"{m['tile']}|{m['cp']}"] = {k: v for k, v in m.items() if k not in ("tags", "how")}
    json.dump(reads, open(reads_file(who), "w"))


def same_tile(n, c, tiles):
    """the tile in tiles that's this one: same CP, the name read alike ('89 al' is '89 a')"""
    if (n, c) in tiles:  # (exact first: '93 A' and '93 AD' at one CP read alike)
        return n, c
    return next(((tn, tc) for tn, tc in tiles if tc == c and isr.same_name(tn, n)), None)


def list_tiles(q, keep=lambda n, c: True):
    """[(name, cp)] on a search's list, no taps on the tiles"""
    out = []

    def visit(i, n, c):
        if keep(n, c):
            out.append((n, c))
        return False

    log(f"--- {q}")
    if ct.long_search(q):
        search.walk_list(visit, odd=lambda n: not named(n))
    return out


def tops(pile):
    """{stat: [(name, cp)]} the pile's ones with that stat at 15. An /ivc name's capitals say which are 15: these
    3 searches check every name at once, so most named ones need no appraisal"""
    return {k: list_tiles(f"{pile}&4{k}") for k in ("attack", "defense", "hp")}


def by_name(m, top, giver):
    """for a named one: (IVs or None, the forms it fits) if its name settles everything an appraisal would, else
    None. The IVs it could have: the name's % with the 15s the searches found (older names like '93 all' count too).
    The name's capitals must be among those 15s. They must pin the species, and none may have a PvP slot that
    counts (CyrillJan: giver_slots). The IV side judges by the name alone."""
    got = re.match(r"(\d{1,3})(?:/\d{1,3})?\s*(\S*)", m["name"] or "")
    if not isr.ivc_name(m["name"]) or top is None or not got:
        return None
    on = [bool(same_tile(m["tile"], m["cp"], top[k])) for k in ("attack", "defense", "hp")]
    if on != [(m["tile"], m["cp"]) in top[k] for k in ("attack", "defense", "hp")] and \
            any((m["tile"], m["cp"]) in top[k] for k in top):
        return None  # (found by a close name in one search, the exact name in another: can't tell)
    if any(not on["ADH".index(ch)] for ch in got[2] if ch in "ADH"):
        return None  # (the name says 15 where the search says not: a stale name, or a misread)
    sp = m["species_options"]
    combos = [iv for iv in itertools.product(range(16), repeat=3)
              if round(sum(iv) * 100 / 45) == int(got[1]) and [x == 15 for x in iv] == on]
    if not combos:
        return None
    fit = [s for s in sp if s in pvp.SPECIES and any(
        pvp.cp(pvp.SPECIES[s]["baseStats"], iv, lv) == m["cp"] and pvp.hp(pvp.SPECIES[s]["baseStats"], iv, lv) == m["hp"]
        for iv in combos for lv in pvp.LEVELS)]
    if len({(sort.SPECIES[s]["dex"], sort.region(s)) for s in fit if s in sort.SPECIES}) != 1:
        return None
    sp = [s for s in fit if s in pvp.PLAIN]
    for iv in combos:
        try:
            sl = base.slots_of(sp, m["cp"], m["hp"], iv)[0] if sp else {}
        except Skip:
            return None
        if giver_slots(m, sl) if giver else sl:
            return None
    return (list(combos[0]) if len(combos) == 1 else None), fit


def read_fast(n, c, reads, top, giver):
    """on its detail screen: read_one's read, skipping the appraisal when an earlier read or its name settles it"""
    m = read_nope(n, c)
    m["tile"] = n
    r = reads.get(f"{n}|{c}")
    if r and r.get("hp") == m["hp"] and r.get("ivs"):
        m.update({k: r[k] for k in ("species_options", "species", "ivs", "moves")}, how="read before")
        return m
    got = by_name(m, top, giver)
    if got:
        m["ivs"], fit = got
        m.update(species_options=fit, species=sort.pick_species(fit), moves=[], how="by its name")
        return m
    m = appraise_one(m)
    m["how"] = "appraised"
    return m


def find(pile, who, dry=False):
    """walk the pile once. Open each suspect once: read it, judge it and keep or clear it right there. One whose
    pool searches aren't typed yet is judged after the walk and acted on in a second walk (act).
    -> (verdicts, unsure). Starts again where it stopped (verdicts.json, unsure.json in the run dir)"""
    import tradeable
    giver = who == tradeable.GIVER
    verdicts, unsure = load("verdicts.json", []), load("unsure.json", [])
    later = load("later.json", [])  # read, waiting for their pool searches
    seen = {(v["tile"], v["cp"]) for v in verdicts + unsure + later}
    low = {(n.lower(), c) for n, c, _ in load_checked(who)}
    reads = load_reads(who)

    names = list_tiles(pile, lambda n, c: named(n))
    high = list_tiles(pile + HIGH_TERMS, lambda n, c: not named(n) and (n.lower(), c) not in low)
    gym = list_tiles(pile + GYM_TERMS, lambda n, c: not named(n))  # (never left out by checked: its rank moves)
    todo = list(dict.fromkeys(t for t in names + high + gym if t not in seen))
    log(f"suspects: {len(names)} named, {len(high)} unnamed 82%+ ones to appraise, {len(gym)} unnamed gym "
        f"defenders, {len(todo)} not done yet")
    if not todo and not later:
        return verdicts, unsure
    top = tops(pile) if any(named(n) and f"{n}|{c}" not in reads for n, c in todo) else None
    known = [reads[k] for k in (f"{n}|{c}" for n, c in todo) if k in reads and reads[k].get("ivs")]
    results, wants = pools(known)
    log(f"suspects: {len(known)} read before, their pool searches typed")

    def visit(i, n, c):
        t = same_tile(n, c, todo)
        if not t or t in seen:
            return False
        n = t[0]
        seen.add(t)
        log(f"tile {i}: {n} CP{c}")
        base.open_tile(i)
        try:
            m = read_fast(n, c, reads, top, giver)
            if m.get("ivs"):
                save_read(reads, who, m)
            iv = sum(m["ivs"]) if m.get("ivs") else None
            log(f"  {m['name']!r} {m['species']} {'/'.join(map(str, m['ivs'] or '???'))} ({m['how']})")
            if not named(n) and iv < HIGH and not is_gym(m):
                add_checked(who, [n, c, iv])
                return False
            if any(q not in results for q, _ in searches(m)):
                later.append(m)
                base.save("later.json", later)
                log("  its pool searches aren't typed yet: judged after the walk")
                return False
            verdict, keep, why = judge(m, results, wants, who)
            v = dict(m, verdict=verdict, keep=keep, why=why)
            if verdict in ("KEEP", "CLEARED") and not dry:
                apply(v, m, who)
                v["done"] = True
            verdicts.append(v)
            base.save("verdicts.json", verdicts)
            log(f"{'DONE ' if v.get('done') else ''}{verdict} {n} CP{c}: {why[0]}")
            return v.get("done") and verdict == "KEEP"  # (a cleared one stays in the pile, under its species name)
        except Skip as e:
            unsure.append({"tile": n, "cp": c, "why": str(e)})
            base.save("unsure.json", unsure)
            raise
        finally:
            isr.back_to_list()

    log(f"--- suspects: open each once: {pile}")
    if ct.long_search(pile):
        search.walk_list(visit, odd=lambda n: not named(n))
    if later:
        results, wants = pools(later)
        for m in later:
            verdict, keep, why = judge(m, results, wants, who)
            verdicts.append(dict(m, verdict=verdict, keep=keep, why=why))
        base.save("verdicts.json", verdicts)
        base.save("later.json", [])
    return verdicts, unsure


# ---------- pools and judge ----------

def iv_name(m):
    """its /ivc name, or the one /ivc would give it now. None: /ivc would show nothing"""
    if isr.ivc_name(m["name"]):
        return m["name"]
    sp = m["species_options"]
    return ivc.make_name(tuple(m["ivs"]), shadow=m["shadow"], size=m["size"], moves=m["moves"], lucky=m["lucky"],
                         legendary=isr.ivcrun.is_legendary(sp), gym=any(s in ivc.GYM_DEFENDERS for s in sp))


def slots(m):
    """{(league, form): rank} for its top-100 PvP slots, and the line's first stage"""
    sp = [s for s in m["species_options"] if s in pvp.PLAIN]
    if not sp or not m.get("ivs"):  # (no IVs: its name showed it has no slot that counts, see by_name)
        return {}, None
    try:
        sl, s = base.slots_of(sp, m["cp"], m["hp"], tuple(m["ivs"]))
    except Skip:
        return {}, None
    return sl, pvp.root(s)


def searches(m):
    """[(search, iv_only)] the judge needs for this one"""
    out = []
    if iv_name(m):
        out += [(q, not q.endswith(sort.NOT_NOPE)) for q in sort.searches_for(dict(m, name=iv_name(m)))]
    sl, first = slots(m)
    if sl and first and pvp.letters(first) is not None:
        out += [(q, False) for q in pvp.line_searches(pvp.tree(first), pool_kind(m))]
    return out


def pools(found):
    results, wants = load("pools.json", {}), load("counts.json", {})
    qs = {}
    for m in found:
        for q, iv_only in searches(m):
            qs[q] = qs.get(q, True) and iv_only  # one that's both reads every tile
    todo = [q for q in qs if q not in results]
    log(f"suspects: {len(qs)} pool searches, {len(qs) - len(todo)} done already")
    if todo:
        search.to_search_list()
    for q in todo:
        got, want = search.run_search(q, qs[q])
        if not got and want is None:
            got, want = search.run_search(q, qs[q])
        if want is not None and len(got) != want:
            got = isr.closer(q, qs[q], got, want)
        results[q], wants[q] = got, want
        base.save("pools.json", results)
        base.save("counts.json", wants)
        log(f"  {q}: {len(got)} tiles (the game says {want})")
    return {k: [tuple(x) for x in v] for k, v in results.items()}, wants


def giver_slots(m, sl):
    """CyrillJan doesn't play PvP. It keeps one only for a slot that's top GIVER_PVP_TOP of all 4,096 IVs, in a league
    the form is viable in (PvPoke's top pvp.VIABLE_TOP there). No Master League: that wants perfect IVs, so the IV
    side covers it."""
    return {(t, s): r for (t, s), r in sl.items() if r <= GIVER_PVP_TOP and pvp.viable(s, t, m["shadow"])}


def judge(m, results, wants, who=None):
    """-> (KEEP | CLEARED | LEAVE, what keeps it {'iv': name, 'pvp': name}, [why]). who: the giver's PvP side is
    giver_slots()"""
    keep, why, unsure = {}, [], False
    name = iv_name(m)
    if name:
        v, w = isr.judge(dict(m, name=name), results, wants)
        why += [f"IV {name!r}: {v}"] + w[:2]
        if v == "KEEP":
            keep["iv"] = name
        elif v != "NOPE":
            unsure = True
    else:
        why.append("IV: /ivc would show nothing")
    sl, first = slots(m)
    import tradeable  # (it imports this file: by now it has loaded)
    giver = who == tradeable.GIVER
    if giver:
        sl = giver_slots(m, sl)
    if sl and pvp.letters(first) is None:
        why.append(f"PvP: the {pvp.display(first)} line branches, its names can't be compared")
        unsure = True
    elif sl:
        qs = pvp.line_searches(pvp.tree(first), pool_kind(m))
        if any(q not in results for q in qs):
            why.append("PvP: a pool search is missing")
            unsure = True
        else:
            others = [(n, s) for q in qs for n, c in results[q] if c and (s := pvp.name_slots(n, first))]
            fell, w = pvp.fallen(sl, others, first)
            why += [f"PvP: {'fallen' if fell else 'keeps'}"] + w[:2]
            if not fell:
                keep["pvp"] = m["name"] if pvp_name(m["name"]) else pvp.slots_name(first, sl)
    elif giver:
        why.append(f"PvP: no top-{GIVER_PVP_TOP} slot in a league it's viable in")
    else:
        why.append("PvP: no top-100 slot")
    return ("KEEP" if keep else "LEAVE" if unsure else "CLEARED"), keep, why


# ---------- act ----------

def is_species_name(n, m):
    k = lambda s: re.sub(r"[^a-z]", "", (s or "").lower())
    return bool(k(n)) and any(k(sort.base_name(s)) == k(n) for s in m["species_options"])


def clear_name(m):
    """blank the nickname: the game shows the species name again"""
    base.still_opened("before the rename")
    go("pencil", "rename")
    with base.changing("clearing the name"):
        base.tap("field")
        time.sleep(0.3)
        for _ in range(2):
            base.key("a", cmd=True)
            base.key("delete")
            if not base.settle(base.field_text, lambda g: not g, timeout=1.5):
                break
        else:
            base.leave_rename("CANCEL")
            raise Stop(f"couldn't empty the nickname box (it shows {base.field_text()!r})")
        base.leave_rename("OK")
        got = base.settle(base.detail_name, lambda g: is_species_name(g, m))
        if not is_species_name(got, m):
            base.keep_capture("rename")
            raise Stop(f"after OK the name reads {got!r}, wanted the species name")


def apply(v, now, who):
    """on its detail screen (now: read_member's read of it). KEEP: star on, Nope off (a PvP keeper too: PvpC is only
    /pvpc's to-do pile), a name if it has none. CLEARED: nickname blanked, Nope stays"""
    if v["verdict"] == "KEEP":
        base.set_star(True)
        base.set_tags(off=["Nope"])
        new = v["keep"].get("iv") or v["keep"].get("pvp")
        if new and not named(now["name"]):
            base.do_rename(new, base.same_name if pvp_name(new) else isr.ivcrun.same_name)
    elif not is_species_name(now["name"], v):
        clear_name(v)
        add_checked(who, [sort.base_name(v["species"]).title(), v["cp"], sum(v["ivs"]) if v.get("ivs") else None])


def act(verdicts, pile, who):
    """-> the ones still unresolved after this"""
    todo = {(v["tile"], v["cp"]): v for v in verdicts if v["verdict"] in ("KEEP", "CLEARED") and not v.get("done")}

    def visit(i, n, c):
        t = same_tile(n, c, list(todo))  # (OCR may read the name a bit differently from the first walk: '93 HP' / '93 H')
        if not t:
            return False
        v, (n, c) = todo[t], t
        log(f"tile {i}: {n} CP{c}: {v['verdict']}")
        base.open_tile(i)
        try:
            now = isr.read_member(n, c, ivc=False)
            if now["hp"] != v["hp"] or not any(base.is_tag(t, "Nope") for t in now["tags"]):
                raise Skip(f"not the one judged: HP{now['hp']} {now['tags']}")
            apply(v, now, who)
            v["done"] = True
            base.save("verdicts.json", verdicts)
            del todo[(n, c)]
            log(f"DONE {v['verdict']} {n} CP{c}: {v['why'][0]}")
            return v["verdict"] == "KEEP"  # (a cleared one stays in the pile, under its species name)
        finally:
            isr.back_to_list()

    if todo:
        dexes = isr.dex_terms(sort.SPECIES[v["species"]]["dex"] for v in todo.values())
        if ct.long_search(pile + (f"&{dexes}" if len(dexes) <= isr.ACT_QUERY_MAX else "")):
            search.walk_list(visit, odd=lambda n: not named(n))
    return [v for v in verdicts if not v.get("done")]


def run(pile, who, dry=False):
    """find (it judges and acts as it goes), then act on the ones judged after its walk. -> [what's still unresolved
    (verdicts and unreadable ones)]"""
    verdicts, unsure = find(pile, who, dry)
    lines = [f"{v['verdict']:8} {v['tile']!r:16} CP{v['cp']:<5} {v['species']:20} {v['why'][0]}"
             + "".join(f"\n           {w}" for w in v["why"][1:]) for v in verdicts]
    lines += [f"UNREAD   {u['tile']!r:16} CP{u['cp']:<5} {u['why']}" for u in unsure]
    open(os.path.join(base.RUN_DIR, "suspects.txt"), "w").write("\n".join(lines) + "\n")
    log("suspects: " + ", ".join(f"{k} {sum(v['verdict'] == k for v in verdicts)}" for k in ("KEEP", "CLEARED", "LEAVE"))
        + f", {len(unsure)} unreadable -> {os.path.join(base.RUN_DIR, 'suspects.txt')}")
    if dry:
        return [v for v in verdicts if v["verdict"] == "LEAVE"] + unsure
    return act(verdicts, pile, who) + unsure


def script(a):
    who = home.trainer()
    if who not in (tradeable.GIVER, tradeable.TAKER):
        raise Stop(f"signed in as {who!r}")
    home.start()
    search.to_search_list()
    left = run(tradeable.SUSPECT_PILE, who, "--dry-run" in a)
    log(f"{len(left)} unresolved")


if __name__ == "__main__":
    import tradeable  # it imports this file again, and that resets the run folder: load it before making ours
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="suspects")
    session.main(script, sys.argv[1:])
