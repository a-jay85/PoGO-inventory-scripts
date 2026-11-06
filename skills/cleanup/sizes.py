#!/usr/bin/env python3
"""An XXL Pokémon, traded or not, is kept: favorite on, its trade, Transfer and IVC tags off (it has value in showcases, the
user 2026-11-04). A never-traded XXS one doesn't get Transfer: it's renamed xxs and tagged IVC. A never-traded trade
evolution gets GIV instead.

  POGO_PHONE=android caffeinate -dimsu python3 sizes.py [--limit N]   sweep the Transfer tags already given
  caffeinate -dimsu python3 sizes.py [--limit N]                      the iPhone, through iPhone Mirroring

Start with Pokémon GO on the Pokémon screen. Searches #&xxl&!#PvpC (every tagged XXL: /pvpc judges its own),
then #Transfer&!traded&xxs. tradeable.py, cleantrades.py and /ivc do the same to their own piles.
Each one is opened. Its size badge must agree with the search, or it's passed over. Then:
  XXL: favorite on, the tags in rules.XXL_OFF off. Its name and other tags stay.
  xxs: named xxs (/ivc's spelling; a name that already says its size keeps it). IVC on, Transfer off. Other tags stay.
/ivc counts an xxs name as done, and leaves sized IVC ones for the user once named.
Then, signed in as HashTagAJay only (CyrillJan wants the XP, HashTagAJay doesn't, 2026-11-02), the never-traded
trade evolutions (free to evolve once traded, cleantrades' TRADE_EVOS), not shadows:
#Transfer&!traded&!shadow&!xxl&!xxs&!#GIV&<dex numbers> -> GIV on, Transfer off, all at once (SELECT ALL).
--limit N changes at most N. Log in runs/<time>-sizes/.

Run it once per account. 'traded' may miss trades from before Oct 2020 (SEARCH.md), so a very old trade could slip in.
"""
import os, re, sys, time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui
import base
from base import Stop, Skip, log, go, wait_for
import search, session, home
import cleantrades as ct
from taps import Pass, next_one, press
from tagsheet import search_exact, tag_chips
from savedsearch import results, tag_pile
from rules import EVO_FOR, TRADE_EVOS, NAMES, TRANSFER, xxl_off

IVC = "IVC"
SWEEP = f"#{TRANSFER}&!traded&%s"
GIV = "GIV"
XXL_SWEEP = "#&xxl&!#PvpC"
EVO_SWEEP = f"#{TRANSFER}&!traded&!shadow&!xxl&!xxs&!#{GIV}&{TRADE_EVOS}"


def same(got, want):
    """OCR mixes the case of xxs (xXS) and drops spaces"""
    flat = lambda s: re.sub(r"\s", "", s or "").lower()
    return flat(got) == flat(want)


def keep_xxl(info, texts):
    """the open detail page of an XXL one: favorite on, its trade, Transfer and IVC tags off"""
    off = xxl_off(tag_chips(texts))
    base.set_star(True)
    if off:
        base.set_tags(off=off)
    log(f"{info['name']} CP{info['cp']}: a favorite{', ' + '/'.join(off) + ' off' if off else ''}")


def name_and_tag(info, size):
    """the open detail page of a never-traded xxs one: its size in the name, IVC on, Transfer off"""
    old = info["name"] or ""
    new = old if re.search(r"xx[ls]", old, re.I) else NAMES[size]
    if new != old:
        base.do_rename(new, same)
    base.set_tags(on=[IVC], off=[TRANSFER])
    log(f"{old} CP{info['cp']} -> {new}, tagged {IVC}")


def walk(find, size, limit):
    """find() runs the search (-> its count). Opens the first one and swipes through. xxl: each one is kept. xxs: each
    one gets renamed and tagged IVC. -> how many were changed"""
    if not find():
        return 0
    go("tile 1", "detail")
    seen, done = set(), 0
    while True:
        _, texts, _, bounds = wait_for("detail")
        info, texts, _ = base.steady_detail()  # (right after the swipe the page is still sliding in)
        me = (info["cp"], info["hp"])  # (not the name: it changes)
        if me in seen:
            break
        seen.add(me)
        base.OPENED["who"] = base.who(info)  # the swipe moved here on purpose: rename and tags check against this one
        try:
            if done >= limit:
                log(f"--limit {limit} reached")
                break
            badge = base.extras(texts)[2]
            if (badge or "").lower() != size:
                raise Pass(f"the search says {size}, the badge reads {badge}")
            if size == "xxl":
                keep_xxl(info, texts)
            else:
                name_and_tag(info, size)
            done += 1
        except (Pass, Skip) as e:
            log(f"pass {info['name']} CP{info['cp']}: {e}")
        if not next_one(bounds, lambda t: (lambda i: (i["cp"], i["hp"]))(ui.detail_info(t)) not in seen):
            break
    go("close", "list")
    return done


def keep_search(q, limit):
    """every XXL one in a typed search is kept -> how many"""
    n = walk(lambda: (search_exact(q), results())[1], "xxl", limit)
    log(f"{q}: {n} kept")
    return n


def sweep(limit, who):
    n = keep_search(XXL_SWEEP, limit)
    limit -= n
    for size in NAMES:
        q = SWEEP % size
        n = walk(lambda: (search_exact(q), results())[1], size, limit)
        log(f"{q}: {n} renamed {NAMES[size]} and tagged {IVC}")
        limit -= n
        left = (search_exact(q), results())[1]
        if left:
            log(f"{q}: {left} still there (passed over or --limit): look at them by hand")
    # then a never-traded trade evolution (free to evolve once traded): GIV, Transfer off. After the sizes: one
    # passed over there stays out. Not a shadow: it can't be traded. Only toward EVO_FOR, who wants the XP
    if who != EVO_FOR:
        tag_pile(TRANSFER, GIV, off=[TRANSFER], query=EVO_SWEEP)


def script(limit):
    base.start()
    search.to_search_list()
    who = home.trainer()
    search.to_search_list()  # (trainer() can end on the map)
    log(f"signed in as {who}")
    sweep(limit, who)


if __name__ == "__main__":
    a = sys.argv[1:]
    if any(x != "--limit" and not x.isdigit() for x in a):
        sys.exit(__doc__)
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="sizes")
    session.main(script, session.limit(a))
