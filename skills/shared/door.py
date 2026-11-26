"""The door: a Pokémon /ivc, /pvpc or /ivc just found isn't a keeper gets its final tag right there (verdict.py), on the
detail page that's still open. No Nope.

  facts = Door(tag)          once a run, before the walk: who's signed in, the species lists, and one search each
                             for what the detail page can't show (traded; shiny; costume; background; caught 100 km+
                             away; under 360 Candy XL), all within the tag
  facts.judge(...)           read the rest off the open page, ask verdict.final_tag, do what it says
  facts.judge_open(i, n, c)  open tile i of the list, appraise it, then judge it as above
  facts.listed()             Pokémon an earlier run left as not sure under today's rules: the walk passes over them

Not sure = left exactly as it is (tag and name) and written to runs/not-sure.json, with why, for a rule offline.
A search whose tiles didn't all read counts as not done: every Pokémon that needs it comes out not sure.

A gym defender's top 20 (rank_gym): before the walk the door looks for gym species in the pile, and reads the whole list
of each one it finds, once a run. sort.gym_top20, /ivc's own rule, ranks each one opened. /ivc passes its own answer.

A lucky one only /ivc can rank (verdict.lucky): anywhere else the door sends it to IVC. One /ivc found out of the
top IV is written to runs/lucky-out.json, so /pvpc's door knows that when the lucky rule sends it on to PvpC (else it
would go back to IVC, round and round).
"""
import copy, datetime, hashlib, json, os, re, sys, time
from collections import Counter
from dataclasses import replace

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import ui, base, search, home, pagefacts, pokedb, raidteams
import rules
from rules import GYM_DEX, XL_CAP, UNDER_360_XL
from base import Stop, log

NOT_SURE = os.path.join(HERE, "runs", "not-sure.json")
LUCKY_OUT = os.path.join(HERE, "runs", "lucky-out.json")
LUCKY_OUT_DAYS = 7  # an older entry is dropped: by then the line may have changed
RULES = hashlib.md5(b"".join(open(os.path.join(HERE, f), "rb").read() for f in ("verdict.py", "door.py", "rules.py"))
                    ).hexdigest()[:8]  # new rules or a new reader: judge again
SEARCHES = {"costume": "costume"}  # the one fact the page and tile can't show. The rest come from pagefacts
RAID = "mythical&raid"  # a mythical caught in a raid can't be traded (verdict.special): typed only when the scope could
# hold a mythical (a scope of dex numbers with none, like /ivc's #IVC&13, or a saved search with !mythical, skips it)
# (2026-10-31: traded and the catch place off the page's bottom, Candy XL off its top, shiny and background off the tile)
SAID = {"traded": "traded", "shiny": "shiny", "background": "background", "far": "distance100-",
        "xl_under": UNDER_360_XL[1:]}  # a scope that already says one of these (#Nope&traded) is believed over the page
Y1 = rules.LUCKY_YEARS[1]
OLD_DAYS = int(re.search(r"\d+", rules.OLD_AGE).group())
# a pile walked in parts (Door.splits), each part's search telling the door what the page's bottom would: traded or
# not, and which of verdict.AGES its catch date is in. Ranges only, no !year or !age (SEARCH.md: ! is ignored on some)
TRADED_SPLITS = (("traded", True), ("!traded", False))
AGE_SPLITS = ((rules.LUCKY_YEAR[1:], "lucky"), (f"year{Y1 + 1}-{rules.OLD_AGE}", "old"),  # (the tag searches' terms)
              (f"year{Y1 + 1}-&age-{OLD_DAYS - 1}", "new"))
DRAG_S, SEARCH_S = 9, 10  # (seconds) a drag to the page's bottom and back (door.md), one typed search counted
TOP_SETTLES = 0.5  # the share of a pile its parts let the top screen judge (tests/verdicts.py: 142 of 259)
UNSURE = "unsure"
EMPTY = []  # (account, a scope's terms, term): the game counted 0 for that search this run. A scope with all of those
# terms and more (#IVC&590 after #IVC) can only be empty too, so it isn't typed. Only an empty answer is kept: a tile
# list goes stale when a Pokémon is renamed, and "costume" can't start being true of a Pokémon mid-run
GYM_TILES = {}  # (account, dex) -> every tile of that gym species, read once a run
vd = powerup = tagsheet = taps = sort = None  # verdict, powerup, tagsheet, taps, sort: imported by Door(). At the top they'd loop back
# (/ivc's run.py loads names.py, which loads this)


