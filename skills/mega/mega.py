#!/usr/bin/env python3
"""Mega Evolve every Pokémon tagged TODO, once a day each.

  POGO_PHONE=android caffeinate -dimsu python3 mega.py [--limit N] [--dry-run]   the Android phone
  caffeinate -dimsu python3 mega.py [--limit N] [--dry-run]                      the iPhone
  POGO_PHONE=both caffeinate -dimsu python3 mega.py [--limit N] [--dry-run]      both phones at once

Searches #TODO&mega&!#TODO4 (Mega-capable species only, so a Braixen never opens), opens the first one and swipes through them.
On each page it opens the Mega level page (the round Mega badge under the types) and Mega Evolves from there:

- Only a tag that is exactly TODO (TODO4 is left alone).
- "Daily level limit met" on the level page: done today, skipped. Mega right now ("07:59 left"): skipped.
- Mewtwo: only when it's free.
- High Level with "Mega Evolve <name> 1 more time" to Max Level: only when it's free.
- X/Y species (Mewtwo, Charizard, Raichu): the form is the nickname's last letter (' X' / ' Y'). None: a Mewtwo
  takes whichever form is free; any other is skipped.
- No MEGA EVOLVE button on the level page (Max Level): skipped.

Free = no number next to the MEGA EVOLVE button, and no xN cost in the "Do you want to Mega Evolve" box.

Then it searches mega1 and Mega Evolves the first one that's free, any tag, and stops there. That ends the Mega Evolution
just made, so its rest timer starts now instead of in 8 hours. A days line or timer by the Mega badge ("5 DAYS",
"11:39 left") means not free: skipped from the Pokémon's page, without opening the level page. With neither, the level
page and the box still check the cost. An X/Y one there takes its nickname's form, or with no letter whichever form is free.
--dry-run goes as far as that box and taps NO. It still taps the phone.
Log in runs/<time>-<phone>/log.txt.

--limit N is at most N per phone, and counts each search on its own: --limit 1 can Mega Evolve one TODO and one mega1.
If the box's cost doesn't match the level page's, it taps NO. Never tapped: the level page's LEVEL UP button (it spends
energy to skip levels).
"""
import argparse, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
import ui
import base
from base import Stop, log, keep_capture, look, front
import search
import session
from taps import Pass, exact, press, next_one, settled_tiles
from tagsheet import search_exact

TAG = "TODO"
SEARCH = "#TODO&mega&!#TODO4"  # mega = mega0-: only species that can Mega Evolve. Not last: a search ending in
# "mega" shows suggestion chips that push the first row of tiles out of reach
FREE_SEARCH = "mega1"  # after the TODO ones: Mega Evolve any of these that's free (the user, 2026-10-28)
PHONE = "android" if ui.ANDROID else "iphone"


# ---------- reading ----------

def rows(texts):
    """-> [(y, joined text)] rows top to bottom"""
    out = []
    for t in sorted(texts, key=lambda t: t[1] + t[3] / 2):
        mid = t[1] + t[3] / 2
        if out and mid - out[-1][0] < 0.012:
            out[-1][1].append(t)
        else:
            out.append([mid, [t]])
    return [(m, "  ".join(x[4] for x in sorted(r, key=lambda x: x[0]))) for m, r in out]


def form_of(name):
    """the nickname's last letter when it's ' X' / ' Y' -> 'X' / 'Y', else None"""
    m = re.search(r"\s([XY])$", (name or "").strip())
    return m.group(1) if m else None


def two_forms(texts):
    """an X/Y species: its energy labels read 'ENERGY X' and 'ENERGY Y'"""
    j = " ".join(ui.norm(t[4]) for t in texts)
    return bool(re.search(r"ENERGY X", j) and re.search(r"ENERGY Y", j))


def badge(texts):
    """the Mega badge's line under the types: '5 DAYS' (rest), '07:59 left' (Mega now), or None (an icon only)"""
    for t in texts:
        s = t[4].strip()
        if re.fullmatch(r"\d+\s*(DAYS?|HOURS?|MINUTES?)", s, re.I) or re.search(r"\d+:\d+\s*left", s, re.I):
            return t
    return None


def badge_spot(texts):
    """-> (fx, fy) of the Mega badge: between the WEIGHT/HEIGHT labels and the Stardust row"""
    b = badge(texts)
    if b:
        return b[0] - 0.07, b[1] + b[3] / 2
    w = [t for t in texts if ui.norm(t[4]) in ("WEIGHT", "HEIGHT") or "WEIGHT" in ui.norm(t[4])]
    s = [t for t in texts if "STARDUST" in ui.norm(t[4])]
    if not w or not s:
        raise Pass("can't find the WEIGHT and STARDUST rows around the Mega badge")
    top = max(t[1] + t[3] for t in w)
    bottom = min(t[1] for t in s) - 0.035  # the Stardust number sits above its label
    if not 0.03 < bottom - top < 0.15:
        raise Pass(f"the Mega badge's gap reads odd: {top:.3f}..{bottom:.3f}")
    return 0.5, (top + bottom) / 2


