#!/usr/bin/env python3
"""Unattended /ivcsort: keep the best IVC Pokémon (favorite + untick IVC), Nope the rest. Rules in sort.py.

  caffeinate -dimsu python3 run.py scan [<run dir>] [--limit N]  1. read every IVC Pokémon (changes nothing), one
                                                            dex-number search at a time (chunks.json). Give the
                                                            run dir to carry on: done chunks are passed over
  caffeinate -dimsu python3 run.py pools <run dir>          2. type the pool searches, read every tile (changes nothing)
  python3 run.py plan <run dir>                             3. decide offline -> <run dir>/plan.txt (no phone)
  caffeinate -dimsu python3 run.py fallen <run dir>         3b. sort the fallen-out ones into groups (changes nothing)
  caffeinate -dimsu python3 run.py act <run dir> [--limit N] [--yes]  4. favorite+untag or Nope, as plan.json says.
                                                            Lists the NOPEs and asks first (--yes: don't ask)
  caffeinate -dimsu python3 run.py act-fallen <run dir> [--limit N]  5. tag the fallen-out ones (after act)
  python3 run.py search "<query>"                           type one search and print the tiles (testing)

Start with Pokémon GO open on the Pokémon screen. Every step writes into runs/<time>/ (scan.json, pools.json,
plan.txt, plan.json, log.txt). Only `act` changes anything, and only after the user says yes to its NOPE list.
"""
import hashlib, importlib.util, os, re, sys, time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ivc"))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
import ui
import run as base
from run import Stop, Skip, log, keep_capture, go, back_to_list, front, save, load, steady_detail, \
    extras, candy, type_line, dynamax, set_tags, set_star

spec = importlib.util.spec_from_file_location("ivcrun", os.path.join(HERE, "..", "ivc", "run.py"))
ivcrun = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ivcrun)
import sort
import search, fallen
from search import to_search_list, start_search, run_search, result_count, looks_same

TAG = "IVC"
CHUNK, MAX_DEX = 50, 1025  # scan searches #IVC by dex number, this many at a time
def new_run_dir(d=None):
    return base.new_run_dir(os.path.join(HERE, "runs"), d)


# ---------- reading the detail screen ----------

def read_member(tile_name, tile_cp, ivc=True):
    info, texts, path = steady_detail()
    for _ in range(2):  # a digit dropped ('CP62' for CP626): read again, off the phone's own screenshot on Android
        if not (info["cp"] and info["cp"] != tile_cp and str(tile_cp).startswith(str(info["cp"]))):
            break
        time.sleep(0.5)
        if ui.ANDROID:
            p = ui.android.sharp()
            texts2 = ui.ocr(p)
            if ui.detail_info(texts2)["cp"] == tile_cp:
                info, texts, path = ui.detail_info(texts2), texts2, p
                break
        info, texts, path = steady_detail()
    a, b = short(info["name"]), short(tile_name)
    if info["cp"] and info["cp"] != tile_cp:
        raise Skip(f"opened CP{info['cp']} but tile said CP{tile_cp}")
    if not a or not b or not (a.startswith(b) or b.startswith(a)):
        if not (info["cp"] == tile_cp and odd_name(sort.clean_name(tile_name))):
            raise Skip(f"opened {info['name']!r} but tile said {tile_name!r}")
        log(f"  tile said {tile_name!r}, the Pokémon is {info['name']!r} (same CP): going by the Pokémon")
    has_tag = any(ui.norm(t) == TAG for t in info["tags"])
    if has_tag != ivc:
        raise Skip(f"{TAG} tag {'missing' if ivc else 'on'}: {info['tags']}")
    shadow, lucky, size = extras(texts)
    m = {"tile": tile_name, "name": info["name"], "cp": tile_cp, "hp": info["hp"], "candy": candy(texts),
         "types": sorted(type_line(texts)), "shadow": shadow, "lucky": lucky, "size": size, "dynamax": dynamax(texts), "tags": info["tags"]}
    m["species_options"] = sort.identify(m["candy"], set(m["types"]), m["cp"], m["hp"], sort.value(m["name"], shadow))
    m["species"] = sort.pick_species(m["species_options"])
    return m


