#!/usr/bin/env python3
"""Unattended /ivcsort: keep the best IVC Pokémon (favorite + untick IVC). The rest get their final tag right there
(../shared/door.py, name cleared), or stay as they are on ../shared/runs/not-sure.json. Rules in sort.py.

  caffeinate -dimsu python3 run.py [sort [<run dir>]] [--limit N] [--look]
        read the IVC Pokémon, then per family: type its searches, decide, favorite or door on the list on screen.
        Up to 60 IVC ones: one search reads them all. More: 50 dex numbers at a time. Give the run dir
        to carry on after a stop. --limit N: change N, then stop. --look: decide only (plan.txt), change nothing
  caffeinate -dimsu python3 run.py fallen <run dir>         sort the fallen-out ones into groups (changes nothing)
  caffeinate -dimsu python3 run.py act-fallen <run dir> [--limit N]  tag the fallen-out ones
  python3 run.py search "<query>" [...]                     type searches and print the tiles (testing; later ones edit the bar's end)
  POGO_PHONE=android caffeinate -dimsu python3 run.py ...   (Android phone over USB, see ../pvpc/android.py)

An IVC Pokémon still named after its species is opened once (look): appraised, named as /ivc does, judged and
favorited or sent to the door right there. Start with Pokémon GO
open. A run writes into runs/<time>/ (scan.json, pools.json, plan.txt, plan.json, act.json, log.txt).
"""
import glob, importlib.util, json, os, re, sys, time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "ivc"))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui
import base
from base import Stop, Skip, log, go, back_to_list, front, save, load, steady_detail, \
    extras, candy, type_line, dynamax, set_tags, set_star

spec = importlib.util.spec_from_file_location("ivcrun", os.path.join(HERE, "..", "ivc", "run.py"))
ivcrun = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ivcrun)
import sort
import search, fallen, session, door
from search import to_search_list, start_search, run_search, result_count, looks_same

TAG = "IVC"
DOORS = {}  # dex number ("all": every #IVC one) -> the door.Door whose searches cover it. Made when act first has a
# DOOR of that dex, over every DOOR the plan has then: the plan grows a chunk at a time


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


ivc_reads = []


def from_ivc(tile_name, tile_cp):
    """what was read on this one's detail screen when it was renamed (read.json of /ivc's and /ivcsort's runs, same
    phone, newest first), as read_member would give it. A name and CP still the same is still that Pokémon (a
    power-up changes the CP, a trade clears the name). Each read stands in for one tile. None: open it"""
    if not ivc_reads:
        phone = "android" if ui.ANDROID else "ios"
        files = [f for d in ("ivc", "ivcsort") for f in glob.glob(os.path.join(HERE, "..", d, "runs", "*", ivcrun.READ))]
        ivc_reads.extend(sorted((r for f in files for r in json.load(open(f)) if r["phone"] == phone),
                                key=lambda r: r["at"], reverse=True))
        ivc_reads.append(None)  # loaded (none left reads as "nothing to match")
    r = next((r for r in ivc_reads if r and r["cp"] == tile_cp and same_name(r["name"], tile_name)), None)
    if r is None:
        return None
    m = {"tile": tile_name, "name": r["name"], "cp": r["cp"], "hp": r["hp"], "candy": r["candy"], "types": r["types"],
         "shadow": r["shadow"], "lucky": r["lucky"], "size": r["size"], "dynamax": r["dynamax"], "tags": r["tags"],
         "bars": r.get("bars"), "raws": r.get("raws")}  # the appraisal: act needn't open it again (none in reads before 2026-10-30)
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
    s = (s or "").strip().replace("\"", "*").replace("0", "o").replace("O", "o")  # * can read as ", O as 0 ('84 A 0*')
    return re.sub(r"[.…\s|]+", "", s).lower()


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
            found.append(unrenamed(n, c, in_range))
            log(f"  {n} CP{c} still has its species name: opened when its family is sorted")
            save("scan.json", found)
            return False
        m = from_ivc(n, c)
        if m is not None:
            log(f"tile {i}: {n} CP{c}: read before, not opening it")
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
        flag_unrenamed(found, a, b)
        chunks[q] = {"want": want, "have": have, "done": want is not None and have >= want}
        save("chunks.json", chunks)  # (no tab switch here: start_search clears the bar and goes back to the top)
        if len(found) >= limit:
            break
    left = {q: f"{c['have']}/{c['want']}" for q, c in chunks.items() if not c["done"]}
    log(f"scanned {len(found)}, {sum(bool(m.get('unrenamed')) for m in found)} still unrenamed; "
        f"chunks not done: {left or 'none'}")