def tile_icons(info):
    """{"shiny", "background"} off the list tile this page was opened from: base.open_tile's, or the last "tile N"
    any go() tapped (/cleanup, /mega). A tile whose CP isn't this page's -> {} (not sure)"""
    pick = base.OPENED.get("tile") or ui.TILE_PICK
    if not pick:
        return {}
    cp = pick[1][1]
    if cp and info.get("cp") and cp != info["cp"]:
        log(f"  tile icons: the tile was CP{cp}, the page CP{info['cp']}: not used")
        return {}
    return pagefacts.tile_icons(*pick)


def key(tile_name, cp):
    return ui.tile_name(tile_name), cp



def candy_owned(texts):
    """the family's Candy count on this page, or None (taps.owned's read)"""
    import taps  # here: taps imports base
    try:
        return taps.owned(texts)[1]
    except Exception:  # (taps.Pass: the row didn't read)
        return None

class Door:
    def __init__(self, tag, scope=None, account=None, find=None, rank_gym=False):
        """scope: the search the Pokémon to judge are in (default #tag). account: who's signed in, when known.
        find(term) -> search.run_search's answer for the pile & term, for a pile that's no typed search (a saved one).
        Then tag only names the pile (the not-sure list): it isn't a tag to take off. rank_gym: read the lists a gym
        defender's top 20 needs (the caller doesn't know it)"""
        global vd, powerup, tagsheet, taps, sort
        run_dir = base.RUN_DIR  # (kept in case an import moves it)
        import verdict as vd
        import powerup  # the power-up cost -> levels, and power-ups to the next Candy XL tier
        import tagsheet  # the tag chips, the caught date at the bottom of the page
        import taps  # purify
        import sort  # /ivc's gym rule
        base.RUN_DIR = run_dir
        self.tag, self.other = tag, "IVC" if tag.upper() == "PVPC" else "PvpC"
        self.source = find is None  # tag is the Pokémon's own tag, to come off
        find = find or (lambda term: search.run_search(f"{self.scope}&{term}"))
        self.account = account or home.trainer()
        self.scope = scope or f"#{tag}"
        self.tables = vd.tables(vd.TO[self.account])
        raidteams.newest(self.account)  # (logs the count's age once a run)
        if "missing" in self.tables:
            log(f"door: no species lists, those rules will say not sure ({self.tables['missing']})")
        self.sets, self.partial = {}, set()
        said = set(self.scope.lower().split("&"))  # '#Nope&traded': every one is traded, so no search can misread it
        if not self.source:  # a saved search's pile (tradeable.door_walk): its terms too (Leftovers: !mythical)
            said |= set(rules.SAVED.get(self.account, {}).get(tag, ()))
        self.said = {k: term in said for k, term in SAID.items() if term in said or "!" + term in said}
        self.terms = said
        empty = lambda term: self.source and any(a == self.account and t == term and wide <= said for a, wide, t in EMPTY)
        searches = dict(SEARCHES)
        dexes = search.dexes_of(self.scope)
        if "!mythical" not in said and (dexes is None or dexes & {x["dex"] for x in vd.pvp.SPECIES.values()
                                                                   if "mythical" in (x.get("tags") or [])}):
            searches["raid"] = RAID
        self.typed = not all(empty(term) for term in searches.values())  # False: the screen wasn't touched
        if self.typed:
            search.to_search_list()
        for k, term in searches.items():
            if empty(term):
                self.sets[k] = Counter()
                log(f"door: {self.scope}&{term}: a wider search already found none, not typed")
                continue
            if term in said or "!" + term in said:
                self.sets[k] = term in said
                log(f"door: {self.scope}: {'every' if term in said else 'no'} one is {term}, no search")
                continue
            got, want = find(term)
            ok = want is not None and len(got) == want
            if self.source and want == 0 and not got:
                EMPTY.append((self.account, said, term))
            self.sets[k] = Counter(key(n, c) for n, c in got)
            # more different tiles than the game counts: some aren't in it (81 for 65, 2026-10-30), so none is trusted.
            # Fewer, or the same tile read twice: a tile read is in it
            usable = ok or want is not None and len(self.sets[k]) <= want
            if not ok:
                self.partial.add(k)
            if not usable:
                self.sets[k] = None
            log(f"door: {self.scope}&{term}: {len(got)} read ({len(set(key(n, c) for n, c in got))} different), "
                f"the game says {want}" + ("" if ok else ": only a tile read in it counts" if usable else ": not used"))
        self.rank_gym = rank_gym
        if rank_gym:
            self.read_gym_lists(find)

    def read_gym_lists(self, find):
        """one search for any gym species in the pile (usually none), then the whole list of each one there"""
        if not self.typed:
            search.to_search_list()
            self.typed = True
        if not find(",".join(map(str, GYM_DEX)))[1]:
            log(f"door: {self.scope}: no gym defenders")
            return
        for dex in GYM_DEX:
            if (self.account, dex) not in GYM_TILES and find(str(dex))[1]:
                got, want = search.run_search(str(dex))
                log(f"door: gym list {dex}: {len(got)} read, the game says {want}")
                if want is not None and len(got) == want:  # (else: those come out not sure)
                    GYM_TILES[self.account, dex] = got

    def splits(self):
        """the pile in parts, each part's search saying what the page's bottom would (TRADED_SPLITS, AGE_SPLITS), so
        more Pokémon are judged off the page's top alone -> [(terms to add to the scope's search, a door that
        believes them)]. One part with no terms: the scope can't be split. A traded one isn't split by age: no rule asks its catch date.
        !traded is believed only with a catch after LUCKY_YEARS: the game's traded misses trades before Oct 2020"""
        age = lambda x: re.fullmatch(r"!?(age|year)\S*", x)
        if any(map(age, self.terms)):  # the scope picks its own ages: new ones only (Leftovers' age0-7) or can't say
            ages = [("", "new" if any((m := re.fullmatch(r"age(?:\d*-)?(\d+)", x)) and int(m[1]) < OLD_DAYS
                                      for x in self.terms) else None)]
        else:
            ages = AGE_SPLITS
        traded = [("", None)] if "traded" in self.said else TRADED_SPLITS
        out = []
        for tt, tv in traded:
            for at, av in [("", None)] if tv else ages:
                known = {"age": av} if av else {}
                if tv is not None and (tv or av in ("old", "new")):
                    known["traded"] = tv
                out.append(("&".join(x for x in (tt, at) if x), self.narrow(known)))
        return out

    def narrow(self, known):
        """this door for a part of its pile whose search says known ({"traded": bool, "age": a verdict.AGES key}):
        the same searches, the same lists"""
        part = copy.copy(self)
        part.said = {**self.said, **known}
        return part

    def gym_rank(self, sp, cp, ivs, shadow):
        """top 20 of its species? None: not a gym defender, its list didn't read, or can't tell"""
        if not self.rank_gym or len(sp) != 1 or sp[0] not in vd.GYM_DEFENDERS:
            return None
        tiles = GYM_TILES.get((self.account, vd.pvp.SPECIES[sp[0]]["dex"]))
        got = None if tiles is None else sort.gym_top20(sp[0], cp, ivs, shadow, tiles)
        log(f"  gym top 20 of {len(tiles or ())} {sp[0]}: {got}")
        return got

    def has(self, k, tile):
        """a search whose count didn't match (a long list read 57 for 55): a tile read in it is in it, one not read
        could be a tile it missed -> None"""
        s = self.sets.get(k)
        if s is None or isinstance(s, bool):
            return s
        return True if tile in s else None if k in self.partial else False

    def renamed(self, old, new):
        """a tile renamed after the searches (/ivc's LOOK): it's in the same ones under its new name"""
        for s in self.sets.values():
            if isinstance(s, Counter) and s[old]:
                s[new] += 1
                s[old] -= 1

    def listed(self):
        """{(tile name, CP) as the walk read them: n} left as not sure by an earlier run of this tag, on this account,
        under these rules. Not one a search misread ('costume or not: not read'): the next run reads it again (the
        costume search read 9 of 15 and all 56 again GIV opened were not sure, CyrillJan 2026-11-24)"""
        return Counter((e["tile"], e["cp"]) for e in load_list()
                       if e["rules"] == RULES and e["account"] == self.account and e["tag"] == self.tag
                       and not e.get("why", "").endswith(" or not: not read"))

    def judge_open(self, i, n, c, **kw):
        """open tile i of the list (the walk read it as name n, CP c), appraise it, find its species and judge it.
        kw: judge's. The page stays open. -> (judge's answer, the IV read as text)"""
        info, texts, _ = base.open_checked(i, n, c)
        _, ivs, raws, iv = base.high_iv()
        sp = ui.species_for(info["name"], info["texts"]) or base.species_from_candy(texts, info["cp"] or c, info["hp"])
        info, texts, _ = base.steady_detail()
        return self.judge(info, texts, sp, ivs, (n, c), size=base.extras(texts)[2], raws=raws, **kw), iv

    def judge(self, info, texts, sp, ivs, tile, size=None, raws=None, gym_top20=None, clear=False, unstar=False,
              iv_top=None, pure_top=None, hold=None):
        """the open detail page of a Pokémon that isn't a keeper. tile: (name, CP) as the walk read the tile.
        gym_top20: what the caller already knows of the gym rule. iv_top: of a lucky one's top IV, pure_top: of a shadow's once purified (verdict.Facts). clear: a plain tag clears the name too (an old /ivc
        name would bring it back as a rival or a fallen-out one). unstar: a plain tag takes the star off too (a fallen-out
        keeper). hold: a tag a Transfer verdict gets instead, before any purify or power-up; star and name stay.
        -> 'left for IVC/PvpC', UNSURE, 'held' or the verdict's kind"""
        if self.source and any(base.is_tag(t, self.other) for t in info["tags"]):  # the other skill judges it next
            base.set_tags(off=[self.tag])
            log(f"  has {self.other} too: unticked {self.tag} only, {self.other} decides")
            return f"left for {self.other}"
        if (got := base.narrow(sp, ivs, tile[1] or info["cp"], info["hp"])) != sp:  # (the walk checked the tile's CP)
            log(f"  {'/'.join(sp)}: only {'/'.join(got)} has these IVs at this CP and HP")
            sp = got
        base.learn_ivs(sp, info["cp"], info["hp"], ivs, raws)
        f, why = self.facts(info, texts, sp, ivs, key(*tile), size, gym_top20, iv_top, tile[1], pure_top)
        v = vd.final_tag(f, self.tables) if not why else vd.unsure(why)
        if v.kind == UNSURE and not why and "page" not in base.OPENED:  # the top alone wasn't enough: every rule
            # that needs a bottom fact answers unsure while it's None, so the bottom is read and the rules asked again
            f = replace(f, **self.page_facts(info, f.lucky, bottom=True))
            v = vd.final_tag(f, self.tables)
        elif "page" not in base.OPENED:
            log(f"  door: page bottom not needed ({v.kind} {'+'.join(v.tags)})")
        if f.lucky and iv_top is False:
            ranked_out(self.account, sp, ivs)
        if hold and v.kind == "tag" and "Transfer" in v.tags:
            log(f"  door: would be {'+'.join(v.tags)} ({v.why}): {hold} instead")
            base.set_tags(on=[hold])
            return "held"
        if v.purify:
            v = self.purify(info, v, sp)
        if v.kind == "tag" and "Transfer" in v.tags:
            v = self.power_up(info, v, tile[1], None if v.purify else f.levels)
        self.last = v
        log(f"  door: {v.kind} {'+'.join(v.tags)}{' -' + '-'.join(v.off) if v.off else ''}"
            f"{' named ' + v.name if v.name else ''}: {v.why}")
        if v.kind == UNSURE:
            add_to_list({"tile": tile[0], "cp": tile[1], "hp": info["hp"], "ivs": list(ivs or ()), "species": sp,
                         "why": v.why, "account": self.account, "tag": self.tag, "rules": RULES,
                         "day": time.strftime("%Y-%m-%d"), "run": base.RUN_DIR})
            return UNSURE
        if v.name and not (info.get("name") or "").upper().startswith(v.name.upper()):  # ('93 A FP*' keeps its FP*)
            base.do_rename(v.name, lambda got, want: (got or "").strip().upper() == want.upper())
        if v.kind == "keep" or v.star:
            base.set_star(True)
        elif (unstar or v.unstar) and v.kind == "tag":
            base.set_star(False)
        on = {ui.norm(t) for t in v.tags}
        off = [t for t in (*([self.tag] if self.source else ()), *v.off) if ui.norm(t) not in on]  # (GIV judged GIV again)
        has = lambda t: any(ui.norm(x) == ui.norm(t) for x in info["tags"])
        if v.tags and not off and all(has(t) for t in v.tags):  # it has them all already: no trip to the tag sheet
            log(f"  door: has {'+'.join(v.tags)} already")
        elif v.tags or off:
            base.set_tags(on=list(v.tags), off=off)
        if (clear or v.clear) and v.kind == "tag" and not v.name:
            base.clear_name()
        return v.kind

    def facts(self, info, texts, sp, ivs, tile, size, gym_top20=None, iv_top=None, tile_cp=None, pure_top=None):
        """-> (Facts, why not sure before any rule: '' when it's up to the rules)"""
        if gym_top20 is None:
            gym_top20 = self.gym_rank(sp, tile_cp or info["cp"], ivs, base.is_shadow(texts))
        dex = {vd.pvp.SPECIES[s]["dex"] for s in sp if s in vd.pvp.SPECIES}
        size = {"XXL": "xxl", "XXS": "xxs"}.get(size, "")
        medal = next((m for d, m in vd.MEDALS.items() if d in dex and m[0]), None)
        if not size and medal and vd.TO[self.account] == vd.GIVER and medal[1](base.who(info)[2] or 0):
            size = None  # an XS Rattata has no badge to read: XS or not is a medal GIV or not. Only the medal rule's
            # account asks, and only for a light one: a heavy one is no medal at any size (2026-11-02)
        hp = ui.hp_line(texts)
        near = [ui.norm(t[4]) for t in texts if hp[1] < t[1] < hp[1] + 0.3]
        chips = tagsheet.tag_chips_sure(texts, (*vd.OWN_TAGS, *vd.TRADE_TAGS, *vd.REMOTE_TAGS, *vd.IGNORED_TAGS,
                                                self.tag, self.other or ""))  # before page_bottom scrolls down
        icons = tile_icons(info)
        said = lambda k, v: self.said.get(k, v)
        rows = [ui.norm(t[4]) for t in texts]
        lucky = any(r.startswith("LUCKY POK") for r in rows)  # only a trade makes one lucky
        costume = self.has("costume", tile)
        favorite = base.star_now()[0] if costume else False  # (only a costume one's rule asks: verdict.costume_fav)
        f = vd.Facts(evolves=can_evolve(texts), account=self.account, sids=list(sp), iv_sum=sum(ivs) if ivs else None,
                     ivs=tuple(ivs) if ivs else None, shiny=said("shiny", icons.get("shiny")),
                     costume=costume, favorite=favorite, background=said("background", icons.get("background")),
                     shadow=base.is_shadow(texts), lucky=lucky,
                     gigantamax="GIGANTAMAX" in near, dynamax="DYNAMAX" in near, size=size, kg=base.who(info)[2],
                     **self.page_facts(info, lucky, bottom=False),
                     levels=self.levels(texts, info, sp, ivs, tile_cp), gym_top20=gym_top20,
                     raid_team=raidteams.on_team(self.account, list(sp), base.is_shadow(texts), info["cp"] or tile_cp,
                                                 info["hp"], *base.who(info)[2:], iv_sum=sum(ivs) if ivs else None),
                     raid=self.has("raid", tile) if "raid" in self.sets else None,
                     iv_top=iv_top, pure_top=pure_top, pvp_judged=self.tag.upper() == "PVPC", ivc_judged=self.tag.upper() == "IVC",
                     other_tags=[t for t in chips
                                 if t not in (self.tag.upper(), *((self.other.upper(),) if self.source else ()))])
        if f.lucky and f.iv_top is None and was_ranked_out(self.account, sp, ivs):
            f.iv_top = False
            log("  lucky: /ivc ranked it out of the top IV already")
        return f, ""

    def page_facts(self, info, lucky, bottom):
        """the Facts read off the page's bottom (traded, caught, far) and its counts (candy, xl, candy_xl), where the
        scope (self.said) or a lucky one doesn't say them already. bottom False: only what shows without a drag (the
        counts on the top screen, or the page bottom already known), the rest None. bottom True: page_bottom's read"""
        page = self.page_bottom(info, drag=bottom)
        said = lambda k, v: self.said.get(k, v)
        if said("age", None) and page["caught"] and vd.age_of(page["caught"]) != self.said["age"]:
            log(f"  door: AGE MISMATCH: this part's search says {self.said['age']}, the date {page['caught']} says "
                f"{vd.age_of(page['caught'])}: the date is believed")  # (Facts.caught goes before Facts.age)
        under = said("xl_under", None if page["xl"] is None else page["xl"] < XL_CAP)
        return dict(traded=True if lucky else said("traded", page["traded"]), caught=page["caught"], age=said("age", None),
                    far=said("far", None if page["california"] is None else not page["california"]),
                    candy_xl=None if under is None else 0 if under else XL_CAP, candy=page.get("candy"), xl=page.get("xl"))

    def page_bottom(self, info, drag=True):
        """the bottom of the page, then back to the top: the caught date (two reads that agree), traded or not, and
        the catch place in California or not, and the counts -> {"caught", "traded", "california", "xl", "candy"}.
        Once per open (base.OPENED). The database's record of this one, when it has all three, saves the drag, if the
        counts showed on the top screen (a Dynamax one's Candy XL is a drag down). drag False: no drag, only what's
        known without one (the rest None, and nothing kept: a later call drags)"""
        if "page" in base.OPENED:
            return base.OPENED["page"]
        top = top_counts(info)
        known = saved_bottom(base.OPENED.get("who"))
        counts = {"xl": top["xl"], "candy": top["candy"]}
        if known and None not in counts.values():
            log(f"  page bottom from the database: caught {known['caught']}, traded {known['traded']},"
                f" California {known['california']}")
            base.OPENED["page"] = {**known, **counts}
            return base.OPENED["page"]
        if not drag:
            return {"caught": None, "traded": None, "california": None, **(known or {}), **counts}
        texts, path, bounds = top["texts"], top["path"], top["bounds"]
        me = tagsheet.who(texts)[1]
        if not (me[3] and me[4]):  # a read as the page fades in can miss the height, or half the weight ('3kg' for
            # 41.18kg): back_to_top would never find that one again (2026-11-13). Look again, keep the last read
            again = base.settle(lambda: base.look()[1], lambda t: ui.classify(t) == "detail" and all(tagsheet.who(t)[1][3:]),
                                timeout=2)
            if ui.classify(again) == "detail":
                me = tagsheet.who(again)[1]
        shots = [(texts, path)]  # the Candy XL row: at the top, or (a Dynamax one's Max Moves box) one drag down
        last = None  # the last look down there: back_to_top's first look (~0.7 s less, Pixel)
        try:
            base.drag(0.08, 0.75, 0.08, 0.2, bounds, settle=tagsheet.IOS_PAGE_SETTLE, android_settle=tagsheet.PAGE_SETTLE)  # down the left edge: no buttons there
            _, t, p, _ = base.look()
            shots.append((t, p))
            last = t
            if pagefacts.caught_read(t):  # on most pages it shows by now: a second drag adds nothing
                if ui.ANDROID:
                    reads = [t, base.sharp_again()]  # (the same screenshot, read 3x bigger: the date's two reads)
                else:  # (the iPhone dragged twice every time, 2026-11-18: a new look is its second read)
                    time.sleep(0.3)
                    reads = [t, base.look()[1]]
                    last = reads[-1]
            else:
                dates = [(round(x[1], 3), x[4]) for x in t if re.search(r"CAUGHT|HATCHED|\d/20\d\d", ui.norm(x[4]))]
                base.log(f"  the caught date isn't on the screen yet ({dates}): one more drag")
                reads = tagsheet.scrolled_bottom(bounds, drags=1)
                last = reads[0] if ui.ANDROID else reads[-1]  # (Android's second one is the sharp read)
                for _ in range(2):  # a tall page (Mewtwo's two Mega rows): the date is a drag or two further
                    if any(pagefacts.caught_read(r) for r in reads):
                        break
                    reads = tagsheet.scrolled_bottom(bounds, drags=1)
                    last = reads[0] if ui.ANDROID else reads[-1]
        finally:
            tagsheet.back_to_top(me, bounds, last)
        xl = next((n for t, p in shots if (n := pagefacts.candy_xl(t)) is not None), None)
        if xl is None:
            xl = next((n for t, p in shots if (n := pagefacts.candy_xl_close(p, t)) is not None), None)
        for t, _ in shots:  # the counts, with the close look's XL (a Dynamax page's candy row is in the second shot)
            base.remember_counts(t, xl=xl)
        candy = next((n for t, _ in shots if (n := candy_owned(t)) is not None), None)
        if candy is None or xl is None:  # (the database's last read of the family, from this account)
            saved = next((r for t, _ in shots if (fam := base.candy(t)) and (r := pokedb.candies().get(fam))), {})
            candy = saved.get("candy") if candy is None else candy
            xl = saved.get("xl") if xl is None else xl
        days = {tagsheet.caught(catch_date(r)) for r in reads}
        base.OPENED["page"] = {"caught": days.pop() if len(days) == 1 else None, "xl": xl, "candy": candy,
                               **pagefacts.bottom(reads)}
        page = base.OPENED["page"]
        pokedb.learn(base.OPENED.get("who"), caught=page["caught"], traded=page["traded"], california=page["california"])
        if base.OPENED["page"]["california"] is False:  # read wrong once and never again (2026-11-06): leave the words to check
            base.log(f"  not California: {[[t[4] for t in r if t[1] > 0.5] for r in reads]}")
        return base.OPENED["page"]

    def purify(self, info, v, sp=None):
        """purify it (the verdict's tags go on after). sp: its speciesIds. Can't purify -> unsure, left as it is"""
        try:
            cp = taps.purify(info, sp)
        except taps.Again as e:
            return vd.unsure(f"purify: the page showed someone else ({e})")
        except Stop as e:
            if not re.search(r"Stardust|Candy|PURIFY", str(e)):
                raise
            return vd.unsure(f"purify: {e}")
        log(f"  purified: CP{info['cp']} -> CP{cp}")
        info["cp"] = cp
        base.moved(base.detail_now(), shadow=False, purified=True)  # its CP and HP moved: still the same one
        return v

    def levels(self, texts, info, sp, ivs, tile_cp):
        """the levels the power-up cost fits. A cost that spans two (4,000 dust: 25 to 26.5, the candy digit not read)
        is narrowed by the appraisal's IVs, CP and HP (two Gengar unsure at 26+, 2026-11-02). -> list, or None"""
        lvs = cost_levels(texts, info["cp"])[1]
        got = self.iv_levels(sp, ivs, info["cp"] or tile_cp, info["hp"], quiet=bool(lvs)) if len(lvs) != 1 else []
        if lvs and got:
            both = sorted(set(lvs) & set(got))
            if both and both != lvs:
                log(f"  power-up cost fits level {lvs}: {both} from IVs, CP and HP")
            return both or lvs
        return lvs or got or None

    def iv_levels(self, sp, ivs, cp, hp, quiet=False):
        """the level from the appraisal's IVs, CP and HP, when the power-up cost doesn't read"""
        got = vd.pvp.levels_for(sp[0], ivs, cp, hp) if len(sp) == 1 and ivs and sp[0] in vd.pvp.SPECIES \
            and cp is not None and hp is not None else []
        if got and not quiet:
            log(f"  power-up cost didn't read: level {got} from IVs, CP and HP")
        return got

    def power_up(self, info, v, tile_cp, levels=None):
        """a few power-ups first if that reaches a higher Candy XL tier on transfer (cleantrades' rule).
        levels: what the facts found, for when the cost doesn't read now"""
        for _ in range(3):  # back from the caught date at the bottom: wait until the cost reads (read once already: no wait)
            now, texts, _ = base.steady_detail()  # (power_up still reads its Stardust and Candy off this page)
            if (known := cost_levels(texts, now["cp"] or tile_cp))[1]:
                break
            time.sleep(0.5)
        try:  # (the walk checked the tile's CP)
            n = powerup.power_up({**info, "cp": now["cp"] or tile_cp}, texts, levels, known=known if known[1] else None)
            log(f"  powered up {n}x before Transfer")
            for _ in range(12):  # the "CP710+31" animation hides the page's buttons: wait it out (2026-10-31)
                texts = base.look()[1]
                if len(texts) > 5 and not any(re.match(r"[cC]\s*[pP].*\+\s*\d+\s*$", t[4].strip()) for t in texts):
                    break
                time.sleep(0.5)
            d = base.detail_now()
            base.moved({**d, "cp": d["cp"] or powerup.last_cp})  # its CP and HP moved: still the same one (the
            # GPS banner can hide the CP: the one the power-up reached)
        except powerup.Unsure as e:
            return vd.unsure(f"Transfer, but the power-up check: {e}")
        except taps.Pass as e:
            log(f"  no power-up: {e}")
        except Stop as e:
            if "Stardust" not in str(e):
                raise
            log(f"  no power-up: {e}")
        return v


