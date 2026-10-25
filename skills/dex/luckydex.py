#!/usr/bin/env python3
"""Put HashTagAJay's missing-lucky list into CyrillJan's saved search Luckydex. Android only for now.

  POGO_PHONE=android caffeinate -dimsu python3 luckydex.py         CyrillJan signed in on the Pixel
  POGO_PHONE=android caffeinate -dimsu python3 luckydex.py check   only step 5: changes nothing

The search is the newest lucky /dex run of HashTagAJay (dex.latest) + SAFE, the terms that keep the Pokémon that
matter out of a trade. A saved search can't be edited, only renamed or removed. So:
 1. Type the new search, then clear it with the bar's (x): only then does it show under Recent (See More).
 2. Hold the newest Recent search: it's saved as a favorite, named after its start ('369,377,44...').
 3. Hold the old Luckydex, Remove, YES. (12 favorites max: when full, this goes first.)
 4. Hold the new one, Rename, 'Luckydex', OK.
 5. Run Luckydex: the same count, and the bar holds the list's start and SAFE's end.
After a Rename or Remove the panel shows Recent: it's switched back to Favorite each time.
Log in runs/<time>-luckydex/.
"""
import os, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
sys.path.insert(0, os.path.join(HERE, "..", "cleanup"))
import ui
import run as base
from run import Stop, log, keep_capture
import home, search, session
import dex
import cleantrades as ct

OWNER, SOURCE = "CyrillJan", "HashTagAJay"  # the shortcut is OWNER's, the list SOURCE's Lucky page
NAME = "Luckydex"
SAFE = "&!#&!favorite&!traded&!shadow&!shiny&!XXL&!4*&!3*&"  # the user's: never trade these away
MAX_FAVORITES = 12
SEE = (0.88, 0.234)  # See More / See Less, right of the panel's header
RECENT_X = 0.165  # the leftmost (newest) Recent search
BUTTON_UP = 0.055  # a shortcut's round button sits this far above its label
HOLD_MS = 900
BOX_X = (0.5, 0.937)  # the round X that closes the Manage Favorite Search box
TOO_MANY = ct.key("too many search")  # 'You have too many search queries favorited...', a banner for a few seconds


def hold(fx, fy, bounds):
    """a long press: the Manage Favorite Search box on a favorite, a save on a Recent search"""
    base.click(fx, fy, bounds, ms=HOLD_MS)


def read():
    path, bounds = ui.capture()
    texts = ui.ocr(path)
    guard(texts, bounds)
    return texts, bounds


def guard(texts, bounds):
    """a stray long press on the list selects a Pokémon, and a tap at the bottom then lands on TRANSFER: never"""
    j = ui.joined(texts)
    if "TRANSFER" in j and ("PROFESSOR" in j or re.search(r"TRANSFER\s*\(\d+\)", j)):
        cancel = next((t for t in texts if ui.norm(t[4]) == "CANCEL"), None)
        if cancel:
            search.click(cancel[0] + cancel[2] / 2, cancel[1] + cancel[3] / 2, bounds)
        keep_capture("transfer")
        raise Stop("a transfer showed up: canceled it, stopping")


def header(texts):
    """the panel's header: 'favorite', 'recent' or None (not the panel)"""
    for t in texts:
        if 0.2 < t[1] < 0.26 and t[0] < 0.3:
            w = ui.norm(t[4])
            if w in ("FAVORITE", "RECENT"):
                return w.lower()
    return None


def view(want):
    """the open panel on its Favorite or Recent page, keyboard down. -> texts, bounds"""
    for _ in range(8):
        time.sleep(0.6)
        texts, bounds = read()
        if any(ui.norm(t[4]) == "MANAGE FAVORITE SEARCH" for t in texts):
            search.click(*BOX_X, bounds)
            continue
        if TOO_MANY in ct.key(ui.joined(texts)):  # 12 already. Its banner blurs the labels under it: wait it out
            log("  the game says there are too many favorites")
            time.sleep(1.5)
            continue
        if ui.ANDROID and any(t[4].strip() == "?123" and t[1] > 0.5 for t in texts):
            base.key("back")  # hides the keyboard only: the panel stays
            continue
        h = header(texts)
        if h == want:
            return texts, bounds
        if h:
            search.click(*SEE, bounds)
            continue
        break
    keep_capture("view")
    raise Stop(f"the search panel's {want} page didn't show")


def handle(q):
    """a new favorite's label is the search's start ('369,377,44...'): this much of it finds it with find_label,
    also inside a row OCR read as one box"""
    return q[:7]


def keyed(q):
    return ct.key(handle(q))


def unnamed(texts, q):
    """a favorite still named after q's start (not renamed yet)?"""
    return ct.find_label(ct.labels(texts), handle(q)) is not None