def sheet(texts):
    """the Mega level page -> what it says. None when it isn't that page"""
    j = " ".join(t[4] for t in texts)
    if "Mega Level" not in j:
        return None
    more = re.search(r"Mega Evolve .{1,30}? (\d+) more times?", j)
    level = re.search(r"\b(Super Max|Max|High|Base) Level\b", j.replace("Mega Level", ""))
    btn = [t for t in texts if ui.norm(t[4]) == "MEGA EVOLVE" and t[1] > 0.4]
    cost = None
    if btn:
        b = btn[0]
        row = [t for t in texts if abs((t[1] + t[3] / 2) - (b[1] + b[3] / 2)) < 0.015 and t[0] > b[0] + b[2]]
        nums = [re.sub(r"[^\d]", "", t[4]) for t in row]
        nums = [int(n) for n in nums if n]
        cost = max(nums) if nums else 0
    return {
        "done_today": "Daily level limit met" in j,
        "mega_now": "REMAINING MEGA EVOLUTION PERIOD" in ui.norm(j),
        "level": level.group(1) if level else None,
        "more": int(more.group(1)) if more else None,
        "button": btn[0] if btn else None,
        "cost": cost,
        "text": j,
    }


def ask_cost(texts):
    """the 'Do you want to Mega Evolve' box -> its xN cost (0: none shown, so free). None: not that box"""
    j = " ".join(t[4] for t in texts)
    if "want to Mega Evolve" not in j:
        return None
    m = re.search(r"(?:^|\s)[x×]\s?([\d,]+)(?:\s|$)", j)
    return int(m.group(1).replace(",", "")) if m else 0


# ---------- the level page ----------

def sharp_texts():
    """the phone's full-size screenshot read again (small numbers stay sharp), or the last look on the iPhone"""
    return ui.ocr(ui.android.sharp()) if ui.ANDROID else look()[1]


def steady(read, tries=30):
    """look until read(texts) gives the same answer (not None) twice in a row: the level page slides up and the
    Mega Evolve box grows in, and a read mid-way misses the cost. -> (answer or None, texts, bounds)"""
    last = None
    for _ in range(tries):
        time.sleep(0.15)
        _, texts, _, bounds = look()
        r = read(texts)
        if r is not None and r == last:
            return r, texts, bounds
        last = r
    return None, texts, bounds


def sheet_key(texts):
    s = sheet(texts)
    if not s or not s["level"]:
        return None
    b = s["button"]
    return s["level"], s["more"], s["done_today"], s["mega_now"], s["cost"], b and round(b[1], 2)


def page_cost(s):
    """the level page's cost, read again off the phone's own screenshot (the capture can miss a number).
    The two disagree: the bigger one (never call it free on one read)"""
    if not ui.ANDROID:
        return s["cost"]
    again = sheet(sharp_texts())
    if not again or not again["button"]:
        return None
    return max(s["cost"], again["cost"])


def box_key(texts):
    """the Mega Evolve box: its cost and where YES and NO are, so steady() waits until it's done growing (a tap while
    it grows can miss, and the box closes with no Mega Evolution). None while it isn't there yet"""
    j = " ".join(t[4] for t in texts)
    yes, no = exact(texts, "YES"), exact(texts, "NO")
    if "lasts for 8 hours" not in j or len(yes) != 1 or len(no) != 1:
        return None
    return ask_cost(texts), round(yes[0][1], 2), round(no[0][1], 2)


def open_sheet(texts, bounds):
    fx, fy = badge_spot(texts)
    base.click(fx, fy, bounds)
    got, texts, bounds = steady(sheet_key)
    if got is None:
        keep_capture("nosheet")
        raise Pass("the Mega level page didn't open (or never held still)")
    return sheet(texts), texts, bounds