def unrenamed(n, c, in_range):
    """an IVC one still named after its species: the name tells the species, the flag searches tell shadow,
    lucky and Dynamax. Its IVs come when it's opened (look)"""
    names = ivcrun.named_species(n)
    opts = [s for s, p in sort.SPECIES.items() if p["speciesName"].split(" (")[0].lower() in names]
    if in_range:
        opts = [s for s in opts if in_range[0] <= sort.SPECIES[s]["dex"] <= in_range[1]] or opts
    return {"tile": n, "name": n, "cp": c, "unrenamed": True, "dex_range": list(in_range) or None,
            "species_options": opts, "species": sort.pick_species(opts) or (opts[0] if opts else None),
            "shadow": False, "lucky": False, "dynamax": False, "size": None}


FLAGS = ("shadow", "lucky", "dynamax")


def flag_unrenamed(found, a, b):
    """the unrenamed ones of chunk a-b: which are shadow, lucky or Dynamax (a search each, over just their dex
    numbers). Their pool searches depend on it, and none of it shows on a tile"""
    us = [m for m in found if m.get("unrenamed") and m.get("species") and chunk_of(m, a, b) and "flags" not in m]
    if not us:
        return
    dex = dex_terms(sort.SPECIES[m["species"]]["dex"] for m in us)
    for f in FLAGS:
        got, _ = run_search(f"#{TAG}&!xxl&!xxs&{dex}&{f}", False, edit=True)
        for m in us:
            m[f] = any(c == m["cp"] and same_name(n, m["tile"]) for n, c in got)
    for m in us:
        m["flags"] = True
        log(f"  {m['tile']} CP{m['cp']}: {m['species']} {' '.join(f for f in FLAGS if m[f])}")
    save("scan.json", found)


# ---------- 2. pools (search) ----------

SHOWN = {"q": None}  # the search in the bar now: a family's last search is the list its Pokémon get tagged on


