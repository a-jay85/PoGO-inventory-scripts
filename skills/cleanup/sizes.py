#!/usr/bin/env python3
"""Never-traded XXL and XXS Pokémon don't get Transfer or Nope: they get renamed XXL or xxs and tagged IVC.

  POGO_PHONE=android caffeinate -dimsu python3 sizes.py [--limit N]   sweep the Transfer and Nope tags already given
  caffeinate -dimsu python3 sizes.py [--limit N]                      the iPhone, through iPhone Mirroring

Start with Pokémon GO on the Pokémon screen. Searches #Transfer,#Nope&!traded&xxl, then the same with xxs.
tradeable.py does the same to its own pile before it tags the rest Transfer (shadows.py leaves them out).
Each one is opened. Its size badge must agree with the search, or it's passed over. Then:
  name -> XXL or xxs (/ivc's spelling). A name that already says its size keeps it.
  tags -> IVC on, Transfer and Nope off. Other tags (Old, ...) stay.
/ivc counts an XXL/xxs name as done, and /ivcsort leaves sized IVC ones for the user.
--limit N changes at most N. Log in runs/<time>-sizes/.
"""
import os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
import ui
import run as base
from run import Stop, Skip, log, go, look, wait_for
import search
import cleantrades as ct
from shadows import Pass, swipe_next
from trades import search_exact

IVC, TRANSFER, NOPE = "IVC", "Transfer", "Nope"
NAMES = {"xxl": "XXL", "xxs": "xxs"}  # search term -> nickname, as ivc.make_name spells them
SWEEP = f"#{TRANSFER},#{NOPE}&!traded&%s"


def same(got, want):
    """OCR mixes the case of xxs (xXS) and drops spaces"""
    flat = lambda s: re.sub(r"\s", "", s or "").lower()
    return flat(got) == flat(want)


def walk(find, size, limit):
    """find() runs the search (-> its count). Opens the first one and swipes through: each one gets renamed and
    tagged IVC. -> how many were changed"""
    if not find():
        return 0
    name = NAMES[size]
    go("tile 1", "detail")
    seen, done = set(), 0
    while True:
        _, texts, _, bounds = wait_for("detail")
        info = ui.detail_info(texts)
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
            old = info["name"] or ""
            new = old if re.search(r"xx[ls]", old, re.I) else name
            if new != old:
                base.do_rename(new, same)
            base.set_tags(on=(IVC,), off=(TRANSFER, NOPE))
            done += 1
            log(f"{old} CP{info['cp']} -> {new}, tagged {IVC}")
        except (Pass, Skip) as e:
            log(f"pass {info['name']} CP{info['cp']}: {e}")
        moved = False
        for attempt in range(2):  # next one; a swipe that does nothing twice = end of the list
            swipe_next(bounds)
            for _ in range(10):
                time.sleep(0.12)
                screen, texts, _, _ = look()
                if screen == "detail" and (lambda i: (i["cp"], i["hp"]))(ui.detail_info(texts)) not in seen:
                    moved = True
                    break
            if moved:
                break
        if not moved:
            break
    go("close", "list")
    return done


def sweep(limit):
    for size in NAMES:
        q = SWEEP % size
        n = walk(lambda: (search_exact(q), ct.results())[1], size, limit)
        log(f"{q}: {n} renamed {NAMES[size]} and tagged {IVC}")
        limit -= n
        left = (search_exact(q), ct.results())[1]
        if left:
            log(f"{q}: {left} still there (passed over or --limit): look at them by hand")


if __name__ == "__main__":
    a = sys.argv[1:]
    if any(x != "--limit" and not x.isdigit() for x in a):
        sys.exit(__doc__)
    limit = int(a[a.index("--limit") + 1]) if "--limit" in a else 10 ** 9
    base.new_run_dir(None, os.path.join(HERE, "runs", time.strftime("%Y%m%d-%H%M%S") + "-sizes"))
    try:
        base.start()
        search.to_search_list()
        log(f"signed in as {ct.account()}")
        sweep(limit)
    except Stop as e:
        log(f"STOP: {e}")
        sys.exit(1)
    finally:
        log(f"run folder: {base.RUN_DIR}")
