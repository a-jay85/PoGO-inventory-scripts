#!/usr/bin/env python3
"""Unattended /ivcsort: keep the best IVC Pokémon (favorite + untick IVC), Nope the rest. Rules in sort.py.

  caffeinate -dimsu python3 run.py [sort [<run dir>]] [--limit N] [--look]
        read the IVC Pokémon, then per family: type its searches, decide, favorite or Nope on the list on screen. Up
        to SMALL IVC ones: one search reads them all. More: 50 dex numbers at a time. Give the run dir
        to carry on after a stop. --limit N: change N, then stop. --look: decide only (plan.txt), change nothing
  caffeinate -dimsu python3 run.py fallen <run dir>         sort the fallen-out ones into groups (changes nothing)
  caffeinate -dimsu python3 run.py act-fallen <run dir> [--limit N]  tag the fallen-out ones
  python3 run.py search "<query>"                           type one search and print the tiles (testing)

Run /ivc first: an IVC Pokémon still named after its species blocks every KEEP it could beat. Start with Pokémon GO
open. A run writes into runs/<time>/ (scan.json, pools.json, plan.txt, plan.json, act.json, log.txt).
"""
import glob, importlib.util, json, os, re, sys, time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ivc"))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
import ui
import run as base
from run import Stop, Skip, log, go, back_to_list, front, save, load, steady_detail, \
    extras, candy, type_line, dynamax, set_tags, set_star

spec = importlib.util.spec_from_file_location("ivcrun", os.path.join(HERE, "..", "ivc", "run.py"))
ivcrun = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ivcrun)
import sort
import search, fallen, session
from search import to_search_list, start_search, run_search, result_count, looks_same

TAG = "IVC"


class NotIVC(Skip):
    """the tile matched a planned one by name and CP, but it has no IVC tag: an older keeper on a family list"""
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
        raise (NotIVC if ivc else Skip)(f"{TAG} tag {'missing' if ivc else 'on'}: {info['tags']}")
    shadow, lucky, size = extras(texts)
    m = {"tile": tile_name, "name": info["name"], "cp": tile_cp, "hp": info["hp"], "candy": candy(texts),
         "types": sorted(type_line(texts)), "shadow": shadow, "lucky": lucky, "size": size, "dynamax": dynamax(texts), "tags": info["tags"]}
    m["species_options"] = sort.identify(m["candy"], set(m["types"]), m["cp"], m["hp"], sort.value(m["name"], shadow))
    m["species"] = sort.pick_species(m["species_options"])
    return m


IVC_FRESH = 12 * 3600  # /ivc's reads this recent stand in for opening the Pokémon (CP or name changed: no match)
ivc_reads = []


def from_ivc(tile_name, tile_cp):
    """what /ivc read on this one's detail screen when it renamed it (its runs' read.json, same phone, last
    IVC_FRESH seconds), as read_member would give it. Each read stands in for one tile. None: open it"""
    if not ivc_reads:
        phone, now = "android" if ui.ANDROID else "ios", time.time()
        for f in sorted(glob.glob(os.path.join(HERE, "..", "ivc", "runs", "*", ivcrun.READ))):
            ivc_reads.extend(r for r in json.load(open(f)) if r["phone"] == phone and now - r["at"] < IVC_FRESH)
        ivc_reads.append(None)  # loaded (none left reads as "nothing to match")
    r = next((r for r in ivc_reads if r and r["cp"] == tile_cp and same_name(r["name"], tile_name)), None)
    if r is None:
        return None
    m = {"tile": tile_name, "name": r["name"], "cp": r["cp"], "hp": r["hp"], "candy": r["candy"], "types": r["types"],
         "shadow": r["shadow"], "lucky": r["lucky"], "size": r["size"], "dynamax": r["dynamax"], "tags": r["tags"]}
    m["species_options"] = sort.identify(m["candy"], set(m["types"]), m["cp"], m["hp"], sort.value(m["name"], m["shadow"]))
    m["species"] = sort.pick_species(m["species_options"])
    if not m["species"]:  # the candy or types weren't read: open it after all
        return None
    ivc_reads.remove(r)
    return m