def read_search(q, iv_only):
    got, want = run_search(q, iv_only, edit=True)
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
    queries = list(dict.fromkeys(q for m in members for q in sort.searches_for(m)))
    head = lambda q: q.rsplit("&", 1)[0]  # searches that differ only in the last term go side by side: the next one
    top = {}                              # edits the bar's end (search.edit_tail), it isn't typed whole
    for q in queries:
        top[head(q)] = max(top.get(head(q), 0), homes[q])
    queries.sort(key=lambda q: (top[head(q)], head(q), homes[q], q))
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
    """a search read short or long only matters when it could flip a KEEP or DOOR (plan would LEAVE it).
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
    if not qs or verdict not in ("KEEP", "DOOR"):
        return verdict, why
    best = lambda t: (max(v for v in (sort.parse_name(t[0]).iv, sort.parse_name(t[0]).purified, -1) if v is not None), t[1])
    worst = dict(results)
    for q in qs:
        k = wants[q] - len(results[q])
        if k > 0 and verdict == "KEEP":
            worst[q] = results[q] + [("100", 99999)] * k
        elif k < 0 and verdict == "DOOR":
            worst[q] = sorted(results[q], key=best, reverse=True)[-k:]
    if worst == results:
        return verdict, why
    v2, _ = sort.decide(m, worst)
    if v2 == verdict:
        return verdict, why
    off = ", ".join(f"{q} read {len(results[q])} of {wants[q]}" for q in qs)
    return "LEAVE", [f"would be {verdict}, but a search was misread ({off}) and that could flip it"] + why


def twin_check(m, results, verdict, why):
    """a DOOR beaten by a tile read two ways ('98 ADBS V' and '98 AD BS*', same IV and CP) may be beaten by one
    Pokémon counted twice. If taking one of each such pair out flips it, leave it."""
    if verdict != "DOOR":
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
    return "LEAVE", [f"would be DOOR, but {', '.join(pairs)} may be one Pokémon read twice"] + why


def dexes_of(q):
    """'25,26&!alola&!#Nope&!shadow' -> {25, 26}"""
    return {int(d) for d in q.split("&")[0].split(",")}


def unrenamed_dexes(u):
    """the dex numbers an unrenamed one's searches cover: its name's species and their families (a 'Happiny' is
    in the Blissey searches). Empty when the name is no species"""
    names = ivcrun.named_species(u["tile"])
    sids = [s for s, p in sort.SPECIES.items() if p["speciesName"].split(" (")[0].lower() in names]
    return {sort.SPECIES[x]["dex"] for s in sids for line in sort.family(s) for x in line if x in sort.SPECIES}


def unrenamed_check(m, scanned, verdict, why):
    """an IVC Pokémon still named after its species has no IV in the pools: it could beat a KEEP. A KEEP whose
    searches could show one (its name's family, or, a name that's no species, the same dex chunk) is left until
    /ivc has renamed it. A DOOR stays a DOOR: one more rival can only push it further down."""
    if verdict != "KEEP" or not re.search(r"\bspot\b", why[0] if why else ""):  # 98%+, own form, Elite TM, gym CP:
        return verdict, why  # no IV ranking that an unknown IV could beat
    could, ranges = set(), []  # (one Happiny read in a one-search scan of 1-1025 held back 23 KEEPs, 2026-10-30)
    for u in (u for u in scanned if u.get("unrenamed")):
        dexes = unrenamed_dexes(u)
        could |= dexes
        if not dexes and u.get("dex_range"):
            ranges.append(u["dex_range"])
    hit = sorted({d for q in sort.searches_for(m) for d in dexes_of(q)
                  if d in could or any(a <= d <= b for a, b in ranges)})
    if not hit:
        return verdict, why
    return "LEAVE", [f"would be KEEP, but an IVC Pokémon still named after its species could be dex {hit}: "
                     "run /ivc first"] + why


def plan(quiet=False):
    scanned, results = load("scan.json"), {k: [tuple(x) for x in v] for k, v in load("pools.json").items()}
    wants = load("counts.json") if os.path.exists(os.path.join(base.RUN_DIR, "counts.json")) else {}
    out, lines, counts = [], [], Counter()
    for m in scanned:
        if m.get("done"):
            verdict, why = "DONE", [f"{m['done']} when it was opened and named"]
        elif m.get("unrenamed") and not (m.get("species") and m.get("flags")):
            verdict, why = "SKIP", ["still has its species name, and the name is no species: run /ivc first"]
        elif m.get("unrenamed"):
            verdict, why = ("LOOK", ["still has its species name: open, appraise, name and judge it"]) \
                if all(q in results for q in sort.searches_for(m)) else ("SKIP", ["a pool search is missing"])
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
              "GuaranteedLucky / Old / the door; act checks each one again on the detail screen first."]
    lines += [f"  {f['name']!r:16} CP{f['cp']:<5} {'shadow ' if f['shadow'] else ''}{'/'.join(f['species'])}: {f['why'][0]}"
              for f in fallen]
    grouped = load("fallen-groups.json") if os.path.exists(os.path.join(base.RUN_DIR, "fallen-groups.json")) else None
    if grouped:
        lines += ["", "FALLEN OUT, by group (from `run.py fallen`):"] + \
            [f"  {g}: {sum(len(v) for v in grouped[g].values())}" for g in grouped]
    unrenamed = counts["SKIP"] and sum(bool(m.get("unrenamed")) and not m.get("flags") for m in scanned)
    head = ([f"WARNING: {unrenamed} IVC Pokémon have a name that's no species. Run /ivc on them first: "
             "until then they don't count in any pool, so too many get kept."] if unrenamed else []) + [f"{dict(counts)}", "KEEP = favorite + untick IVC.  DOOR = its final tag at the door (or left as is, not sure).  LOOK = still named after its species: opened once, named, judged and tagged right there.  DONE = that happened this run.  LEAVE/SKIP = untouched.", ""]
    with open(os.path.join(base.RUN_DIR, "plan.txt"), "w") as f:
        f.write("\n".join(head + lines) + "\n")
    if not quiet:
        print("\n".join(head))
        print(f"table: {os.path.join(base.RUN_DIR, 'plan.txt')}")


# ---------- fallen out ----------
# Older Pokémon (no IVC tag) that the new keepers push out of the top. Not traded and caught 2016-2020 ->
# GuaranteedLucky (a trade is guaranteed lucky). Not traded and older than OLD_DAYS -> Old. Anything else
# (traded: a Pokémon can only be traded once, or newer) -> star off, its final tag at the door. Shiny and costume
# ones are never touched.

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
    """tiles with an /ivc name, no IVC tag, that come out DOOR for every species the search could have shown.
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
            if verdicts and all(v == "DOOR" for v, _ in verdicts.values()):
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
    FALLEN_SPECIES[(n, c)] = [m["species"]]
    FALLEN_RANK[(n, c)] = lucky_rank(m)
    verdict, why = judge(m, results, wants)
    return verdict == "DOOR", f"{verdict} {m['species']} ({why[0] if why else ''})"


