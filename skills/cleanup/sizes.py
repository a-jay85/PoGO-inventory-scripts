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
import search, session
import cleantrades as ct
from shadows import Pass, swipe_next, press
from trades import search_exact, sheet_rows, still_sheet

IVC, TRANSFER, NOPE = "IVC", "Transfer", "Nope"
NAMES = {"xxl": "XXL", "xxs": "xxs"}  # search term -> nickname, as ivc.make_name spells them
SWEEP = f"#{TRANSFER},#{NOPE}&!traded&%s"


def same(got, want):
    """OCR mixes the case of xxs (xXS) and drops spaces"""
    flat = lambda s: re.sub(r"\s", "", s or "").lower()
    return flat(got) == flat(want)


def retag():
    """IVC on, Transfer and Nope off. base.set_tags only sees the rows on screen, and Transfer can sit below them:
    this scrolls the sheet down until it has seen every one. A tag this account doesn't have is fine, except IVC"""
    base.still_opened("before the tags")
    go("menu", "menu")
    go("TAG", "tags")
    left = {IVC.upper(): True, TRANSFER.upper(): False, NOPE.upper(): False}  # tag -> the tick it should end with
    names = {t.upper(): t for t in (IVC, TRANSFER, NOPE)}
    with base.changing("ticking tags"):  # the row's box, like ct.tag_pile: the word Transfer is never tapped
        same, before = 0, None
        for _ in range(30):
            texts, path, bounds = still_sheet()
            rows = sheet_rows(texts, path)
            T = next((T for T in left if T in rows), None)
            if T:  # one at a time, then read the sheet again: a tick can move the rows
                box, ticked = rows[T]
                v = left.pop(T)
                if ticked is not v:
                    press(box, bounds)
                    for _ in range(20):
                        time.sleep(0.15)
                        _, t2, p2, _ = wait_for("tags")
                        r = sheet_rows(t2, p2)
                        if T in r and r[T][1] is v:
                            break
                    else:
                        base.keep_capture("tick")
                        raise Stop(f"tapped {names[T]} but its tick didn't change")
                    if ui.ANDROID:
                        ui.android.fresh()
                same = 0
                continue
            if not left:
                break
            now = [t[4] for t in texts]
            same = same + 1 if now == before else 0
            if same >= 2:  # the bottom of the sheet
                break
            before = now
            base.drag(0.3, 0.62, 0.3, 0.4, bounds)  # small steps: a big scroll skips rows
            if ui.ANDROID:
                ui.android.fresh()
        texts, _, bounds = still_sheet()
        press(next(t for t in texts if ui.norm(t[4]) == "DONE"), bounds)
        wait_for("detail")
        if IVC.upper() in left:
            raise Stop(f"no {IVC} tag on this account: {TRANSFER} or {NOPE} may be off already, look at it")
        good = lambda t: IVC.upper() in t and not {TRANSFER.upper(), NOPE.upper()} & set(t)
        tags = base.settle(base.detail_tags, good)
        if not good(tags):
            base.keep_capture("tags")
            raise Stop(f"after DONE tags are {tags}, wanted {IVC} on, {TRANSFER} and {NOPE} off")


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
            retag()
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


def script(limit):
    base.start()
    search.to_search_list()
    log(f"signed in as {ct.account()}")
    sweep(limit)


if __name__ == "__main__":
    a = sys.argv[1:]
    if any(x != "--limit" and not x.isdigit() for x in a):
        sys.exit(__doc__)
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="sizes")
    session.main(script, session.limit(a))