def pick_form(form, texts, bounds):
    """tap the level page's MEGA <NAME> X/Y tab, and check the energy line names that form"""
    tab = [t for t in texts if re.fullmatch(rf"MEGA \S+ {form}[\WIl1]?", ui.norm(t[4])) and t[1] < 0.45]  # 'MEGA MEWTWO YI'
    if len(tab) != 1:
        raise Pass(f"can't find the Mega {form} tab: {[t[4] for t in texts if t[1] < 0.45]}")

    def shows(texts):  # the energy line under LEVEL UP names the form: 'MEGA MEWTWO X N ENERGY 9,147', or 'XN'
        line = " ".join(ui.norm(r) for y, r in rows(texts) if "ENERGY" in ui.norm(r) and y > 0.45)
        return sheet_key(texts) if re.search(rf"MEGA \S+ {form}", line) else None
    if shows(texts) is None:  # (the page opens on the form it last used)
        press(tab[0], bounds)
    got, texts, bounds = steady(shows, tries=12)
    if got is not None:
        return sheet(texts), texts, bounds
    # while it rests after one form, the other form's tab is greyed out and a tap does nothing
    raise Pass(f"the {form} tab is greyed out (resting after the other form)")


def show_me(texts, bounds):
    """the 'You can now increase the Mega Level of this Pokémon!' popup after a Mega Evolve: tap its SHOW ME.
    That only closes it, back to the Pokémon page. Back and a tap anywhere else do nothing. -> True if tapped"""
    j = " ".join(t[4] for t in texts)
    if "increase the" not in j or "Mega Level of this" not in j:
        return False
    button = exact(texts, "SHOW ME")
    if len(button) != 1:
        return False
    press(button[0], bounds)
    time.sleep(1.0)
    return True


def close_sheet():
    """Back (Android) or the round X: to the Pokémon page"""
    for _ in range(3):
        screen, texts, _, bounds = look()
        if show_me(texts, bounds):
            screen, texts, _, bounds = look()
        if screen == "detail":  # Back here would close the Pokémon too
            return
        if ui.ANDROID:
            ui.android.key("back")
        else:
            screen, texts, _, bounds = look()
            if screen == "detail":
                return
            if not any(t[4].strip().endswith("Mega Level") for t in texts):  # the X there would close the Pokémon too
                keep_capture("notsheet")
                raise Stop(f"not on the Mega level page: {' | '.join(t[4] for t in texts)[:200]}")
            base.click(0.5, 0.937, bounds)
        for _ in range(15):
            time.sleep(0.15)
            screen, texts, _, _ = look()
            if screen == "detail":
                return
    keep_capture("closesheet")
    raise Stop("couldn't get from the Mega level page back to the Pokémon")


def to_list():
    """from a Pokémon's page to the list. Just after a Mega Evolve the 'increase the Mega Level' popup can still come
    up, and the X tap can end on the level page, where there's no X to find: close those and tap again"""
    for attempt in range(3):
        _, texts, _, bounds = look()
        if show_me(texts, bounds):
            _, texts, _, bounds = look()
        if any(t[4].strip().endswith("Mega Level") for t in texts):
            log("  on the Mega level page: closing it")
            close_sheet()
        try:
            return base.go("close", "list")
        except Stop:
            if attempt == 2 or not any(t[4].strip().endswith("Mega Level") for t in look()[1]):
                raise


# ---------- one Pokémon ----------

def check(info, texts, free_only=False):
    """-> (Mewtwo, the forms to try: [] for a one-form species). Raises Pass for one to leave alone.
    free_only (the mega1 pass): any tag, and an X/Y one with no letter takes whichever form is free"""
    if not free_only and TAG not in [t.strip() for t in info["tags"]]:
        raise Pass(f"tags {info['tags']}: no exact {TAG}")
    b = badge(texts)
    if b and free_only:  # the line by the badge means it's resting or Mega now: never free
        raise Pass(f"not free yet ({b[4].strip()})")
    if b and "left" in b[4].lower():
        raise Pass(f"Mega Evolved right now ({b[4].strip()})")
    mewtwo = "MEWTWO" in " ".join(ui.norm(t[4]) for t in texts)
    if not two_forms(texts):
        return mewtwo, []
    form = form_of(info["name"])
    if form:
        return mewtwo, [form]
    if mewtwo or free_only:  # a Mewtwo with no letter: whichever form is free (the user, 2026-10-28)
        return mewtwo, ["X", "Y"]
    raise Pass("X/Y species and the nickname doesn't end in X or Y")


def can(s, mewtwo, free_only=False):
    """the level page (one form) -> (page cost, needs free, why). Raises Pass when it can't or mustn't Mega Evolve"""
    if s["done_today"]:
        raise Pass("daily level limit met: done today")
    if s["mega_now"]:
        raise Pass("Mega Evolved right now")
    if not s["button"]:
        raise Pass(f"{s['level']} Level: no MEGA EVOLVE on the level page")
    cost = page_cost(s)
    one_more = s["level"] == "High" and s["more"] == 1
    need_free = mewtwo or one_more or free_only
    why = "mega1" if free_only else "Mewtwo" if mewtwo else "1 more time to Max Level" if one_more else ""
    if need_free and cost != 0:
        raise Pass(f"{why}: only when free, costs {cost}")
    return cost, need_free, why