FALLEN_SPECIES = {}  # (tile name, CP) -> [species id], as recheck_fallen read it: the door judges that one
FALLEN_RANK = {}  # (tile name, CP) -> a lucky one's rank (lucky_rank), as recheck_fallen judged it


def act_fallen(limit):
    fallen.act(limit, recheck_fallen, TAG, lambda n, c: FALLEN_SPECIES[(n, c)], gym_top20=False,
               iv_top=lambda n, c: FALLEN_RANK[(n, c)],
               stop=lambda n: not re.match(r"\d", n), odd=odd_name)


# ---------- 4. act ----------

def favorite_and_untag():
    set_star(True)
    set_tags(off=[TAG])


def lucky_rank(m):
    """a DOOR here is out of the lucky rule's top 5/6 (sort.decide runs it for a lucky one; a strong line's plain
    spots are the same 5/6): False. With no IV in its name, or read as not lucky on a weak line, it was never
    ranked: None, the door leaves it not sure"""
    ranked = m["lucky"] or all(sort.strong(line)[0] for line in sort.lines_of(m["species"]))
    return False if ranked and sort.value(m["name"], m["shadow"]) is not None else None


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


def load_plan():
    """plan.json, with a run folder from before 2026-10-30 read the same: its DOOR was called NOPE"""
    return [dict(m, verdict="DOOR") if m["verdict"] == "NOPE" else m for m in load("plan.json")]


def plan_key(m):
    return m["tile"], m["cp"], m.get("name"), m.get("species"), m.get("shadow"), m.get("lucky")  # (unrenamed: neither)


def dex_of(m):
    return sort.SPECIES[m["species"]]["dex"]


def door_for(m):
    """the door whose searches cover this one's dex, if any yet"""
    return DOORS.get("all") or DOORS.get(dex_of(m))


ACTS = ("KEEP", "DOOR", "LOOK")  # the verdicts act opens a Pokémon for


def renamed_in_pools(results, n, c, name, own):
    """the pools showed this one as its species name (n): it's name now. own: its searches, where it belongs even
    if no tile of it was read"""
    for q, tiles in results.items():
        j = next((j for j, (t, tc) in enumerate(tiles) if tc == c and ivcrun.untouched(t) and same_name(t, n)), None)
        if j is not None:
            tiles[j] = (name, c)
        elif q in own:
            tiles.append((name, c))


