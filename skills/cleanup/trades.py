#!/usr/bin/env python3
"""Cleanup: retag the Nope Pokémon that should be traded away instead.

  caffeinate -dimsu python3 trades.py [--limit N] [--dry-run]     (N = most Pokémon to retag; dry run changes nothing)
  POGO_PHONE=android caffeinate -dimsu python3 trades.py ...   (Android phone over USB)

Start with Pokémon GO on the Pokémon screen. Two groups, each one searched, opened and swiped through:
  1. not traded, and legendary, Ultra Beast, Meltan or Melmetal -> Remote Trade + RT (+ Old if caught 300+ days ago)
  2. traded -> Spot Transfer
and Nope comes off. Shiny and costume ones are kept out by the search. On its detail screen each one is retagged only
if: its only tag is Nope, no star, no XXL/XXS in the name. Group 1 also needs: not shadow, a tradeable family (not
Deoxys and the other mythicals) and, for Kyurem and Necrozma, not fused. Its age comes off the caught date at the
bottom, read twice. Anything else keeps Nope and is passed over.
Log and done.json go in runs/<time>/.
"""
import datetime, os, random, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "pvpc"))
import ui
import run as base
from run import Stop, log, keep_capture, go, look, wait_for, save, load, candy
import search
from shadows import Pass, GM, press, swipe_next, settled_tiles, exact

OLD_DAYS = 300  # caught this many days ago or more -> Old (the game's age300-)
LEGENDS = "#Nope&!traded&!shiny&!costume&legendary"
BEASTS = "#Nope&!traded&!shiny&!costume&793-806,808,809"  # Ultra Beasts, Meltan, Melmetal (801, 802: candy check)
TRADED = "#Nope&traded&!shiny&!costume"


def family(tag):
    return {p["speciesName"].split(" (")[0].upper() for p in GM["pokemon"] if tag in p.get("tags", [])}


TRADEABLE = family("legendary") | family("ultrabeast") | {"MELTAN"}  # Melmetal's candy is Meltan's
FUSES = {"KYUREM", "NECROZMA"}  # fused ones can't be traded
DRY = False  # --dry-run: read and log, change no tags


# ---------- search: start and end of the bar both read back ----------

_views = []


def strict(got, q):
    """the bar text vs q, symbol for symbol, off the phone's own screenshot on Android. A long search shows only its
    end while typing and only its start after Return: note which part matched, search_exact() adds them up."""
    if ui.ANDROID:
        box = ui.search_box(ui.ocr(ui.android.sharp()))
        got = ui.search_text(box) if box else ""
    s = re.sub(r"\s", "", got or "").lower()
    s = re.sub(r"^[<‹]?[q9]?(?=#)", "", s)  # the magnifier glued on
    Q = re.sub(r"\s", "", q).lower()
    if s == Q:
        _views.append(("all", len(s)))
    elif len(s) >= 15 and Q.endswith(s):
        _views.append(("end", len(s)))
    elif len(s) >= 15 and Q.startswith(s):
        _views.append(("start", len(s)))
    else:
        return False
    return True


def search_exact(q):
    search.bar_shows = strict
    Q = re.sub(r"\s", "", q)
    for attempt in range(3):
        _views.clear()
        search.start_search(q)
        got = {}
        for k, n in _views:
            got[k] = max(got.get(k, 0), n)
        if "all" in got or got.get("start", 0) + got.get("end", 0) > len(Q):
            return
        log(f"only part of {q!r} read back ({got}): typing it again")
    keep_capture("search")
    raise Stop(f"couldn't read back all of {q!r} in the search bar")


def result_tiles(q):
    search_exact(q)
    return settled_tiles()


# ---------- one Pokémon ----------

def who(texts):
    """name, CP, HP, weight, height: twins with the same name and CP still differ in weight and height"""
    info = ui.detail_info(texts)
    kg = next((t[4].strip() for t in texts if re.fullmatch(r"[\d.,]+\s*kg", t[4].strip())), None)
    m = next((t[4].strip() for t in texts if re.fullmatch(r"[\d.,]+\s*m", t[4].strip())), None)
    return info, ((info["name"] or "").replace(" ", ""), info["cp"], info["hp"], kg, m)  # OCR reads "80 h" or "80h"


def tag_chips(texts):
    """the tags under the name: between the HP line and the weight row (they can wrap onto two lines)"""
    hp = next(t for t in texts if re.search(r"\d+\s*/\s*\d+\s*HP", t[4]))
    kg = [t[1] for t in texts if re.fullmatch(r"[\d.,]+\s*kg", t[4].strip()) and t[1] > hp[1]]
    low = min(kg) if kg else hp[1] + 0.06
    return sorted(n for t in texts if hp[1] + 0.005 < t[1] < low - 0.005 and (n := ui.norm(t[4]))
                  and n not in ("DYNAMAX", "GIGANTAMAX") and not n.startswith("LUCKY POK"))