# ---------- walking a list ----------

def odd_name(n):
    """a tile name that doesn't look like an /ivc name (IV number first, or a move-only name like 'FP*')"""
    return not re.match(r"\d{2}|[A-Z]{2}\*", n or "")


def walk_list(visit, limit=10 ** 9, stop=None):
    return search.walk_list(visit, limit, stop, odd=odd_name)


# ---------- 1. scan ----------

def short(s):
    return re.sub(r"[.…\s|]+", "", (s or "").strip().replace("\"", "*")).lower()  # * can read as "


def same_name(a, b):
    """two reads of one name: a stray mark can add or drop a letter at the end ('40 al', '84/9', '96')"""
    a, b = short(a), short(b)
    return bool(a and b) and (a.startswith(b) or b.startswith(a))


def fits(m, a, b):
    """could this member be in the dex chunk a-b?"""
    opts = m.get("species_options") or []
    return not opts or any(a <= sort.SPECIES[s]["dex"] <= b for s in opts)


def same_member(x, y):
    """the same Pokémon read twice (tile names were misread differently): same detail name, CP, species, flags"""
    if x.get("unrenamed") or y.get("unrenamed"):
        return False
    return x["cp"] == y["cp"] and same_name(x["name"], y["name"]) and x["shadow"] == y["shadow"] \
        and x["lucky"] == y["lucky"] and (set(x["species_options"] or []) & set(y["species_options"] or [])
                                         or not (x["species_options"] or y["species_options"]))


def dedupe(found):
    """drop earlier reads of one Pokémon (the latest read has its current name; keep a known chunk),
    and chunks a member can't be in"""
    out = []
    for m in found:
        if m.get("dex_range") and not fits(m, *m["dex_range"]):
            m["dex_range"] = None
        twin = next((o for o in out if same_member(o, m)), None)
        if twin is None:
            out.append(m)
        else:
            m["dex_range"] = m.get("dex_range") or twin.get("dex_range")
            out[out.index(twin)] = m
    return out


def chunk_of(m, a, b):
    """is this scanned member in the dex chunk a-b? Read in that chunk, or every species it could be is in it."""
    if m.get("dex_range"):
        return m["dex_range"] == [a, b]
    opts = m.get("species_options") or ([m["species"]] if m.get("species") else [])
    return bool(opts) and not m.get("size") and all(a <= sort.SPECIES[s]["dex"] <= b for s in opts)