# ---------- walking a list ----------

def odd_name(n):
    """a tile name that doesn't look like an /ivc name (IV number first, one digit for 0-9% like '9 h', or a move-only name like 'FP*')"""
    return not re.match(r"\d{2}|\d(\s|/|$)|[A-Z]{2}\*", n or "")


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


CHUNKS = [(a, min(a + CHUNK - 1, MAX_DEX)) for a in range(1, MAX_DEX + 1, CHUNK)]


def scan(limit=10 ** 9, only=None):
    """read the IVC Pokémon of every dex chunk (only: just these chunks). Carries on from an earlier scan.json in
    the same run dir: tiles already read are passed over"""
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
        m = from_ivc(n, c)
        if m is not None:
            log(f"tile {i}: {n} CP{c}: /ivc read it just now, not opening it")
            add(m)
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
        add(m)
        return False

    def add(m):
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
    every = only or CHUNKS
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
        save("chunks.json", chunks)  # (no tab switch here: start_search clears the bar and goes back to the top)
        if len(found) >= limit:
            break
    left = {q: f"{c['have']}/{c['want']}" for q, c in chunks.items() if not c["done"]}
    log(f"scanned {len(found)}, {sum(bool(m.get('unrenamed')) for m in found)} still unrenamed; "
        f"chunks not done: {left or 'none'}")


# ---------- 2. pools (search) ----------

SHOWN = {"q": None}  # the search in the bar now: a family's last search is the list its Pokémon get tagged on


def read_search(q, iv_only):
    got, want = run_search(q, iv_only)
    SHOWN["q"] = q
    return got, want


def home(m):
    """the family search this member shows in: its own pool's (shadow or not), else the first one it needs"""
    qs = sort.searches_for(m)
    pool = "shadow" if m["shadow"] else "plain"
    return next((q for q, _, ss in sort.groups(m["species"], pool) if m["species"] in ss and q in qs),
                qs[0] if qs else None)


def pools(members=None):
    """type the searches these members need (default: every scanned one) that the run hasn't typed yet.
    The search most of them show in goes last: its list is still on screen for act"""
    members = [m for m in members or load("scan.json") if m.get("species")]
    homes = Counter(home(m) for m in members)
    queries = sorted(dict.fromkeys(q for m in members for q in sort.searches_for(m)), key=lambda q: homes[q])
    done = load("pools.json") if os.path.exists(os.path.join(base.RUN_DIR, "pools.json")) else {}
    wants = load("counts.json") if os.path.exists(os.path.join(base.RUN_DIR, "counts.json")) else {}
    log(f"{len(queries)} searches, {len(done)} done already")
    if SHOWN["q"] is None:  # the first search of this run: may be on a tag's list or a Pokémon
        front()
        to_search_list()
    for q in queries:
        if q in done:
            continue
        iv_only = not q.endswith(sort.NOT_NOPE)  # gym searches need every CP
        got, want = read_search(q, iv_only)
        if not got and want is None:  # no tiles and no count: the search didn't run
            got, want = read_search(q, iv_only)
            if not got and want is None:
                log(f"  {q}: no tiles and no count twice, not saved (plan will SKIP; rerun pools)")
                to_search_list()
                SHOWN["q"] = None
                continue
        if want is not None and len(got) != want:
            got = closer(q, iv_only, got, want)  # read it once more and keep the closer one
        done[q], wants[q] = got, want
        save("pools.json", done)
        save("counts.json", wants)
        log(f"  {q}: {len(done[q])} tiles, {sum(sort.parse_name(n).iv is not None for n, _ in done[q])} with an IV")
    reread(members, done, wants)