def manage(name, action):
    """hold a favorite, tap Rename or Remove in its box. -> texts, bounds of what opened"""
    for _ in range(3):  # OCR now and then misreads a label ('Luckyaex')
        texts, bounds = view("favorite")
        lab = ct.find_label(ct.labels(texts), name)
        if lab:
            break
    else:
        raise Stop(f"no {name!r} favorite to {action.lower()}: {sorted(ct.labels(texts))}")
    hold(lab[0], lab[1] - BUTTON_UP, bounds)
    for _ in range(6):
        time.sleep(0.5)
        texts, bounds = read()
        row = next((t for t in texts if t[4].strip().upper() == action.upper() and t[1] > 0.6), None)
        if row and any(ui.norm(t[4]) == "MANAGE FAVORITE SEARCH" for t in texts):
            search.click(row[0] + row[2] / 2, row[1] + row[3] / 2, bounds)
            time.sleep(1.2)
            return read()
    keep_capture("manage")
    raise Stop(f"holding {name!r} didn't open the Manage Favorite Search box")


def remove(name):
    texts, bounds = manage(name, "Remove")
    yes = next((t for t in texts if ui.norm(t[4]) == "YES"), None)
    if not (yes and "REMOVE THIS" in ui.joined(texts)):
        keep_capture("remove")
        raise Stop(f"no 'remove this search' box for {name!r}")
    search.click(yes[0] + yes[2] / 2, yes[1] + yes[3] / 2, bounds)
    texts, _ = view("favorite")
    if ct.find_label(ct.labels(texts), name):
        raise Stop(f"{name!r} is still a favorite after Remove")
    log(f"removed {name!r}")


def rename(name, to):
    texts, bounds = manage(name, "Rename")
    if "SET SEARCH NAME" not in ui.joined(texts):
        keep_capture("rename")
        raise Stop("no Set Search Name box")
    ui.android.type_text(to)
    for _ in range(6):
        time.sleep(0.5)
        texts, bounds = read()
        if any(ct.key(t[4]) == ct.key(to) for t in texts if t[1] < 0.5):
            break
    else:
        keep_capture("rename")
        raise Stop(f"{to!r} didn't show in the Set Search Name box")
    base.key("return")  # the keyboard goes, the box stays
    for _ in range(6):
        time.sleep(0.6)
        texts, bounds = read()
        ok = next((t for t in texts if ui.norm(t[4]) == "OK" and 0.35 < t[0] + t[2] / 2 < 0.65 and t[1] < 0.6), None)
        if ok and "SET SEARCH NAME" in ui.joined(texts) and not any(t[4].strip() == "?123" for t in texts):
            search.click(ok[0] + ok[2] / 2, ok[1] + ok[3] / 2, bounds)
            break
    else:
        keep_capture("rename")
        raise Stop("no OK in the Set Search Name box")
    texts, _ = view("favorite")
    if not ct.find_label(ct.labels(texts), to):
        raise Stop(f"no {to!r} favorite after Rename: {sorted(ct.labels(texts))}")
    log(f"renamed {name!r} to {to!r}")


def save_recent(q, n):
    """the newest Recent search must be q (its start, its count): hold it, and it's a favorite"""
    texts, bounds = view("recent")
    rec = next(t[1] for t in texts if header(texts) and ui.norm(t[4]) == "RECENT")
    row = sorted((t for t in texts if rec + 0.08 < t[1] < rec + 0.16 and not re.fullmatch(r"[\d,]+", t[4].strip())),
                 key=lambda t: t[0])
    first = row[0][4].split()[0] if row else ""
    count = next((int(t[4].replace(",", "")) for t in texts if rec + 0.12 < t[1] < rec + 0.2 and t[0] < 0.3
                  and re.fullmatch(r"[\d,]+", t[4].strip())), None)
    if not ct.key(first).startswith(keyed(q)) or (count is not None and count != n):
        keep_capture("recent")
        raise Stop(f"the newest Recent search reads {first!r} ({count}), wanted {q[:10]!r}... ({n})")
    hold(RECENT_X, row[0][1] - BUTTON_UP, bounds)
    time.sleep(1.5)
    texts, _ = view("favorite")
    if not unnamed(texts, q):
        return None
    log(f"saved it as a favorite: {first!r}")
    return handle(q)


def bar_ends(want):
    """run nothing: tap the filled bar, jump to its end, read it sharp. True if it ends with want"""
    for _ in range(3):  # a tap while the list still loads does nothing
        _, bounds = read()
        search.click(0.45, 0.183, bounds, gap=search.BAR_GAP)
        if any(ui.search_panel(read()[0]) for _ in range(8)):
            break
    else:
        return False
    ui.android.shell("input keyevent KEYCODE_MOVE_END")
    end = ct.same_l(want.rstrip("&"))[-20:]  # the game drops a trailing & when it saves a search
    for _ in range(4):
        time.sleep(0.5)
        if any(ct.same_l(t[4]).endswith(end) for t in ui.ocr(ui.android.sharp())):
            return True
    return False