def scan(limit):
    """carries on from an earlier scan.json in the same run dir: tiles already read are passed over"""
    path = os.path.join(base.RUN_DIR, "scan.json")
    found = load("scan.json") if os.path.exists(path) else []
    before = len(found)
    found[:] = dedupe(found)
    if len(found) < before:
        log(f"dropped {before - len(found)} second reads of the same Pokémon")
        save("scan.json", found)
    had = list(found)  # scanned members not yet passed in this run
    in_range = []
    if found:
        log(f"carrying on: {len(found)} already scanned")

    def passed(n, c):
        """an already-scanned member this tile could be: the exact tile name first, then a near read"""
        ok = [m for m in had if m["cp"] == c and (not in_range or fits(m, *in_range))]
        m = next((m for m in ok if sort.clean_name(m["tile"]) == n), None) or \
            next((m for m in ok if same_name(m["tile"], n)), None)
        if m is None and odd_name(n) and in_range and len(ok) == 1:  # name unreadable: the CP alone, in this chunk
            log(f"  {n!r} CP{c}: name unreadable, taking it as the scanned {ok[0]['tile']!r}")
            m = ok[0]
        return m

    def visit(i, n, c):
        m = passed(n, c)
        if m is not None:
            had.remove(m)
            if in_range and not m.get("dex_range"):  # read before chunks: now we know its chunk
                m["dex_range"] = list(in_range)
                save("scan.json", found)
            return False
        if ivcrun.untouched(n):
            log(f"  {n} CP{c} still has its species name: run /ivc first")
            found.append({"tile": n, "cp": c, "unrenamed": True, "dex_range": list(in_range) or None})
            save("scan.json", found)
            return False
        log(f"tile {i}: {n} CP{c}")
        try:
            ivcrun.open_tile(i)
        except Stop:
            if base.look()[0] == "list":  # the tap never opened anything: nothing changed, pass it by
                raise Skip("tap didn't open the tile")
            raise
        try:
            m = read_member(n, c)
        finally:
            back_to_list()
        if in_range and len(m["species_options"] or []) > 1:  # the search was by dex number: drop the others
            fit = [s for s in m["species_options"] if in_range[0] <= sort.SPECIES[s]["dex"] <= in_range[1]]
            if fit:
                m["species_options"], m["species"] = fit, sort.pick_species(fit)
        m["dex_range"] = list(in_range) or None
        twin = next((o for o in found if same_member(o, m)), None)
        if twin is not None:  # read before under another tile name
            log(f"  same as the scanned {twin['tile']!r} CP{twin['cp']}")
            if twin in had:
                had.remove(twin)
            twin["dex_range"] = twin.get("dex_range") or m["dex_range"]
            save("scan.json", found)
            return False
        found.append(m)
        save("scan.json", found)
        flags = " ".join(f for f in ("shadow", "lucky", "dynamax") if m[f])
        log(f"  {m['name']!r} {m['species'] or m['species_options']} {flags} {m['size'] or ''}")
        return False

    front()
    to_search_list()
    chunks = load("chunks.json") if os.path.exists(os.path.join(base.RUN_DIR, "chunks.json")) else {}
    every = [(a, min(a + CHUNK - 1, MAX_DEX)) for a in range(1, MAX_DEX + 1, CHUNK)]
    query = lambda ab: f"#{TAG}&!xxl&!xxs&{ab[0]}-{ab[1]}"
    # chunks never searched first; the ones that came up short get their retry at the end
    for a, b in sorted(every, key=lambda ab: query(ab) in chunks):
        q = query((a, b))
        if chunks.get(q, {}).get("done"):
            continue
        in_range[:] = [a, b]
        path, texts, _ = start_search(q)
        want = result_count(texts)
        for _ in range(3):  # the count can be missed on the first read
            if want is not None:
                break
            time.sleep(0.5)
            want = result_count(ui.ocr(ui.capture()[0]))
        have = sum(chunk_of(m, a, b) for m in found)
        log(f"{q}: the game says {want}, {have} scanned")
        if want == 0:
            pass
        elif want is None or have < want:
            try:
                walk_list(visit, limit - len(found))
            finally:
                in_range[:] = []
            have = sum(chunk_of(m, a, b) for m in found)
            log(f"  {q}: {have} of {want} scanned")
        chunks[q] = {"want": want, "have": have, "done": want is not None and have >= want}
        save("chunks.json", chunks)
        to_search_list()
        if len(found) >= limit:
            break
    left = {q: f"{c['have']}/{c['want']}" for q, c in chunks.items() if not c["done"]}
    log(f"scanned {len(found)}, {sum(bool(m.get('unrenamed')) for m in found)} still unrenamed; "
        f"chunks not done: {left or 'none'}")


# ---------- 2. pools (search) ----------