def cost_levels(texts, cp):
    """powerup.cost_levels(), once an open: the same one at the same CP again (OPENED's who: a power-up or a purify
    changes it) gets the first read that found levels, with no looks. Each look there took ~0.5 s, and a page back from
    its caught date could take 9 of them (2026-11-09)"""
    k = (base.OPENED.get("who"), cp)
    if base.OPENED.get("cost", (None,))[0] == k:
        return base.OPENED["cost"][1]
    got = powerup.cost_levels(texts, cp)
    if got[1]:
        base.OPENED["cost"] = (k, got)
    return got


def can_evolve(texts):
    """an Evolve button under Power Up on the detail page -> True; Power Up and the moves row under it but no Evolve
    between them -> False (a costume Piplup); that part of the page didn't show -> None. (Mega Evolve starts MEGA)"""
    rows = [ui.norm(t[4]) for t in texts]
    if any(r.startswith("EVOLVE") for r in rows):
        return True
    if any(r.startswith("POWER UP") for r in rows) and any(r.startswith("GYMS") or "TRAINER BATTLES" in r for r in rows):
        return False
    return None


def dead_end(costume, sp, texts):
    """a costume one whose plain form evolves but it can't (verdict.dead_end): /pvpc and /ivc judge it as its own
    species only. costume: Door.has's answer. -> True, False, or None (costume or the Evolve button didn't read)"""
    import verdict  # (not at the top: see vd)
    if len(sp) != 1 or sp[0] not in verdict.pvp.SPECIES or not verdict.plain_evolves(sp[0]):
        return False
    ev = can_evolve(texts)
    if ev or costume is False:  # (an Evolve button: no dead end, whatever the costume search read)
        return False
    return None if costume is None or ev is None else True