def closer(q, iv_only, got, want):
    """read q again: the read nearer the game's count wins"""
    got2, want2 = read_search(q, iv_only)
    return got2 if want2 is not None and abs(len(got2) - want2) < abs(len(got) - want) else got


REREADS = 2  # extra reads for a search whose miscount would turn a verdict into LEAVE


def reread(members, done, wants):
    """a search read short or long only matters when it could flip a KEEP or NOPE (plan would LEAVE it).
    Read just those again, up to REREADS times each, until one matches the count."""
    results = {k: [tuple(x) for x in v] for k, v in done.items()}
    flips = []
    for m in members:
        if any(q not in results for q in sort.searches_for(m)):
            continue
        verdict, why = sort.decide(m, results)
        if recheck(m, results, wants, verdict, why)[0] == "LEAVE" != verdict:
            flips += [q for q in sort.searches_for(m) if wants.get(q) is not None and wants[q] != len(results[q])]
    flips = list(dict.fromkeys(flips))
    if not flips:
        return
    log(f"{len(flips)} miscounted searches could flip a verdict: reading them again")
    for q in flips:
        for _ in range(REREADS):
            if len(done[q]) == wants[q]:
                break
            done[q] = closer(q, not q.endswith(sort.NOT_NOPE), done[q], wants[q])
        save("pools.json", done)
        log(f"  {q}: {len(done[q])} of {wants[q]} after rereading")


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


def dexes_of(q):
    """'25,26&!alola&!#Nope&!shadow' -> {25, 26}"""
    return {int(d) for d in q.split("&")[0].split(",")}


def unrenamed_check(m, scanned, verdict, why):
    """an IVC Pokémon still named after its species has no IV in the pools: it could beat a KEEP. A KEEP whose
    searches could show one (same dex chunk) is left until /ivc has renamed it. A NOPE stays a NOPE: one more
    rival can only push it further down."""
    if verdict != "KEEP" or not re.search(r"\bspot\b", why[0] if why else ""):  # 98%+, own form, Elite TM, gym CP:
        return verdict, why  # no IV ranking that an unknown IV could beat
    ranges = [r for r in (u.get("dex_range") for u in scanned if u.get("unrenamed")) if r]
    hit = sorted({d for q in sort.searches_for(m) for d in dexes_of(q) if any(a <= d <= b for a, b in ranges)})
    if not hit:
        return verdict, why
    return "LEAVE", [f"would be KEEP, but an IVC Pokémon still named after its species could be dex {hit}: "
                     "run /ivc first"] + why


def plan(quiet=False):
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
            verdict, why = unrenamed_check(m, scanned, verdict, why)
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
    if not quiet:
        print("\n".join(head))
        print(f"table: {os.path.join(base.RUN_DIR, 'plan.txt')}")


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


def plan_key(m):
    return m["tile"], m["cp"], m.get("name"), m.get("species"), m["shadow"], m["lucky"]


