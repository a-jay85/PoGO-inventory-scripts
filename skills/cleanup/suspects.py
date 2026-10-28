#!/usr/bin/env python3
"""Suspects: an untraded Nope that may still belong in its species' top IV or PvP spots. tradeable.py tag --nope
checks every one before it tags anything (the user's rule: no tag until it's cleared).

A suspect is in the untraded Nope pile and either
  - still has an /ivc name ('96 HD') or a Pvp name: it was named once, so it may still be a keeper, or
  - 93%+ (an IV sum of 42+) whatever its name. Every stat 11+ and 3* finds those; the appraisal tells.
Steps, in the tag run's dir:
  find   open and appraise each one -> suspects.json (and unsure.json: ones it couldn't read)
  pools  the searches /ivcsort and /pvpc compare with (everything owned in the line, minus Nope) -> pools.json
  judge  offline. IV: /ivcsort's judge() on its /ivc name (or the name /ivc would give it). PvP: pvp.fallen() on
         its top-100 slots against every Pvp name in the line. CyrillJan (no PvP there) counts only giver_slots():
         top 20 in a league the form is viable in, Master League too. -> verdicts.json
  act    KEEP (either side keeps): star on, Nope off. A PvP keeper gets PvpC back, like /pvpc's keepers (not a
         Master League one: /pvpc doesn't rank that). One with
         neither kind of name gets the one /ivc (or /pvpc) would give it.
         CLEARED: nickname blanked, so the game shows the species name. Nope stays: tag --nope tags it next.
         LEAVE: unsure (a misread search, a branching line, XXL/xxs): nothing changes.
run() -> the ones still unresolved. tag --nope tags nothing while there are any.
runs/checked-<trainer>.json remembers the species-named ones already appraised (name, CP), so a rerun doesn't
appraise them again.

  POGO_PHONE=android caffeinate -dimsu python3 suspects.py [--dry-run]   find, pools, judge; --dry-run stops there
"""
import importlib.util, json, os, re, sys, time

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


def pool_kind(m):
    return "shadow" if m["shadow"] else "plain"


# ---------- find ----------

def read_one(n, c):
    """on its detail screen: species, flags and exact IVs. Comes back to the detail screen"""
    m = isr.read_member(n, c, ivc=False)
    if not any(base.is_tag(t, "Nope") for t in m["tags"]):
        raise Skip(f"no Nope tag on detail: {m['tags']}")
    _, texts, _, _ = base.wait_for("detail")
    opts = m["species_options"] or base.species_from_candy(texts, m["cp"], m["hp"])
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


def find(pile, who):
    """-> (suspects, unsure). Starts again where it stopped (suspects.json, unsure.json in the run dir)"""
    found, unsure = load("suspects.json", []), load("unsure.json", [])
    seen = {(f["tile"], f["cp"]) for f in found} | {(u["tile"], u["cp"]) for u in unsure}
    checked = json.load(open(checked_file(who))) if os.path.exists(checked_file(who)) else []
    low = {(n.lower(), c) for n, c, _ in checked}

    def visit(i, n, c, high):
        if (n, c) in seen or (not high and not named(n)) or (high and (named(n) or (n.lower(), c) in low)):
            return False  # (high: the named ones were read in the first walk)
        log(f"tile {i}: {n} CP{c}")
        seen.add((n, c))
        base.open_tile(i)
        try:
            m = read_one(n, c)
        except Skip as e:
            unsure.append({"tile": n, "cp": c, "why": str(e)})
            base.save("unsure.json", unsure)
            raise
        finally:
            isr.back_to_list()
        iv = sum(m["ivs"])
        log(f"  {m['name']!r} {m['species']} {'/'.join(map(str, m['ivs']))} ({round(iv * 100 / 45)}%)")
        if high and iv < HIGH:
            checked.append([n, c, iv])
            json.dump(checked, open(checked_file(who), "w"))
            return False
        m["tile"], m["why"] = n, ("named" if not high else f"{round(iv * 100 / 45)}%")
        found.append(m)
        base.save("suspects.json", found)
        return False

    for high in (False, True):
        q = pile + (HIGH_TERMS if high else "")
        log(f"--- suspects: {'93%+, any name' if high else 'an /ivc or Pvp name'}: {q}")
        if ct.long_search(q):
            search.walk_list(lambda i, n, c: visit(i, n, c, high), odd=lambda n: not named(n))  # zoom a misread name
    log(f"suspects: {len(found)} found, {len(unsure)} couldn't be read")
    return found, unsure


# ---------- pools and judge ----------