def look(i, n, c, p, members):
    """a LOOK: open it once, appraise and name it as /ivc does, judge it against the pools right there, and favorite
    it or take it to the door while its detail screen is open. -> True if it left the list on screen"""
    r = ivcrun.read_one(i, n, c)
    info, texts, name = r["info"], r["texts"], r["name"]
    sp = [s for s in r["sp"] if s in sort.SPECIES]
    m = dict(p, unrenamed=False, hp=info["hp"], candy=candy(texts), types=sorted(type_line(texts)), shadow=r["shadow"],
             lucky=r["lucky"], size=r["size"], dynamax=dynamax(texts), tags=info["tags"],
             species_options=sp or p["species_options"], bars=list(r["bars"]), raws=list(r["raws"]) if r["raws"] else None)
    for k in ("verdict", "why", "flags"):
        m.pop(k, None)
    m["species"] = sort.pick_species(m["species_options"]) or p["species"]
    if m["species"] not in sp and sp:
        log(f"  {n!r} is {sp}, its name said {p['species']}")
    if name == "->PvpC":
        ivcrun.retag("PvpC")
        verdict, gone, why = "PvpC", "PvpC", ["IV too low to show, good for PvP: /pvpc names it"]
    elif name is None:  # IV too low to show: nothing to name it, the door gives its final tag (as /ivc does)
        verdict, why = "DOOR", ["IV too low to show"]
        if not door_for(m):
            raise Skip(f"a {m['species']}: outside what the door's searches covered, next run")
        gone = door_for(m).judge(info, texts, sp or [m["species"]], r["ivs"], (n, c), size=r["size"], raws=r["raws"])
    else:
        ivcrun.do_rename(name, ivcrun.same_name)
        ivcrun.keep_read(r)  # a later run takes it from here instead of opening it
        m["name"] = m["tile"] = name
        results = {k: [tuple(x) for x in v] for k, v in load("pools.json").items()}
        wants = load("counts.json") if os.path.exists(os.path.join(base.RUN_DIR, "counts.json")) else {}
        renamed_in_pools(results, n, c, name, set(sort.searches_for(m)))
        save("pools.json", results)
        if any(q not in results for q in sort.searches_for(m)):
            verdict, why = "LEAVE", ["named; a pool search it needs is missing: judged after the family's searches"]
        else:
            verdict, why = judge(m, results, wants)
            others = [x for x in load("scan.json") if plan_key(x) != plan_key(p)]
            verdict, why = unrenamed_check(m, others, verdict, why)  # a KEEP waits for the family's other unnamed ones
        gone = verdict
        if verdict == "KEEP":
            favorite_and_untag()
        elif verdict == "DOOR" and not door_for(m):
            verdict, gone = "LEAVE", "LEAVE"
            why = ["named; DOOR, but outside what the door's searches covered: next run"] + why
        elif verdict == "DOOR":
            info, texts, _ = steady_detail()
            gone = door_for(m).judge(info, texts, [m["species"]], r["ivs"], (name, c), size=r["size"], raws=r["raws"],
                                     gym_top20=False, clear=True, iv_top=lucky_rank(m))
    log(f"DONE LOOK -> {verdict}{'' if gone == verdict else ' -> ' + gone} {m['name']!r} CP{c} {m['species']}: "
        f"{why[0] if why else ''}")
    if verdict not in ("LEAVE", "SKIP"):  # a LEAVE stays a member: planned again with the family
        m["done"] = verdict
    found = load("scan.json")
    for x in found + members:
        if plan_key(x) == plan_key(p):
            x.clear()
            x.update(m)
    save("scan.json", found)
    # an #IVC list loses it when IVC comes off. A name list: named (moves up past what's walked) or named and
    # cleared again (back where it was), so the next tile keeps its place
    return bool(SHOWN["q"] and SHOWN["q"].startswith("#")) and gone not in ("LEAVE", "SKIP", door.UNSURE)