def pools():
    members = [m for m in load("scan.json") if m.get("species")]
    queries = list(dict.fromkeys(q for m in members for q in sort.searches_for(m)))
    done = load("pools.json") if os.path.exists(os.path.join(base.RUN_DIR, "pools.json")) else {}
    wants = load("counts.json") if os.path.exists(os.path.join(base.RUN_DIR, "counts.json")) else {}
    log(f"{len(queries)} searches, {len(done)} done already")
    front()
    to_search_list()
    for q in queries:
        if q in done:
            continue
        iv_only = not q.endswith(sort.NOT_NOPE)  # gym searches need every CP
        got, want = run_search(q, iv_only)
        if not got and want is None:  # no tiles and no count: the search didn't run
            got, want = run_search(q, iv_only)
            if not got and want is None:
                log(f"  {q}: no tiles and no count twice, not saved (plan will SKIP; rerun pools)")
                to_search_list()
                continue
        if want is not None and len(got) != want:
            got2, want2 = run_search(q, iv_only)  # read it once more and keep the closer one
            if want2 is not None and abs(len(got2) - want2) < abs(len(got) - want):
                got = got2
        done[q], wants[q] = got, want
        save("pools.json", done)
        save("counts.json", wants)
        log(f"  {q}: {len(done[q])} tiles, {sum(sort.parse_name(n).iv is not None for n, _ in done[q])} with an IV")


# ---------- 3. plan ----------

def recheck(m, results, wants, verdict, why):
    """a search read a few tiles more or fewer than the game counted. If those few could flip the answer, leave it.
    Fewer: add that many 100% / huge-CP tiles. More: take out that many of the best ones."""
    qs = [q for q in sort.searches_for(m) if wants.get(q) is not None and wants[q] != len(results[q])]
    if not qs or verdict not in ("KEEP", "NOPE"):
        return verdict, why
    best = lambda t: (max(v for v in (sort.parse_name(t[0]).iv, sort.parse_name(t[0]).purified, -1) if v is not None), t[1])
    worst = dict(results)
    for q in qs:
        k = wants[q] - len(results[q])
        if k > 0 and verdict == "KEEP":
            worst[q] = results[q] + [("100", 99999)] * k
        elif k < 0 and verdict == "NOPE":
            worst[q] = sorted(results[q], key=best, reverse=True)[-k:]
    if worst == results:
        return verdict, why
    v2, _ = sort.decide(m, worst)
    if v2 == verdict:
        return verdict, why
    off = ", ".join(f"{q} read {len(results[q])} of {wants[q]}" for q in qs)
    return "LEAVE", [f"would be {verdict}, but a search was misread ({off}) and that could flip it"] + why


def twin_check(m, results, verdict, why):
    """a NOPE beaten by a tile read two ways ('98 ADBS V' and '98 AD BS*', same IV and CP) may be beaten by one
    Pokémon counted twice. If taking one of each such pair out flips it, leave it."""
    if verdict != "NOPE":
        return verdict, why
    fewer, pairs = dict(results), []
    for q in sort.searches_for(m):
        seen, keep = {}, []
        for n, c in results[q]:
            v = sort.value(n, m["shadow"])
            key = (v, c)
            if c and v is not None and key in seen and seen[key] != n and looks_same(seen[key], n):
                pairs.append(f"{seen[key]!r}/{n!r} CP{c}")
                continue
            seen.setdefault(key, n)
            keep.append((n, c))
        fewer[q] = keep
    if not pairs:
        return verdict, why
    v2, _ = sort.decide(m, fewer)
    if v2 == verdict:
        return verdict, why
    return "LEAVE", [f"would be NOPE, but {', '.join(pairs)} may be one Pokémon read twice"] + why