def script(only_check=False):
    who = home.trainer()
    if who != OWNER:
        raise Stop(f"signed in as {who}: the {NAME} shortcut is {OWNER}'s")
    missing, run = dex.latest("lucky", SOURCE)
    if not missing:
        raise Stop(f"no lucky /dex run of {SOURCE} yet: dex.py lucky on {SOURCE}")
    lists = dex.searches(missing)
    if len(lists) != 1:
        raise Stop(f"{SOURCE}'s list needs {len(lists)} searches: one saved search holds only one")
    q = lists[0] + SAFE
    log(f"{SOURCE}'s list from {os.path.basename(run)}: {len(missing)} Pokémon, {len(q)} characters\n  {q}")

    home.start()
    path, bounds = ui.capture()
    search.leave_multiselect(ui.ocr(path), bounds)
    n0 = dex.search_exact(lists[0])  # the list, checked whole on the bar
    if not ct.append(SAFE):  # SAFE, checked on the bar's end (the list scrolls out of it)
        raise Stop("couldn't add the safe terms to the search")
    n = ct.results()
    log(f"the new search finds {n} (the list alone {n0})")
    _, bounds = read()
    if not search.x_button(bounds):  # cleared: only now is it a Recent search
        raise Stop("couldn't clear the search")
    if only_check:
        check(q, n)
        print(f"\n{NAME} on {OWNER} holds {SOURCE}'s newest list ({os.path.basename(run)}): finds {n}")
        return

    for _ in range(3):  # an earlier run stopped before its Rename
        texts, _ = view("favorite")
        if not unnamed(texts, q):
            break
        log(f"a favorite from an earlier run: {handle(q)!r}...")
        remove(handle(q))
    else:
        raise Stop(f"couldn't remove the favorites named {handle(q)!r}...")
    for _ in range(3):  # a misread ('Luckyaex') mustn't leave two of them
        had = ct.find_label(ct.labels(texts), NAME)
        if had:
            break
        texts, _ = view("favorite")
    else:
        log(f"no {NAME} favorite yet: {sorted(ct.labels(texts))}")
    new = save_recent(q, n)
    if not new and had:  # 12 already: the old one goes first
        log(f"no room for another favorite: removing the old {NAME} first")
        remove(NAME)
        had = None
        new = save_recent(q, n)
    if not new:
        keep_capture("save")
        raise Stop("holding the Recent search didn't save it as a favorite")
    if had:
        remove(NAME)
    rename(new, NAME)
    check(q, n)
    log(f"done: {NAME} = {SOURCE}'s missing luckies + the safe terms, finds {n}")
    print(f"\n{NAME} on {OWNER}: {len(missing)} Pokémon from {os.path.basename(run)}, finds {n} now\n{q}")


def run_saved(name):
    """tap a favorite with the keyboard down (ct.run_shortcut keeps it up, and it hides the 3rd row). -> its count"""
    for _ in range(3):
        texts, bounds = view("favorite")
        lab = ct.find_label(ct.labels(texts), name)
        if not lab:
            continue
        search.click(lab[0], lab[1] - BUTTON_UP, bounds)
        time.sleep(1.0)
        texts, bounds = read()
        if any(ui.norm(t[4]) == "MANAGE FAVORITE SEARCH" for t in texts):  # the tap was a long press
            continue
        return ct.results(texts)
    keep_capture("shortcut")
    raise Stop(f"couldn't run the {name!r} favorite")


def check(q, n):
    """Luckydex finds n, and the bar holds q's start and SAFE's end"""
    search.clear_search()
    got = run_saved(NAME)
    if got != n:
        raise Stop(f"{NAME} finds {got}, the typed search {n}")
    box = ui.search_box(ui.ocr(ui.android.sharp()))
    start = re.sub(r"\D", "", ui.search_text(box) if box else "")[:8]
    if not start or not re.sub(r"\D", "", q).startswith(start):
        raise Stop(f"{NAME}'s bar doesn't start with the list: {ui.search_text(box) if box else None!r}")
    if not bar_ends(SAFE):
        keep_capture("end")
        raise Stop(f"{NAME}'s search doesn't end with {SAFE!r}")
    _, bounds = read()
    search.close_panel(bounds)


def main():
    if not ui.ANDROID:
        sys.exit("Android only for now: POGO_PHONE=android")
    base.new_run_dir(os.path.join(HERE, "runs"), suffix="luckydex")
    session.main(script, sys.argv[1:] == ["check"])


if __name__ == "__main__":
    main()