def plain(info, texts, path):
    """the shadow cleanup's skips: raise Pass unless it's tagged Nope only, no star, no XXL/XXS in the name"""
    if tag_chips(texts) != ["NOPE"]:
        raise Pass(f"tags {info['tags']}: not just Nope")
    if re.search(r"xx[ls]", info["name"] or "", re.I):
        raise Pass("XXL/XXS in the name")
    star = ui.star_filled(path, texts)
    if star is None and ui.ANDROID:
        sp = ui.android.sharp()
        star = ui.star_filled(sp, ui.ocr(sp))
    if star is not False:
        raise Pass("favorite" if star else "can't see the star")


def scrolled_bottom(bounds):
    """drag the detail page up to its bottom (caught date) -> texts seen there, both reads"""
    base.drag(0.08, 0.75, 0.08, 0.2, bounds)  # down the left edge: no buttons there
    base.drag(0.08, 0.75, 0.08, 0.2, bounds)
    reads = []
    for _ in range(2):
        _, texts, _, _ = look()
        reads.append(texts)
        if ui.ANDROID:
            reads.append(ui.ocr(ui.android.sharp()))
            break
        time.sleep(0.3)
    return reads


def back_to_top(me):
    """drag from the weight number: a drag down the left edge doesn't move the page from its bottom.
    A drag at the top closes the page, so only drag while the CP is out of sight; else wait and look again."""
    _, _, _, bounds = look()
    for _ in range(6):
        texts = ui.ocr(ui.android.sharp()) if ui.ANDROID else look()[1]
        if ui.classify(texts) == "detail" and who(texts)[1] == me:
            return
        kg = [t for t in texts if re.search(r"\d\s*kg$", t[4].strip())]
        # long pages (Zacian's form text) hide the weight at the bottom: then any plain text up top
        plain = [t for t in texts if 0.05 < t[1] < 0.35 and len(t[4]) > 12
                 and not re.search(r"POWER|ATTACK|FORM|BUDD|RAIDS|BATTLES|PURIFY|MEGA|EVOLVE", ui.norm(t[4]))]
        hold = (kg or plain)[:1]
        if hold and not any(re.fullmatch(r"[cC]\s*[pP]\s*\d+", t[4].strip()) for t in texts):
            x, y = hold[0][0] + hold[0][2] / 2, hold[0][1] + hold[0][3] / 2
            # at the top the weight sits at ~0.6: drag the weight just short of there, any more and the page closes
            to = random.uniform(0.56, 0.58) if kg else y + random.uniform(0.4, 0.45)
            base.drag(x, y, x, max(to, y + 0.03), bounds)
        time.sleep(0.8)
    keep_capture("top")
    raise Stop("couldn't get back to the top of the detail page")


def caught(texts):
    ds = {m for t in texts for m in re.findall(r"\b(\d{1,2}/\d{1,2}/20\d\d)\b", t[4])}
    if len(ds) != 1:
        return None
    try:
        return datetime.datetime.strptime(ds.pop(), "%m/%d/%Y").date()
    except ValueError:
        return None


def check_trade(info, texts, path, bounds, me):
    """group 1: raise Pass if it can't or shouldn't be traded. -> the tags it gets"""
    plain(info, texts, path)
    if base.is_shadow(texts):
        raise Pass("shadow: can't be traded")
    c = candy(texts)
    if not c:
        raise Pass("can't read the candy name")
    if c not in TRADEABLE:
        raise Pass(f"{c.title()}: not a tradeable legendary/Ultra Beast")
    reads = scrolled_bottom(bounds)
    try:
        if c in FUSES and not all(any("can fuse with" in t[4] for t in r) for r in reads):
            raise Pass(f"{c.title()}: no 'can fuse with' line, may be fused")
        days = {caught(r) for r in reads}
        if len(days) != 1 or None in days:
            raise Pass(f"caught date reads {days}")
        day = days.pop()
        age = (datetime.date.today() - day).days
        if not 0 <= age < 4000:
            raise Pass(f"caught date {day} looks wrong")
    finally:
        back_to_top(me)
    log(f"  {c.title()}, caught {day} ({age} days)")
    return ["Remote Trade", "RT"] + (["Old"] if age >= OLD_DAYS else [])


# ---------- the tag sheet ----------

def sheet_rows(texts, path):
    """tag rows that are safe to tap (not under the fade at the bottom): norm name -> (box, ticked)"""
    ticks = dict((ui.norm(n), on) for n, on in ui.ticked_tags(path, texts))
    rows = {}
    for t in texts:
        n = ui.norm(t[4].lstrip("•· "))
        if n in ticks and 0.2 < t[1] < 0.7:
            rows[n] = (t, ticks[n])
    return rows


def still_sheet():
    last = None
    for _ in range(10):
        _, texts, path, bounds = wait_for("tags")
        ys = [(t[4], round(t[1], 3)) for t in texts]
        if ys == last:
            return texts, path, bounds
        last = ys
        time.sleep(0.25)
    return texts, path, bounds