def mega(info, dry, free_only=False):
    """on a Pokémon's page: decide, and Mega Evolve it from its level page. -> what happened (a log line)"""
    _, texts, _, bounds = look()
    mewtwo, forms = check(info, texts, free_only)
    s, texts, bounds = open_sheet(texts, bounds)
    try:
        if not forms:
            cost, need_free, why = can(s, mewtwo, free_only)
        else:
            nope = []
            for form in forms:
                try:
                    s, texts, bounds = pick_form(form, texts, bounds)
                    cost, need_free, why = can(s, mewtwo, free_only)
                    break
                except Pass as e:
                    nope.append(f"{form}: {e}")
                    _, texts, _, bounds = look()
            else:
                raise Pass("; ".join(nope))
            if len(forms) > 1:
                why = f"{why}, Mega {form}"
        press(s["button"], bounds)
        asked, texts, bounds = steady(box_key)
        if asked is None:
            keep_capture("noask")
            raise Stop("no 'Do you want to Mega Evolve' box after MEGA EVOLVE")
        asked = asked[0]
        if ui.ANDROID:  # and off the phone's own screenshot: the bigger one
            asked = max(asked, ask_cost(sharp_texts()) or 0)
        yes, no = exact(texts, "YES"), exact(texts, "NO")
        # the energy icon in front of the page's number can read as one more digit: '915' for 15
        glued = cost is not None and asked and len(str(cost)) == len(str(asked)) + 1 and str(cost).endswith(str(asked))
        bad = (need_free and asked != 0) or (cost is not None and asked != cost and not glued)
        if bad or dry:
            press(no[0], bounds)
            time.sleep(0.8)
            if bad:
                raise Pass(f"the box says x{asked}, the page said {cost}{' (' + why + ': only free)' if need_free else ''}: NO")
            return f"DRY would Mega Evolve for {asked} energy ({s['level']} Level, {s['more']} more{', ' + why if why else ''})"
        press(yes[0], bounds)
        finish()
        return f"Mega Evolved for {asked} energy ({s['level']} Level, {s['more']} more{', ' + why if why else ''})"
    finally:
        if look()[0] != "detail":
            close_sheet()


def finish():
    """after YES: tap the energy crystal, YES on 'will no longer be Mega Evolved', wait for 'HH:MM left'"""
    end = time.time() + 45
    tapped = 0
    back_since = None
    while time.time() < end:
        time.sleep(0.2)
        try:
            screen, texts, _, bounds = look()
        except ui.Refused:
            continue
        j = " ".join(t[4] for t in texts)
        if "no longer be Mega" in j:
            yes = exact(texts, "YES")
            if len(yes) == 1:
                press(yes[0], bounds)
                time.sleep(0.8)
                continue
        if show_me(texts, bounds):
            continue
        if "Mega Level" in j and "increased" in j:  # a level up (High -> Max): Back, or its round X at the bottom
            if ui.ANDROID:
                ui.android.key("back")
            else:
                base.click(0.5, 0.937, bounds)
            time.sleep(1.0)
            continue
        s = sheet(texts)
        if not tapped and s and s["button"] and "want to Mega" not in j:  # back on the level page: YES didn't take
            back_since = back_since or time.time()
            if time.time() - back_since > 5:
                keep_capture("noyes")
                raise Pass("the YES tap didn't take: no Mega Evolution")
            continue
        back_since = None
        tap_line = [t for t in texts if "TAP TO MEGA" in ui.norm(t[4])]
        if tap_line and tapped < 6:
            t = tap_line[0]
            base.click(0.5, t[1] - 0.1, bounds)  # the crystal sits above the xN and TAP TO MEGA EVOLVE! lines
            tapped += 1
            time.sleep(1.5)  # the 'no longer be Mega Evolved' box can take a moment: a 2nd tap would close it
            continue
        b = badge(texts)
        if screen == "detail" and b and "left" in b[4].lower():
            time.sleep(1.5)  # the CP still changes a moment after the badge reads 'left': a swipe then doesn't take
            return
    keep_capture("finish")
    raise Stop("the Mega Evolution didn't finish in 45 s: check by hand")


# ---------- the run ----------

