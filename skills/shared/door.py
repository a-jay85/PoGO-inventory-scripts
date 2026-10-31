"""The door: a Pokémon /ivc, /pvpc or /ivc just found isn't a keeper gets its final tag right there (verdict.py), on the
detail page that's still open. No Nope.

  facts = Door(tag)          once a run, before the walk: who's signed in, the species lists, and one search each
                             for what the detail page can't show (traded; shiny; costume; background; caught 100 km+
                             away; under 360 Candy XL), all within the tag
  facts.judge(...)           read the rest off the open page, ask verdict.final_tag, do what it says
  facts.listed()             Pokémon an earlier run left as not sure under today's rules: the walk passes over them

Not sure = left exactly as it is (tag and name) and written to runs/not-sure.json, with why, for a rule offline.
A search whose tiles didn't all read counts as not done: every Pokémon that needs it comes out not sure.

A lucky one only /ivc can rank (verdict.lucky): anywhere else the door sends it to IVC. One /ivc found out of the
top IV is written to runs/lucky-out.json, so /pvpc's door knows that when the lucky rule sends it on to PvpC (else it
would go back to IVC, round and round).
"""
import hashlib, json, os, re, sys, time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "cleanup"))
import ui, base, search, home, pagefacts
from base import Stop, log

NOT_SURE = os.path.join(HERE, "runs", "not-sure.json")
LUCKY_OUT = os.path.join(HERE, "runs", "lucky-out.json")
LUCKY_OUT_DAYS = 7  # an older entry is dropped: by then the line may have changed
RULES = hashlib.md5(b"".join(open(os.path.join(HERE, f), "rb").read() for f in ("verdict.py", "door.py"))
                    ).hexdigest()[:8]  # new rules or a new reader: judge again
SEARCHES = {"costume": "costume"}  # the one fact the page and tile can't show. The rest come from pagefacts
# (2026-10-31: traded and the catch place off the page's bottom, Candy XL off its top, shiny and background off the tile)
SAID = {"traded": "traded", "shiny": "shiny", "background": "background", "far": "distance100-",
        "xl_under": "countcandyxl0-359"}  # a scope that already says one of these (#Nope&traded) is believed over the page
UNSURE = "unsure"
vd = ct = trades = shadows = None  # verdict, cleantrades, trades, shadows: imported by Door(). At the top they'd loop back
# (/ivc's run.py loads names.py, which loads this)


def key(tile_name, cp):
    return ui.tile_name(tile_name), cp