def plan():
    scanned, results = load("scan.json"), {k: [tuple(x) for x in v] for k, v in load("pools.json").items()}
    wants = load("counts.json") if os.path.exists(os.path.join(base.RUN_DIR, "counts.json")) else {}
    out, lines, counts = [], [], Counter()
    for m in scanned:
        if m.get("unrenamed"):
            verdict, why = "SKIP", ["still has its species name: run /ivc first"]
        elif not m.get("species"):
            verdict, why = "SKIP", [f"species unsure: {m.get('species_options')}"]
        elif any(q not in results for q in sort.searches_for(m)):
            verdict, why = "SKIP", ["a pool search is missing: run pools again"]
        else:
            verdict, why = sort.decide(m, results)
            verdict, why = recheck(m, results, wants, verdict, why)
            verdict, why = twin_check(m, results, verdict, why)
        counts[verdict] += 1
        out.append(dict(m, verdict=verdict, why=why))
        flags = " ".join(f for f in ("shadow", "lucky", "dynamax") if m.get(f))
        lines.append(f"{verdict:5} {m.get('name') or m['tile']!r:16} CP{m['cp']:<5} {m.get('species') or '?':20} {flags}")
        lines += [f"        {w}" for w in why]
    save("plan.json", out)
    fallen = fallen_candidates(scanned, results, wants)
    save("fallen.json", fallen)
    lines += ["", f"FALLEN OUT: {len(fallen)} older Pokémon (no IVC tag) now outside the top. `run.py fallen` sorts them into "
              "GuaranteedLucky / Old / Nope; act checks each one again on the detail screen first."]
    lines += [f"  {f['name']!r:16} CP{f['cp']:<5} {'shadow ' if f['shadow'] else ''}{'/'.join(f['species'])}: {f['why'][0]}"
              for f in fallen]
    grouped = load("fallen-groups.json") if os.path.exists(os.path.join(base.RUN_DIR, "fallen-groups.json")) else None
    if grouped:
        lines += ["", "FALLEN OUT, by group (from `run.py fallen`):"] + \
            [f"  {g}: {sum(len(v) for v in grouped[g].values())}" for g in grouped]
    unrenamed = sum(bool(m.get("unrenamed")) for m in scanned)
    head = ([f"WARNING: {unrenamed} IVC Pokémon still have their species name. Run /ivc on them first: "
             "until then they don't count in any pool, so too many get kept."] if unrenamed else []) + [f"{dict(counts)}", "KEEP = favorite + untick IVC.  NOPE = untick IVC, tick Nope.  LEAVE/SKIP = untouched.", ""]
    with open(os.path.join(base.RUN_DIR, "plan.txt"), "w") as f:
        f.write("\n".join(head + lines) + "\n")
    print("\n".join(head))
    print(f"table: {os.path.join(base.RUN_DIR, 'plan.txt')}")


def approved(yes):
    """show the NOPE list and ask once per plan. The answer is kept (approved.txt holds the plan's hash),
    so restarting act on the same plan doesn't ask again. --yes says yes without asking."""
    raw = open(os.path.join(base.RUN_DIR, "plan.json"), "rb").read()
    digest = hashlib.sha256(raw).hexdigest()
    ok_path = os.path.join(base.RUN_DIR, "approved.txt")
    if os.path.exists(ok_path) and open(ok_path).read().strip() == digest:
        return True
    plan_ = load("plan.json")
    nopes = [m for m in plan_ if m["verdict"] == "NOPE"]
    keeps = sum(m["verdict"] == "KEEP" for m in plan_)
    for m in nopes:
        print(f"NOPE  {m.get('name') or m['tile']!r:16} CP{m['cp']:<5} {m.get('species') or '?':20} {(m.get('why') or [''])[0]}")
    print(f"{len(nopes)} to Nope, {keeps} to keep (favorite + untick IVC). Full table: {os.path.join(base.RUN_DIR, 'plan.txt')}")
    if not yes:
        if not sys.stdin.isatty():
            sys.exit("act needs a yes: run it in a terminal, or add --yes once the user has said yes to this list")
        if input("Go ahead? [y/N] ").strip().lower() not in ("y", "yes"):
            return False
    with open(ok_path, "w") as f:
        f.write(digest + "\n")
    return True