def iv_name(m):
    """its /ivc name, or the one /ivc would give it now. None: /ivc would show nothing"""
    if isr.ivc_name(m["name"]):
        return m["name"]
    sp = m["species_options"]
    return ivc.make_name(tuple(m["ivs"]), shadow=m["shadow"], size=m["size"], moves=m["moves"], lucky=m["lucky"],
                         legendary=isr.ivcrun.is_legendary(sp), gym=any(s in ivc.GYM_DEFENDERS for s in sp))


def slots(m):
    """{(league, form): rank} for its top-100 PvP slots, the line's first stage, and what it is now"""
    sp = [s for s in m["species_options"] if s in pvp.PLAIN]
    if not sp:
        return {}, None, None
    try:
        sl, s = base.slots_of(sp, m["cp"], m["hp"], tuple(m["ivs"]))
    except Skip:
        return {}, None, None
    return sl, pvp.root(s), s


def searches(m):
    """[(search, iv_only)] the judge needs for this one"""
    out = []
    if iv_name(m):
        out += [(q, not q.endswith(sort.NOT_NOPE)) for q in sort.searches_for(dict(m, name=iv_name(m)))]
    sl, first, _ = slots(m)
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


def giver_slots(m, sl, now):
    """CyrillJan doesn't play PvP. It keeps one only for a slot that's top GIVER_PVP_TOP of all 4,096 IVs, in a league
    the form is viable in (PvPoke's top pvp.VIABLE_TOP there), Master League too (what it is now or evolves into).
    -> (those of sl, [Master forms])"""
    good = lambda s, t, r: r <= GIVER_PVP_TOP and pvp.viable(s, t, m["shadow"])
    sl = {(t, s): r for (t, s), r in sl.items() if good(s, t, r)}
    ml = [s for s in (pvp.family(now) if now else []) if s in pvp.PLAIN
          and good(s, "M", pvp.rank(s, tuple(m["ivs"]), pvp.ML_CAP))]
    return sl, ml


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
    sl, first, now = slots(m)
    import tradeable  # (it imports this file: by now it has loaded)
    giver, ml = who == tradeable.GIVER, []
    if giver:
        sl, ml = giver_slots(m, sl, now)
    if ml:  # no name shows a Master League slot, so there's no rival to compare with
        why.append(f"PvP: Master League top {GIVER_PVP_TOP} as " + ", ".join(pvp.display(s) for s in ml))
        keep["pvp"] = m["name"] if named(m["name"]) else pvp.slots_name(first, sl) if sl else name
    elif sl and pvp.letters(first) is None:
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


def act(verdicts, pile, who):
    """-> the ones still unresolved after this"""
    todo = {(v["tile"], v["cp"]): v for v in verdicts if v["verdict"] in ("KEEP", "CLEARED") and not v.get("done")}
    checked = json.load(open(checked_file(who))) if os.path.exists(checked_file(who)) else []

    def visit(i, n, c):
        v = todo.get((n, c))
        if not v:
            return False
        log(f"tile {i}: {n} CP{c}: {v['verdict']}")
        base.open_tile(i)
        try:
            now = isr.read_member(n, c, ivc=False)
            if now["hp"] != v["hp"] or not any(base.is_tag(t, "Nope") for t in now["tags"]):
                raise Skip(f"not the one judged: HP{now['hp']} {now['tags']}")
            if v["verdict"] == "KEEP":
                base.set_star(True)
                # (a Master League keeper has no Pvp name: PvpC would send it to /pvpc, which ranks only L/G/U)
                base.set_tags(on=["PvpC"] if pvp_name(v["keep"].get("pvp")) else [], off=["Nope"])
                new = v["keep"].get("iv") or v["keep"].get("pvp")
                if new and not named(now["name"]):
                    base.do_rename(new, base.same_name if pvp_name(new) else isr.ivcrun.same_name)
            elif not is_species_name(now["name"], v):
                clear_name(v)
                checked.append([sort.base_name(v["species"]).title(), c, sum(v["ivs"])])
                json.dump(checked, open(checked_file(who), "w"))
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
    """find, pools, judge, act. -> [what's still unresolved (verdicts and unreadable ones)]"""
    found, unsure = find(pile, who)
    results, wants = pools(found)
    verdicts = load("verdicts.json") or []
    known = {(v["tile"], v["cp"]) for v in verdicts}
    for m in found:
        if (m["tile"], m["cp"]) not in known:
            verdict, keep, why = judge(m, results, wants, who)
            verdicts.append(dict(m, verdict=verdict, keep=keep, why=why))
    base.save("verdicts.json", verdicts)
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