def walk_parts(gate, whole, count, walk, limit=None):
    """walk gate's pile in its parts (Door.splits). whole: the game's count of the pile, still on screen. count(terms):
    type the pile's search & terms ('' = the pile alone) -> the game's count. walk(part door): walk the list on screen
    -> True when the run's limit is reached. limit: how many the run opens at most. Parts that don't add up to the
    whole (a term the game reads another way) aren't believed: the pile is walked whole, as before. A pile too small
    for its parts' searches to pay back in drags saved is walked whole too"""
    parts, typed = gate.splits(), ""
    n = min(whole or 0, limit or whole or 0)
    if len(parts) > 1 and n * DRAG_S * TOP_SETTLES < len(parts) * SEARCH_S:
        log(f"door: {n} to open, {len(parts)} parts' searches cost more than the drags they'd save: walked whole")
        parts = [("", gate)]
    if len(parts) > 1:
        got = {}
        for terms, _ in parts:
            got[terms] = count(terms)
            typed = terms
        log(f"door: {whole} in the pile, in parts {got}")
        if whole is None or None in got.values() or sum(got.values()) != whole:
            log(f"door: the parts add up to {sum(n or 0 for n in got.values())}, not {whole}: walked whole")
            parts = [("", gate)]
        else:
            parts = sorted((p for p in parts if got[p[0]]), key=lambda p: p[0] != typed)  # the one on screen first
    for terms, part in parts:
        if terms != typed:
            count(terms)
        typed = None
        if walk(part):
            return