def act(limit, members):
    """tag one family's KEEPs and DOORs on its own search lists (an IVC Pokémon has no Nope, so it shows there):
    the list still on screen from pools first, then any other list that holds one. -> (how many were opened,
    how many weren't found: the family isn't done then, a rerun walks its lists again)"""
    mine = {plan_key(m) for m in members}
    lists, plans = {}, [m for m in load_plan() if m["verdict"] in ACTS and plan_key(m) in mine]
    if any(m["verdict"] in ("DOOR", "LOOK") and not door_for(m) for m in plans):  # (a LOOK may turn out DOOR)
        # its searches only over the dex numbers sent to the door and not covered yet: a short list reads right more often
        new = {dex_of(m) for m in load_plan() if m["verdict"] in ("DOOR", "LOOK") and m.get("species") in sort.SPECIES
               and not door_for(m)}
        dex = dex_terms(new)
        scope = f"#{TAG}&{dex}" if len(dex) <= ACT_QUERY_MAX else None
        was = next(iter(DOORS.values()), None)
        made = door.Door(TAG, scope=scope, account=was and was.account)  # (its searches leave the bar on something else)
        DOORS.update(dict.fromkeys(new, made) if scope else {"all": made})
        SHOWN["q"] = None
    listed = next(iter(DOORS.values())).listed() if DOORS else Counter()  # not sure last time, same rules: passed over
    for m in plans:
        k = (sort.clean_name(m["tile"]), m["cp"])
        if m["verdict"] == "DOOR" and listed[k]:
            listed[k] -= 1
            log(f"  {m['name']!r} CP{m['cp']}: on the not-sure list, passed over")
            continue
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
        return 0, 0, 0
    pooled = []  # pools and counts, loaded the first time a Pokémon has to be judged again
    opened, missed, looked = [0], 0, [0]
    todo, want = Counter(), {}

    def visit(i, n, c):
        if not todo[(n, c)]:  # the scan read the tile another way ('89 al' for '89 a'): same CP, either name close
            n = next((k[0] for k, v in todo.items() if v and k[1] == c and any(
                same_name(n, x) for p in want[k] for x in (k[0], p["name"]))), n)
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
        p = next((p for p in plans if p["verdict"] == "LOOK"), None)
        if p:
            gone = look(i, n, c, p, members)
            looked[0] += 1
            plans.remove(p)
            todo[(n, c)] -= 1
            progress["done"].append([n, c, p["name"], p["species"]])
            save("act.json", progress)
            go("close", "list")
            return gone
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
                if verdict not in ("KEEP", "DOOR"):
                    raise Skip(f"judged again with the right shadow/lucky: {verdict} {why[:1]}")
                plans.remove(p)
                m = dict(fixed, verdict=verdict, why=why)
                plans.append(m)
        if not m:
            raise Skip(f"detail doesn't match the plan: {now['name']!r} {now['species']}")
        verdict = gone = m["verdict"]
        if verdict == "DOOR" and not door_for(m):
            raise Skip("judged DOOR here, outside what the door's searches covered: next run")  # (no read would mean 'no')
        if verdict == "KEEP":
            favorite_and_untag()
        else:  # a name can be wrong ('FP*' on a 98% lucky): appraise before the door, unless /ivc just did
            if m.get("bars"):
                log(f"  /ivc's appraisal: {'/'.join(map(str, m['bars']))}, not appraising again")
            keep, ivs, raws, what = base.high_iv(m.get("bars"), m.get("raws"))
            if keep:  # 98%+ always keeps
                favorite_and_untag()
                verdict = gone = "KEEP"
                progress.setdefault("kept98", []).append([n, c])
                log(f"  the plan said DOOR, appraised {what}: 98%+")
            else:  # sort.decide ran the gym rule: a gym defender's DOOR is out of both top 20s
                info, texts, _ = steady_detail()
                gone = door_for(m).judge(info, texts, [m["species"]], ivs, (n, c), size=now["size"], raws=raws,
                                  gym_top20=False, clear=True, iv_top=lucky_rank(m))
                if gone in ("keep", door.UNSURE) or gone.startswith("left for"):  # still here: a rival in the pools
                    progress.setdefault("stayed", []).append([n, c])
        plans.remove(m)
        todo[(n, c)] -= 1
        progress["done"].append([n, c, m["name"], m["species"]])
        save("act.json", progress)
        log(f"DONE {verdict}{'' if gone == verdict else ' -> ' + gone} {m['name']!r} CP{c} {m['species']}: "
            f"{m['why'][0] if m['why'] else ''}")
        go("close", "list")
        # a cleared name leaves the IV names (a list sorted by Name), IVC off leaves an #IVC list. Left as it is, or
        # on a gym list, it stays: passed when it comes up again
        if gone == door.UNSURE:
            return False
        return gone not in (verdict, "keep") and not gone.startswith("left for") or SHOWN["q"].startswith("#")

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
        # sorted by Name, IV names come first: a plain name after them ends them. Only after one: a list not sorted
        # by Name (seen 2026-10-27, 'Dodrio' on top) is walked to its end
        digits, iv_seen = all(re.match(r"\d", n) for n, _ in todo), [False]
        left = lambda: sum(v for k, v in todo.items() if k not in skipped)

        def stop(n):
            iv = bool(re.match(r"\d", n))
            iv_seen[0] |= iv
            return opened[0] >= limit or not left() or (digits and iv_seen[0] and not iv)
        walk_list(visit, stop=stop)
        if left() and opened[0] < limit:
            log(f"  left over on {q} (not found): {left()}")
            missed += left()
    return opened[0], missed, looked[0]


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
    """per 50-dex chunk: read its IVC Pokémon. Then per family: type its searches, decide, and favorite or door
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
        unfinished = False
        SHOWN["q"] = None  # scan typed its own search
        members = [m for m in load("scan.json") if m.get("species") and chunk_of(m, a, b)]
        for qs, fam in families(members):
            fkey = "|".join(sorted(qs))
            if fkey in fams_done:
                continue
            missed = 0
            for _ in range(2):  # the LOOKs first named, then the KEEPs they held back (one open each all the same)
                rest = [m for m in fam if not m.get("done")]
                if not rest:
                    break
                pools(rest)
                plan(quiet=True)  # every scanned one so far: the earlier families' are done already (act.json)
                verdicts = Counter(m["verdict"] for m in load_plan() if plan_key(m) in {plan_key(f) for f in fam})
                log(f"family {sorted({m['species'] for m in fam})}: {dict(verdicts)}")
                if look:
                    break
                n, missed_now, looked = act(left, fam)
                left -= n
                missed += missed_now
                if not looked or left <= 0:
                    break
            if left <= 0:  # the family may have more to change: not done (a rerun passes over what act.json has)
                log(f"--limit {limit} reached: `sort {base.RUN_DIR}` carries on")
                return
            if not look and missed:  # not done (an IVC one not found): a rerun tries again
                unfinished = True
                continue
            fams_done.append(fkey)
            save("families.json", fams_done)
        if members:
            plan()  # this chunk's members that need nothing typed (SKIP) get their line in plan.txt too
        if unfinished:
            log(f"{key}: a family isn't done (an IVC one not found): `sort {base.RUN_DIR}` tries again")
            continue
        done.append(key)
        save("sorted.json", done)
    counts = Counter(m["verdict"] for m in load_plan()) if os.path.exists(
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
        for q in a[1:]:  # (more than one: each after the first edits the bar's end, like a family's searches)
            got, want = run_search(q, edit=True)
            for n, c in got:
                print(f"CP{c:<5} {n}")
            print(f"{q}: {len(got)} read, the game says {want}")


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