# ---------- fallen out ----------
# Older Pokémon (no IVC tag) that the new keepers push out of the top. Not traded and caught 2016-2020 ->
# GuaranteedLucky (a trade is guaranteed lucky). Not traded and older than OLD_DAYS -> Old. Anything else
# (traded: a Pokémon can only be traded once, or newer) -> star off + Nope. Shiny and costume ones are never touched.

def ivc_name(n):
    """a name /ivc made ('96 HD', '87/96 A* XXL'), not another app's ('15/15/14')"""
    m = re.match(r"(\d{1,3})(?:/(\d{1,3}))?(?=\s|$)", n)
    return bool(m) and int(m.group(1)) <= 100 and (not m.group(2) or int(m.group(1)) < int(m.group(2)) <= 100)


def species_of_search():
    """pool search -> the species whose tiles it shows"""
    out = {}
    for sid in sort.SPECIES:
        for pool in ("plain", "shadow"):
            for q, _, ss in sort.groups(sid, pool):
                out.setdefault(q, set()).update(ss)
    return out


def judge(m, results, wants):
    if any(q not in results for q in sort.searches_for(m)):
        return "SKIP", ["a pool search is missing"]
    verdict, why = sort.decide(m, results)
    verdict, why = recheck(m, results, wants, verdict, why)
    return twin_check(m, results, verdict, why)


def fallen_candidates(scanned, results, wants):
    """tiles with an /ivc name, no IVC tag, that come out NOPE for every species the search could have shown.
    Lucky, Dynamax and size aren't known from a tile: act reads them on the detail screen and judges again."""
    ivc = Counter((sort.clean_name(m["tile"]), m["cp"]) for m in scanned)
    which, out, seen = species_of_search(), [], set()
    for q, tiles in results.items():
        if not (q.endswith("&shadow") or q.endswith("&!shadow")) or q not in which:
            continue
        shadow = q.endswith("&shadow")
        for n, c in tiles:
            if ivc[(n, c)]:
                ivc[(n, c)] -= 1
                continue
            p = sort.parse_name(n)
            if not c or (n, c, shadow) in seen or not ivc_name(n) or p.size or p.pvp:
                continue
            seen.add((n, c, shadow))
            verdicts = {s: judge({"species": s, "cp": c, "name": n, "shadow": shadow, "lucky": False, "dynamax": False},
                                 results, wants) for s in sorted(which[q])}
            if verdicts and all(v == "NOPE" for v, _ in verdicts.values()):
                out.append({"name": n, "cp": c, "shadow": shadow, "species": sorted(verdicts),
                            "dex": sorted({sort.SPECIES[s]["dex"] for s in verdicts}),
                            "why": next(iter(verdicts.values()))[1]})
    return out


def recheck_fallen(n, c):
    """on its detail screen: lucky, Dynamax and size known now, so judge it again"""
    results = {k: [tuple(x) for x in v] for k, v in load("pools.json").items()}
    wants = load("counts.json") if os.path.exists(os.path.join(base.RUN_DIR, "counts.json")) else {}
    m = read_member(n, c, ivc=False)
    if not m["species"]:
        raise Skip(f"species unsure: {m['species_options']}")
    verdict, why = judge(m, results, wants)
    return verdict == "NOPE", f"{verdict} {m['species']} ({why[0] if why else ''})"


def act_fallen(limit):
    fallen.act(limit, recheck_fallen, stop=lambda n: not re.match(r"\d", n), odd=odd_name)


# ---------- 4. act ----------

def favorite_and_untag():
    set_star(True)
    set_tags(off=[TAG])


ACT_QUERY_MAX = 120  # a longer dex list costs more typing than walking past the tiles it would hide


def dex_terms(dexes):
    """[1, 4, 5, 7] -> '1,4-5,7': the game's OR of dex numbers and ranges"""
    runs = []
    for d in sorted(set(dexes)):
        if runs and d == runs[-1][1] + 1:
            runs[-1][1] = d
        else:
            runs.append([d, d])
    return ",".join(f"{a}-{b}" if a != b else str(a) for a, b in runs)