def top_counts(info):
    """the open page's top screen and the counts on it, read once per open (base.OPENED): {"xl", "candy" (None: not
    on the top screen), "texts", "path", "bounds"}. No database fallback here: page_bottom's drag reads what's missing"""
    if "top" in base.OPENED:
        return base.OPENED["top"]
    seen = ui._seen  # the detail page read just now, with no tap since, is the top (one look less)
    if seen and seen[4] == "detail" and time.time() - seen[0] < 1.5:
        _, path, texts, bounds, _ = seen
    else:
        _, texts, path, bounds = base.look()
    xl = pagefacts.candy_xl(texts)
    if xl is None:
        xl = pagefacts.candy_xl_close(path, texts)
    base.remember_counts(texts, xl=xl)
    base.OPENED["top"] = {"xl": xl, "candy": candy_owned(texts), "texts": texts, "path": path, "bounds": bounds}
    return base.OPENED["top"]


def saved_bottom(who):
    """the page bottom's facts the database kept for this one (page_bottom's own reads, which never change):
    {"caught", "traded", "california"}, or None when any of them isn't there"""
    r = pokedb.record(who)
    if not r or not r.get("caught") or r["flags"].get("traded") is None or r["flags"].get("california") is None:
        return None
    try:
        caught = datetime.date.fromisoformat(r["caught"])
    except ValueError:
        return None
    return {"caught": caught, "traded": bool(r["flags"]["traded"]), "california": bool(r["flags"]["california"])}