def act(limit, members):
    """tag one family's KEEPs and NOPEs on its own search lists (an IVC Pokémon isn't Nope, so it shows there):
    the list still on screen from pools first, then any other list that holds one. -> how many were opened"""
    mine = {plan_key(m) for m in members}
    lists = {}
    for m in load("plan.json"):
        if m["verdict"] in ("KEEP", "NOPE") and plan_key(m) in mine:
            lists.setdefault(home(m) or act_query([m]), []).append(m)
    # what earlier act runs on this run dir did or skipped: a restart doesn't open those again
    has = os.path.exists(os.path.join(base.RUN_DIR, "act.json"))
    progress = load("act.json") if has else {"done": [], "skipped": []}
    for n, c, name, species in progress["done"]:
        for ms in lists.values():
            p = next((p for p in ms if (sort.clean_name(p["tile"]), p["cp"], p["name"], p["species"]) == (n, c, name, species)), None)
            if p:
                ms.remove(p)
                break
    skipped = {tuple(k) for k in progress["skipped"]}
    lists = {q: ms for q, ms in lists.items() if any((sort.clean_name(m["tile"]), m["cp"]) not in skipped for m in ms)}
    if not lists:
        return 0
    pooled = []  # pools and counts, loaded the first time a Pokémon has to be judged again
    opened = [0]
    todo, want = Counter(), {}

    def visit(i, n, c):
        if not todo[(n, c)] or (n, c) in skipped:
            return False
        try:
            return change(i, n, c)
        except NotIVC as e:  # an older keeper with the same name and CP: the IVC one is further down
            log(f"  tile {i}: {n} CP{c} isn't the IVC one ({e}), passing")
            go("close", "list")
            return False
        except Skip:
            skipped.add((n, c))
            progress["skipped"] = sorted(skipped)
            save("act.json", progress)
            raise

    def change(i, n, c):
        """-> True if it left the list on screen"""
        plans = want[(n, c)]
        opened[0] += 1
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
        verdict = m["verdict"]
        if verdict == "KEEP":
            favorite_and_untag()
        else:  # a name can be wrong ('FP*' on a 98% lucky): appraise before any Nope
            keep, ivs, raws, what = base.high_iv()
            if keep:  # 98%+ always keeps
                favorite_and_untag()
                verdict = "KEEP"
                log(f"  the plan said NOPE, appraised {what}: 98%+")
            else:
                base.nope(TAG, now["tags"], only=False, ivs=ivs, raws=raws)  # swap IVC for Nope, keep any other tags
        plans.remove(m)
        todo[(n, c)] -= 1
        progress["done"].append([n, c, m["name"], m["species"]])
        save("act.json", progress)
        log(f"DONE {verdict} {m['name']!r} CP{c} {m['species']}: {m['why'][0] if m['why'] else ''}")
        go("close", "list")
        # a Nope leaves a !#Nope list, anything leaves an #IVC one. On a gym list it stays: passed when it comes up again
        return verdict == "NOPE" or SHOWN["q"].startswith("#")

    for q in sorted(lists, key=lambda q: q != SHOWN["q"]):  # the list on screen first
        todo.clear()
        want.clear()
        for m in lists[q]:
            k = (sort.clean_name(m["tile"]), m["cp"])
            todo[k] += 1
            want.setdefault(k, []).append(m)
        if opened[0] >= limit:
            break
        if q == SHOWN["q"]:
            if search.scrolled:
                search.to_top(ui.capture()[1])
        else:
            SHOWN["q"] = None  # a stop mid-search leaves the bar unknown
            start_search(q)
            SHOWN["q"] = q
        log(f"{q}: {sum(todo.values())} to change")
        digits = all(re.match(r"\d", n) for n, _ in todo)  # IV names sort first: a plain name ends them
        left = lambda: sum(v for k, v in todo.items() if k not in skipped)
        walk_list(visit, stop=lambda n: opened[0] >= limit or not left() or (digits and not re.match(r"\d", n)))
        if left():
            log(f"  left over on {q} (not found): {left()}")
    return opened[0]


# ---------- sort: one dex chunk at a time ----------

SMALL = 60  # an IVC pile this size or less is read in one search, not in 50-dex chunks


def chunks_for(done):
    """a small IVC pile: one chunk, the whole dex (one search, its families typed once). A big one: 50-dex chunks,
    so each is tagged before the next is read. A run keeps the way it started (sorted.json)"""
    began = done or [q.rsplit("&", 1)[1] for q in (load("chunks.json") if os.path.exists(
        os.path.join(base.RUN_DIR, "chunks.json")) else {})]
    if began:  # carrying on: the same way, or the Pokémon read so far wouldn't be in any chunk
        return [(1, MAX_DEX)] if set(began) == {f"1-{MAX_DEX}"} else CHUNKS
    front()
    to_search_list()
    q = f"#{TAG}&!xxl&!xxs"
    _, texts, _ = start_search(q)
    n = result_count(texts)
    log(f"{q}: the game says {n}")
    return [(1, MAX_DEX)] if n is not None and n <= SMALL else CHUNKS