def retag(on, off=("Nope",)):
    """tick on, untick off, scrolling down the sheet to find each. Afterwards the tags must be exactly on."""
    go("menu", "menu")
    go("TAG", "tags")
    want = {**{t.upper(): False for t in off}, **{t.upper(): True for t in on}}
    left, same = dict(want), 0
    for _ in range(30):
        texts, path, bounds = still_sheet()
        rows = sheet_rows(texts, path)
        for T in [T for T in left if T in rows]:
            if rows[T][1] is not left[T]:
                press(rows[T][0], bounds)
                for _ in range(20):
                    time.sleep(0.15)
                    _, t2, p2, _ = wait_for("tags")
                    r = sheet_rows(t2, p2)
                    if T in r and r[T][1] is left[T]:
                        break
                else:
                    keep_capture("tick")
                    raise Stop(f"tapped {T} but its tick didn't change")
                if ui.ANDROID:
                    ui.android.fresh()
            del left[T]
        if not left:
            break
        before = [t[4] for t in texts]
        base.drag(0.3, 0.62, 0.3, 0.4, bounds)
        if ui.ANDROID:
            ui.android.fresh()
        after = [t[4] for t in still_sheet()[0]]
        same = same + 1 if after == before else 0
        if same >= 2:
            go("CANCEL", "detail")
            raise Stop(f"no {', '.join(left)} tag in the list: cancelled")
    else:
        go("CANCEL", "detail")
        raise Stop(f"couldn't find {', '.join(left)} in the tag list: cancelled")
    go("DONE", "detail")
    good = sorted(t.upper() for t in on)
    got = base.settle(lambda: tag_chips(wait_for("detail")[1]), lambda t: t == good, timeout=4)
    if got != good:
        keep_capture("tags")
        raise Stop(f"after DONE the tags read {got}, wanted {good}")


# ---------- the walk ----------

def walk(q, decide, done, limit):
    """open the first result and swipe through. decide() raises Pass or returns the tags to give it."""
    if not result_tiles(q):
        log(f"none in {q}")
        return
    log(f"--- {q}")
    go("tile 1", "detail")
    seen, passed, agains = set(), {}, 0
    while len(done) < limit:
        t0 = time.time()
        _, texts, path, bounds = wait_for("detail")
        info, me = who(texts)
        if None in me:
            agains += 1
            if agains > 5:
                raise Stop(f"can't read this one: {me}")
            time.sleep(0.3)
            continue
        if me in seen:
            log("swiped back onto one already seen: end of the list")
            break
        seen.add(me)
        try:
            if me in passed:
                raise Pass(passed[me])
            tags = decide(info, texts, path, bounds, me)
        except Pass as e:
            if me not in passed:
                log(f"pass {info['name']} CP{info['cp']}: {e}")
            passed[me] = str(e)
        else:
            if DRY:  # tags left alone: swipe on to the next one
                log(f"DRY would retag {info['name']} CP{info['cp']}: {' + '.join(tags)}, Nope off")
                passed[me] = "dry run"
            else:
                retag(tags)
                done.append({"name": info["name"], "cp": info["cp"], "tags": tags})
                save("done.json", done)
                log(f"retagged {info['name']} CP{info['cp']}: {' + '.join(tags)}, Nope off  ({time.time() - t0:.1f}s, #{len(done)})")
                texts = go("close", "list")[1]  # it no longer fits the search: back to the list, open the top one again
                if not ui.tiles(texts):
                    time.sleep(0.4)
                    if not settled_tiles():
                        return
                go("tile 1", "detail")
                seen = set()
                continue
        moved = False
        for attempt in range(2):  # next one; a swipe that does nothing twice = end of the list
            swipe_next(bounds)
            for _ in range(10):
                time.sleep(0.12)
                screen, texts, _, bounds = look()
                if screen == "detail" and who(texts)[1] != me and None not in who(texts)[1]:
                    moved = True
                    break
            if moved:
                break
        if not moved:
            break
    if len(done) >= limit:
        log(f"--limit {limit} reached")
    if look()[0] != "list":
        go("close", "list")


def check_traded(info, texts, path, bounds, me):
    plain(info, texts, path)
    return ["Spot Transfer"]


if __name__ == "__main__":
    a = sys.argv[1:]
    if any(x not in ("--limit", "--dry-run") and not x.isdigit() for x in a):
        sys.exit(__doc__)
    DRY = "--dry-run" in a
    limit = int(a[a.index("--limit") + 1]) if "--limit" in a else 10 ** 9
    base.new_run_dir(os.path.join(HERE, "runs"))
    done = []
    t_start = time.time()
    try:
        base.front()
        for q, decide in ((LEGENDS, check_trade), (BEASTS, check_trade), (TRADED, check_traded)):
            if len(done) < limit:
                walk(q, decide, done, limit)
    except Stop as e:
        log(f"STOP: {e}")
        sys.exit(1)
    finally:
        log(f"retagged {len(done)} in {time.time() - t_start:.0f}s")
        log(f"run folder: {base.RUN_DIR}")