def catch_date(texts):
    """the page's bottom can show a date each for a trade, an egg received and the catch or hatch. -> texts with only
    the first date under CAUGHT or HATCHED left in (all of them when neither label reads)"""
    label = [t[1] for t in texts if re.search(r"\b(CAUGHT|HATCHED)\b", ui.norm(t[4]))]
    dates = sorted((t for t in texts if re.search(r"\b\d{1,2}/\d{1,2}/20\d\d\b", t[4])), key=lambda t: t[1])
    if len(label) != 1:
        return texts
    got = next((t for t in dates if t[1] > label[0]), None)
    return [t for t in texts if t not in dates or t is got]


def load_list():
    try:
        return json.load(open(NOT_SURE))
    except FileNotFoundError:
        return []


def add_to_list(e):
    got = [x for x in load_list() if not (x["tile"] == e["tile"] and x["cp"] == e["cp"] and x["hp"] == e["hp"]
                                          and x["account"] == e["account"] and x["tag"] == e["tag"])] + [e]
    base.write_json(NOT_SURE, got, indent=1, ensure_ascii=False)


def lucky_key(account, sp, ivs):
    """by dex: /pvpc may read two forms where /ivc read one"""
    return [account, sorted({vd.pvp.SPECIES[s]["dex"] for s in sp if s in vd.pvp.SPECIES}), list(ivs or ())]


def ranked_out(account, sp, ivs):
    """a lucky one /ivc found out of the top IV: saved for LUCKY_OUT_DAYS"""
    if not ivs:
        return
    k, today = lucky_key(account, sp, ivs), time.strftime("%Y-%m-%d")
    got = [e for e in load_lucky_out() if e["key"] != k] + [{"key": k, "day": today}]
    base.write_json(LUCKY_OUT, got, indent=1, ensure_ascii=False)


def was_ranked_out(account, sp, ivs):
    return bool(ivs) and any(e["key"] == lucky_key(account, sp, ivs) for e in load_lucky_out())


def load_lucky_out():
    try:
        got = json.load(open(LUCKY_OUT))
    except FileNotFoundError:
        return []
    cut = time.strftime("%Y-%m-%d", time.localtime(time.time() - LUCKY_OUT_DAYS * 86400))
    return [e for e in got if e["day"] >= cut]