class Door:
    def __init__(self, tag, scope=None, account=None, find=None):
        """scope: the search the Pokémon to judge are in (default #tag). account: who's signed in, when known.
        find(term) -> search.run_search's answer for the pile & term, for a pile that's no typed search (a saved one).
        Then tag only names the pile (the not-sure list): it isn't a tag to take off"""
        global vd, ct, trades, shadows
        run_dir = base.RUN_DIR  # (kept in case an import moves it)
        import verdict as vd
        import cleantrades as ct  # the power-up cost -> levels, and power-ups to the next Candy XL tier
        import trades  # the tag chips, the caught date at the bottom of the page
        import shadows  # purify
        base.RUN_DIR = run_dir
        self.tag, self.other = tag, "IVC" if tag.upper() == "PVPC" else "PvpC"
        self.source = find is None  # tag is the Pokémon's own tag, to come off
        find = find or (lambda term: search.run_search(f"{self.scope}&{term}"))
        self.account = account or home.trainer()
        self.scope = scope or f"#{tag}"
        self.tables = vd.tables(vd.TO[self.account])
        if "missing" in self.tables:
            log(f"door: no species lists, those rules will say not sure ({self.tables['missing']})")
        self.sets, self.partial = {}, set()
        search.to_search_list()
        said = set(self.scope.lower().split("&"))  # '#Nope&traded': every one is traded, so no search can misread it
        self.said = {k: term in said for k, term in SAID.items() if term in said or "!" + term in said}
        for k, term in SEARCHES.items():
            if term in said or "!" + term in said:
                self.sets[k] = term in said
                log(f"door: {self.scope}: {'every' if term in said else 'no'} one is {term}, no search")
                continue
            got, want = find(term)
            ok = want is not None and len(got) == want
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

    def has(self, k, tile):
        """a search whose count didn't match (a long list read 57 for 55): a tile read in it is in it, one not read
        could be a tile it missed -> None"""
        s = self.sets.get(k)
        if s is None or isinstance(s, bool):
            return s
        return True if tile in s else None if k in self.partial else False

    def listed(self):
        """{(tile name, CP) as the walk read them: n} left as not sure by an earlier run of this tag, on this account,
        under these rules"""
        return Counter((e["tile"], e["cp"]) for e in load_list()
                       if e["rules"] == RULES and e["account"] == self.account and e["tag"] == self.tag)

    def judge(self, info, texts, sp, ivs, tile, size=None, raws=None, gym_top20=None, clear=False, unstar=False,
              iv_top=None):
        """the open detail page of a Pokémon that isn't a keeper. tile: (name, CP) as the walk read the tile.
        gym_top20: what the caller already knows of the gym rule. iv_top: of a lucky one's top IV (verdict.Facts). clear: a plain tag clears the name too (an old /ivc
        name would bring it back as a rival or a fallen-out one). unstar: a plain tag takes the star off too (a fallen-out
        keeper). -> 'left for IVC/PvpC', UNSURE or the verdict's kind"""
        if self.source and any(base.is_tag(t, self.other) for t in info["tags"]):  # the other skill judges it next
            base.set_tags(off=[self.tag])
            log(f"  has {self.other} too: unticked {self.tag} only, {self.other} decides")
            return f"left for {self.other}"
        if (got := base.narrow(sp, ivs, tile[1] or info["cp"], info["hp"])) != sp:  # (the walk checked the tile's CP)
            log(f"  {'/'.join(sp)}: only {'/'.join(got)} has these IVs at this CP and HP")
            sp = got
        f, why = self.facts(info, texts, sp, ivs, key(*tile), size, gym_top20, iv_top, tile[1])
        v = vd.final_tag(f, self.tables) if not why else vd.unsure(why)
        if f.lucky and iv_top is False:
            ranked_out(self.account, sp, ivs)
        if v.purify:
            v = self.purify(info, v)
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
        if v.name:
            base.do_rename(v.name, lambda got, want: (got or "").strip().upper() == want.upper())
        if v.kind == "keep":
            base.set_star(True)
        elif unstar and v.kind == "tag":
            base.set_star(False)
        off = [*([self.tag] if self.source else ()), *v.off]
        if v.tags or off:
            base.set_tags(on=list(v.tags), off=off)
        if (clear or v.clear) and v.kind == "tag" and not v.name:
            base.clear_name()
        return v.kind

    def facts(self, info, texts, sp, ivs, tile, size, gym_top20=None, iv_top=None, tile_cp=None):
        """-> (Facts, why not sure before any rule: '' when it's up to the rules)"""
        dex = {vd.pvp.SPECIES[s]["dex"] for s in sp if s in vd.pvp.SPECIES}
        size = {"XXL": "xxl", "XXS": "xxs"}.get(size, "")
        if not size and dex & {d for d, (sizes, _, _) in vd.MEDALS.items() if sizes}:
            size = None  # an XS Rattata has no badge to read: XS or not is a medal GIV or not
        hp = next(t for t in texts if re.search(r"\d+\s*/\s*\d+\s*HP", t[4]))
        near = [ui.norm(t[4]) for t in texts if hp[1] < t[1] < hp[1] + 0.3]
        xl = self.said.get("xl_under", self.xl_under())
        page = self.page_bottom(info)
        icons = pagefacts.tile_icons(*base.OPENED["tile"]) if base.OPENED.get("tile") else {}
        said = lambda k, v: self.said.get(k, v)
        rows = [ui.norm(t[4]) for t in texts]
        evolves = True if any(r.startswith("EVOLVE") for r in rows) else False if any(
            r.startswith("POWER UP") for r in rows) else None  # (Mega Evolve starts MEGA)
        lucky = any(r.startswith("LUCKY POK") for r in rows)  # only a trade makes one lucky
        f = vd.Facts(evolves=evolves,account=self.account, sids=list(sp), iv_sum=sum(ivs) if ivs else None,
                     ivs=tuple(ivs) if ivs else None, shiny=said("shiny", icons.get("shiny")),
                     costume=self.has("costume", tile), background=said("background", icons.get("background")),
                     traded=True if lucky else said("traded", page["traded"]), caught=page["caught"], shadow=base.is_shadow(texts),
                     lucky=lucky,
                     gigantamax="GIGANTAMAX" in near, dynamax="DYNAMAX" in near, size=size, kg=base.who(info)[2],
                     candy_xl=None if xl is None else 0 if xl else vd.XL_CAP,
                     levels=ct.cost_levels(texts, info["cp"])[1] or self.iv_levels(sp, ivs, info["cp"] or tile_cp, info["hp"]) or None, far=said("far", None if page["california"] is None else not page["california"]), gym_top20=gym_top20,
                     iv_top=iv_top, pvp_judged=self.tag.upper() == "PVPC", ivc_judged=self.tag.upper() == "IVC",
                     other_tags=[t for t in trades.tag_chips(texts)
                                 if t not in (self.tag.upper(), *((self.other.upper(),) if self.source else ()))])
        if f.lucky and f.iv_top is None and was_ranked_out(self.account, sp, ivs):
            f.iv_top = False
            log("  lucky: /ivc ranked it out of the top IV already")
        return f, ""

    def xl_under(self):
        """under 360 Candy XL, off the page's top (a 3x crop when the count is too small to read) -> bool or None"""
        _, texts, path, _ = base.look()
        n = pagefacts.candy_xl(texts)
        if n is None:
            n = pagefacts.candy_xl_close(path)
        return None if n is None else n < 360

    def page_bottom(self, info):
        """the bottom of the page, then back to the top: the caught date (two reads that agree), traded or not, and
        the catch place in California or not -> {"caught", "traded", "california"}. Once per open (base.OPENED)"""
        if "page" in base.OPENED:
            return base.OPENED["page"]
        _, texts, _, bounds = base.look()
        me = trades.who(texts)[1]
        try:
            reads = trades.scrolled_bottom(bounds)
        finally:
            trades.back_to_top(me, bounds)
        days = {trades.caught(catch_date(r)) for r in reads}
        base.OPENED["page"] = {"caught": days.pop() if len(days) == 1 else None, **pagefacts.bottom(reads)}
        return base.OPENED["page"]

    def purify(self, info, v):
        """purify it (the verdict's tags go on after). Can't purify -> unsure, left as it is"""
        try:
            cp = shadows.purify(info)
        except shadows.Again as e:
            return vd.unsure(f"purify: the page showed someone else ({e})")
        except Stop as e:
            if not re.search(r"Stardust|Candy|PURIFY", str(e)):
                raise
            return vd.unsure(f"purify: {e}")
        log(f"  purified: CP{info['cp']} -> CP{cp}")
        info["cp"] = cp
        base.OPENED["who"] = base.who(base.detail_now())  # its CP and HP moved: still the same one
        return v

    def iv_levels(self, sp, ivs, cp, hp):
        """the level from the appraisal's IVs, CP and HP, when the power-up cost doesn't read"""
        got = base.levels_for(sp[0], ivs, cp, hp) if len(sp) == 1 and ivs and sp[0] in vd.pvp.SPECIES \
            and cp is not None and hp is not None else []
        if got:
            log(f"  power-up cost didn't read: level {got} from IVs, CP and HP")
        return got

    def power_up(self, info, v, tile_cp, levels=None):
        """one or two power-ups first if that reaches a higher Candy XL tier on transfer (cleantrades' rule).
        levels: what the facts found, for when the cost doesn't read now"""
        for _ in range(3):  # back from the caught date at the bottom: wait until the cost reads
            now, texts, _ = base.steady_detail()
            if ct.cost_levels(texts, now["cp"] or tile_cp)[1]:
                break
            time.sleep(0.5)
        try:
            n = ct.power_up({**info, "cp": now["cp"] or tile_cp}, texts, levels)  # (the walk checked the tile's CP)
            log(f"  powered up {n}x before Transfer")
            base.OPENED["who"] = base.who(base.detail_now())  # its CP and HP moved: still the same one
        except ct.Unsure as e:
            return vd.unsure(f"Transfer, but the power-up check: {e}")
        except ct.Pass as e:
            log(f"  no power-up: {e}")
        except Stop as e:
            if "Stardust" not in str(e):
                raise
            log(f"  no power-up: {e}")
        return v


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
    os.makedirs(os.path.dirname(NOT_SURE), exist_ok=True)
    got = [x for x in load_list() if not (x["tile"] == e["tile"] and x["cp"] == e["cp"] and x["hp"] == e["hp"]
                                          and x["account"] == e["account"] and x["tag"] == e["tag"])] + [e]
    json.dump(got, open(NOT_SURE, "w"), indent=1, ensure_ascii=False)


def lucky_key(account, sp, ivs):
    """by dex: /pvpc may read two forms where /ivc read one"""
    return [account, sorted({vd.pvp.SPECIES[s]["dex"] for s in sp if s in vd.pvp.SPECIES}), list(ivs or ())]


def ranked_out(account, sp, ivs):
    """a lucky one /ivc found out of the top IV: saved for LUCKY_OUT_DAYS"""
    if not ivs:
        return
    k, today = lucky_key(account, sp, ivs), time.strftime("%Y-%m-%d")
    got = [e for e in load_lucky_out() if e["key"] != k] + [{"key": k, "day": today}]
    os.makedirs(os.path.dirname(LUCKY_OUT), exist_ok=True)
    json.dump(got, open(LUCKY_OUT, "w"), indent=1, ensure_ascii=False)


def was_ranked_out(account, sp, ivs):
    return bool(ivs) and any(e["key"] == lucky_key(account, sp, ivs) for e in load_lucky_out())


def load_lucky_out():
    try:
        got = json.load(open(LUCKY_OUT))
    except FileNotFoundError:
        return []
    cut = time.strftime("%Y-%m-%d", time.localtime(time.time() - LUCKY_OUT_DAYS * 86400))
    return [e for e in got if e["day"] >= cut]