def walk(q, limit, dry, free_only=False):
    front()
    log(f"--- {q}{' (only free)' if free_only else ''}")
    if not settled_tiles_after(q):
        log(f"nothing in {q}")
        return
    # how many: a swipe that fails with more to come isn't the end of the list
    total = search.result_count(look()[1])
    base.go("tile 1", "detail")
    seen, counts, t_start = set(), {"done": 0, "skip": 0}, time.time()
    pos = 1  # its tile number: the swipe order is the list order
    while True:
        _, texts, _, _ = base.wait_for("detail")
        info = ui.detail_info(texts)
        me = key(texts)
        if me in seen:
            log("swiped back onto one already seen: end of the list")
            break
        seen.add(me)
        label = f"{info['name']} CP{info['cp']}"
        try:
            if counts["done"] >= limit:
                log(f"--limit {limit} reached")
                break
            did = mega(info, dry, free_only)
            log(f"{label}: {did}")
            counts["done"] += 1
            if free_only:  # one is enough to end the last Mega Evolution (the user, 2026-11-05)
                log("that's the first free one: done with this search")
                break
            if not dry:
                # the page after a Mega Evolution won't swipe: back to the list, open the next tile
                pos += 1
                if total and pos > total:
                    log(f"all {total} seen")
                    break
                if not reopen(pos):
                    break
                continue
        except Pass as e:
            log(f"skip {label}: {e}")
            counts["skip"] += 1
        if total and pos >= total:
            log(f"all {total} seen")
            break
        now = key(base.wait_for("detail")[1])
        if not next_one(None, lambda t: key(t)[1] is not None and key(t) != now):
            if not total:
                log("the swipe didn't move: end of the list")
                break
            # a swipe can fail for 15 s with more to come (2026-11-05, at number 2 of 76)
            log(f"the swipe didn't move, and there are {total}: back to the list for number {pos + 1}")
            if not reopen(pos + 1):
                break
        pos += 1
    log(f"done: {counts['done']} {'would Mega Evolve (dry run)' if dry else 'Mega Evolved'}, {counts['skip']} skipped, {time.time() - t_start:.0f}s")
    if look()[0] != "list":
        to_list()


def reopen(pos):
    """back to the list and open its pos-th Pokémon. -> False when there's no such one (logged)"""
    to_list()
    showing = len(settled_tiles())
    if not showing:
        return False
    try:
        if open_tile(pos, showing):
            return True
        log(f"the swipe to number {pos} didn't move: end of the list")
    except base.Lost:
        log(f"no tile {pos} on the list: end of the list")
    return False


def open_tile(pos, showing):
    """from the list, open its pos-th Pokémon. Past the tiles on the screen: open the last one showing and swipe on.
    -> False if a swipe didn't move"""
    base.go(f"tile {min(pos, showing)}", "detail")
    for _ in range(pos - showing):
        now = key(base.wait_for("detail")[1])
        if not next_one(None, lambda t: key(t)[1] is not None and key(t) != now):
            return False
    return True


def key(texts):
    """one Pokémon page: name, weight, height, HP, tags. No CP: the flames and sparkles behind it make it read
    differently look to look (Chandelure: 1846, 1816, 184), so the same page looked like a new one, and the walk
    ended early. Weight and height read the same on 100 of 100 looks (2026-11-05)"""
    d = ui.detail_info(texts)
    _, hp, kg, m = base.who(d)
    return d["name"], kg, m, hp, tuple(d["tags"])


def settled_tiles_after(q):
    search_exact(q)
    return settled_tiles()


def script(limit, dry):
    base.start()
    walk(SEARCH, limit, dry)
    # then a free one from mega1 ends the last Mega Evolution, so its rest timer starts now. --limit counts each pass
    walk(FREE_SEARCH, limit, dry, free_only=True)


def main():
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("--limit", type=int, default=10 ** 9, help="at most N Mega Evolutions per phone this run")
    ap.add_argument("--dry-run", action="store_true", help="everything but YES in the Mega Evolve box")
    a = ap.parse_args()
    if os.environ.get("POGO_PHONE", "").lower() != "both":  # ui read POGO_PHONE on import: android, else the iPhone
        base.new_run_dir(os.path.join(HERE, "runs"), suffix=PHONE)
        session.main(script, a.limit, a.dry_run)
    ui.ensure_helper()  # built once here, so the two phones don't both compile it
    procs = []
    for phone in ("ios", "android"):
        cmd = [sys.executable, os.path.realpath(__file__), "--limit", str(a.limit)] + (["--dry-run"] if a.dry_run else [])
        procs.append(subprocess.Popen(cmd, env=dict(os.environ, POGO_PHONE=phone)))
    sys.exit(max(p.wait() for p in procs))


if __name__ == "__main__":
    main()
