#!/usr/bin/env python3
"""Re-judge HashTagAJay's #GIV or #Transfer pile by species alone, with no Pokémon opened (the user, 2026-11-16).

  python3 specieswise.py plan GIV|Transfer                                   the Mac: the searches it would tag
  POGO_PHONE=android caffeinate -dimsu python3 specieswise.py GIV|Transfer   HashTagAJay on the Pixel: tag them

Each species is judged once by ../shared/verdict.py, the one rule book, as a plain one: untraded, caught 30 days ago,
no odd size, level 20, caught nearby, its gym top 20 out. HashTagAJay's Candy and Candy XL per family come from the
Pokémon database (../shared/pokedb.py: what the scripts read last); a family it has no count for counts as 360+ XL
and plenty of Candy (most of HashTagAJay's are). So the species rules decide: Reroll, GIV (raid top 6, stage 2, hard
evolutions, egg families, gym lines, trade evolutions, costly lines, short of Candy for Dynamax), 2XL (under 360 XL),
or Transfer. No appraisal, no power-up cost, no page read: the IV and level rules (98%+, XLX) don't run.

Left as they are, out of every search: ones a rule before the species rules decides (traded, lucky, shadow, shiny,
costume, background, XXL, XXS, Dynamax, Gigantamax, caught 300+ days ago or in 2016-2020, special trades), ones with
another of the user's tags, and a species verdict.py isn't sure of (regionals and Spinda: by hand). A dex number whose
forms disagree is searched form by form (37&alola, 37&!alola).

Each group (one tag, one search) is tagged in bulk: long press, SELECT ALL, the new tag on, the pile's tag off
(../shared/savedsearch.py tag_pile). A group whose answer is the pile's own tag isn't touched.
"""
import datetime, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "shared"))
sys.path.append(os.path.join(HERE, "..", "ivc"))  # verdict needs /ivc's GYM_DEFENDERS
import base
from base import Stop, log
import ui
import pvp, rules, search

PILES = ("GIV", "Transfer")
WHO = rules.TAKER  # HashTagAJay
# a rule before the species ones decides these (or the user does): never in a search
LEFT_OUT = ("&!favorite&!traded&!lucky&!shadow&!shiny&!costume&!background&!xxl&!xxs&!dynamax&!gigantamax"
            "&!legendary&!mythical&!ultrabeast&!age300-&!year2016-2020"
            "&!#IVC&!#PvpC&!#Old&!#2XL&!#XLX&!#Reroll&!#GuaranteedLucky&!#RT")
CHUNK = 700  # characters of dex numbers per search: with LEFT_OUT, well under the 1,000 a search keeps to


def family(sid):
    """the family's Candy name, as the page reads it ('ARON')"""
    s = sid
    while (p := pvp.parent(s)) is not None:
        s = p
    return pvp.base_name(s).upper()


def species_tag(sid, t, counts, vd):
    """-> verdict.Verdict for a plain one of this species on HashTagAJay"""
    c = counts.get(family(sid)) or {}
    candy, xl = c.get("candy"), c.get("xl")
    candy = 10 ** 6 if candy is None else candy
    xl = 10 ** 6 if xl is None else xl
    f = vd.Facts(account=WHO, sids=[sid], iv_sum=30, ivs=(10, 10, 10), traded=False,
                 caught=datetime.date.today() - datetime.timedelta(days=30), gender="", size="", kg=None,
                 candy_xl=xl, candy=candy, xl=xl, levels=[20.0], evolves=True, far=False, gym_top20=False)
    return vd.final_tag(f, t)


def groups(pile):
    """-> ({tag: [search part]}, {tag: n species}, [(sid, why) not sure])"""
    import verdict as vd
    import pokedb
    t = vd.tables(vd.TO[WHO])
    if "missing" in t:
        raise Stop(f"no species lists: {t['missing']}")
    counts = pokedb.candies(WHO)
    by_dex = defaultdict(dict)  # dex -> {sid: tag or None (not sure)}
    unsure = []
    for sid, p in pvp.PLAIN.items():
        if not p.get("released", True) or set(p.get("tags") or []) & set(rules.SPECIAL):
            continue
        v = species_tag(sid, t, counts, vd)
        if v.kind == "tag" and len(v.tags) == 1:
            by_dex[p["dex"]][sid] = v.tags[0]
        else:
            by_dex[p["dex"]][sid] = None
            unsure.append((sid, f"{v.kind} {'+'.join(v.tags)}: {v.why}"))
    parts = defaultdict(lambda: defaultdict(list))  # tag -> the form terms ('', '&alola', '&!alola') -> [dex]
    n = defaultdict(int)
    for d, forms in sorted(by_dex.items()):
        if len(set(forms.values())) == 1:  # every form agrees: the dex number alone
            tag = next(iter(forms.values()))
            if tag:
                parts[tag][""].append(d)
                n[tag] += len(forms)
            continue
        for sid, tag in forms.items():
            terms = pvp.search(sid, "plain").removeprefix(str(d)).removesuffix(pvp.POOL_TERMS["plain"])
            if not terms:  # forms with no region term (Burmy's cloaks) that disagree: by hand
                unsure.append((sid, f"its dex's forms disagree and have no search term"))
                continue
            if tag:
                parts[tag][terms].append(d)
                n[tag] += 1
    out = {}
    for tag, by_terms in parts.items():
        if tag == pile:
            continue
        qs = []
        for terms, dexes in sorted(by_terms.items()):
            chunk = []
            for r in search.dex_ranges(dexes):
                if chunk and len(",".join(chunk + [r])) > CHUNK:
                    qs.append(",".join(chunk) + terms)
                    chunk = []
                chunk.append(r)
            if chunk:
                qs.append(",".join(chunk) + terms)
        out[tag] = qs
    return out, dict(n), unsure


def query(pile, part):
    return f"#{pile}&{part}{LEFT_OUT}"


def cmd_plan(pile):
    got, n, unsure = groups(pile)
    for tag, qs in got.items():
        print(f"\n{tag} ({n.get(tag, 0)} species), #{pile} off:")
        for q in qs:
            print(f"  {query(pile, q)}")
    print(f"\nleft as #{pile}: {n.get(pile, 0)} species. Not sure (left as they are): {len(unsure)}")
    for sid, why in unsure:
        print(f"  {sid}: {why}")


def cmd_tag(pile):
    import home, session, savedsearch
    base.new_run_dir(os.path.join(HERE, "runs"), suffix=f"specieswise-{pile.lower()}")
    who = home.trainer()
    if who != WHO:
        if not ui.ANDROID:  # account.py signs in on the Pixel only
            raise Stop(f"signed in as {who!r}: this is {WHO}'s pile")
        import account
        log(f"signed in as {who!r}: switching to {WHO}")
        account.switch(WHO)
    home.start()
    got, n, unsure = groups(pile)
    log(f"#{pile}: {len(unsure)} species not sure, left as they are")
    done = {}
    for tag, qs in got.items():
        for q in qs:
            k = savedsearch.tag_pile(f"#{pile}", tag, off=(pile,), query=query(pile, q))
            done[tag] = done.get(tag, 0) + k
            log(f"DONE {tag}: {k} from #{pile} ({query(pile, q)})")
    log(f"#{pile} by species: {done}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["plan"] and a[1:2] and a[1] in PILES:
        cmd_plan(a[1])
    elif a[:1] and a[0] in PILES:
        import session
        session.main(cmd_tag, a[0])
    else:
        sys.exit(__doc__)