def families(members):
    """members whose searches overlap, together: one family's lists are read, then tagged, before the next family"""
    out = []
    for m in members:
        qs = set(sort.searches_for(m)) or {f"own:{plan_key(m)}"}
        joined = [f for f in out if f[0] & qs]
        for f in joined:
            out.remove(f)
        out.append((qs.union(*(f[0] for f in joined)), [x for f in joined for x in f[1]] + [m]))
    return sorted(out, key=lambda f: min(sort.SPECIES[m["species"]]["dex"] for m in f[1]))


def sort_all(limit, look):
    """per 50-dex chunk: read its IVC Pokémon. Then per family: type its searches, decide, and favorite or Nope
    its IVC ones on the list still on screen. A family is done before the next one's searches are typed, so a stop
    loses nothing: `sort <run dir>` carries on. look: decide only (plan.txt), change nothing"""
    done = load("sorted.json") if os.path.exists(os.path.join(base.RUN_DIR, "sorted.json")) else []
    fams_done = load("families.json") if os.path.exists(os.path.join(base.RUN_DIR, "families.json")) else []
    left = limit
    for a, b in chunks_for(done):
        key = f"{a}-{b}"
        if key in done:
            continue
        scan(only=[(a, b)])
        SHOWN["q"] = None  # scan typed its own search
        members = [m for m in load("scan.json") if m.get("species") and chunk_of(m, a, b)]
        for qs, fam in families(members):
            fkey = "|".join(sorted(qs))
            if fkey in fams_done:
                continue
            pools(fam)
            plan(quiet=True)  # every scanned one so far: the earlier families' are done already (act.json)
            verdicts = Counter(m["verdict"] for m in load("plan.json") if plan_key(m) in {plan_key(f) for f in fam})
            log(f"family {sorted({m['species'] for m in fam})}: {dict(verdicts)}")
            if not look:
                left -= act(left, fam)
            if left <= 0:  # the family may have more to change: not done (a rerun passes over what act.json has)
                log(f"--limit {limit} reached: `sort {base.RUN_DIR}` carries on")
                return
            fams_done.append(fkey)
            save("families.json", fams_done)
        if members:
            plan()  # this chunk's members that need nothing typed (SKIP) get their line in plan.txt too
        done.append(key)
        save("sorted.json", done)
    counts = Counter(m["verdict"] for m in load("plan.json")) if os.path.exists(
        os.path.join(base.RUN_DIR, "plan.json")) else {}
    log(f"sorted every chunk{' (look only: nothing changed)' if look else ''}: {dict(counts)}. "
        f"Table: {os.path.join(base.RUN_DIR, 'plan.txt')}")


def script(a, cmd, limit):
    if cmd == "act-fallen" and not os.path.exists(os.path.join(base.RUN_DIR, "fallen-groups.json")):
        sys.exit("run fallen first, and read plan.txt")
    if cmd == "fallen" and not os.path.exists(os.path.join(base.RUN_DIR, "pools.json")):
        sys.exit("fallen needs a sort run's folder")
    base.start()
    if cmd == "sort":
        sort_all(limit, "--look" in a)
    elif cmd == "fallen":
        fallen.groups(iv_only=True)
        plan()
    elif cmd == "act-fallen":
        act_fallen(limit)
    elif cmd == "search":
        front()
        got, want = run_search(a[1])
        for n, c in got:
            print(f"CP{c:<5} {n}")
        print(f"{len(got)} read, the game says {want}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0].startswith("--"):
        a = ["sort"] + a
    if a[0] not in ("sort", "fallen", "act-fallen", "search"):
        sys.exit(__doc__)
    limit = session.limit(a)
    cmd = a[0]
    given = a[1] if len(a) > 1 and not a[1].startswith("--") and cmd != "search" else None
    new_run_dir(os.path.abspath(given) if given else None)
    session.main(script, a, cmd, limit)