def act_query(plans):
    """only the dex numbers that still have work, when that's short enough to type; else every IVC one.
    XXL/xxs are never in the plan (scan leaves them out), so they don't need to be in the list either"""
    q = f"#{TAG}&!xxl&!xxs"
    dex = dex_terms(sort.SPECIES[m["species"]]["dex"] for m in plans if m.get("species") in sort.SPECIES)
    return f"{q}&{dex}" if dex and len(dex) <= ACT_QUERY_MAX else q


def act(limit):
    todo = Counter()
    want = {}
    for m in load("plan.json"):
        if m["verdict"] in ("KEEP", "NOPE"):
            key = (sort.clean_name(m["tile"]), m["cp"])
            todo[key] += 1
            want.setdefault(key, []).append(m)
    # what earlier act runs on this run dir did or skipped: a restart doesn't open those again
    has = os.path.exists(os.path.join(base.RUN_DIR, "act.json"))
    progress = load("act.json") if has else {"done": [], "skipped": []}
    for n, c, name, species in progress["done"]:
        p = next((p for p in want.get((n, c), []) if (p["name"], p["species"]) == (name, species)), None)
        if p:
            want[(n, c)].remove(p)
            todo[(n, c)] -= 1
    skipped = {tuple(k) for k in progress["skipped"]}
    log(f"act: {sum(todo.values())} to change ({len(progress['done'])} done by earlier runs, "
        f"{len(skipped)} skipped earlier: delete act.json to try those again)")
    pooled = []  # pools and counts, loaded the first time a Pokémon has to be judged again

    def visit(i, n, c):
        if not todo[(n, c)] or (n, c) in skipped:
            log(f"  tile {i}: {n} CP{c} not in the plan{' (skipped earlier)' if (n, c) in skipped else ''}, passing")
            return False
        try:
            return change(i, n, c)
        except Skip:
            skipped.add((n, c))
            progress["skipped"] = sorted(skipped)
            save("act.json", progress)
            raise

    def change(i, n, c):
        plans = want[(n, c)]
        log(f"tile {i}: {n} CP{c}")
        ivcrun.open_tile(i)
        now = read_member(n, c)
        for _ in range(2):  # candy or type line misread: no species. Read again
            if now["species"]:
                break
            time.sleep(0.8)
            now = read_member(n, c)
        nospace = lambda x: sort.clean_name(x).replace(" ", "")  # OCR adds or drops spaces ('89 H C*' / '89 HC*')
        m = next((p for p in plans if nospace(p["name"]) == nospace(now["name"]) and p["species"] == now["species"]
                  and p["shadow"] == now["shadow"] and p["lucky"] == now["lucky"]), None)
        if not m:  # a stray icon read as one letter after the name ('96A i'): the tile name, CP and species agree, so take it
            m = next((p for p in plans if len(nospace(now["name"])) == len(nospace(p["name"])) + 1
                      and nospace(now["name"]).startswith(nospace(p["name"])) and p["species"] == now["species"]
                      and p["shadow"] == now["shadow"] and p["lucky"] == now["lucky"]), None)
        if not m:  # the scan misread shadow or lucky (a sparkly lucky background hides its line): judge it again as it is
            p = next((p for p in plans if nospace(p.get("name") or p["tile"]) == nospace(now["name"]) and p["species"] == now["species"]), None)
            if p:
                if not pooled:
                    pooled.append({k: [tuple(x) for x in v] for k, v in load("pools.json").items()})
                    pooled.append(load("counts.json") if os.path.exists(os.path.join(base.RUN_DIR, "counts.json")) else {})
                fixed = dict(p, shadow=now["shadow"], lucky=now["lucky"], size=now["size"], dynamax=now["dynamax"])
                verdict, why = judge(fixed, *pooled)
                log(f"  the plan had {p.get('name') or p['tile']!r} as {'shadow' if p['shadow'] else 'lucky' if p['lucky'] else 'plain'}, "
                    f"it's {'shadow' if now['shadow'] else 'lucky' if now['lucky'] else 'plain'}: judged again -> {verdict}")
                if verdict not in ("KEEP", "NOPE"):
                    raise Skip(f"judged again with the right shadow/lucky: {verdict} {why[:1]}")
                plans.remove(p)
                m = dict(fixed, verdict=verdict, why=why)
                plans.append(m)
        if not m:
            raise Skip(f"detail doesn't match the plan: {now['name']!r} {now['species']}")
        if m["verdict"] == "KEEP":
            favorite_and_untag()
        else:  # a name can be wrong ('FP*' on a 98% lucky): appraise before any Nope
            keep, ivs, raws, what = base.high_iv()
            if keep:  # 98%+ always keeps
                favorite_and_untag()
                plans.remove(m)
                todo[(n, c)] -= 1
                log(f"DONE KEEP {m['name']!r} CP{c} {m['species']}: the plan said NOPE, appraised {what}: 98%+")
                go("close", "list")
                return True
            base.nope(TAG, now["tags"], only=False, ivs=ivs, raws=raws)  # swap IVC for Nope, keep any other tags
        plans.remove(m)
        todo[(n, c)] -= 1
        progress["done"].append([n, c, m["name"], m["species"]])
        save("act.json", progress)
        log(f"DONE {m['verdict']} {m['name']!r} CP{c} {m['species']}: {m['why'][0] if m['why'] else ''}")
        go("close", "list")
        return True

    left = [m for k, ms in want.items() if k not in skipped for m in ms]
    if not left:
        log("nothing left to change")
        return
    front()
    to_search_list()
    q = act_query(left)
    _, texts, _ = start_search(q)
    log(f"{q}: the game says {result_count(texts)}")
    walk_list(visit, limit)
    log(f"left over (not found in the list): {sum(todo.values())}, skipped: {len(skipped)}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("scan", "pools", "plan", "fallen", "act", "act-fallen", "search"):
        sys.exit(__doc__)
    limit = int(a[a.index("--limit") + 1]) if "--limit" in a else 10 ** 9
    cmd = a[0]
    given = a[1] if len(a) > 1 and not a[1].startswith("--") and cmd != "search" else None
    new_run_dir(os.path.abspath(given) if given else None)
    code = 0
    try:
        if cmd == "scan":
            scan(limit)
        elif cmd == "pools":
            pools()
        elif cmd == "plan":
            plan()
        elif cmd == "fallen":
            fallen.groups(iv_only=True)
            plan()
        elif cmd == "act-fallen":
            if not os.path.exists(os.path.join(base.RUN_DIR, "fallen-groups.json")):
                sys.exit("run fallen first, and read plan.txt")
            act_fallen(limit)
        elif cmd == "act":
            if not os.path.exists(os.path.join(base.RUN_DIR, "plan.json")):
                sys.exit("run plan first, and read plan.txt")
            if any(m.get("unrenamed") for m in load("plan.json")) and "--force" not in a:
                sys.exit("some IVC Pokémon aren't renamed yet: run /ivc first (or --force)")
            if not approved("--yes" in a):
                sys.exit("not approved, nothing changed")
            act(limit)
        elif cmd == "search":
            front()
            got, want = run_search(a[1])
            for n, c in got:
                print(f"CP{c:<5} {n}")
            print(f"{len(got)} read, the game says {want}")
    except Stop as e:
        keep_capture("stop")
        log(f"STOPPED: {e}")
        code = 1
    except KeyboardInterrupt:
        log("interrupted")
        code = 130
    except Exception as e:
        keep_capture("crash")
        log(f"CRASHED: {type(e).__name__}: {e}")
        code = 2
    sys.exit(code)
